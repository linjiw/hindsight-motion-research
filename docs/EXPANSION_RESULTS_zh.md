# 扩展实验：关键场景的复现、下蹲反例与数据接口

> Follow-up completed: a second traversal family now passes all three intervention panels. Cumulative main episodes: 120. See [new results and token comparison](SECOND_FAMILY_AND_TOKENS_zh.md). The earlier counts below describe their original experiment stage.

## 本轮结论

已经完成 **122 次新增 native 仿真 episode：50 次预检/仪器对照 + 72 次场景干预**。连同上一轮，主实验已有 **96/480 次**，覆盖 4 个编辑动作对、3 个源数据分组、2 类待验证机制。

最明确的进展是：**收臂穿越的完整干预结果在第二个源分组 KIT/9 上复现了。** 第二类下蹲机制出现了预期的接触差异，但控制场景中的 tracking 不稳定，因此没有获得合格的关键性标签。

| 动作对 | 源分组 | 关键场景：目标动作通过 | 关键场景：对照动作通过 | 完整面板合格 |
| --- | --- | ---: | ---: | ---: |
| 收臂 / 展臂，原实验 | KIT/205 | 3/3 | 0/3 | 3/3 |
| 收臂 / 展臂，新增 | KIT/9 | 3/3 | 0/3 | 3/3 |
| 收臂 / 展臂，新增 | KIT/317 | 2/3 | 0/3 | 1/3 |
| 下蹲 / 直立，新增 | KIT/9 | 1/3 | 0/3 | 0/3 |

每个面板包含同一初始扰动下的 2 个动作 × 4 种场景。完整合格要求：六个控制 episode 全通过、目标动作穿过关键场景、对照动作发生指定身体部位的障碍接触，以及测量到的共同初始状态和历史匹配。初始横向扰动仍为 0、−1.5、+1.5 cm。

累计 **7/12 个面板合格，2/4 个动作对在三个扰动下全部合格**。这是开发集上的机制复现；三个扰动不是三个独立源样本，两个 KIT/9 动作对也不是两个独立源分组。

## 1. 扩大 teacher 支持范围的实测结果

从本机 900 条 G1 动作库存中预先指定了 12 个源分组的片段，包括普通慢走、潜行和 step-over 命名片段。片段名称没有被当作已验证的动作能力。

- 原动作、收臂、展臂共 36 个候选进入仿真，11 个通过原有严格 tracking 门槛。
- 最初 14 cm 的 pelvis 下移在保持双脚世界位置和朝向时，12 个候选全部超过脚部误差限。这些是 **IK 构造失败**，没有被计为仿真失败。
- 预先记录的修订按 12、10、8、6 cm 顺序选取最深的几何合格编辑，保留全部 46 次几何尝试。6 个候选进入仿真，2 个通过 tracking。
- 修改保留 root XY、非腿关节以及共同进入/退出段；通过 native URDF 的双腿逆运动学补偿 pelvis 高度变化。脚部构造限为位置误差 2 mm、姿态误差 0.02 rad。

Teacher checkpoint、名义动力学、无观测噪声配置和成功门槛保持不变：无 native termination、平均身体位置误差 ≤10 cm、最大 root XY 误差 ≤25 cm。主实验另要求无超过 1 N 的障碍/非脚部地面接触、终点距离 ≤25 cm，以及穿出障碍平面至少 20 cm。

## 2. 可审计的批量场景执行

新增执行器在相距 8 m 的环境原点上布置各自的静态场景。逐环境验证 motion 分配与场景原点；逐身体解析 PhysX sensor 行顺序；记录 200 Hz 的本场景接触，并检查所有其他场景障碍的接触力。

先重放上一轮零扰动的 8 个 episode，才运行新增实验。结果满足预先保存的等价性门槛：

