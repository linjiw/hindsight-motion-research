# 同步：两处 pending 接口研究，保持各自的因果比较

2026-09-20。只读相邻项目已提交的 `2a3cfb47`；本仓库及相邻 origin 均无 incoming，未覆盖相邻未提交工作。四份文档/标量证据逐字匹配该 commit，快照及 SHA-256 保存在 `runs/pending_sibling_sync_20260920/`，[公开摘要](../results/pending_sibling_sync.json)只包含结果、事件时刻和来源，不包含 motions 或 raw trajectories。

## 相邻实际测到了什么

相邻 calibrated continuous controller 的 backward-start（−0.10 m）原失败仍保留：它于 tick 126 请求 loop，但 clearance 未达到既定门槛，保持 short，完成通过/恢复却无法达到停止目标。新增 pending public controller 锁存原请求，在 pre-action **138** 观察到 clearance 后接受，424 ticks 完成任务，最终 **3D** 距离 **0.290882 m**，radius margin **0.209118 m**，speed **0.024539 m/s**；有完整 50-tick hold，无测得禁用接触或跌倒。

同任务的 supplied-loop control 在 126 强制给定 loop，也在 424 ticks 成功，最终 3D 距离 **0.295951 m**。它提供动作支持/时机对照，不能计为自主 public success。两次共 **848 control steps、3,392 contact frames、84.789 s native wall**，零过程失败、重试、teacher query、优化或训练数据准入，独立于本仓库预算。

Public reference/token/action 首次差异在 138，pre-action root 在 139；supplied reference/token/action 在 127，pre-action root 在 128。原始状态、历史、RNG、动力学及此前完整前缀精确相同。旧的 11 条成功变 reset 历史及 2 条 zero control，在 5,119 recorded rows 上离线输出保持；不能说新增执行了 13 条。

## 与本仓库的问题如何对接

| 比较维度 | 相邻实验 | 本仓库 pending 比较 |
| --- | --- | --- |
| 主问题 | backward reset 的 continuous 请求是否可保留至 clearance | Linear29 在 farther goal 丢失的选择是否可保留 |
| endpoint predictor | 已执行终点校准模型 | 原预测模型，冻结不替换 |
| 实测门槛 | 相同类型的全身 2 cm clearance | 原全身 2 cm clearance |
| 共同前缀限制 | continuous 首差 172，最晚接受 167 | 包含 Linear29 qdot 首差 167，共同最晚接受 162 |
| 额外供给 | 独立 supplied-loop 控制 | 无强制 loop；原请求锁存 |
| 已有控制保留 | 13 条旧历史离线重放 | 三条新 native 控制完整轨迹精确保留 |
| 预算 | 两次新执行，另有已登记 retry 条款 | 原四次 ceiling，零 retry；admission 02 只补一格 |

不能直接拿相邻 167 窗口给 Linear29 使用。两处版本都只承诺接下来五个 **control ticks**（0.10 s），更远的 motor forecast 可以修订；五个 ticks 不是五个 100 ms native samples。即使当前姿态参考相同，未来输入改变也可能马上改变 action。

## 当前解释与下一阶段条件

相邻结果支持一个具体解释：固定时刻拒绝后永不复查，是该任务中可修复的 supervisor 限制。两种时机均成功，所以它没有证明“等待优于早承诺”，没有隔离量化损失，也没有证明任意 late switch 安全。负的保守 proxy separation（约 −4.98 mm）与零测得禁用接触并存，应保留两类诊断，不能合并为物理碰撞。

本仓库仍先完成自己冻结的 continuous/Linear29 比较。若 delayed Linear29 完整成功，最小下一步是整理 **controller/codec 兼容的完整 episode inventory**，明确 causal 输入、request/acceptance、reference forecast、动作、结果及 loss-validity；然后另行设计有 simple continuous 对照的学习问题。若接受后仍失败，先定位执行/停止阶段，不立即扩大 tokenizer。资源延期则保留未运行，不用相邻成功填补本格。

未来小学生模型应先从公共 goal/map/proprioception/history 学 family 和请求，通过共同 executor 输出；共享 clearance gate 不能被宣称为学习到了 clearance。失败可成为 outcome label，未经资格验证的 suffix 不能作为正 action target；supplied controls、重复物理历史、同祖先切窗各自明确标注。下一实验必须按完整 episode/reset/goal 分组并固定学习剂量，不能把 5,119 帧当独立样本。更低梁、blocked routes、速度/姿态范围、新动作祖先及因果深度观测仍是独立未解决的问题。
