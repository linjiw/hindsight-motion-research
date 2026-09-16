# 时间连续性与腿部重建：执行机制实验结果

本轮完成 **192 次预检 + 96 次固定场景干预**。另保留一次 GPU 内存分配失败：144 个已调度 slot，0 个记录完整的 episode，不计作 144 次行为失败。

[实验协议](TOKEN_MECHANISM_PROTOCOL.md) · [执行对照图](../artifacts/token_mechanism.png) · [预检回放](../artifacts/mechanism_preflight_viewer.html) · [运行状态](../artifacts/mechanism_status.html)

## 1. 两个干预与实际预检结果

比较固定 RVQ+body9 的五帧 binomial smoothing、原始 50 Hz 腿部 oracle，以及实际可编码的 10 Hz / 12-bit leg12。腿部替换发生在 smoothing 后。连续参考和 Linear29 同批重测。所有方法保留原始 root 和进入段；0.6–1.2 s 过渡至解码关节。

一次通过同时要求 native passage 和原始连续参考 fidelity：身体平均误差 ≤10 cm、root XY 最大误差 ≤25 cm、200 个有效控制步。只有两个 continuation 都在三个扰动中通过才算一个 qualified pair。

| 表示 | 合格 episode | 完全合格动作对 |
| --- | ---: | ---: |
| continuous | 18/18 | 3/3 |
| linear29 | 16/18 | 2/3 |
| body9_raw | 0/18 | 0/3 |
| body9_smooth | 0/18 | 0/3 |
| body9_legoracle | 15/18 | 2/3 |
| body9_smooth_legoracle | 17/18 | 2/3 |
| body9_leg12 | 15/18 | 2/3 |
| body9_smooth_leg12 | 15/18 | 2/3 |

### 配对干预

| 干预 | 失败变通过 | 通过变失败 | 原始身体误差平均变化 cm |
| --- | ---: | ---: | ---: |
| smooth_with_decoded_legs | 0/18 | 0/18 | -1.37 |
| original_legs_without_smoothing | 15/18 | 0/18 | -29.51 |
| original_legs_with_smoothing | 17/18 | 0/18 | -28.82 |
| smooth_with_original_legs | 2/18 | 0/18 | -0.68 |
| leg12_without_smoothing | 15/18 | 0/18 | -29.23 |
| leg12_with_smoothing | 15/18 | 0/18 | -28.49 |

这些是三个相关编辑动作对、两个源分组内的配对比较。Smoothing 同时改变接缝和 patch 内部运动；原始腿替换同时改变位置及速度，不能宣称单独识别了所有 token 边界误差的因果作用。Oracle leg 不属于公平压缩结果。

## 2. 固定场景复核

按预先登记顺序，每个预定 main case 选择第一个全部合格的实际可编码方法，配合新执行的 continuous control。障碍、目标、初始扰动和任务门槛保持原样。Main case 仍为两个既有 KIT/205 动作对。

完整关系面板 **12/12** 合格。目标 critical 运行和全部控制还须保持原始动作 fidelity；预期碰撞的 critical 对照可因碰撞偏离参考。

| 表示 cell | 完整干预面板 |
| --- | ---: |
| mech_arm03_body9_leg12 | 3/3 |
| mech_arm03_continuous | 3/3 |
| mech_hybrid205_body9_leg12 | 3/3 |
| mech_hybrid205_continuous | 3/3 |

不能将 representation cell 计作新独立动作对。[逐 panel 证据](../runs/token_mechanism_validation_20260915_v1/aggregate.json)保留全部结果；未通过的对照或控制不被删去。

## 3. 几何和脚部重建测量解释了哪些差异

四个既有动作对、643 个固定场景候选的完整解码参考几何结果如下。这里没有 native entry adapter，比较目标是连续参考的几何判定，不是物理真值。

| 表示 | clearance MAE cm | 错误接受 | 漏掉参考接受 |
| --- | ---: | ---: | ---: |
| continuous | 0.0000 | 0 | 0 |
| linear29 | 0.0565 | 2 | 1 |
| body9_raw | 1.0948 | 7 | 49 |
| body9_smooth | 0.7595 | 7 | 38 |
| body9_legoracle | 1.0948 | 7 | 49 |
| body9_smooth_legoracle | 0.7595 | 7 | 38 |
| body9_leg12 | 1.0948 | 7 | 49 |
| body9_smooth_leg12 | 0.7595 | 7 | 38 |

在这组 arm/beam 候选中，改变腿部没有改变 clearance 判定；这不代表腿部对执行无关。对实际送入参考的 1.2 s 后区间，原始 body9 的脚部位置 RMSE 为 11.19 cm，smoothing 后为 10.94 cm；leg12 为 0.369 cm。脚部速度 RMSE 分别约 1.612、0.874、0.117 m/s。它们是 ankle-link FK 误差，不是实测滑脚或接触。

Body9 的关节逻辑码率为 1,220 bit/s，leg12 方案为 2,660 bit/s，Linear29 为 3,480 bit/s。各方法另保留 11,200 bit/s root，并有未计入上述码率的原始进入段、模型和容器开销。原始腿 oracle 的额外信息为 19,200 bit/s。

## 4. 新 carrier 资格

移除文件名 `walk` 过滤，在同一运动学资格规则下取得 57 条候选、35 个此前未执行源分组；按固定 gait 描述符排序选八组。原始 carrier 与收臂版本分别执行，未 retime 或制作 duck/bend。

| 源分组 | 原始 carrier | 收臂版本 | 可进入下一步 acquisition |
| --- | ---: | ---: | --- |
| CMU/107 | 3/3 | 3/3 | 是 |
| KIT/421 | 0/3 | 0/3 | 否 |
| KIT/12 | 3/3 | 0/3 | 否 |
| KIT/4 | 0/3 | 0/3 | 否 |
| KIT/442 | 0/3 | 0/3 | 否 |
| KIT/6 | 0/3 | 0/3 | 否 |
| CMU/132 | 0/3 | 0/3 | 否 |
| KIT/7 | 0/3 | 0/3 | 否 |

原始 carrier 完全通过 **2/8** 组；原始与收臂都通过 **1/8** 组。这些还不是 obstacle-qualified pair，下一步仍须构造可执行 alternatives、提出关键场景并完成干预。

## 5. 实际账本与证据边界

- 本轮记录预检 192 次，额外保留失败基础设施 slot 144 个；本轮主实验 96 次。
- 累计预检已调度 584 个 slot，其中完整记录 440 个 episode；累计 main 312/480，剩余 168 次。
- 本轮 representation 数据 19200 个控制行，16800 个受支持 imitation 行，保存在独立索引中。
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