- 初始 root、关节、速度和 930 维 proprio 历史与单场景基线完全一致。
- 8/8 个 episode 的各项通过/失败判定一致。
- 成功 episode 的身体 XYZ 坐标 RMS 差异为 0.83–1.38 cm，低于 2 cm 门槛；不是逐位确定性复现。
- 首次障碍接触相差 10 ms，低于 50 ms 门槛。
- 跨场景障碍接触为 0 N；两个新增主实验批次也均为 0 N。

48 个新增 arm episode 在同一次 native 启动中完成，用时 32.82 s；24 个 duck episode 用时 33.86 s。这是本机当次运行的耗时记录，不是受控的性能基准。

## 3. 场景 proposer：哪些结果成立

### 收臂：复现与边界

每个新增动作对枚举 145 个通道，使用空场中实测动作的 45 个 native 碰撞外包络。原有几何门槛不变：目标动作采样分离下界 ≥3 cm，对照动作存在解析实体内部至少 1 cm 的重叠证据。

KIT/9 有 9 个几何合格候选，选中 0.76 m 通道。收臂在关键通道 3/3 通过且接触力为 0 N；展臂在三次运行中均发生手部接触，峰值 201.0–313.5 N。放宽、移除、横移障碍后，两种动作全部通过。这是第二个完整复现的源分组。

KIT/317 有 7 个几何合格候选，选中 0.66 m 通道。展臂三次均发生手部接触，峰值 646.5–690.8 N。但是多个控制 episode 与一个收臂关键 episode 的身体 tracking 超过 10 cm；因此只有 +1.5 cm 扰动的完整面板合格。不能只依据碰撞差异把三个面板都标成成功。

### 下蹲：接触差异成立，完整关键性不成立

初始每对 115 个横梁候选均未满足双侧几何门槛；最近的候选差约 1–2 mm。随后在看到任何横梁物理结果之前记录细化方案：13 个时间位置 × 4 种梁厚度 × 4 个内部重叠深度，每个深度做 16 次高度二分。两对各评估 208 个候选，所有结果保留。

KIT/205 仍无合格横梁。KIT/9 有 18 个几何合格候选，选中底面高度 1.28958 m、沿行进方向厚度 0.24 m 的横梁，两侧有支柱；目标分离下界 3.0675 cm、对照内部重叠证据 1.0102 cm。这个余量很窄，不代表已经测出鲁棒的可行参数区间。

物理运行中，直立动作在关键场景 3/3 与 `torso_link` 上的碰撞体接触，峰值 402.6–902.1 N；下蹲在三个关键运行中均没有障碍接触。然而下蹲只有 1/3 关键运行通过严格 tracking，放宽/移除/横移控制中的通过率分别为 0/3、1/3、0/3。**0/3 个完整面板合格，未生成下蹲机制的正关系标签。**

这支持把下一步优先级放在可重复执行的下蹲动作/teacher 上。当前证据不能把失败归因于一个已识别的动力学原因，也不支持事后放宽 tracking 门槛。

**事后敏感性诊断，单独保存、不改变主结果：** 下蹲误差靠近 10 cm 门槛。仅将身体 tracking 限改为 10.5 cm、11 cm 时，合格面板分别变为 2/3、3/3；其余接触、目标、root 误差及共同初始状态条件不变。KIT/317 在 10.5 cm 时也会变为 3/3。这个分析说明严格标签对该门槛敏感，不能将“未通过预设 tracking 条件”写成“机器人无法无接触穿过横梁”。主数据仍采用预先规定的 10 cm，所有 support mask 和 headline 数字保持不变。后续应在独立任务上事先校准 tracking 容忍度与下游效用，而非用本组结果选择通过率最高的门槛。

## 4. 面向 BFM 的实际数据产物

统一索引位于 `runs/critical_dataset_20260915_v2/development_episodes.jsonl`，逐文件带 SHA-256。包含所有 96 个主实验 episode，排除重复的仪器等价性 episode。

