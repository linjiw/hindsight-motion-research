# 从可跟踪 carrier 到关键场景：CMU/107 的首次 acquisition 检验

**已完成的原始动作／收臂比较没有产生可进入仿真的场景：0/145。**
这次结果区分了两个条件：原始 carrier 和收臂版本都能被 teacher 跟踪，并不自动保证它们能在同一障碍下形成经过几何支持的行为选择。

[协议](CARRIER_SCENE_PROTOCOL.md) · [原始比较登记](../configs/carrier_scene_v1.plan.json) · [汇总](../results/carrier_scene.json) · [结果图](../artifacts/carrier_scene_geometry.png)

## 1. 已完成的比较

复用此前 CMU/107 `carrier00` 的原始动作和收臂动作，各三个已执行的空场景扰动。两者此前均为 3/3 合格。本轮没有修改这些参考动作，没有重新拟合 codebook，也没有放宽 3 cm 正例间隙或 1 cm 负例内球重叠门槛。

在原有五个放置时刻和 29 个门宽组成的 145 个候选上，对每个动作的全部 200 帧进行检查。一个场景必须在所有三个扰动中满足收臂全身外包络间隙、原始手臂解析几何内球重叠，以及 relaxed/displaced 控制的两种动作间隙。removed 控制没有障碍。

| 几何条件 | 满足条件的候选数 |
| --- | ---: |
| 收臂动作最差扰动间隙 ≥3 cm | 49/145 |
| 原始手臂最差扰动内球重叠 ≥1 cm | 27/145 |
| 同时满足上述两个 critical 条件 | 0/145 |
| 两种非空控制、两种动作、全部扰动的间隙 ≥3 cm | 143/145 |
| 满足全部 admission 条件 | **0/145** |

各行是重叠筛选条件，不是互斥失败类型，不能将计数相加。145 个场景同源且高度相关，不是 145 个独立任务。

最佳 critical slack 仍为 **−3.11 cm**。它对应第 130 帧、0.58 m 门宽：收臂动作最差间隙下界为 −0.11 cm，而原始手臂最差内球距离为 +1.71 cm，未达到所需的 −1 cm 内球距离。这不是一个已经测得碰撞的失败穿越；它是未通过保守几何证据门槛的候选。

所有候选及各扰动数值保存在本地 `runs/carrier_scene_proposals_20260916_v1/`，包括登记副本、代码快照和输入哈希。本轮按登记规则停止，没有额外搜索，也没有将未通过的候选送入仿真。

## 2. 结论的边界

结果只支持：**现有原始／收臂对在该固定 portal 网格及几何检验下没有合格的对比场景。**

它不证明任意障碍均无效。外包络间隙是保守下界；内球没有重叠也不证明整个解析碰撞体没有接触。不同障碍形状、位置或更精细几何证据可能改变 admission，但这些需要新的登记，不能在本轮结果中补选。

这也不是 tokenizer 失败、导航策略失败或原始人类行为意图的证据。没有新执行的障碍 episode，因此不增加 canonical pair/source 计数，也不消耗新的 main attempt。

## 3. 单独登记的后续：固定宽臂／收臂对比

[新的对比登记](../configs/carrier_contrast_v1.plan.json)在本轮零接受结果之后、构造和执行之前创建。使用现有 `critical.edit_motion` 的固定 wide/tuck 参数，不搜索角度、不 retime、不改变 root、腰部或腿部。

已完成构造检查：

- root、腰部和腿部参考与原始 carrier 完全相同；
- 共同进入、退出和过渡规则不变；
- tuck 参考与此前已合格版本逐元素相同；
- native 格式往返误差通过既有门槛。

先登记最多 **6 次预检、1 次 launch**：两个固定 continuation × 三个原有初始扰动。只有两个 continuation 全部合格，才能应用同一 145 网格。只有几何通过，才进入最多 **24 次 main 干预、1 次 launch**。

本次资源队列完成登记的 **600 秒等待、30 次检查**，未满足连续两次 ≥12,000 MiB 空闲 GPU 的条件，已记录 **deferred_resources**。最后一次空闲 GPU 为 9,086 MiB。没有 native launch，没有新增预检或 main episode，也没有后台任务继续等待；未中断其他工作。

因此累计仍为 **440 个已记录预检 + 312/480 个 main attempt**，剩余 **168 个 main attempt**；此前的 144 个基础设施失败 slot 单独保留。Canonical acquisition 仍是 5 个编辑动作对、3 个源分组。

执行状态见[机器可读汇总](../results/carrier_scene.json)。没有 launch 的等待不计为执行失败或已消耗 episode。不得自动恢复失败 launch。新对比即使成功，也只能支持人工构造的 wide/tuck 行为选择，不能替换原始动作比较的负结果。

## 4. 后续研究顺序

1. **先完成可执行对比资格。** 如果固定 wide 编辑失败，报告 teacher/编辑覆盖限制，不再仅凭较大的几何臂宽宣称 scene 数据可用。
2. **再取得完整干预面板。** critical、relaxed、removed、displaced 必须按原门槛验证；不能只保存 favorable critical 运行。
3. **再比较数据获取方法。** 在相同 geometry-query/native-execution 预算下比较随机放置、root、连续全身及 token 条件方法；主要衡量单位预算得到的已验证行为选择和 source 覆盖。
4. **最后进入固定 learner 效用研究。** 先单独登记 ancestry-aware split、独立 authored scene 测试、相同 learner/decoder/训练预算。当前数据仍为 development，未授权将相关帧随机划分后称为 held-out 导航实验。

运动 token、scene token、relation 监督和 motor 接口仍是不同对象。先建立 scene/goal 控制效用，再扩展语言条件和世界模型；本轮没有训练 BFM、导航学生、LLM 或 scene tokenizer。

## 重算

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
  /home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python \
  -m hindsight_motion.carrier_scene_report
```

原始 proposal 目录不可覆盖。新的 acquisition 应使用新登记和新目录。
