# 第二类穿越机制通过验证；完成 clearance-aware motion token 对照

## 本轮完成了什么

新增 **36 次动作资格预检 + 24 次场景干预**，并完成六种 motion 表示在固定场景候选上的几何对照。现在有两类经过完整干预验证的动作：收臂过窄通道，以及**小幅下蹲结合弯腰穿过横梁**。

累计主实验 120/480 个 episode，5 个编辑动作对、3 个源分组；3 个动作对在全部三个扰动面板中合格，累计 10/15 个面板合格。新增机制来自 KIT/205，尚未在另一个源分组上完整复现。

## 1. 用可重复执行的编辑修复第二类机制

上一轮 6 cm pelvis 下移在 KIT/9 上接近 10 cm tracking 门槛。本轮保留两个原下蹲 anchor，增加五个候选配方：4 cm pelvis 下移并将 waist pitch 平滑变为 0.35 rad，或保持 root/腿部参考并将 waist pitch 平滑变为 0.50 rad。

所有编辑保留共同进入/退出段。pelvis 下移通过腿部 IK 保持脚部世界位置和朝向；单独的 waist 编辑不改 root 或腿关节。未改变 teacher、控制/物理步长或成功门槛。

原计划最多七对 × 两种 continuation × 三个初始扰动，共 42 次预检。KIT/359 的组合编辑违反脚部保持误差限，在构造阶段被拒绝，因此实际执行六对、36 个 episode。准备程序有一次时间戳参数重复错误，在首次 native 启动前修复并记录；没有消耗或隐藏仿真尝试。

| 配方 / 源 | 编辑动作通过 | 直立对照通过 | 三个共同初始状态匹配 |
| --- | ---: | ---: | --- |
| 原 6 cm 下蹲 / KIT/205 | 3/3 | 3/3 | 是 |
| 原 6 cm 下蹲 / KIT/9 | 0/3 | 3/3 | 是 |
| 4 cm 下蹲 + 0.35 rad 弯腰 / KIT/205 | 3/3 | 3/3 | 是 |
| 4 cm 下蹲 + 0.35 rad 弯腰 / KIT/9 | 3/3 | 3/3 | 是 |
| 单独 0.50 rad 弯腰 / KIT/205 | 3/3 | 3/3 | 是 |
| 单独 0.50 rad 弯腰 / KIT/9 | 3/3 | 3/3 | 是 |

该比较说明组合编辑和弯腰编辑在这次重复预检中有执行支持。它不单独识别组合编辑中的哪一项导致改善，也不证明任意幅度的弯腰都可执行。

本机名称匹配的 squat/bending 片段大多平移很少；GRAB 的 duck 文件名也不能直接作为 duck-under 动作标签。先前的 sneak 片段已经未通过严格 tracking，因此本轮选择明确控制的配方，未将名称当作自然穿越能力的证据。

## 2. Proposer 同时检查三个实测轨迹，再做物理干预

只有通过全部预检的五个动作对进入横梁搜索。每对 208 个候选，共 **1,040 个最终参数候选**；每个候选的高度搜索还包括 16 次距离评估，不把这些内部查询藏在最终候选数中。

接受规则保持为：目标动作的全身碰撞外包络在**每个**实测扰动下都留出至少 3 cm 采样分离下界；直立动作在**每个**扰动下都存在至少 1 cm 的解析实体内部重叠证据。不是从三个运行中挑出最有利的一次。

仅 KIT/205 的组合编辑产生了合格场景，13/208 个候选通过。其他四对全部保留为几何拒绝。按预定的最差侧余量选取一个场景：

- 横梁底面高度 1.28693 m，沿行进方向厚度 8 cm，跨度 1.8 m，高度 10 cm，配两侧支柱。
- 全部目标轨迹的最小采样分离下界 3.058 cm。
- 三次直立轨迹的内部重叠证据分别约 1.025、1.038、1.010 cm。

