# 数据源与 tokenizer 选择

核验日期：2026-09-15。下面按研究用途选择主流基础数据与近期数据，不把规模、下载量或发布时间当作“最火”的统一排名。

## 1. 本机真正找到的数据

| 本地数据 | 已核实内容 | 本轮用途 |
| --- | --- | --- |
| `/home/linjiw/dataset/amass-licensed/extracted/smplh-g` | 280 个原始 NPZ：ACCAD 252、HumanEva 28。样本包含 SMPL+H poses、trans、betas、dmpls、gender、mocap_framerate | 核对人体数据格式与来源；本轮未重新做人体重定向 |
| `/home/linjiw/dataset/amass-licensed/retargeted-candidates` | 900 个 G1 NPY；样本为 `[T,36]`：root xyz、xyzw 四元数、29 个关节角 | 核对已有重定向来源 |
| `/home/linjiw/dataset/amass-licensed/phase-g-bank-rebuilt-fmt8` | 对应的 900 个 G1 NPZ；29 个关节角/速度、30 个 link 的世界位置/四元数/速度；50 Hz | **本轮实际处理的全部实验输入** |
| `/home/linjiw/groot-wbc-sonic-sim-trackb/data/smpl_filtered` | 131,455 个 `.pkl`，约 32.20 GB；抽查使用 joblib 解压，包含 pose_aa `[T,72]`、transl `[T,3]`、smpl_joints `[T,24,3]`、fps，以及原始姿态/帧率 | 后续规模扩展；目前只完成文件统计与单样本格式核验 |
| `/home/linjiw/lucid/GR00T-WholeBodyControl/data/motion_lib_bones_seed/robot_filtered` | 512 个 G1 `.pkl`，约 33.4 MB；抽查嵌套 motion 字典包含 root_trans_offset、pose_aa `[T,30,3]`、dof `[T,29]`、root_rot、smpl_joints、fps | 后续与人体版本配对、身体部位表示和 G1 数据接口实验 |
| `/home/linjiw/research-data/m2s-hindsight-dataset-v1-20260911` | 已有 120-motion 场景数据、viewer、scene/task 导出与历史记录 | 后续接口复用；没有把这批既有合成动作计入新 mocap 结果 |

900 个机器人 NPY 与 900 个 NPZ 是同一批动作的不同表示，不能算成 1,800 次表演。280 个原始动作与重定向库也有来源重叠。131k SMPL 与 BONES-SEED G1 的映射必须由 metadata 确认，不能当作独立测试人群。

