# 解码后的动作能否保留关键穿越？本轮 210 次 native 实验

## 结论

**Linear29 可以作为目前的执行表示基线；旧 RVQ 系列尚不能作为可靠的 motion-to-teacher 输入。** 在冻结的收臂通道和横梁场景中，Linear29 与连续参考都保留了完整的干预结果。本轮同时尝试三个新源分组，但它们连空场景 tracking 都未合格，因此没有增加源覆盖。

本轮完成 90 次 decoder 预检、24 次新源预检、96 次固定场景干预，共 **210 次仿真 episode**。累计 248 次预检、216/480 次主实验。全部为 development evidence；未训练 BFM 或导航学生。

- [交互回放](../artifacts/decoder_viewer.html)：96 次主实验的实测身体运动，默认显示 Linear29 横梁穿越。
- [结果图](../artifacts/decoder_execution.png) / [PDF](../artifacts/decoder_execution.pdf)。
- [机器可读汇总](../runs/decoder_validation_20260915_v1/aggregate.json)。

## 1. 冻结什么，比较什么

执行前登记 `configs/decoder_execution_v1.plan.json`，并保存构造时副本。沿用同一 SONIC checkpoint、G1 collision assets、50 Hz 控制、200 Hz 接触采样和成功门槛。三个初始 lateral offset 为 0、−1.5、+1.5 cm。

预检比较三对现有动作：KIT/205 收臂、KIT/9 收臂、KIT/205 下蹲加弯腰。每对有两种 continuation，五种表示、三个扰动，共 90 个 episode。主实验事先限定为 KIT/205 的两种机制，只有预检中两个 continuation 都通过全部扰动的方法才进入主实验。

五种表示为连续参考、RVQ、RVQ+body9、RVQ+PCA9、Linear29，使用上一轮冻结的 codebook、训练集残差模型和标量范围，没有重新训练或根据物理结果调参。Linear29 为 10 Hz、每关节 12-bit 的量化 knot，线性插值至 50 Hz。

### 共同进入状态与执行接口

解码关节参考先接受 native joint-limit 检查；本批所有方法实际都没有触发投影。保留原动作前 0.6 s，再以 quintic 权重过渡，1.2 s 后全部采用解码关节参考。root 全程保留原始 50 Hz 参考。

这项比较有**原始进入段和 root 信息辅助**。它不是完整 clip 的独立 codec，也不是将 RVQ ID 直接送入 SONIC motor decoder。关节信息的逻辑码率仍是 RVQ 140 bit/s、两种 residual 方案 1,220 bit/s、Linear29 3,480 bit/s；每种方法另有 11,200 bit/s 的 root，以及未计入这些关节码率的进入段信息。NPZ 文件不是 bit-packed codec。

除了检查 teacher 对当前解码参考的 tracking，还将实测身体位置与**原始连续参考**比较：平均身体误差 ≤10 cm、最大 root XY 误差 ≤25 cm、完整 200 行有效执行。这样可以拒绝“很好地跟踪了一条已失真的参考”。

## 2. 空场景资格：几何改善没有自动变成执行改善

表中一次通过必须同时满足 native tracking、无不允许的接触、移动到达和原始参考 fidelity。

| 表示 | KIT/205 收臂 | KIT/9 收臂 | KIT/205 横梁动作 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 连续参考 | 6/6 | 6/6 | 6/6 | 18/18 |
| RVQ | 0/6 | 0/6 | 0/6 | 0/18 |
| RVQ + body9 | 0/6 | 0/6 | 0/6 | 0/18 |
| RVQ + PCA9 | 0/6 | 0/6 | 0/6 | 0/18 |
| Linear29 | 6/6 | 5/6 | 6/6 | 17/18 |

三个 RVQ 方法的 54 次运行均未发生 native termination 或非脚部地面接触；全部未通过 tracking 和终点到达。它们并非全部摔倒。身体 tracking 误差范围为 RVQ 28.2–50.6 cm、body9 27.2–48.1 cm、PCA9 20.8–39.4 cm。

Linear29 唯一失败是 KIT/9 wide、−1.5 cm 扰动：身体误差 9.897 cm，但最大 root XY 误差 25.375 cm、终点误差 25.578 cm，超过固定的 25 cm 门槛。该 pair 没有被当作全部合格，门槛也未放宽。

上一轮 body9 降低了 clearance 几何误差，本轮它仍然无法支持可靠执行。这两项评价测量不同的性质，不能用几何指标代替 teacher 执行资格。