这仍是很窄的几何余量，不能当作一个连续可行区间或现实机器人安全保证。最终使用真实 native 接触与任务结果验证。

### 新增 24 次主实验结果

| 场景 | 组合下蹲/弯腰通过 | 直立通过 |
| --- | ---: | ---: |
| 关键横梁 | 3/3 | 0/3 |
| 横梁抬高 30 cm | 3/3 | 3/3 |
| 移除横梁和支柱 | 3/3 | 3/3 |
| 整个结构横移 2 m | 3/3 | 3/3 |

**3/3 个完整面板通过关键性审计。** 组合动作的关键场景身体 tracking 误差为 5.27–5.68 cm，终点误差 3.97–5.42 cm，障碍法向接触力 0 N。

直立动作在三个关键运行中均由 `torso_link` 上的碰撞体接触横梁，峰值为 242.9、187.4、204.9 N，首次接触发生在 1.635–1.660 s。它们仍然到达目标，失败项是障碍接触；不能把结果写成“横梁阻止了直立机器人到达”。对未来 traversal 研究，这里的效用是**无接触穿越**。

三个初始扰动仍为 0、−1.5、+1.5 cm；所有控制通过。跨环境障碍接触为 0 N。依然仅验证移动到达，不含停止/站稳。

## 3. Motion token：固定候选、明确码率的对照

### 实验设计

在此前四个动作对的 **643 个固定场景候选**上评估六种表示；每个候选对应两个 continuation，共 1,286 个 motion–scene 几何评估。场景和评价门槛在比较前固定，不用本轮横梁物理结果挑选 tokenizer。

新残差模型只使用原训练划分中的 605 条动作、137 个源分组、23,548 个 10 Hz knot，排除当前物理实验的 KIT/205、KIT/9、KIT/317。旧 RVQ codebook 维持原样，其历史训练数据可能包含这些源分组，因此本实验不能宣称未见源泛化。

各方法保留相同的全速 root side channel。五帧一个 10 Hz knot，标量使用训练集范围校准的 12-bit 量化；本次评估没有标量 clipping。

- **RVQ**：原有两个 128-entry codebook。
- **RVQ + body9**：增加 waist pitch 和双侧 shoulder pitch/roll/yaw、elbow 的九个残差通道。通道按身体结构指定，不按场景评分选择。
- **RVQ + PCA9**：相同额外码率，增加训练残差的九个 PCA 系数。
- **Linear29**：29 个关节的 10 Hz 量化值，线性插值到 50 Hz。
- 完整连续参考作为几何对照；root + 共同初始关节姿态保持作为信息基线，后者不是物理合格的替代控制器。

### 结果

| 表示 | 关节信息逻辑码率 | clearance 下界平均绝对误差 | 错误接受候选 | 漏掉参考接受候选 |
| --- | ---: | ---: | ---: | ---: |
| RVQ | 140 bit/s | 3.592 cm | 1 | 109 |
| RVQ + PCA9 | 1,220 bit/s | 3.280 cm | 6 | 108 |
| RVQ + body9 | 1,220 bit/s | 1.095 cm | 7 | 49 |
| Linear29 | 3,480 bit/s | 0.0565 cm | 2 | 1 |
| 连续参考 | 46,400 bit/s | 0 | 0 | 0 |

共有 111 个候选被连续参考几何接受。表中的错误接受/漏掉都是**相对连续参考几何**，不是相对物理接触真值。连续参考与实际 teacher 执行也有差异，某些物理选定场景并不被参考轨迹的同一几何规则接受。

body9 相比同码率 PCA9，更好地保留了本组避障决策；但仍有七个错误接受候选，且旧下蹲例子的判定仍丢失。不能仅凭平均误差降低就取消后续几何/物理检查。root + 初始姿态基线漏掉全部 88 个 arm 候选，保留了 23 个 root 高度已解释的 duck 候选，说明不同机制依赖的信息不同。

