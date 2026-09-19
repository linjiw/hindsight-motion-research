# 距离覆盖的新证据：表示比较继续，停止预测问题独立

2026-09-19。本轮按主计划继续前，fetch 确认本仓库 `cca3fc2` 与远端一致；相邻工作区已有本地提交 `7b416f76`，上游无新增提交待合并。相邻 dirty tree 只读，没有 pull 覆盖、修改或提交其工作。读取其 `DUCK_EXIT_ENVELOPE_20260919.md`、公开 analysis / endpoint-diagnosis 及已有 distance-exit runtime；新提交没有改变我们拟复用的 composer、bank 或 checkpoints。

## 已完成的相邻实验

相邻对 beam/clear × goal 延长 0、0.45、0.60、0.90、1.20 m，比 frozen public choice 和 short-only：**public 9/10，short-only 5/10，五个 paired gains、一个 regression**。二十个比较格中七格复用，十三格新执行；另一个 nominal-loop supplied support control 为新增，所以共十四次新 native attempt。不要把这些次数、成功或 raw 数据并入本仓库 codec 账本。

本轮看这些结果之后才登记 [四格 codec 实验](DISTANCE_CODEC_PROTOCOL.md)，明确仍为此前选定的 original/farther beam 两个熟悉请求，没有将 +0.45 m 事后加入同一个 native panel，也不声称 held-out。

| 相邻新增证据 | 对先前判断的更新 |
| --- | --- |
| +0.60 m beam 同 scene：short-only 超时，XY error 0.607014 m；public loop 成功，0.384866 m | 先前缺失的匹配 short-only baseline 已补齐，支持 frozen package 在这一请求的收益 |
| nominal-loop clear/+0.90 m supplied control 成功，424 ticks，XY error 0.297540 m | nominal-loop 已有连续执行支持；不等于 Linear29 也通过或任意 loop/来态都合格 |
| +0.45 m beam：short 成功，XY error 0.477781 m；public loop 超时，0.542452 m | Public choice 不占优于所有请求；短选项只有 0.022219 m 半径余量，必须保留这个回归 |
| 冻结预测器给 short/loop 预测误差 0.466636 / 0.450515 m，仅差 0.016121 m | 单次估计选择 loop，但其停止位置超出容差；动作可执行与目标选择正确是两个问题 |

全部请求沿用同一场景字节、一个 ancestry 00976、seed 96161、原 reset 与 0.50 m XY goal radius。相邻独立重算 8,856 个 reference/token/action/index 及完整 scorer；14 次新执行为 6,224 control steps、24,896 physics samples、385.537 s native wall；零基础设施失败、重试、teacher-action query、训练或 learning-row admission。七格复用的 2,632 steps 单列。多个条件共享实际动作历史，不是独立的泛化演示。

相邻报告的 executed-loop displacement 校准只是**事后离线假设**：用两个 supplied controls 的 decision→最后 50 帧均值位移，重算后只有 +0.45 m beam 改选 short。它会映射到十个既有成功候选，但尚不是 calibrated controller 的 10/10 新执行。原 planned geometric displacement 不应被执行估计静默替换。

## 本仓库的下一步为什么不扩大 tokenizer

我们仍需先回答：已经会按 goal 改变退出动作的 controller，其 Linear29 是否在**自己的闭环状态**上保留 clearance gate、short/loop choice、完整恢复与停止。此前只在 continuous 历史上生成 shadow references，不能推出实际 codec 的选择。

四格比较固定原始 endpoint predictor 与 motor，只替换已声明的 q/qdot 表示。它可定位表示接口的损失，却不回答 +0.45 m 的 controller 修复是否有效。两者若都成功，继续保留简单表示；后续应优先联合考察停止余量与来态覆盖，不把“又通过熟悉原/远 goal”重复计作新科学贡献。若只有 codec 失败，则按已观测故障登记 velocity 或边界诊断，而不是直接训练更大模型。

相邻下一阶段拟版本化 endpoint model 并做距离边界对照；我们的后续配对表示测试应以冻结且已取得支持的版本为前提，并预先声明校准来自哪条动作、是否依赖表示、侧信息与成本。把同一 continuous 执行位移模型直接用于 decoded reference，是需要检验的兼容性假设。真正的目标仍是可泛化完整任务与清晰的 goal/observation→motion→measured termination 接口；语言或 BFM 接入不能弥补停止预测本身的错误。

来源记录已冻结于[公开标量与哈希快照](../results/distance_followup.json)。原报告为相邻 `docs/motion2scene/DUCK_EXIT_ENVELOPE_20260919.md`，analysis / endpoint-diagnosis 位于其 `docs/motion2scene/evidence/duck-exit-envelope-20260919/`；完整原始 packet 保持本地。