### 探索性诊断：token 边界不连续

在 1.2 s 之后的实际送入参考上统计关节相邻帧差异。以下是六条 continuation 的等权平均；这些 continuation 相互关联，不是独立统计样本。

| 表示 | 5 帧 patch 边界的关节步长 RMS | patch 内部 RMS | 最大单关节帧间跳变 |
| --- | ---: | ---: | ---: |
| 连续参考 | 0.01033 rad | 0.01031 rad | 0.09237 rad |
| RVQ | 0.08967 rad | 0.00606 rad | 0.99911 rad |
| RVQ + body9 | 0.08438 rad | 0.01178 rad | 0.99911 rad |
| RVQ + PCA9 | 0.08037 rad | 0.01438 rad | 0.91971 rad |
| Linear29 | 0.00998 rad | 0.00982 rad | 0.07986 rad |

body9 不修正腿关节，其腿部参考 RMSE 与 RVQ 相同，约 0.11357 rad；Linear29 为 0.00721 rad。大幅接缝和腿部重建误差都是合理的候选解释，**当前实验没有分别干预它们，因此尚不能归因**。不能由此断言任何离散 tokenizer 都不可执行。

## 3. 96 次固定场景干预：Linear29 保留了两类机制

连续参考与 Linear29 分别复用原有的 critical、relaxed、removed、displaced 几何。障碍位置、尺寸、目标和任务门槛逐字段审计相等，没有为解码后的动作重新摆放障碍。

| 表示 / 机制 | critical：目标 / 对照 | relaxed：目标 / 对照 | removed：目标 / 对照 | displaced：目标 / 对照 | 完整面板 |
| --- | --- | --- | --- | --- | ---: |
| 连续 / 收臂通道 | 3/3 · 0/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 |
| Linear29 / 收臂通道 | 3/3 · 0/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 |
| 连续 / 横梁 | 3/3 · 0/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 |
| Linear29 / 横梁 | 3/3 · 0/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 · 3/3 | 3/3 |

全部 12/12 个面板也通过额外的原始动作 fidelity 审计：目标 critical 运行和全部控制都保持原动作的 tracking 门槛。碰撞对照的 critical 运行不要求维持原轨迹，否则会把预期碰撞偏离误当作表示失败。

Linear29 收臂 critical 的目标障碍接触为 0 N，终点误差 2.56–4.75 cm；wide 的峰值障碍接触为 456.6–509.7 N。Linear29 横梁目标接触为 0 N，终点误差 4.75–5.72 cm；直立对照出现 199.2–340.6 N 接触，但仍到达目标。横梁机制支持的是**无接触穿越优势**，不是“直立无法走到目标”。

跨方法、continuation 和场景的共同进入状态误差最大 1.91×10⁻⁶，低于 10⁻⁵ 审计门槛。跨环境障碍接触为 0 N。两对动作都来自 KIT/205；结果不构成新的跨源复现。

## 4. 新源 acquisition：明确保留零成功结果

排除此前检查过的 13 个源分组，在本地 bank 的 walk 名称候选中按预定的位移、向前速度、侧向速度、root 高度波动和路径直线度筛选。筛选后只有五条候选、三个源分组，未为凑满六组而放宽规则。每组选择最接近两个已支持 gait anchor 的关节/速度描述符候选。

对每个 carrier 检查标准化收臂的 upright、0.50 rad 弯腰、4 cm root 下移加 0.35 rad 弯腰。最后一个组的组合编辑未满足脚部 IK 保持误差限，在进入 physics 前拒绝。因此实际为 24 个 episode。

| 源分组 | 运行数 | upright 通过 | bend 通过 | hybrid 通过 | 身体 tracking 误差范围 |
| --- | ---: | ---: | ---: | ---: | --- |
| KIT/675 | 9 | 0/3 | 0/3 | 0/3 | 11.83–15.13 cm |
| Eyes_Japan_Dataset/kaiwa | 9 | 0/3 | 0/3 | 0/3 | 11.63–16.42 cm |
| Eyes_Japan_Dataset/aita | 6 | 0/3 | 0/3 | IK 拒绝 | 24.78–27.54 cm |

24 次都未通过 tracking；没有 native termination、非脚部地面接触或障碍接触。由于 upright 基线也不合格，当前瓶颈先发生在 teacher 对这些 carrier 的支持范围，而不是横梁的几何位置。这里的 upright 也经过统一 arm-tuck 编辑，不能将其解释为对原始人类数据质量的结论。

