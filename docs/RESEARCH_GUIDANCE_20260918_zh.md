# 外部研究指导：保存、复核与采用

2026-09-18。用户提供的完整指导已逐字保存在本地 `artifacts/research_guidance/20260918_user_review_zh.txt`（293 行；SHA-256 `f145ea8a4cc446a435ab9b5c89135ccc46caad7438553ffe4bd70476e81802fb`）。原文不纳入公开站点；本文件记录经过复核的采用决定。[主计划](RESEARCH_PLAN_zh.md)与[小模型协议](LLM_INTERFACE_PROTOCOL_zh.md)据此修订。

## 核心问题与反假设

**在相同实际来态、场景和冻结控制器下，表示是否保留原本可执行的选择；这种保持是否帮助机器人完成接近、低姿态穿越、全身离开、恢复直立与持续停止？**

反假设同样有效：简单连续参考或 native motor 已足够，瓶颈在 supervisor、root 计划、切换支持或闭环选择。先定位瓶颈，再训练新 codec。小 LLM 是检验接口的信息通路，不是绕过这个门槛的新主线。

## 采用的具体改变

| 指导 | 采用与可审查交付物 |
| --- | --- |
| 先检验表示瓶颈 | 以下 2×3 执行矩阵成为下一项物理研究的核心；后续第一行 pilot 各 4/4；第二行同相位子面板各 8/8；第三行熟悉 known-map selector 各 2/2；场景变化已有开发结果，扰动及跨族拼接未测 |
| 更强的简单对手 | 全程保守蹲行，目标附近恢复直立并停止；几何规则使用全身包络、障碍后缘与延迟余量 |
| 明确任务变化 | 开发后冻结横梁位置、高度、沿行进方向长度及初速度的独立变化；不得按某方法成功与否筛选测试集 |
| 明确终止 | 分开碰撞、全身离开、恢复、目标误差、停止、超时；直立同时约束腿伸展/骨盆高度与躯干姿态 |
| 来态不仅是 pose | 保存物理状态、速度、支撑、控制器/已执行动作历史与随机状态；优先取真实 rollout 的降低、进入、离开、停止时刻 |
| 不把新任务混入旧预算 | 原剩余 168 main attempts 继续属于旧协议；完整任务需独立登记、成本和支持资格 |
| 泛化分层 | 首先测固定合格动作库/控制器下的独立未见场景；跨动作 ancestry 泛化另行采样与证明 |
| 信息经过 LLM 后是否仍有用 | 先离线接口探针，再同一真实 motion 的压缩/LLM/解码对照，最后相同来态下的物理执行 |

建议的目标误差 0.25 m、速度 0.1 m/s、保持 1 s 只是新 task profile 的开发候选，尚未构成物理资格标准。本次合成接口探针使用这些数字做字段保持测试，不能据此宣称机器人已能做到。

## 下一项物理交付：完整任务支持与表示瓶颈报告

| 执行条件 | Continuous | Linear29 | 区分的问题 |
| --- | --- | --- | --- |
| 正确完整参考，从 reset 执行 | 后续 pilot 4/4 | 同任务配对 4/4；两帧 reset anchor | 任务本身是否受支持，codec 是否损害执行 |
| 相同真实来态/历史，提供合格后续 chunk | 同相位、无扰动子面板 8/8 | 同真实 prefix 配对 8/8 | 当前只资格验证同相位 continuation；新选择与恢复待测 |
| reset 开始，因果 composer 选择并重规划 | 熟悉 known-map selector 2/2；新 scene screen 1/3 | 同 continuous planner bank：熟悉 2/2；新 screen 1/3 | 新六格完成：两者均 shift 成功、低梁接触、远 goal 超时；跨族稳健性待测 |

后续执行见[完整任务报告](COMPLETE_TASK_RESULTS_zh.md)：既有 goal050 profile、两 clip/clear+beam、有完整参考辅助。原始用户指导逐字副本未改动。

第二行首个子面板见[continuation 物理结果](CONTINUATION_ADMISSION02_RESULTS_zh.md)：新 admission 执行 16 格、八个配对来态/历史误差为 0，两种表示各 8/8，4,136 control steps，零训练。原 0-launch 资源延期另存。它只测无扰动同相位切换；这项 handoff 本身不能升级为因果 composer。随后独立登记的[known-map selector 结果](SELECTION_CODEC_RESULTS_zh.md)已取得两表示各 2/2，从 reset 闭环选择；它的熟悉来源和 continuous planner bank 限制单独保留。

横向比较主要隔离表示；纵向信息条件与状态分布不同，只用于定位系统缺口。前两行不是自主导航。第三行共享因果 composer 的 root 目标，计入 root 成本；不可读取隐藏未来 root、进入段或示范 phase。由观测和已执行动作更新的内部进度允许使用。

Native 先单独通过同参考、同完整 proprio history 的 encoder→decoder 与直接 decoder 一致性检查。不能将 token 在不同状态轨迹播放当作公平上界；不能假设 10 Hz sample-and-hold 等价于原发布频率。跨 reference/native 的差异首先属于整个接口路线比较。[官方接口文档](https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vla_inference.html)

## 指标与统计约束

在相同来态 h 和场景 g 下，记录降低身体与直立两种选择的完整成功概率差 A_R(g,h)，再看 critical 与 removed 条件的差 I_R(h)。同时报告所有格子的绝对成功率、碰撞和终止，避免两个行为一起损坏却差值不变。

