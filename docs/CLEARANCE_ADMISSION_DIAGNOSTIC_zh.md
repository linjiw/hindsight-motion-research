# 下一项诊断：请求可否等待安全准入，而不改写已承诺动作

> 2026-09-20 更新：[pending-exit 协议已登记并部分执行](PENDING_EXIT_RESULTS_zh.md)。三个原有成功控制完整保留；关键 farther-Linear29 因最后资源等待期间 queue 收到 SIGTERM 而尚未启动。原比较、失败与本设计历史保留，延迟准入修复仍待物理验证。

2026-09-19。**拟议、尚未登记或执行 native。** 本文接续 [continuous 2/2、Linear29 1/2 的完整任务结果](DISTANCE_CODEC_ADMISSION02_RESULTS_zh.md)；现有四次预算已用完。新实验须单独冻结实现、逐字段前缀证明、输入哈希、预算和停止规则，不能恢复旧 queue 或把失败当作需要重试的基础设施问题。

## 假设及最小干预

观测：远目标 Linear29 在 tick 126 正确请求 loop，但 clearance 差规定余量 1.069 mm；tick 134 gate 打开，原 controller 已不再查询。**可证伪假设：一次性的固定时刻准入，把本来可能接受的 loop 请求永久丢失；在共同承诺前缀内等待 clearance，可能保留完整任务能力。** gate 后真正切到 decoded loop 是否可执行仍未知。

先固定原 endpoint predictor、动作库、root、motor、codec scale/anchor/速度规则、beam、goal 和所有 scorer 阈值。只增加“待接受请求”的生命周期：

1. tick 126 按旧规则计算请求及预测误差一次并锁存；goal 不在本实验中改变。原 short 请求立即保持 short。若请求 loop 且 gate 已开，保持旧行为。
2. 若 loop 请求被 gate 拦住，记为 `pending`，暂时保持 short；以后每个 control tick 从实际 measured state 重新检查原 2 cm 全身 gate。**不把 tick 126 校准的 displacement 直接加到更晚 root 重算终点。** 那会额外干预 endpoint model，破坏单因素诊断。
3. 只有 gate 打开，且新旧 option 在已承诺五帧及其他冻结接口约束中仍完全兼容，才接受 loop。composed clock 不重置、不重复 donor frames、不改原始速度及 synthetic support masks；未承诺预测可改变，真实 history 不可伪造。
4. 从两种表示的 q、qdot、root、root velocity、rotation 和 index/commitment 规则逐项推导并冻结**共同最晚接受时刻**。现有 preflight 的 decoded qdot 首次分支差在 167，提示五帧窗口的候选上界为 162；这是待实现前缀审计的上界，不是未经证明的运行常数。tick 134 的五帧 134–138 在已知共同 joint 前缀内；仍须核对全部字段。
5. 超过证明过的窗口则 `expired/unsupported`，保留 short fallback 及失败评分；这个返回值不等于新资格验证的安全停止。不得强制 loop、降低 clearance 至 18 mm、放宽 0.50 m **3D** goal 半径、延长 10 s deadline 或事后挑选成功目标。

**承诺语义也须单独版本化。** 原 continuous pilot 在任一分支改动进入 0.90 s native horizon 之前就决定出口；晚到 134 的选择会改写之前可见的 future samples。拟议新 profile 只承诺未来五个 control ticks（0.10 s），余下十个 100 ms 间隔 horizon 样本中的远期部分是可修订 forecast。不能声称它保留原先所有已可见帧。必须核对实际 packing/source clocks；相同当前 joint 帧也不保证相同 action，因为 motor 读取整个 horizon。若这个版本化 contract 不能证明，就拒绝晚切，另行资格验证后续 splice。

这个干预是 controller/reference 接口的时间机制，不是“Linear29 已修好”、量化优化或新的语义 tokenizer。

## 实现前必须通过的离线检查

实现独立 wrapper，保持原绑定模块及新旧 receipts。pending 功能关闭时，复现本次 1,660 个实际状态的 issued reference/index/decision。开启时，在 continuous 和原目标 Linear29 的既有历史上保留旧 choices；对远目标 Linear29 的既有历史只能报告预期首次接受及前缀合法性，不能把 shadow 当成 rollout。新日志分别记录 requested、pending reason、measured margin、accepted tick、expired、selected route、actual task completion。

增加有意义的时序测试：gate 在决策前/当刻/窗口内/截止后打开、从不打开，short 请求、已接受请求不重复切换、越界或不兼容字段拒绝。要求所有候选 frame、motor horizon、padding 和首帧来源一致。离线阶段不查询 motor 或 teacher，不拟合新 endpoint/codec。

## 拟议最小物理矩阵及预算

| Controller | 原 goal × continuous / Linear29 | 远 0.60 m goal × continuous / Linear29 |
| --- | --- | --- |
| 原一次性 gate | 复用本次两格，须绑定 exact source/task/reset | 复用本次两格，含真实 deadline |
| pending + bounded clearance admission | 拟新增两格，验证不回退 | 拟新增两格，测真实选择及完整任务 |

拟议新预算最多 **4 attempts、2,000 control steps、8,000 physics samples**；每格 500 ticks / 600 s wall、0 retries/训练/teacher-action queries，采用原串行资源门槛和 300 s 等待。不是新的四次已获科学注册，也不从历史 main 余额扣除。新连续控制必须与现有连续轨迹逐项一致；reset/history/dynamics/RNG 严格匹配。若 identity/qualification 不成立，停止并记录，不能把不同实现结果当作可复用对照。

完整 scorer 使用原 3D goal distance、通过/恢复/50 tick hold、速度、禁用接触与 deadline。保存全部 native动作、状态、真实 clearance、前缀和事件时序；独立 scorer 与 reference replay 后才报告 success。

## 预先说明如何解释

- 仅远目标 Linear29 由 pending→accepted→完整成功，其他格严格保留：支持一次性准入时机是这个开发任务的操作性瓶颈；仍不证明泛化或所有 decoded loop 的资格。
- 接受 loop 后仍失败：定位 first divergence、contact/recovery/endpoint/hold；再单独登记 matched-state loop 支持及速度/插值/clip-range 组成干预。不得把失败归咎给某个未隔离组件。
- 前缀窗口内 gate 始终不开或其他约束拒绝：保留 unsupported 结果，说明等待策略不能覆盖这个来态，不强制 unsafe switch。
- continuous 或原目标回退：wrapper 或承诺规则未保持，应先修实现/接口；不通过增加 tokenizer 容量掩盖。

相邻 endpoint calibration 后的 [reset screen 快照](../results/reset_controller_sync.json)已完成：continuous 在 backward 10 cm beam 上也错过 126 gate，138 才开，5/6 beam、6/6 clear、两项 zero controls 保留，两个成功的余量仅毫米级。这支持先处理时间接口的脆弱性，而非把失败视为所有量化特有。相邻下一步拟做 backward reset 的 public pending 与 early supplied-loop 两项物理对照，尚未执行；它的 supplied control 不算 public success。优先复用兼容的版本化 wrapper，不重复整个 reset screen；本仓库四格仍隔离 codec 干预并固定原 predictor。若 wrapper 改了 endpoint/其他参数，不能直接用于本比较。随后再组合 endpoint compatibility 与新 reset 支持，并用未参与开发的场景/ancestry 验证泛化。

对未来 BFM/VLA/LLM 的直接设计启发是把**请求与接受、有效时间窗与已承诺前缀、实际完成与字段正确**分开。小模型可测试这些状态字段是否保留；身体执行仍需真实状态上的资格和完整任务结果。