简单的 Linear29 基线最好：643 个 pair–scene 判定中只翻转 3 个。它的关节码率高于两个残差方案。**每个方法另有共同的 11,200 bit/s root side channel**；以上不是完整系统或磁盘文件的压缩比，NPZ 也不是实际 bit-packed codec。训练后的 codebook、PCA 和量化范围开销均未计入表内。

本轮没有执行解码后的运动。结果支持把低速连续关节 token 作为下一阶段强基线，并测试更精确的身体通道，而不是现在宣称已经获得可直接驱动 robot 的离散行为词汇。10 Hz 中心采样使用未来运动信息，适合作为离线 proposer 输入或训练目标，不是因果 student 观测。

## 4. 实际数据与验证

新的统一索引为 `runs/critical_dataset_20260915_v3/development_episodes.jsonl`：

- 120 个主实验 episode，24,000 行控制记录。
- 91 个 scene-pass episode，18,200 行有支持的 motor imitation 目标。
- Actor / teacher-only / target 文件分离，逐文件 SHA-256；失败保留，关系标签与单次 imitation support 分开。
- 本轮新增 36 个预检不混入主数据集；累计预检 134 次，主实验 120 次，共 254 个 native episode。
- 18 项测试通过；新增主实验数据审计通过。token 符号、重建、固定候选判定和索引还做了单独复核。

两类机制都成立，但完整复现的独立源分组仍只有 KIT/205、KIT/9，不能用 24,000 行当作 24,000 个独立训练任务。尚未训练 BFM 或验证导航学生的收益。

## 5. 由本轮证据决定的下一步

1. **跨源复现第二类机制。** 寻找更多有执行支持的组合动作。保留当前几何拒绝；区分真实空间不足与碰撞外包络过于保守。若采用更精确的 native primitive 距离，应先单独验证，再注册新的 acquisition 对照。
2. **解码后的物理资格。** 固定 Linear29、body9 和同码率 PCA9，在相同场景和共同进入段上做 tracking/接触对照。未经此步，不能将几何表示的改进当作 motor 接口的改进。
3. **冻结 proposer 和 student 的评估来源。** 继续增加独立动作对；对 root、连续全身、离散+residual proposer 使用相同的候选/物理查询预算，并保留 no-scene/reject 输出。
4. **再做同学习器的数据效用试验。** scene-first 人工场景作为独立评价，比较用普通 motion、随机场景、关键场景训练的同一个 student。控制场景的多种可行 continuation 应保留多模态目标。text2nav 排在已知地图/目标导航之后。

主实验剩余 360 次。上一轮追加预检预算用了 86/96 个 episode、4/4 次启动；剩余十个 episode 不自动授权第五次启动。下一次预检需在执行前记录新的明确预算，不通过静默重跑填补成功样本。

## 复核入口

- `runs/robust_duck_preflight_20260915_v1_construction/`：配方、IK 拒绝、参考动作。
- `runs/robust_duck_preflight_20260915_v1/`：36 次重复预检及共同初始状态审计。
- `runs/robust_beam_proposals_20260915_v1/`：全部 1,040 个候选与选择记录。
- `runs/robust_beam_interventions_20260915_v1/`：24 次物理干预与逐身体接触。
- `runs/clearance_tokens_20260915_v1/`：预先固定的协议、训练清单、模型、解码数组、全部候选评分。
- `artifacts/second_family_viewer.html`：五个动作对的实测回放。
- `artifacts/clearance_token_comparison.png`、`.pdf`：token 对照图。

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=src:/home/linjiw/groot-wbc-sonic-sim-trackb
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
"$RESEARCH_PY" -m pytest -q tests
"$RESEARCH_PY" -m hindsight_motion.robust_duck analyze runs/robust_duck_preflight_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.batch_audit analyze runs/robust_beam_interventions_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.second_family_report
```