补充有效启动时间窗、预定可达来态集合上的支持比例、分阶段退化。不能把有限采样支持率称为完整可行域，也不能将 ankle FK 重建误差称为实测滑脚/接触。机制报告可以条件于 continuous 合格子集，但必须另外报告全部预定任务上的结果、支持覆盖和未运行数。

场景配对退化优先于孤立均值；训练 seed、场景簇和来源簇分别处理。先用 pilot 估计方差，再登记主实验量。未显著改善不证明等价；简单方法足够的判断需要预先定义可接受差距与成本。

## 方法选择与停止条件

最新[距离响应完整任务](DISTANCE_CODEC_ADMISSION02_RESULTS_zh.md)已完成：continuous 2/2、Linear29 1/2，一个 codec-only 配对成功退化。远目标请求正确，但实际身体时序使一次性 clearance gate 拒绝 loop；后续虽开 gate 却不复查。先按[时间准入诊断](CLEARANCE_ADMISSION_DIAGNOSTIC_zh.md)隔离 controller/表示接口，不直接扩大 tokenizer 或 LLM。尚未发出的 loop blend 不能造成决策前失败；limiting ankle 也不能单独证明腿 codec 是原因。

若确认表示瓶颈，首个学习候选为**全身联合、来态条件化的连续 temporal latent**。所有方法共享坐标变换、姿态锚定、速度推导和 committed-prefix 规则；同架构普通重建与执行相关训练对照。再与等总预算的自适应 scalar/spline 比较，允许简单方法胜出。量化放在连续学习表示获得实际收益之后。

固定控制器响应差可以作为局部诊断或训练侧敏感性指标，但不是物理成功替代；不可假设 ONNX/仿真可微。敏感区间权重只由 train/dev 获取。未来支撑是预测目标，不能作为 actor 的示范未来输入。

完整参考失败→修 supervisor/tracker；共同来态失败→查支撑与切换；正确后续成功但 composer 失败→修 root/决策/重规划。两种简单表示均合格→直接比较固定 learner 的成本与学习效用。数据研究另开一项：同基础生成器、相同总获取成本，比较加入执行验证的临界对比与普通采样，计入失败、过滤、teacher 查询与仿真时长。

## 文献复核带来的定位修正

[ActionPiece v1](https://arxiv.org/html/2609.18487v1) 已用解码动作的物理距离排序保持评价 tokenizer，并控制策略训练条件比较下游表现；不能把“超越 MSE、保持动作关系、测下游”单独当新颖性。我们的待证问题是同一状态/场景中可执行选择的保持；距离排序保持并不必然保留临界间隙。应加入几何关系保持基线，而非仅在文字中区分。

[OAT v2](https://arxiv.org/html/2602.04215v2) 研究压缩、总可解码性及有序前缀。借鉴前缀/成本测试，但可解码不等于能从当前人形支撑状态执行。[PASSAGE v1](https://arxiv.org/html/2609.18732v1) 的连续性与任务训练已有直接重叠；加 loss 或停止 scorer 本身不足以构成贡献。接下来优先做区分实验，暂不扩展泛泛模型清单。


### 9 月 19 日继续：从完整任务退化到可检验的时间机制

原零 launch 的[延期记录](DISTANCE_CODEC_RESULTS_zh.md)保留，新 admission 完成四格，零重试/训练。四次均无禁用接触，远目标 Linear29 最终距目标 0.674383 m；完整 scorer 实际使用 **3D** 距离，早期 XY 文字误标另见[更正](DISTANCE_METRIC_CORRECTION_20260919.md)。旧 shadow 的信息响应未能在真实状态资格中保留，说明 request、pending、accepted、expired、complete 要分开记录。下一项在冻结阈值与共同承诺窗口内检验延迟准入，尚未资格验证修复。

相邻 continuous endpoint 校准已独立物理执行，12/12 对 11/12；在本仓库既有 Linear29 历史上的 calibrated shadow 仍被 gate 拒绝。停止预测、状态支持与语言字段保真继续分层，不互相代替。用户指导逐字原件不变。

### 9 月 20 日继续：先完成决定性一格

[pending-exit 实验](PENDING_EXIT_RESULTS_zh.md)已经实现并预注册，三个新控制精确保留旧成功路径，83 tests 通过；关键远目标 Linear29 未启动，queue 在资源等待中 SIGTERM，sender 未知。只补唯一 never-launched case 的新 admission，不重跑三控制、不放宽 gate、不将 shadow 134 接受或三个无等待成功升级为 repair。总四次 ceiling 剩一，最多 500 control ticks。执行、请求/接受与证据类别继续分开；暂不转向更大 tokenizer 或 LLM。


### 同日 admission 02：保留资源阻塞，不扩展结论

[独立 admission 02](PENDING_EXIT_ADMISSION02_RESULTS_zh.md)已实现，只补关键一格；428 项绑定及 92 tests 合格。300 s 资源门槛正常超时、15 次采样零合格，GPU free 最高 11,218 MiB < 12,000；零新 native，累计仍三条成功控制。先确认资源可用，再为同一 never-launched case 新 admission，总四次 ceiling 不变。相邻 `2a3cfb47` 的 continuous pending 成功[单独同步](PENDING_CONTROLLER_SYNC_20260920_zh.md)，不计为本仓库 Linear29 结果。任务证据、数据角色与时间接口继续优先于新模型名字。
