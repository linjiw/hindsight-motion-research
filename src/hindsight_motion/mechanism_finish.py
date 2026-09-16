"""Finish the registered study after queued preflights, preserving deferred/failure states."""

import json
from pathlib import Path
import time
import traceback

from .batch_audit import analyze
from .budget import main_attempts
from .carrier_screen import qualify as qualify_carriers
from .core import sha256
from .critical import PROJECT, dump
from .decoder_execution import fidelity, qualify
from .mechanism import PLAN, prepare_scenes
from .mechanism_report import (
    CARRIERS,
    FAILED,
    GEOMETRY,
    MAIN,
    OUTPUT,
    PREFLIGHT,
    report,
)
from .resource_queue import run as queue_run

STATUS = OUTPUT / "stage_status.json"


def status(state, message, **fields):
    payload = dict(state=state, message=message, updated_unix_s=time.time(), **fields)
    temporary = STATUS.with_suffix(".tmp")
    dump(temporary, payload)
    temporary.replace(STATUS)


def write_results(summary):
    methods = "\n".join(
        f"| {r['method']} | {r['joint_passes']}/18 | {r['fully_qualified_pairs']}/3 |"
        for r in summary["methods"]
    )
    carriers = "\n".join(
        f"| {r['source_group']} | {r['successes']['original']}/3 | {r['successes']['tuck']}/3 | {'是' if r['acquisition_ready'] else '否'} |"
        for r in summary["carrier_qualification"]
    )
    effects = json.loads((OUTPUT / "paired_mechanism_effects.json").read_text())[
        "summary"
    ]
    effect_rows = "\n".join(
        f"| {r['contrast']} | {r['rescued']}/18 | {r['regressed']}/18 | {100*r['mean_original_body_error_change_m']:.2f} |"
        for r in effects
    )
    geometry = json.loads((GEOMETRY / "results.json").read_text())["summary"]
    geometry_rows = "\n".join(
        f"| {r['method']} | {100*r['macro_clearance_mae_m']:.4f} | {r['false_admissions']} | {r['missed_admissions']} |"
        for r in geometry
    )
    panels = (
        json.loads((OUTPUT / "representation_panels.json").read_text())
        if (OUTPUT / "representation_panels.json").exists()
        else []
    )
    panel_rows = "\n".join(
        f"| {p} | {sum(x['representation_relation_verified'] for x in panels if x['pair_id']==p)}/3 |"
        for p in dict.fromkeys(x["pair_id"] for x in panels)
    )
    text = f"""# 时间连续性与腿部重建：执行机制实验结果

本轮完成 **{summary['new_recorded_preflight_episodes']} 次预检 + {summary['new_main_episodes']} 次固定场景干预**。另保留一次 GPU 内存分配失败：144 个已调度 slot，0 个记录完整的 episode，不计作 144 次行为失败。

[实验协议](TOKEN_MECHANISM_PROTOCOL.md) · [执行对照图](../artifacts/token_mechanism.png) · [预检回放](../artifacts/mechanism_preflight_viewer.html) · [运行状态](../artifacts/mechanism_status.html)

## 1. 两个干预与实际预检结果

比较固定 RVQ+body9 的五帧 binomial smoothing、原始 50 Hz 腿部 oracle，以及实际可编码的 10 Hz / 12-bit leg12。腿部替换发生在 smoothing 后。连续参考和 Linear29 同批重测。所有方法保留原始 root 和进入段；0.6–1.2 s 过渡至解码关节。

一次通过同时要求 native passage 和原始连续参考 fidelity：身体平均误差 ≤10 cm、root XY 最大误差 ≤25 cm、200 个有效控制步。只有两个 continuation 都在三个扰动中通过才算一个 qualified pair。

| 表示 | 合格 episode | 完全合格动作对 |
| --- | ---: | ---: |
{methods}

### 配对干预

| 干预 | 失败变通过 | 通过变失败 | 原始身体误差平均变化 cm |
| --- | ---: | ---: | ---: |
{effect_rows}

这些是三个相关编辑动作对、两个源分组内的配对比较。Smoothing 同时改变接缝和 patch 内部运动；原始腿替换同时改变位置及速度，不能宣称单独识别了所有 token 边界误差的因果作用。Oracle leg 不属于公平压缩结果。

## 2. 固定场景复核

按预先登记顺序，每个预定 main case 选择第一个全部合格的实际可编码方法，配合新执行的 continuous control。障碍、目标、初始扰动和任务门槛保持原样。Main case 仍为两个既有 KIT/205 动作对。

完整关系面板 **{summary['verified_representation_panels']}/{summary['representation_panels']}** 合格。目标 critical 运行和全部控制还须保持原始动作 fidelity；预期碰撞的 critical 对照可因碰撞偏离参考。

| 表示 cell | 完整干预面板 |
| --- | ---: |
{panel_rows if panel_rows else '| 无方法进入 main | — |'}

不能将 representation cell 计作新独立动作对。[逐 panel 证据](../runs/token_mechanism_validation_20260915_v1/aggregate.json)保留全部结果；未通过的对照或控制不被删去。

## 3. 几何和脚部重建测量解释了哪些差异

四个既有动作对、643 个固定场景候选的完整解码参考几何结果如下。这里没有 native entry adapter，比较目标是连续参考的几何判定，不是物理真值。

| 表示 | clearance MAE cm | 错误接受 | 漏掉参考接受 |
| --- | ---: | ---: | ---: |
{geometry_rows}

在这组 arm/beam 候选中，改变腿部没有改变 clearance 判定；这不代表腿部对执行无关。对实际送入参考的 1.2 s 后区间，原始 body9 的脚部位置 RMSE 为 11.19 cm，smoothing 后为 10.94 cm；leg12 为 0.369 cm。脚部速度 RMSE 分别约 1.612、0.874、0.117 m/s。它们是 ankle-link FK 误差，不是实测滑脚或接触。

Body9 的关节逻辑码率为 1,220 bit/s，leg12 方案为 2,660 bit/s，Linear29 为 3,480 bit/s。各方法另保留 11,200 bit/s root，并有未计入上述码率的原始进入段、模型和容器开销。原始腿 oracle 的额外信息为 19,200 bit/s。

## 4. 新 carrier 资格

移除文件名 `walk` 过滤，在同一运动学资格规则下取得 57 条候选、35 个此前未执行源分组；按固定 gait 描述符排序选八组。原始 carrier 与收臂版本分别执行，未 retime 或制作 duck/bend。

| 源分组 | 原始 carrier | 收臂版本 | 可进入下一步 acquisition |
| --- | ---: | ---: | --- |
{carriers}

原始 carrier 完全通过 **{summary['original_supported_carriers']}/{summary['screened_carrier_groups']}** 组；原始与收臂都通过 **{summary['acquisition_ready_carriers']}/{summary['screened_carrier_groups']}** 组。这些还不是 obstacle-qualified pair，下一步仍须构造可执行 alternatives、提出关键场景并完成干预。

## 5. 实际账本与证据边界

- 本轮记录预检 {summary['new_recorded_preflight_episodes']} 次，额外保留失败基础设施 slot 144 个；本轮主实验 {summary['new_main_episodes']} 次。
- 累计预检已调度 {summary['cumulative_preflight_scheduled_attempts']} 个 slot，其中完整记录 {summary['cumulative_recorded_preflight_episodes']} 个 episode；累计 main {summary['cumulative_main_attempts']}/480，剩余 {summary['main_budget_remaining']} 次。
- 本轮 representation 数据 {summary['representation_control_rows']} 个控制行，{summary['representation_supported_motor_rows']} 个受支持 imitation 行，保存在独立索引中。
- Canonical scene acquisition 仍是 5 个动作对、3 个源分组。新增 carrier 资格不提升该数字。
- Actor / teacher-only / targets 分离。原始参考、source/method 标识、未来 motion code 和关系标签不进入因果 actor 观测。
- 全部 development。未训练 BFM，未证明 scene-first 导航学生或 text2nav 的收益。接下来优先使用已经合格的 carrier 扩大场景干预覆盖，然后按相同查询/执行预算比较 proposer 与固定 learner 的数据效用。

## 重算分析

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=src:/home/linjiw/groot-wbc-sonic-sim-trackb
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
"$RESEARCH_PY" -m hindsight_motion.mechanism_report
"$RESEARCH_PY" -m pytest -q
```

Native 目录禁止覆盖重跑。资源等待记录、失败 launch、单次明确登记 recovery 和全部 outcome 保留；详见 `runs/token_mechanism_validation_20260915_v1/launch_ledger.json`。
"""
    (PROJECT / "docs/TOKEN_MECHANISM_RESULTS_zh.md").write_text(text)