- **19,200 行**控制记录；其中 70 个 scene-pass episode 提供 **14,000 行**有支持的 motor imitation 目标。
- Actor：930 维因果 proprio、机器人局部坐标系的 metric scene object tokens、mask、当前局部目标；这里假设完整地图和准确定位。
- Teacher-only：640 维 future-reference encoder 输入、privileged state、参考身体位置。
- Targets：执行时同状态查询的 29 维 action 和 **64 维连续 teacher motor token**、有效性 mask。
- Scene tokens 可有 2 或 3 个物体槽；collator 按批次最大值补齐，false mask 表示完整地图中已知不存在。
- 关系标签只从合格的完整面板产生；时间、身体接触位置及这些未来推导标签不进入 actor。

**64 维 motor token 不等于先前的 VQ/RVQ motion code。** 本轮没有训练新的 tokenizer 或 BFM。之前发现的压缩后 clearance 失真仍未解决。

同一个控制场景和共同初始状态可能对应多个可行 continuation。未来 student 的目标应保留多模态选择，不能直接把不兼容的动作/latent 平均。单个 episode 可用于 imitation 的支持，与它所属面板是否证明关键性，是两种不同标签。

所有样本均为 development。当前没有合法的随机逐帧 train/test 切分来证明泛化，也没有独立 scene-first 的导航性能结果。任务仍是移动中到达，不含停止/站稳。

## 5. 下一阶段的具体优先级

1. **先扩大可重复的动作支持。** 为候选的空场资格加入同样的初始扰动和重复执行；采用有裕量的 acquisition 排序，保持主实验成功门槛不变。优先找自然下蹲/弯身片段，或单独验证更合适的 teacher；改变 teacher 必须建立新证据链。
2. **保留学不到关键性的拒绝标签。** 将“构造失败、空场 tracking 不足、几何无解、接触对比成立但控制失败、完整面板成立”分开。让 proposer 有明确的 no-scene/reject 输出。
3. **再比较 motion 表示。** 对同一组固定候选比较 root、连续全身、VQ/RVQ、带关键身体轨迹 residual 的表示；除了重建误差，还报告几何判定翻转与实际执行。关系监督只用已验证面板。
4. **达到足够源覆盖后训练 proposer/student。** 当前只有两个完全复现的源分组，适合调试数据接口。下一包继续在剩余 384 次主实验预算内增加独立动作对，再冻结未见源/场景评估；先验证已知地图与目标条件下的选择和到达，再引入 grounded text。

## 证据与复核

| 内容 | 路径 |
| --- | --- |
| 12 源动作预检与构造失败 | `runs/expansion_preflight_20260915_v1/` |
| 小幅下蹲修订、全部 46 次 IK 尝试 | `runs/expansion_ducks_20260915_v1/` |
| 批量仪器等价性 | `runs/batch_equivalence_20260915_v1/equivalence-audit.json` |
| 初始通道/横梁与拒绝候选 | `runs/expansion_proposals_20260915_v1/` |
| 横梁细化及拒绝候选 | `runs/expansion_beam_refinement_20260915_v1/` |
| 48 次 arm 主实验 | `runs/expansion_interventions_20260915_v1/` |
| 24 次 duck 主实验 | `runs/expansion_duck_interventions_20260915_v1/` |
| 统一索引和累计统计 | `runs/critical_dataset_20260915_v2/` |
| 可交互实测回放 | `artifacts/expansion_viewer.html` |
| 可导出的结果图 | `artifacts/expansion_interventions.png`、`.pdf` |

完整测试集 14 项通过；新增批次的数据审计核对了原始接触判定、view 字段隔离、数组形状/有限值、物体 mask、imitation support 与共同初始状态。所有 native 启动 exit=0。累计预检 98 次（原 48 + 新 36 + 新 6 + 等价性 8），主实验 96 次，共 194 次 native episode；IK 和几何候选不计为物理 episode。

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=src:/home/linjiw/groot-wbc-sonic-sim-trackb
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
"$RESEARCH_PY" -m pytest -q tests
"$RESEARCH_PY" -m hindsight_motion.batch_audit equivalence runs/batch_equivalence_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.batch_audit analyze runs/expansion_interventions_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.batch_audit analyze runs/expansion_duck_interventions_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.expansion_present
```
