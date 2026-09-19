# 文献复核：动作 tokenizer 应该服务于什么

2026-09-18。定向检索原论文、作者项目及官方代码，复核已有相关文献并补入近期直接竞争工作。不是系统综述，也没有复现这些模型。全文可访问不等于逐字审完所有附录；下面明确本次用于判断的阅读范围。数据集库存仍见 [DATASETS_zh.md](DATASETS_zh.md)，其库存日期不变。

## 1. 对研究定位最有影响的工作

| 原始来源与阅读范围 | 论文中的接口/证据 | 本项目的推论与边界 |
| --- | --- | --- |
| [PASSAGE v1，9 月 16 日](https://arxiv.org/html/2609.18732v1)，§III–IV、接口/评价段落 | Scene-aligned 示范训练局部目标+历史+多层地图的短时 motion planner；perceptive tracker 执行，另有 planner RL 与闭环评价 | 最接近 downstream。应比较连续 chunk 路线；不能把“地图→全身参考→tracker”作为独有创新。其标准不等于我们的 upright/stop profile |
| [TANGO v1，9 月 8 日](https://arxiv.org/html/2609.09158v1)，§3、§4.4、§8.2 | Plan–Edit–Track 合成并筛选动作；RGB/语言/关节状态驱动 action expert。输出关节+base rotation chunk 给 tracker；保留计划/编辑参考为监督，而非直接以实测轨迹替代 | “可执行合成数据+VLA”已有直接路线；需纳入 scene-first expert。论文还比较另一 tracker，因此兼容性本身也要更细地界定 |
| [SceneBot v1](https://arxiv.org/html/2606.27581v1)，§3–4 | 从 retargeted motion 后补 scene-interaction graph，并用 per-link contact 指令跟踪；低层输入仍有 reference | 否定首次 motion→scene 的宽泛定位。主动接触是独立语义；不能把它描述成无参考视觉导航 |
| [SONIC v4，8 月 13 日](https://arxiv.org/html/2511.07820v4)，§3.2、§3.6、部署接口；对照 v3 | 编码器/FSQ/控制 decoder，另有运动重建与输入对齐；VLA 可使用原生 token 接口 | 新 tokenizer 必须与已存在的 native 表示比较；版本化 adapter 比“全模型共享相同 ID”更可信。论文能力不自动属于本机 pinned checkpoint |
| [Perceptive BFM v1](https://arxiv.org/html/2606.08059v1)，§1、teacher/student 与 action alignment 段落 | 保留 raw kinematic reference，以地形观测修正接触、姿态及时序；经过适配参考 teacher、对齐蒸馏和 finetuning | 任务 planner 与 perceptive tracker 解决不同误差，不能假设 tokenizer 必须独自承担所有地形适配 |
| [Perceptive Humanoid Parkour v1](https://arxiv.org/html/2602.15827v1)，方法/训练流程 | Motion matching 组织技能/过渡，privileged experts 向 depth student 蒸馏并作任务训练 | 数据应覆盖 transition；完整技能链比孤立姿态更相关。不把其速度命令接口直接当作 global goal navigation |

这些论文并未使目标失去价值；它们使“再拼一次大管线”的研究定位不够具体。我们的判断是：优先用小型完整任务与简单/原生接口揭示**表示的哪种信息改变了闭环决策**。这是基于文献和本地失败的研究选择，不是文献已经证明的新方法。

## 2. Foundation model、动作词表与压缩不是同一问题

| 来源与本次阅读范围 | 可以借鉴的内容 | 不应外推的结论 |
| --- | --- | --- |
| [BFM v1](https://arxiv.org/html/2509.13780v1)，§IV 控制/mask/CVAE | Masked online distillation 和条件行为分布；不同指定程度的目标控制 | 遮掉我们 tracker 的必需输入不等于训练过的 sparse mode；CVAE 本身不解决场景选择 |
| [BFM-Zero v1](https://arxiv.org/html/2511.04131v1)，摘要/方法概览 | Forward–backward 表示与任务 prompting 是另一种可复用行为学习路线 | 它不是 BFM 的同名实现，task latent 也不是 RVQ motion ID |
| [ScaleBFM v1](https://arxiv.org/html/2607.15163v1)，摘要/架构概览 | 规模化行为建模及架构路线 | 不与 2025 CVAE-BFM 混用；本次没有评估本机可部署性 |
| [HOVER v2](https://arxiv.org/abs/2410.21229v2)，摘要/版本页 | 多控制模式的统一 whole-body policy | 多模式支持需要相应训练和验证，不由 API 命名获得 |
| [FAST v1](https://arxiv.org/html/2501.09747v1)，§IV–V | DCT、量化与 BPE 压缩 action chunks，强调序列预测效率 | 其机器人操作实验不证明适合我们的支撑脚/接触高频信号；低频截断需要执行验证 |
| [MoMask v1](https://arxiv.org/html/2312.00063v1)，方法/评价概览 | 分层 residual quantization 与 masked motion generation | HumanML3D 的 motion-generation 指标不是 humanoid traversal 指标 |
| [T2M-GPT v4](https://arxiv.org/abs/2301.06052v4)，摘要/版本页 | VQ-VAE+GPT 是合理的离散序列对照 | 本仓库 K-means RVQ 失败不代表该神经方法失败，也不代表复现过它 |
| [MotionGPT](https://arxiv.org/abs/2306.14795)，摘要/版本页 | Motion-language 对齐支持把 motion 当序列建模 | 文本对齐不自动保留米制 clearance、gait 或 native control 语义 |
| [SnapMoGen / MoMask++ v2](https://arxiv.org/abs/2507.09122v2)，摘要/数据描述 | 更详细语言、连续长序列与多尺度 token | 可以补语义与过渡数据；仍需 ancestry、retarget 和物理资格 |

本研究不需要把这些架构全部复现才开始。先选与问题匹配的一个 temporal encoder，保留连续 latent 与 rate-matched 简单 codec 控制。若直接预测 native token 或连续 chunk 更好，就让结果改变设计。

## 3. Hindsight 与数据源的证据义务

| 来源与阅读范围 | 与本研究的关系 | 必须补的局部证据 |
| --- | --- | --- |
| [SUMMON / Scene Synthesis from Human Motion](https://arxiv.org/html/2301.01424v1)，方法概览 | 人体动作提供 scene synthesis 约束，已有直接 motion→scene 先例 | 合理场景不等于机器人可执行，也不等于恢复原始人类意图 |
| [LfH-CP v1](https://arxiv.org/html/2509.26513v1)，方法/实验概览 | Critical points 分解动态障碍生成，并评价学到的 planner | 借鉴“关键性”与数据效用；人形全身可执行替代、接触、视野时机需另测 |
| [PHUMA v2](https://arxiv.org/abs/2510.26236v2)，摘要/版本页 | 物理可靠 locomotion 数据与约束 retarget 提供候选来源 | 该数据中的可靠性不能代替本机 teacher、完整 stop 和 ancestry 验证 |

AMASS/BABEL/HumanML3D 与 retargeted collections 有来源联系；不能按数据集名字拆分后就宣称无泄漏。自然 motion 提供姿态协调和时序，不能单独赋予“此时为了避障”的因果语义。主动 support-contact 还需力/接触状态与环境信息。

## 4. 还需要怎样的 deep dive

需要，但应围绕决策而读：

1. **先读接口和执行。** SONIC 的 native FSQ、观测历史、参考时域与动作归一化，和 PASSAGE/TANGO 的 chunk 切换、tracker 反馈；对应 P0/P1。原论文的配置不直接覆盖本机快照。
2. **再读表示损失和预算。** MoMask 的时序编码、FAST 的 action-rate 定义、连续 motion chunk 的可学习性；对应 P2。重点是所有 side channel、预测吞吐和执行损失，非只摘 FID。
3. **再读真实感知。** 横梁可见性、局部地图更新时间、未知空间与记忆；对应 P4。训练时可见标签不代表部署时足够早可观察。
4. **最后扩展 support contacts 与跨 embodiment。** 接触意图、动作适配、可移植状态变量；先明确新的 downstream task 才扩大文献范围。

停止阅读并进入实验的条件：能写出主要 rival explanation、一个强简单比较和各结果如何改变路线。继续增加论文数量无法替代执行证据。

本次定位不依赖某篇摘要的“first”措辞，也不跨论文比较不同 task、预算和成功定义的百分数。未阅读到的附录、未复现的实现与新颖性覆盖仍然是限制；目前不主张 exhaustive novelty。

## 5. 用户指导后的定向补充

- [ActionPiece v1](https://arxiv.org/html/2609.18487v1)：复核 §3–5.1。解码动作空间的物理距离排序 PRC 与受控 VLA 比较已有直接证据；“超越 MSE”不够新。加入几何关系保持基线，检验它与相同来态/场景下可执行选择是否分离。
- [OAT v2](https://arxiv.org/html/2602.04215v2)：复核摘要、§III–IV。压缩、总可解码性与顺序/prefix 设计值得借鉴；能解码不能替代当前支撑状态下的物理资格。
- 小模型的许可与使用模式直接核对官方 [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B)、[Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) 和 [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B) 模型卡；选择及推理范围见[协议](LLM_INTERFACE_PROTOCOL_zh.md)。本次只有 0.6B 进行了合成接口推理，无模型训练。
