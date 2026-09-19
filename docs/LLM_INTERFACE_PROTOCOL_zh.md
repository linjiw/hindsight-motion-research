# 小型开放权重 LLM：动作与任务信息保持协议 v1

登记：2026-09-18；用户指导的采用记录见[研究指导](RESEARCH_GUIDANCE_20260918_zh.md)。这是主计划 P0 的离线分支。**L0 可先做；L1/L2 不绕过完整任务支持门槛。** 机器可读登记见 [config](../configs/llm_interface_v1.plan.json)，实现见 [llm_interface.py](../src/hindsight_motion/llm_interface.py)。

## 科学问题

不仅问 LLM 能否输出语法正确的 token，而是问：同一任务/动作通过语言模型后，**哪些任务约束、动作细节与可执行选择被丢失；这些丢失是否影响原本能完成的任务？** 分开任务理解、候选选择、信息传递、动作生成、物理执行。LLM 自评或文本相似度不是判据。

反假设：结构化目标 + 简单规则/小型非语言 planner 已足够；LLM 增加延迟和错误，未提高未见指令/任务组合的能力。若成立，保留 LLM 作任务入口，让经过验证的运动模块负责连续精度和时序。

## 先选小而可控的模型

| 模型 | 角色 | 当前范围 |
| --- | --- | --- |
| [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) | 低成本局部探针 | 固定 `c1899de289a04d12100db370d81485cdf75e47ca`；Apache-2.0；本次仅 CPU 推理 |
| [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | 同家族容量对照 | 固定候选 `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`；Apache-2.0；尚未运行 |
| [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B) | 需要跨家族验证时再加入 | Apache-2.0；本轮不下载、不运行 |

选择依据是小规模、可本地复现和许可清楚，不宣称它们是最新或最佳。先固定非思考模式与 greedy 解码检查可复现接口；这不是厂商推荐采样设置的性能评测。后续温度/多 seed 单独登记。模型卡建议通过 `enable_thinking=False` 明确关闭思考；不能把隐藏思考预算省略于成本。

## 三层实验，结论不可跨层

| 层 | 输入/对照 | 判据与结论范围 |
| --- | --- | --- |
| **L0：接口探针，已实现** | 手写合成状态、候选 motion record、显式规则；无 LLM 规则基线 vs 0.6B；完整记录 relay vs ID + lossless sidecar | 单位、坐标、时钟、状态绑定、前缀、支撑、root/骨盆样本、终止字段保持；只测接口规则，不是人形可执行性 |
| **L1：真实动作保持，拟议** | 同一 local motion：原始/codec 重建/LLM 传递后重建；oracle 正确选择与模型选择分开 | root/关节、支撑转换时序、关键间隙窗口、速度、边界、解码失败；需 ancestry split 和冻结真实数据/decoder |
| **L2：任务效用，拟议** | 同场景、完整实际来态、controller/history、相同反馈与预算；直接结构化任务 vs LLM 任务/动作入口 | 完整任务、有效启动窗、错误选择、拒绝覆盖、恢复/停止、延迟；只能在独立注册的物理执行后作任务结论 |

L0 的样本是手写的两个时刻 root/骨盆数值与 desired support，不是合法 G1 关节轨迹、native motor token 或学习得到的 motion latent。不能将 L0 通过率称作“tokenizer 兼容 LLM 已验证”。

## L0 冻结范围与独立检查

六种状态：身体尚未完全离开、身体已离开但未直立、目标附近仍在移动、已静止仍需保持、几何未知、支撑来态不在候选范围。每种两种等价表述/ID 重编号/候选顺序变体，共 12 输入；变体不是独立任务。长横梁、高度/速度连续扫描和任务目标变化留待新版，并不声称本轮覆盖。

两条路线各 12 次生成：

1. **Relay：** LLM 选择 ID，并原样返回全部 task 与所选 motion。按字段独立检查复制准确性和选择正确性。
2. **Sidecar：** LLM 只返回 ID 与 task ID；程序按原始映射保留精确内容。sidecar 的数值保持属于确定性程序保证，不能归功于 LLM。错误选择仍判失败。

JSON 不修复、不重试；拒绝重复 key、NaN、缺字段、额外字段、未知 ID、错误单位/时序或布尔值冒充数值。所有已尝试生成进入分母；基础设施错误与未运行另列。null 只在声明的未知/不支持场景算正确，不能靠总是拒绝刷分。输出截断、各病例原始响应、输入/输出 token、耗时、源码/config/fixture hash 均留档。

显式规则与模型相同；测试的是规则执行/记录传递。预先手写标签核对无 LLM 规则实现，模型 prompt 只含 actor view，不含 expected ID。未采用模型裁判。variant 同时改变措辞、ID、顺序，故若发生退化，只能定位为这一组扰动的敏感性，不能分别归因。

预算：0.6B、FP32、CPU 4 线程、最多 24 次生成，每次最多 384 新 token；每次软时间限 60 s，总推理调度限 900 s（最后一次生成可能跨过调度界限）。不训练、不使用 GPU、不启动 native。输入合成，无许可动作发送至外部服务。原始指导本地保存。

## L1/L2 的四个必要比较

将 `R = representation`、`P = predictor` 分开；同 motion/任务先跑 R-only 编码解码，再增加 P。teacher forcing 下的 token NLL 可诊断易预测性，但主要报告 free-running 解码和完整任务，避免把正确 prefix 当自主能力。

| 比较 | 隔离的问题 |
| --- | --- |
| 无 LLM、同样的确定性 serializer/adapter | 下游错误是否已经由 codec/adapter 引入 |
| LLM 只选具名能力/候选 + 保真 sidecar | 选择和语言理解；不要求模型重写连续数字 |
| LLM 文本摘要 vs 完整结构化记录 | 摘要是否丢失时序、support、root 或 terminal；同模型、同输入内容与预算 |
| 同 backbone/head 的连续输出 vs 已对齐 motion token 输出 | 表示的可学习性；需要训练，随机整数 ID/零样本复制不是运动语言对齐 |

先保留真实 motion 的全参考、编码重建、LLM 之后三份数据。对每个关键字段记录变化，再在**同一来态**检查功能差异。后续训练 target 可包含未来 motion；actor 只能看任务与因果观测/历史。语言 token 数≠motion bits，sidecar、root、进入段、模型存储、推理 token/时间均要算成本。

扰动包括 beam 长度/高度、初速度、提前恢复、停止要求、单位/坐标转换、过期状态、候选 ID 重排、指令改写、未知几何与不支持来态。拆成语义不变扰动和应当改变选择的最小对照。固定同一个历史、decoded horizon、committed prefix 与反馈频率；不让某个接口得到隐藏参考。

优先固定动作库支持范围内的未见场景/指令组合。新动作来源单独做 ancestry holdout；所有模板改写留在相同 split。保留固定预定测试集与支持覆盖分母，不能只报告模型愿意回答或 continuous 成功的子集。LLM 本身不担任在线安全控制器；被拒绝请求如何恢复需另外验证。

## 与近期文献的关系

[ActionPiece](https://arxiv.org/html/2609.18487v1) 已经比较关系保持与受控 VLA 下游表现。我们的候选机制需要通过状态/场景下有效选择证明；不仅比较文本或重建。[OAT](https://arxiv.org/html/2602.04215v2) 支持 ordered/prefix action decoding，但前缀的物理可执行性仍要在本任务验证。这里不能把复制 motion ID 当作这些方法的复现。

## 复现

无需模型的检查：

```bash
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 "$RESEARCH_PY" -m pytest -q tests/test_llm_interface.py
PYTHONPATH=src "$RESEARCH_PY" -m hindsight_motion.llm_interface \
  --backend rule --output runs/llm_interface_my_new_rule
```

模型 runner 使用可选 `transformers==4.57.6`、`huggingface-hub==0.36.2`、`tokenizers==0.22.2`、`safetensors==0.7.0` 与本机 `torch==2.11.0+cu128`（只用 CPU）。本轮依赖单独装在 `/tmp/hindsight-llm-deps`，没有改变 research 环境。先从官方仓库下载 config 中固定 revision；runner 强制 `local_files_only=True`、`trust_remote_code=False`。

新环境可用 `python -m pip install -e '.[llm]'` 安装可选依赖，然后缓存固定 revision（模型权重约 1.2 GB；本机已下载，不必重复）：

```python
from huggingface_hub import snapshot_download
snapshot_download(
    "Qwen/Qwen3-0.6B", revision="c1899de289a04d12100db370d81485cdf75e47ca",
    allow_patterns=["*.json", "*.safetensors", "*.txt", "LICENSE", "README.md"],
    max_workers=2,
)
```

```bash
PYTHONPATH=src:/tmp/hindsight-llm-deps HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 "$RESEARCH_PY" \
  -m hindsight_motion.llm_interface --backend transformers \
  --output runs/llm_interface_my_new_qwen06
```

每个 output 必须不存在；不得覆盖或选择性替换失败记录。新 prompt、fixture、模型、采样或预算需新协议版本。该命令是复现说明，不表示可以无限重复本次预算。
