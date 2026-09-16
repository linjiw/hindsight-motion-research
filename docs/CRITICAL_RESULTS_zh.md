# 第一组真实物理仿真实验：动作为什么需要避障

> 后续已完成跨源与下蹲扩展，累计 96 次主实验。见 [最新扩展结果](EXPANSION_RESULTS_zh.md)。本页保留最初单动作对实验。

## 结论

我们已经实现一个寻找关键避障位置的几何 scene proposer，并用本机 SONIC teacher 完成了 **48 次动作预检 + 24 次场景干预 rollout**。

在这一组动作中，生成的通道确实让收臂动作变得有用。两个动作来自同一条 KIT 行走数据，root 和腿部参考完全相同，只有手臂轨迹不同；它们都能在控制场景里完成穿行。

| 场景干预 | 收臂动作通过 | 展臂动作通过 |
| --- | ---: | ---: |
| 关键位置：0.76 m 通道 | 3/3 | 0/3 |
| 放宽通道至 1.36 m | 3/3 | 3/3 |
| 移除障碍 | 3/3 | 3/3 |
| 障碍横移 2 m | 3/3 | 3/3 |

三个初始位置为横向偏移 0、−1.5、+1.5 cm。**3/3 组完整干预面板通过关键性审计**：同组八次运行的初始 root、关节、关节速度和 930 维 proprioceptive history 完全一致；控制场景中两个动作都通过，关键场景中收臂通过、展臂与障碍发生手部接触。

这是 **1 个 source group、1 个经过编辑的动作对、1 种 arm-tuck 机制**的开发实验。三个扰动不是三个独立场景，也不是泛化性能估计。原计划的 20 个动作对、2 类机制和最多 480 次主实验尚未完成；当前使用其中 24 次。

## 测量到的行为

- 收臂穿过关键通道：最大障碍接触力为 0 N；终点误差范围 2.58–3.60 cm。
- 展臂在关键通道受阻：双手发生障碍接触，最大法向力范围 499.8–501.2 N；终点误差 60.9–65.8 cm。
- 所有控制场景中，两种动作都通过，障碍接触力为 0 N。
- 判定包含 tracking、200 Hz 的逐身体/障碍接触、共同目标和穿出通道的进度；“没有摔倒”本身不算成功。

任务终止要求是移动中到达，不包含站稳或停住。Teacher 使用未来参考动作，尚未训练一个自主看场景选择动作的导航学生。

## Teacher 支持范围

初始选了六个不同 KIT source group 的行走片段，各生成原动作、收臂、展臂、90° 转向四种候选，共 24 条。第一批在默认噪声/机器人随机化下，23 条完成参考时钟，但只有 3 条通过严格 tracking 门槛。第二批去掉这些独立干扰，24 条完成，6 条通过严格门槛。

90° root-yaw 编辑在两批中均无合格候选。它改变朝向，却没有生成与侧向行走一致的支撑脚运动；不能把这种编辑当作可执行的侧身替代动作。所有失败均保留，没有为了凑成功样本替换。

## Scene proposer 已经做了什么

使用 native G1 的 45 个碰撞形状和实际空场执行轨迹，枚举了 145 个通道。6 个候选同时满足“收臂留出至少 3 cm 的采样几何余量”和“展臂存在至少 1 cm 的解析形状内部重叠证据”。按两侧余量选择 0.76 m 的开口后，再进行上述物理验证。

这是一版可执行、可审计的几何 proposer。先前训练的小网络仍是几何有效性 ranker；本次没有把一个动作对包装成学会泛化的 scene generator。

## Tokenization 暴露了下一处关键问题

两个动作的 root 参考逐帧完全相同，RVQ token 则在 40 个 patch 中有 26 个不同。不过 token 有差异，并不意味着避障细节保存得足够准确。

本次进一步用 native URDF 的运动学和碰撞外包络检查解码结果。运动学先与仿真记录比对，最大位置差小于 0.003 mm。对收臂动作，关键通道的采样分离下界为：

| 表示 | 分离下界 | 通过 3 cm 几何门槛 |
| --- | ---: | --- |
| 连续参考 | 9.89 cm | 是 |
| VQ 128 | 0.99 cm | 否 |
| RVQ 128 × 2 | −1.19 cm | 否 |

**负下界不等于已证明碰撞；量化后的动作没有执行物理 rollout。** 这个开发诊断说明现有重建式 tokenizer 未能保留该收臂参考的几何余量。下一步应比较显式身体几何残差和 clearance-aware token 学习，并用新来源分组评估。

## 给后续 BFM 留下的实际数据接口

已经导出 4,800 个控制时刻，包含三种分离的数据视图：

- Actor：因果 proprioception、当前局部目标、带 mask 的 3D scene tokens。当前假设完整地图和精确定位。
- Teacher-only：未来 motion reference 与 privileged simulator state。
- Targets：同一状态查询/执行的 29 维动作、64 维 native SONIC motor token、分目标 support mask。

4,200 行具有本次穿行任务的正向 imitation support；受阻 rollout 作为失败/关系标签保留，不进入正向动作支持集。RVQ motion code 与 SONIC motor token 是不同空间，需要单独学习和验证接口。全部数据当前属于 development；没有训练或报告 BFM/text2nav 的收益。

## 验证与复查入口

- 24/24 native 命令正常结束；所有尝试和结果都保留。
- 11 个针对几何、动作编辑和关键性门槛的测试通过。
- 数据审计通过：source/scene hashes、actor 字段边界、场景与目标坐标重建、teacher target 对齐、接触记录覆盖、初始状态匹配及 runtime dependency hashes。
- [实验图](../artifacts/critical_interventions.png) · [交互物理轨迹回放](../artifacts/critical_viewer.html) · [token 几何诊断图](../artifacts/critical_token_clearance.png)。
- [协议与数据契约](CRITICAL_EXPERIMENT.md) · [汇总结果](../runs/critical_interventions_20260915_v1/aggregate.json) · [逐次结果](../runs/critical_interventions_20260915_v1/all_attempts_and_outcomes.csv) · [关系审计](../runs/critical_interventions_20260915_v1/paired_relation_audit.json) · [完整性验证](../runs/critical_interventions_20260915_v1/verification.json)。

## 紧接着做什么

1. 增加独立来源的合格动作对，并找到第二类可执行机制；优先自然的下蹲/抬脚动作或满足足部接触约束的编辑。
2. 在更多真实执行的通道宽度、初态和动力学扰动上验证参数区间。
3. 训练能预测“可执行且有行为必要性”的 proposer，并与随机安全放置、几何 ranker 在相同预算下比较。
4. 用物理关系标签改进 motion/scene token，再做冻结 teacher 的 BFM distillation 和独立 scene-first 导航测试。

我们现在有了第一条完整链路：**本机 mocap → 可执行替代动作 → 关键场景提议 → 物理干预验证 → 有证据边界的数据与 token 接口**。
