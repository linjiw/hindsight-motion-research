# 下一门槛：目标距离必须改变可执行的退出与停止

2026-09-19。沿[主计划](RESEARCH_PLAN_zh.md)的 complete-task 优先级推进。这是下一阶段设计，**不是已完成的 composer，也不自动启动新 native sweep 或训练**。本轮六格表示诊断另见[登记协议](SELECTION_BOUNDARY_PROTOCOL.md)。

## 同日进展更新：表示比较完成，下一步测时间准入

原先四个未运行 codec case 已在[admission 02](SELECTION_BOUNDARY_ADMISSION02_RESULTS_zh.md)补齐，两表示均保留低梁接触与远 goal 超时。相邻 `8b90ccaa` 也已独立实现一次 blended exit：raw seams 0/4,961 合格，另构造 0.40 s bridge 并以八次新 execution 资格验证，public/support 各 4/4。它替换了 retiming，使用 fixed composed clock 与一次距离选择；不是本仓库的新实现，也不是通用距离控制。

本仓库[四格 native 比较已完成](DISTANCE_CODEC_ADMISSION02_RESULTS_zh.md)：continuous 2/2，Linear29 1/2。新 admission 四次 / 1,660 steps / 6,640 physics samples，原零启动延期保留。远目标 Linear29 请求 loop，但 tick 126 clearance 差规定余量 1.069 mm；gate 于 134 打开却未复查，保持 short 并在目标外超时，无接触或跌倒。旧 continuous-history shadow 的响应不等于自由闭环能力。

[有截止时间的 clearance 准入](PENDING_EXIT_RESULTS_zh.md)已实现并独立注册。三个无需延迟的控制成功且完整轨迹与旧结果相同；关键远 goal Linear29 尚未启动，queue 在最后资源等待时收到 SIGTERM。共同合法窗口截至 162，shadow 在 134 接受，物理修复未知。下一步只给唯一 never-launched case 新 admission，保留三控制和中断；最多一次、总四次 ceiling 不变。2 cm clearance、predictor、codec、goal050/recovery/hold/deadline 不改。goal scorer 用 3D 距离，旧 XY 文字误标见[更正](DISTANCE_METRIC_CORRECTION_20260919.md)。

相邻最新 `eb8f1f8c` 的独立 endpoint calibration 已物理执行，calibrated 12/12 对 incumbent 11/12；不是离线假设了。它不改本比较旧 predictor，且在实际 Linear29 历史上的 calibrated shadow 仍受 false gate 阻止，详情及独立成本见[本次报告](DISTANCE_CODEC_ADMISSION02_RESULTS_zh.md)。相邻真实 reset screen 也已完成，continuous backward-start 出现相同 gate 错过；更广来态覆盖、更低梁与自由 goal 更新仍未建立。下列 A/B 是原始设计及更强能力约束。

## 原始缺口与问题（旧 selector）

相邻项目 `5184085c` 的冻结动作库 screen 发现：两种已有控制方式均能通过测试中的 ±20 cm 梁位移及 ±15° 路线转角；10 cm 更低的梁造成接触；60 cm 更远的 beam goal 在穿越及恢复后仍超时。后一个任务的 nominal clear 对照成功，不能据此断言 duck 动作也具备响应距离的能力。

其事后共同历史诊断显示，在原先 359 个 beam / 366 个 clear state 上，仅增加目标距离不改变任何候选、source index 或 640D reference。当前选择器可以改变方向、选完整 motion 并局部重定时，却没有获得按剩余距离延长出口步行的证据。Separate physical runs 的 floor extent 也随 goal 改变，不能把两条轨迹的差别全部归因于 goal feedback。

待证问题因此是：**保留已获支持的 duck，能否用实测剩余距离决定退出步行何时继续、何时进入完整停止，并保持 whole-body/support 连续？** 先获得可执行的连续对照，再问 Linear29 是否保留该能力。只有任务支持先成立，才有可解释的表示学习比较。

## A：先完成离线命令与拼接资格