没有候选进入横梁搜索，`accepted_pairs.json` 为空，没有追加 source-main 运行，也没有用替换候选静默填充成功配额。

## 5. 数据与实验账本

- 原有 acquisition 数据仍为 **120 个 episode、5 个编辑动作对、3 个源分组、10/15 个验证面板**；其中 3 对通过全部面板。未因本轮重复/解码执行而增加独立动作对数。
- 新建单独的 representation 索引：`runs/decoder_validation_20260915_v1/development_representation_episodes.jsonl`，包含 96 个 episode、19,200 控制行、16,800 有支持的 imitation 目标行。
- 索引显式标注 `experiment_role=representation_validation`、`independent_acquisition=false` 和 canonical pair；不直接并入 acquisition 索引。
- Actor 仍只包含因果 proprioception、完整已知地图和目标。原始参考 fidelity、未来参考、来源、method 和 relation label 不进入 actor 输入。
- 原始 native support 保留；另导出 `original_motion_preserving_imitation_support`。失败用于适当的 outcome/contact 目标，不能作为成功 imitation 样本。
- 新增预算使用 114/144 次预检、2/2 次预检启动、96 次主实验。三个 native 启动均正常退出，无重试。剩余预检额度不转成第三次未登记启动。
- 累计 248 次预检 + 216 次主实验 = **464 个 native episode**；480 次主实验上限还剩 264 次。decoder 后代也消耗主实验预算。

所有 210 个新 episode 已复核 outcome 与 actor/teacher/target 划分；主实验另检查 frozen geometry、原始参考一致性和接触隔离。代码测试及逐文件哈希审计见 `analysis_receipt.json`。

## 6. 下一步如何推进原始目标

### 先建立可解释的执行表示对照

保留 Linear29 为强基线。下一次针对 RVQ 做**时间连续性 × 腿部 fidelity** 的分离干预：比较原 patch 解码与平滑解码，分别保留 RVQ 腿部或提供原始腿部参考。后者是 oracle 诊断，有额外信息成本，不作为公平压缩结果。沿用冻结 teacher、进入段和场景；先空场景资格，再验证场景机制。只有这个实验才能区分接缝问题与 gait 重建问题。

未来 learned tokenizer 的候选损失应同时包含关节位置/速度、脚部运动和接触、身体 clearance、原始行为决策保持。不能只优化上身平均重建误差；先用上述干预确定当前失败来自哪里，再决定是否增加模型复杂度。

### 增加 teacher 支持的独立 carrier，再训练 criticality proposer

当前 nearest-gait 描述符没有带来新合格 source。下一次应先建立更多**未编辑 carrier 的 teacher 执行资格**，检查 root pace、脚接触与跟踪误差，再考虑受约束 retiming 或编辑；每种改变单独标注并重新 qualification。仍保留原始失败，不通过放宽阈值扩大数据集。

随后把已支持的 carrier 交给同一个 whole-body scene search，增加独立来源和第二机制的跨源复现。在足够来源上比较 root-only、连续 full-body、Linear29 和改进 tokenizer 的 proposer，并控制几何查询与 physics 预算。`no-scene / out-of-support` 必须是合法输出。

### BFM 和 text2nav 的接口已经更清楚，但效用还未测量

Motion 表示可以服务于离线 proposer 和行为目标；实际 student 仍应预测与冻结 SONIC decoder 兼容的 64D motor latent 或 29D action。当前 10 Hz 中心采样 token 与教师未来参考不是因果观测。下一阶段的导航学生需要从 scene、goal 和当前机器人状态选择可执行 continuation，不能仅回放一条事先知道的完整运动。

最终仍使用独立 scene-first 任务比较相同 learner 在普通 motion、随机场景、关键场景数据上的收益。当前单源 representation 成功不支持 BFM 泛化或 text2nav 的性能结论。

## 复核与重现

已有 native 目录不重跑；其 launch/config/code snapshots、source/reference 哈希和日志保留。以下命令只重算分析：

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=src:/home/linjiw/groot-wbc-sonic-sim-trackb
export OPENBLAS_NUM_THREADS=2
export OMP_NUM_THREADS=2
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
"$RESEARCH_PY" -m hindsight_motion.decoder_execution qualify runs/decoder_preflight_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.source_acquisition qualify runs/new_source_preflight_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.batch_audit analyze runs/decoder_interventions_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.decoder_execution fidelity runs/decoder_interventions_20260915_v1 runs/decoder_preflight_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.decoder_report
"$RESEARCH_PY" -m pytest -q
```