def finish():
    OUTPUT.mkdir(exist_ok=True)
    try:
        while True:
            exits = [(r / "exit.json").exists() for r in (PREFLIGHT, CARRIERS)]
            failed = [
                r
                for r in (PREFLIGHT, CARRIERS)
                if (r / "exit.json").exists()
                and json.loads((r / "exit.json").read_text())["exit_code"] != 0
            ]
            deferred = [
                r
                for r in (PREFLIGHT, CARRIERS)
                if (r / "resource_deferred.json").exists()
            ]
            if failed or deferred:
                status(
                    "failed" if failed else "deferred",
                    "Native work stopped; no automatic recovery.",
                    runs=[str(r) for r in failed + deferred],
                )
                return
            if all(exits):
                break
            active = next(
                (
                    r
                    for r in (PREFLIGHT, CARRIERS)
                    if (r / "launch.json").exists() and not (r / "exit.json").exists()
                ),
                None,
            )
            waiting = PREFLIGHT if not exits[0] else CARRIERS
            resource_log = waiting / "resource_wait.jsonl"
            sample = (
                json.loads(resource_log.read_text().splitlines()[-1])
                if resource_log.exists()
                else {}
            )
            status(
                "running" if active else "waiting_resources",
                (
                    f"Executing {active.name}"
                    if active
                    else "Waiting for stable GPU and host-memory headroom."
                ),
                completed_preflight_batches=sum(exits),
                last_resource_sample=sample,
                cpu_geometry_complete=True,
                failed_infrastructure_slots=144,
            )
            time.sleep(20)
        status(
            "analyzing",
            "Qualifying every preflight and selecting the registered practical decoder.",
        )
        qualify(PREFLIGHT)
        qualify_carriers(CARRIERS)
        prepare_scenes(PREFLIGHT, MAIN)
        if (MAIN / "batch.json").exists():
            status(
                "waiting_main_resources",
                "Preflights complete; frozen-scene interventions queued.",
            )
            queue_run([MAIN], timeout_s=3600)
            if not (MAIN / "exit.json").exists():
                status(
                    "deferred", "Main scenes prepared but deferred by resource gate."
                )
                return
            analyze(MAIN)
            fidelity(MAIN, PREFLIGHT)
        status(
            "auditing",
            "Auditing original-motion fidelity, scenes, contacts and dataset views.",
        )
        report()
        summary = json.loads((OUTPUT / "aggregate.json").read_text())
        assert main_attempts() == summary["cumulative_main_attempts"]
        hash_checks = 0
        index = OUTPUT / "development_representation_episodes.jsonl"
        if index.exists():
            for line in index.read_text().splitlines():
                for item in json.loads(line)["files"].values():
                    assert sha256(item["path"]) == item["sha256"]
                    hash_checks += 1
        write_results(summary)
        plan = json.loads(PLAN.read_text())
        plan.update(
            status="executed_and_audited",
            completed_unix_s=time.time(),
            execution_results=summary,
        )
        dump(PLAN, plan)
        dump(
            OUTPUT / "completion_receipt.json",
            dict(
                completed_unix_s=time.time(),
                indexed_file_hash_checks=hash_checks,
                report=str(PROJECT / "docs/TOKEN_MECHANISM_RESULTS_zh.md"),
                all_data_development=True,
                student_trained=False,
            ),
        )
        status(
            "complete",
            "Registered execution and evidence audits completed.",
            summary=summary,
            viewer=(
                "mechanism_viewer.html"
                if summary["new_main_episodes"]
                else "mechanism_preflight_viewer.html"
            ),
        )
    except Exception as exc:
        status("error", str(exc), traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    finish()
