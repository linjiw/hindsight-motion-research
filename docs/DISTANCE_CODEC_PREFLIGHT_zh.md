# 距离响应 composer 与 Linear29：离线接口预检

2026-09-19。完成旧 selector 的[六格 screen](SELECTION_BOUNDARY_ADMISSION02_RESULTS_zh.md)期间，同步相邻 `8b90ccaa`，并按[离线注册](../configs/distance_codec_preflight_v1.plan.json)检查新 exit composer。**本预检没有新 native attempt、motor-action query 或训练；不能报告 Linear29 已完成新 farther-goal 任务。**

## 新的连续支持来自哪里

相邻 `DUCK_DISTANCE_EXIT_20260919.md` 及 `/home/linjiw/research-data/m2s-duck-distance-exit-20260919-v2/` 记录：旧 direct seam 搜索 4,961 对，1,023 对支撑条件合格，但严格运动接缝 **0 对通过**。没有调宽原限制。随后单独构造 0.40 s Hermite blend，加一段 nominal 步行：499 → 557 frames；19 个 synthetic interior frames 的 observed-support validity 仍为 false。

它在内部 tick 126，以当前身体是否完全过梁及实测 root 加历史执行获得的 suffix-displacement estimate，选择 short/one-loop；原 goal 选 short，远 beam goal 选 loop。控制器使用固定 composed clock，取代旧 local retiming；只有一次长度决策，不能处理后续任意 goal 更新、重复 loops 或泛化反馈制动。

相邻八次 native：supplied controls 4/4、public controller 4/4，3,056 control steps / 12,224 physics samples；public farther-beam 为 424 ticks，final XY error 0.384866 m，沿路线 overshoot 约 0.378 m。它在旧 0.50 m 容差内完成，但不是精确停止。八次只包含三种实际 action history、一个 ancestry/seed；nominal-loop 尚未选中或物理资格验证。两 goal 使用同一 scene 字节；新场景上的 short-only farther-beam baseline 仍缺失，不能将跨研究 pass/fail 直接解释为独立 controller 效果。

本预检没有修改相邻代码、动作库、support mask 或其结果。Raw direct-seam failure、synthetic planned reference 和新 measured execution 各保留其含义。

## 复现新接口并施加原 codec

使用不变的 `decode_candidate`、named 12-bit scale、offset 2 / stride 5、两帧 reset anchors 与原 native finite-difference velocity 规则，对 nominal/local_duck 的 short/loop 四个数组编码。**四项 public history 共 1,528 state 的 continuous reference、十帧 composed indices 和实际 choice 精确复现**；Linear29 shadow reference 在全部 1,528 state 与 continuous 不同。它们尚未经过 motor/action 或物理回放。

每个 short：100 knots、2,900 symbols、400 clipped；每个 loop：111 knots、3,219 symbols、444 clipped。冻结四个 wrist 通道的 clipping 没有重校准。Loop 关节 logical payload 为 38,628 bits + 1,856 anchor bits，仍不包含 root、planner bank、source/bridge metadata、模型和容器；没有实际 wire/storage 节省结论。

## 两个不能静默忽略的差别

| 检查 | 实测离线结果 | 对下一实验的含义 |
| --- | --- | --- |
| 连续 short/loop 首个 q / qdot 差异 | 都在 composed frame 172 | 新连续桥有明确的分支边界 |
| Linear29 short/loop 首个差异 | q 在 168；qdot 在 167 | 插值会把分支差异向较早预测帧扩散，不等于物理关节提前跳变 |
| Decision 后五帧承诺 | 两表示各自 short/loop 的 q/qdot 前缀都保持一致 | 当前硬承诺未被这个离线处理破坏；尚无闭环物理保证 |
| Decision 之前曾预测到的最后一帧 | frame 170 | decoded options 在部分曾预测帧上已不一致，不能沿用“整个曾见 horizon 一致”的描述 |
| 未压缩 loop 的 supplied qdot vs 对 q 做 native FD | 20 frames 不同，最大 0.0932425 rad/s，自 frame 171 开始 | 新 analytic blend velocity 和 q-only decoder 的速度语义不同；并非所有差异来自量化 |

Local-duck 两个 decoded options 在 frame ≤170 的最大 q 差为 0.00170517 rad、qdot 差为 0.0284255 rad/s；nominal 对应 0.00103503 / 0.0172526。它们是 planned-reference 差异，不能推断实际碰撞或不稳定。

在 original-beam 的 **同一条 368-state 历史**上比较原/远 goal，新 composer 分别选择 short/loop。Continuous 首次 goal-dependent reference 差异在 tick **127**，Linear29 在 **126**，即早一个 20 ms control tick；changed rows 为 241 / 242。Decision 仍在 126，**没有在决策之前改变发出的 reference**。Original-clear 同样 368-state 对比，两 goal 都选择 short，两种表示的 changed rows 都是 0。这不证明真实 Linear29 trajectory 会经过相同 gate 或选择相同分支。

## 下一实验的具体约定

优先复用已支持的新 continuous controller，比较 original/farther beam 的 continuous 与 raw Linear29；不要另造一套 composer。拟议四格需另登记。保留新 continuous planner bank、root alignment、一次决策及 inherited terminal profile；不将旧 retiming 混入新 controller。

为 raw Linear29 明确：在 composed array 的时钟上编码，indices 指向 composed frames；桥的 donor ancestry 与 synthetic mask 是附属信息，不能当原 source row。五帧 committed prefix 必须相同，决策后的 forecast 可以产生已量出的早一 tick 差异，并记录它。Provided continuous qdot 与 decoded finite-difference qdot 的差异属于这个接口方案的总干预，不能事后仅归因于 12-bit quantization。若需要保持全部已预测前缀或额外边界锚点，另建版本并计费，不覆盖 raw baseline。

Native 比较先精确复现相邻 continuous controls，再匹配各 method 的初态、history、dynamics 和 RNG。随后分别记录 measured clearance、短/长选择、实际进度、通过/恢复/停止及 contact。若 Linear29 alone 失败，再针对真实失败点登记 velocity-only 或边界处理对照；若都成功，继续冻结简单表示，用 upstream 的距离 envelope 去检验支持范围，而非立即训练更大 tokenizer。

LLM/BFM/VLA 接口还需明确 request、clock、support provenance、进度与终止语义。保真字段并不保证目标会改变动作；保留每个预测浮点值也不是所有接口的要求，应由已声明的承诺和执行结果决定。

复现：[脚本](../scripts/audit_distance_codec_preflight.py)、[标量结果与 hashes](../results/distance_codec_preflight.json)。本地 packet `runs/distance_codec_preflight_20260919_v1/` 保存 decoded descendants、source snapshot 与绑定；这些数据不发布。旧 controller 的 0/719 goal-response 结果和本次新 controller 的 241/242 changed rows 属于不同控制器及不同历史，不能合并为同一 repeated sample。