1. 固定原 goal 与 farther goal、相同 observed map / incoming state / action history。给每个 reference 记录 request、source ancestry、segment、dense indices、时间戳、局部 root / velocity、joint order、support 类型与 validity。检查两种 goal 的 reference 是否在需要继续步行的阶段出现合理差异；改变一个无关标量不算通过。
2. 从已有可执行库标注 approach、duck、exit、stop，列出实际 frame 范围和版本化来源。找不到可重复 locomotion segment 或受支持 seam 就记录缺口；不以循环某个数组或把 clip 拉长充当可执行循环。
3. 使用原 joint、velocity、root、rotation、support 与承诺前缀 gate，先枚举 exit→exit、exit→stop 候选边。当前候选库中的 joint ≤0.10 rad、joint velocity ≤0.50 rad/s、root position ≤0.03 m、root velocity ≤0.15 m/s、rotation ≤0.10 rad 只是在同动作 retiming 中使用的限制；跨 segment 复用是待资格验证的假设。必须报告所有被拒绝的边和 support 无效区间，不修改阈值迎合结果。
4. 同时检查 committed prefix、50 Hz dense 与 10 Hz native horizon、root坐标、q/qdot 一致性以及终端 padding。至少 46 个 dense frames 支撑 0.9 s native horizon。临近 segment 边界不能截短 horizon 后仍宣称接口完整，也不能让 source cursor 覆盖已承诺帧。
5. 用 measured progress / remaining distance / velocity 决定继续还是停止。给 transition、blocked、replan 明确定义；离线无合格边时返回 unsupported，并保留失败原因。这个返回值不是已经验证过的物理安全停止。

输出应是可检查的 segment/edge manifest、共同历史的 reference 差异及拒绝记录。给 continuous 和 Linear29 同一 segment/decision 计划并分别保留正确 source 时钟；之后的自由闭环才允许它们访问各自状态。冻结 Linear29 scale、anchors、joint mapping、root 与所有附加 side channel 成本。重复 segment 的索引与 seam metadata 也要计费。

## B：分开验证参考支持与在线选择

离线完成后再登记 native：原 goal / farther goal × beam / matched clear，先验证 supplied composed continuous-reference support，再验证 public measured-state composition；表示比较继续以 continuous / Linear29 为主。最终执行矩阵、预算、controller version、所有 segment 与 stop 规则须在运行前明确，不在此预支次数。

同一张足够大的 floor 和障碍场景可服务两个 goal；仅改变 requested goal 时，绑定相同 scene 文件及 hash，并核对初态、动力学、action history、RNG。保留旧 screen 作为 development regression。实际 reset pose / speed 的变化另开轴，不把“路线相对固定 reset 转向”改称 reset 多样性。

冻结完整 scorer：全身离开梁、15 tick 恢复、goal050、速度 ≤0.10 m/s、新 50 tick hold、接触与 deadline。到达旧 clip 终点不等于完成新请求。目标方向/长度响应、物理成功及停止条件分别给证据；不能以宽容差内碰巧停住替代距离响应检查。

解释规则：

- supplied composed continuous 也失败：修 segment 支持或执行过渡，不能用其作成功 supervisor。
- supplied composed continuous 成功、public composer 失败：查选择、反馈、承诺与停止时机。
- continuous 成功、Linear29 失败：在匹配进段状态下隔离 range clipping、速度推导、时间重建与 seam 损失，再考虑新 codec。
- 两种表示均完成变化的请求：继续固定它们进行更广任务支持和 learner 效用比较；还没有证明统计等价或通用最优。

## C：低梁与语言接口保持独立

更低的梁需要新的可执行更深 duck 或替代路线。已有候选的包络重叠既可能保守过预测，也可能对应真实接触；原 screen 同时出现两种情况。不能从这些结果事后挑一个 clearance 阈值就宣称安全拒绝，也不能推出 motor 不可能执行任何更低动作。

未来 BFM / VLA / LLM 应提交 goal、约束与终止要求，并读回 measured progress、remaining distance、unsupported / blocked / complete。保真 sidecar 能保存 schema 和解码信息；它不能为动作库补出缺失的 exit/stop 能力。继续将小 LLM 字段保持测试与真实 motion/task 执行分开，待这个连续控制门槛成立后再注册物理语言干预。