实际实验库覆盖 14 个来源目录，包括 KIT、CMU、GRAB、BMLmovi 等。它是以 AMASS 来源为主的既有重定向库，不能把其中每个来源都称作新采集的 AMASS 数据。具体分布见 pilot 的 `aggregate.json`。G1 原始 NPY 的四元数顺序与格式已对照 [retarget 数据卡](https://huggingface.co/datasets/fleaven/Retargeted_AMASS_for_robotics)；本地 NPZ 为 **wxyz**，不能直接混用。

本地搜索没有确认完整的 BABEL、HumanML3D、LAFAN1 或 BONES-SEED metadata 安装；这不等于证明机器其他位置绝对没有。当前已有数据足以开展离线试验。源动作留在本地，发布时采用源索引、场景增量、转换代码和许可允许的派生内容。

## 2. 推荐的数据组合及表示

| 数据 | 官方资料核实的内容 | 对本研究的价值与 tokenizer 接口 |
| --- | --- | --- |
| AMASS + BABEL | AMASS 提供统一人体模型表示；BABEL 为 AMASS 动作提供动作语义与时间标注，两者不是独立采集的两套库。[AMASS](https://amass.is.tue.mpg.de/)、[BABEL](https://babel.is.tue.mpg.de/) | 人体模型 FK → 世界关节/表面；BABEL 做事件语义对齐。保留来源、体型与模型版本 |
| LAFAN1 | BVH 骨架序列，含 locomotion、obstacles、crouch/crawl 等动作主题，官方代码包含 FK 和读取工具。[官方仓库](https://github.com/ubisoft/ubisoft-laforge-animation-dataset) | 少量仔细分析的跨步/蹲行素材；BVH FK → 部位轨迹。主题“obstacles”不等于有精确场景几何 |
| HumanML3D | 14,616 段动作、44,970 个描述，20 Hz，22 关节及处理后的运动特征；与 AMASS/KIT 有来源联系。[官方仓库](https://github.com/EricGuo5513/HumanML3D) | 动作—语言与现有 tokenizer 的基线；必须保留或正确恢复米制 root 路径 |
| BONES-SEED | 数据卡列出 142,220 段，含 71,132 原始与 71,088 镜像，约 288 小时；SOMA BVH、G1 CSV、文本和时间分段。[官方数据卡](https://huggingface.co/datasets/bones-studio/seed) | **本机扩展优先项**；用匹配 metadata 联接人体/G1/文本，多尺度 token；镜像和原始动作同组 |
| PHUMA | 最新 v2 标题为 *Physically Reliable Humanoid Locomotion Dataset*，2026-06-04 修订；73 小时，物理筛选与约束重定向。[论文](https://arxiv.org/abs/2510.26236) | G1 动作质量和执行验证的补充来源；接入时核查与 AMASS 等库的源动作重叠。不要沿用设计稿中旧版标题/数量口径而不核对 |
| Motion-X / Motion-X++ | Motion-X 提供大规模 SMPL-X 全身动作与文本；后续版本扩展配对模态。[官方仓库](https://github.com/IDEA-Research/Motion-X) | 语义和上肢动作扩展；光学动捕、视频恢复数据分层评估，身体/手部可分码流，面部暂不参与导航 |
| SnapMoGen | 20k 片段、44 小时、122k 详细文本，保留长序列连续关系；MoMask++ 使用多尺度 token。[论文](https://arxiv.org/abs/2507.09122) | 适合你提出的“完整句子式动作过程”和细粒度事件；来源序列先划分，再切窗 |

第一优先级是现有 G1 库的身体几何与动作资格核验，然后接入 512 G1 / 131k SMPL；缺少可靠源分组、时间标签或可执行性时，不急于扩大训练集。

## 3. 实际实现的 token 与未来的神经 tokenizer

### 已完成的可复现实验

每个 token 表示连续 5 帧、29 关节角，即 50 Hz 下的 0.1 秒动作块。训练集有 632 个动作，拟合使用最多 20,000 个训练块；单层 128 个码字，第二层量化第一层残差。root 世界位置和四元数作为共同连续旁路保留。码本只用训练来源分组学习。

输出包含：离散码、原始文件 SHA、动作起止帧、真实帧率、末端速度、旁路字段说明。`<END>` 不是停下标签。事件层记录分段、骨盆 yaw 变化、躯干相对骨盆 yaw、行进方向与身体朝向差、手间距、左右脚高度；允许并行动作描述。当前 turn 标签由骨盆朝向变化触发，不能直接解释为路径曲率事件；脚高度是 link 原点的高度，不是鞋底净空或真实接触力。

当前代码是 **K-means VQ / RVQ 基线**，没有训练神经 VQ-VAE，也没有自然语言对齐。小评分器收到四个时间区间的码频率；它保留粗顺序，丢失区间内部的精确顺序。

### 后续建议的三层接口

```text
Motion segment
  1. discrete motion codes: pelvis/torso, left/right arm, left/right leg
  2. interpretable events: interval, translation, facing, twist, clearance cues
  3. continuous geometry: root transform, robot geometry identity, swept-body reference
```

下一版比较 temporal VQ-VAE、RVQ，以及姿态/速度或身体部位分流的码本；可借用 [T2M-GPT](https://github.com/Mael-zys/T2M-GPT)、[MoMask](https://github.com/EricGuo5513/momask-codes) 和 [MotionGPT](https://arxiv.org/abs/2306.14795) 的公开表示方法。普通整数码需要语义对齐，语言模型不会天然懂得 `<motion_173>`。

重建损失至少包括 root 路径与朝向、关节/表面位置、速度、脚接触估计和关键身体表面间距。使用训练集的独立障碍探针计算 clearance loss；测试探针另行冻结。评价同时报告重建误差、碰撞判断翻转、false-safe、码率和连续旁路开销。

理论上一个 128 码字索引需要 7 bit，两层为 14 bit/0.1 秒，关节码约 140 bit/s；这**不包括** root 连续旁路、码本、事件、几何索引或容器开销，不是本次 JSON/NPZ 文件的实测压缩率。
