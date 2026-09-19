# 面向可泛化人形穿越的动作表示：重新确定研究问题

修订：2026-09-18。依据全部阶段结果报告、公开汇总与关键 run 汇总、相关本地 traversal 项目及本次[文献复核](LITERATURE_REASSESSMENT_20260918_zh.md)。初次重审没有执行新仿真或训练。后续用户明确要求推进后，已单独登记并完成 [continuous/Linear29 完整参考任务 pilot](COMPLETE_TASK_RESULTS_zh.md)：各 4/4；没有改变旧 native 注册或启动训练。本次补入[用户指导采用记录](RESEARCH_GUIDANCE_20260918_zh.md)及[小 LLM 离线协议](LLM_INTERFACE_PROTOCOL_zh.md)；合成接口推理单独登记，不属于物理证据。[旧计划](https://github.com/linjiw/hindsight-motion-research/blob/fc85b01082c703fa31b3c7776152677adbee7c3b/docs/RESEARCH_PLAN_zh.md)保留历史语境。

## 1. 判断：目标保留，研究重心需要移动

目标仍然值得做：让人形机器人根据目标、当前场景观测和自身状态，自主协调身体穿越杂乱环境；动作表示应支持未来 BFM、VLA 或语言任务接口。现在没有证据证明某一种 tokenizer 是最有希望的最终答案。

**中心问题：在固定控制器、因果观测、训练数据和学习预算下，保留支撑转换与避障时序的短时动作表示，能否比简单连续表示更好地保留从当前实际状态出发仍有效的选择，并改善未见场景中的完整任务成功率？**

明确反假设：简单连续/native 接口已足够，主要瓶颈在 supervisor、root 规划、切换支持或闭环决策。先识别瓶颈，再投入新 codec。

“好的 tokenizer”首先是有用的动作接口，可以是连续、离散或混合表示。新颖性不能仅来自 motion→scene、身体分流、加 contact loss、接入 LLM 或规划器+tracker。近期工作已有直接先例。候选贡献是：**用执行后的决策保持、过渡恢复和闭环效用选择表示，并证明相对简单表示的收益及成本**。这个贡献尚待验证。

本仓库承担表示与数据诊断；现有 goal-conditioned traversal 项目承担完整控制任务。两者共享任务/接口规范，分别保留数据、预算和结果，避免再建立一个互不兼容的“BFM”。

## 2. 证据到底支持什么

| 已测事实 | 解释与设计影响 |
| --- | --- |
| Pilot 的 root+token 未稳定超过 root；粗几何 26 个见证仅 3 个通过精细检查 | 码不同、障碍可放、排序高，都不证明有用行为。功能标签来自执行和控制干预。[报告](RESULTS_zh.md) |
| Acquisition：120 episodes，5 编辑对/3 来源组，10/15 完整面板；3 对全部合格 | 已有收臂和蹲身+弯腰的局部功能证据；第二类尚无跨源完整复现。[报告](SECOND_FAMILY_AND_TOKENS_zh.md) |
| Decoder study：RVQ 三方案合计 0/54；Linear29 为 17/18 | 未达 fidelity 与任务资格，不是全部跌倒。10 Hz 连续 knot 必须是强基线。[报告](DECODER_EXECUTION_zh.md) |
| 最新重复：body9 0/18、平滑 0/18、leg12 15/18、Linear29 16/18、continuous 18/18 | 腿重建干预有局部作用；不能据此识别普适接缝机制。[报告](TOKEN_MECHANISM_RESULTS_zh.md) |
| leg12 保留六个选定 arm/beam 面板，却不改变该组 clearance 分数 | 上身几何和动态执行可解耦，不能用 clearance MAE/MPJPE 单独挑冠军 |
| 新 carrier 原始/tuck 各 3/3，但固定网格 0/145 场景合格 | 可跟踪不保证存在有用对比；这是几何拒绝，不是 145 次物理失败。[报告](CARRIER_SCENE_RESULTS_zh.md) |
| 累计 440 记录预检 + 312 main；另有 144 失败基础设施 slot 无 episode | 312 = 120 acquisition + 192 representation repeats；重复不增加独立源。本仓库未训练导航学生 |

相邻 traversal 项目 9 月 18 日复核也指出：熟悉布局成功、teacher 支持和低离线误差，尚未转成可靠的布局变化与恢复/停止。本次只读其记录；不同任务分数**不并入本仓库**。版本与范围见[同步记录](REVIEW_SYNC_20260918.md)。

成本也需要重新判断：body9+leg12 的关节逻辑码率是 2,660 bit/s，Linear29 是 3,480；共同 root 为 11,200。含 root 后是 **13,860 对 14,680 bit/s，仅减少约 5.6%**，还未计原始进入段、模型及容器。较复杂 codec 需要通过预测难度、延迟或下游数据效率赚取价值。

## 3. 从最终任务反推表示

第一项完整任务：**接近 → 蹲身通过横梁 → 全身离开 → 恢复直立 → 到目标持续停止**。窄通道收臂提供 root 接近而上身不同的补充诊断。先用声明完整地图和定位假设的场景，再换成因果深度/LiDAR 与地图记忆。

“灵巧身体穿越”先解释为协调躯干、手臂、脚和时机。未来主动手/臂支撑另需接触许可、接触时序、力和恢复协议；物体操作是后续扩展。现在 contact-free 结果不能升级为 contact-rich 能力。

旧 scorer 只要求移动到达；新任务另行版本化停止时间、速度、姿态及 deadline。任务成功要求从 reset 开始的因果闭环，不能靠隐藏 clip、phase 或 teacher prefix。Reference fidelity 适合 codec 诊断；自主任务可以采用不同的成功动作，不能用隐藏示范误差惩罚正确的新解。

必要基线：普通走路、**保守蹲行并在目标附近恢复直立/停止**、使用全身包络/障碍后缘/延迟余量的几何规则，以及合格参考 composer。不能只与注定无法满足直立终止的“永远蹲着”比较。旧面板证明调整有用，**未证明必须学习选择**：若一直收臂在所有条件都成功，场景策略只能通过预先定义的时间/能耗/自然性等成本赚取优势。不能事后修改成功定义让常量策略失败。

## 4. 共享接口，而不是万能整数词表

```text
LLM / VLM：目标、对象指代、约束、终止要求
                         ↓
当前观测 + 机器人/动作历史 → 场景记忆 → 局部行为规划器
                                         ↓
                    短时全身参考 / 连续 latent / 离散+残差
                                         ↓
                    版本化 adapter → motor / tracker → 动作
                                         ↑                  ↓
                       进度、阻塞、置信度、实际终止 ← 测量反馈
仅训练：人类动作、完整未来、teacher、反事实执行、关系标签
```

先把**可检查的短时参考 chunk**作为组件交换格式：局部 root 增量/速度、关节或关键 link 轨迹、支撑/接触 mask、时基、有效范围与终止语义。内部可压缩，对外保留计量单位及 embodiment/decoder 身份。[接口设计](MOTION_INTERFACE_V2.md)是草案，不是假称已集成的 API。

两条路线需要比较：

1. **参考路径，优先任务基线：** goal+scene+history → chunk → 已验证 reference encoder/tracker。Linear29 是最小可解释候选，随后比较 temporal encoder、FSQ/RVQ 与连续 latent。
2. **原生 motor 路径，必要对照：** goal+scene+history → checkpoint 对应 SONIC 64D token → 固定 decoder。少一层 codec，但 portability 受 checkpoint/normalization 限制。

共享接口不要求共享 latent。BFM 接收带可用性 mask 的目标/身体约束；VLA 可预测连续 chunk 或 motor token；LLM 调用具名技能/子目标并读取完成状态。文本不必输出每个关节，离散码也不会自动获得语义。

人类动作提供协调、时序、多模态先验；机器人动作提供 embodiment 特定的几何与执行标签。保留两层及映射，不能只规范化身高就宣称跨机器人通用。Contact 区分 measured/estimated/desired；pose 不直接提供支撑力，也不能恢复唯一原环境或人类意图。

## 5. 最小、可证伪的实验顺序

以下是**拟议工作包**，不新增 native 授权或自动启动。每项运行前绑定来源、checkpoint/代码哈希、预算、固定比较及停止规则。

### P0：接口与资格核对

从已有记录核对 root/joint 顺序、四元数、时间戳、decoder history、native 64D 值域/量化路径及进入段成本。当前 hook 记录 decoder 浮点输入，不等于实测 entropy-coded 词表；源码支持 FSQ 不能替代 pinned checkpoint 配置核验。先序列化/离线一致性，再另注册物理回放。

整理人物/表演、镜像、重定向、切窗和编辑祖先。900 动作是候选库存，不是 900 可执行任务。输出 capability/interface matrix：哪些命令在什么状态、频率和观测下实际通过。

### P1：完整任务的可执行基线

**已完成第一行 pilot：continuous 4/4，Linear29+两帧 reset anchor 4/4，四个配对初态/历史/动力学完全匹配。** 使用两个既有 clip、clear/beam、冻结 goal050/recovery/stop profile；有完整未来参考和 root 辅助，不是自主任务。详细范围、wrist clipping、成本与下一步见[结果](COMPLETE_TASK_RESULTS_zh.md)及[协议](COMPLETE_TASK_PROTOCOL.md)。当前主优先级移到第二行的实际来态 continuation/switching，暂不启动新 codec 训练。

**第二行首个子面板已实现并登记，但未获得物理证据。** 两个 beam task × pre-entry/entry/exit/pre-hold × continuous/Linear29，共 16 格；共同 prefix、history/RNG 与 native adapter 的审计已实现。300 s 资源等待超时，0 attempts、16 unrun；不是 16 次行为失败。离线发现某些 handoff 的膝参考变化也明显，不能把未来退化全归为 wrist clipping。见[执行状态与诊断](CONTINUATION_RESULTS_zh.md)。下一项仍是资源可用后新建关联的 admission packet 执行这八个配对；同相位无扰动成功也不替代新 chunk 选择、扰动恢复和 composer。

对齐相邻项目的 task-aware composer：按当前位姿和场景选取并衔接 approach/duck/exit/stop。先用 continuous 与 Linear29 做[两种表示×三种执行条件](RESEARCH_GUIDANCE_20260918_zh.md)矩阵：完整正确参考、真实相同来态的合格后续 chunk、因果 composer 从 reset 闭环。Native 先做同参考/同历史接口 parity，后作独立路线对照。

横梁位置、高度、长度与初速度独立变化；新 task profile 分开全身离开、恢复、目标误差、持续停止和超时。姿态含骨盆高度/腿伸展，不能只看躯干角度。第三行共享因果生成的 root，计入成本；不提供隐藏未来或原始进入段。真实 snapshot 包含速度、支撑、控制器与已执行动作历史。共同来态比较机制；各自访问状态衡量实际效用。

- Continuous 也失败：查任务、teacher、过渡支持。
- Continuous 成功而 codec 失败：表示损失值得研究。
- 提供正确 chunk 成功，闭环 composer 失败：查决策、重规划、可观察性。

CMU 固定 wide/tuck 后续仍是独立 acquisition 分支：原登记最多六个预检，合格后才几何/干预，资源等待已经结束。它不再阻挡整个表示研究；本次改计划不自动恢复执行。

### P0-L：小型 LLM 的信息保持分支

先执行不需要 native 的 L0 合成接口测试：Qwen3-0.6B、无 LLM 规则基线、完整记录 relay 与 ID+保真 sidecar。测任务/动作字段保持、错误选择、未知/不支持请求与成本；[首轮报告](LLM_INTERFACE_RESULTS_zh.md)与真实 motion/物理结果严格分开。Qwen3-1.7B 是后续容量对照，尚未运行。

随后 L1 才用本地真实动作比较原始→codec→LLM→解码，区分正确选择下的信息传递与模型自己的选择；L2 在完整任务门槛通过后固定 controller/history/scorer 执行。不把语法正确、复制 ID 或 sidecar 的保真当作 LLM 掌握运动语义。[完整协议与复现](LLM_INTERFACE_PROTOCOL_zh.md)。

### P2：控制器感知的表示比较

冻结支持任务、完整过渡和 source split。首个学习候选为全身联合、来态条件化的连续 temporal latent；先证明学习压缩的效用，再加量化。保留 continuous、Linear29/等总预算自适应 scalar 或 spline、body9+leg12 与 native 路线。同架构普通重建/执行相关训练对照；坐标、锚定、速度与 prefix 处理对所有方法相同。ActionPiece 式几何关系保持是必要邻近基线；确需离散时再加入 FAST/OAT 式候选。

候选损失：位置/速度、支撑脚误差、身体表面/间隙、chunk 接缝、受支持 native action 一致性；接触/关系各有 mask。身体分流只是消融假设，必须保留跨部位同步，独立 limb 码流拼接可能不受支持。

分开三个问题：**固定 source 重建回放；实际 incoming state 下切换/恢复；因果策略预测表示的完整任务**。未来可作为离线编码/训练 target；actor 只能看过去，预测未来不等于读取未来。

优先报告固定合格动作库/控制器下独立未见场景的完整任务差异；未见动作 ancestry 是另一个更强结论。报告对照退化、执行后决策保持、命令响应、延迟与全信息成本。离线误差和支持范围分开。若只赢 MPJPE 而输任务，或节省很小且无学习收益，保留简单方案。更换 decoder 后需要 adapter 再训练，不称 zero-shot。

### P3：小型 downstream 效用研究

有完整 supervisor 后，训练 history+scene+goal learner。固定通过资格的 motor 路线，用相同数据/容量/优化预算比较两种最有希望的表示；不要同时更换表示、tracker、数据和传感器。

另做数据实验：简单可行配景、root hindsight、full-body verified contrast、scene-first Plan–Edit–Track-style expert。共享 motion bank、查询预算和 learner；报告等样本与等总获取成本，包含失败、过滤及回放。旧结果不回填新 held-out 集。

同时报告预定全任务分布的成功/支持覆盖/未运行，以及 continuous 合格子集的 codec 保持率。独立场景先于 motion 采样，分别定义 ancestry、障碍位置/尺寸/组合、初态/速度 holdout。Optimizer seeds 与 scene/source clusters 分开，报告配对收益及退化；pilot 估计方差后注册主实验规模。当前三源 development 不支持泛化置信区间。

### P4：感知、语言与更大范围

1. 保留动作 API，把完整地图替换为因果深度/LiDAR、三维/多层局部地图及记忆。记录 calibration、延迟、unknown；测横梁离开视野后仍需低姿态的情况。
2. Scene-goal 控制成立后，比较结构化目标与语言解析的同一目标；同话不同场景、同场景不同指令、未见组合，避免文本记住 clip。
3. 增加 route/subgoal planner、重复障碍和替代路线；global 导航需要定位/记忆及 blocked/replan 反馈。
4. 主动手/臂支撑另定义 contact-aware scorer；硬件与跨 embodiment 各有独立证据义务。

## 6. 推荐与放弃条件

**最有根据的路线：完整 traversal 基线 → 表示执行与切换比较 → 固定 learner 效用 → 感知/语言扩展。** Hindsight scene 是构造 informative tests 与数据的手段，不必成为唯一入口。

保留 tokenizer 作为研究主题，但允许实验回答“不需要新离散 codec”“native token 更合适”或“瓶颈在 controller/观测”。若无法超过简单 composer/持续蹲身，只报告机制和接口；获取比较为 null，则保留系统与负结果，不用更大模型替代问题定位。

下一份主要物理交付是“完整任务支持与表示瓶颈报告”，含冻结 task profile、因果 composer 和 2×3 矩阵。小 LLM 报告作为独立接口附件，不替代该交付。在同一个完整、可观察任务上说明：**保留哪些信息，才让 robot 更容易学会正确且可执行的选择。**
