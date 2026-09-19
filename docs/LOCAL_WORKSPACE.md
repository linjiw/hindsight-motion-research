# Hindsight Motion Research

**Current stage:** [Live token-mechanism experiment status](../artifacts/mechanism_status.html) · [Registered protocol](TOKEN_MECHANISM_PROTOCOL.md) · [Completed CPU diagnostics](../artifacts/token_mechanism_offline.png). Eight decoder variants and eight new carrier groups are prepared. Native work uses a serial resource gate; the live page distinguishes waiting, execution, failure and audited completion, and links measured results when available. The initial 144-slot GPU allocation failure is retained separately from recorded episodes.

**Latest:** [Decoded-motion physics results](DECODER_EXECUTION_zh.md) · [96-episode representation replay](../artifacts/decoder_viewer.html) · [Comparison figure](../artifacts/decoder_execution.png). Added 114 preflights and 96 frozen-scene runs. Linear29 passes 17/18 preflights and preserves all six arm/beam panels on two existing KIT/205 pairs; continuous controls also preserve all six. The three RVQ variants pass 0/54 preflights. Three additional source groups pass 0/24. Cumulative: 248 preflights, 216 main episodes; no new independent scene pairs or student training.

**Core acquisition dataset:** [Second traversal family](SECOND_FAMILY_AND_TOKENS_zh.md) · [120-episode replay](../artifacts/second_family_viewer.html). Five base pairs, three source groups, 24,000 control rows and 18,200 supported motor targets. The new [representation-validation index](../runs/decoder_validation_20260915_v1/development_representation_episodes.jsonl) separately retains 96 correlated descendants and 16,800 supported motor targets. All development-only.

An executed local-data pilot for whole-body motion tokens and hindsight obstacle scenes. This research workspace is separate from existing Motion2Scene training work.

**Start here:** [中文实验结果](RESULTS_zh.md) · [研究与实验设计](RESEARCH_PLAN_zh.md) · [数据源与 tokenizer 选择](DATASETS_zh.md) · [交互动作回放](../artifacts/viewer.html) · [结果图](../artifacts/pilot_summary.png).

**New physical experiment:** [Critical-scene results](CRITICAL_RESULTS_zh.md) · [Native protocol and BFM data contract](CRITICAL_EXPERIMENT.md) · [Executed comparison viewer](../artifacts/critical_viewer.html) · [Intervention figure](../artifacts/critical_interventions.png) · [Token-clearance diagnostic](../artifacts/critical_token_clearance.png).

**Expansion completed:** [Results and limitations](EXPANSION_RESULTS_zh.md) · [Four-pair measured replay](../artifacts/expansion_viewer.html) · [96-episode result figure](../artifacts/expansion_interventions.png) · [BFM data index](../runs/critical_dataset_20260915_v2/development_episodes.jsonl). Arm criticality now replicates fully in two source groups. The ducking contact contrast did not pass the complete control-panel gate. Cumulative: 98 preflight episodes, 96 main episodes, 19,200 control rows and 14,000 supported motor targets; all development-only.

**Roadmap:** [Critical scenes → BFM → text-to-navigation](ROADMAP_SCENE_BFM_TEXT2NAV.md), with a [bounded execution plan](../configs/critical_decisions_v1.plan.json). Five motion pairs across three source groups have been tested; two arm pairs and one crouch-plus-bend pair pass every panel. Expanding to 20 pairs, replicating the second family across sources, learning a criticality proposer, and evaluating student policies remain open.

## First native result

A proposer enumerated 145 passages from native collision geometry and measured teacher trajectories. In all three matched initial-state panels, tucked arms pass its selected critical passage and wide arms make hand-obstacle contacts; both alternatives pass when the passage is widened, removed, or displaced. This is one edited motion pair from one source group, not a generalization estimate.

The original 24 scene runs export 4,800 control records with separate actor, teacher-only, and target views. Actor inputs contain causal proprioception, a complete known map, and the local goal. The 21 passing episodes support 4,200 positive imitation rows, all development-only. Failed contrasts are retained. Later decoded-motion qualification is reported in the latest results above; the original RVQ representations fail that physical gate.

## Earlier offline pilot

- Audited and processed 900 local G1 mocap retargets with source hashes and 201 source-directory groups.
- Fitted 128-entry VQ and two-level RVQ codebooks on training groups; exported 6,872 kinematic events.
- Generated 25,472 supported primitive scene candidates for 398 translating clips; retained 1,194 geometry candidates.
- Trained six small proposal rankers: root, root + events, root + tokens, two seeds each.
- Rechecked all 84 test scenes against MuJoCo collision geometry at 100 Hz. All original motions clear; only 3 of 26 rigid-overlap proxy witnesses survive the model-geometry check.

**Offline pilot scope:** kinematic geometry, representation and proposal ranking. Those earlier exported candidates still carry `physics_verified=false` and `functional_counterfactual_verified=false`. The newer native intervention evidence is a separate dataset; it does not retroactively qualify the offline candidates. The rigid-posture comparator is an information diagnostic.

## Reproduce

Dependencies are NumPy, SciPy, MuJoCo, Matplotlib and PyTorch; pytest is used for validation. `configs/pilot.json` points to the local licensed inputs and pinned G1 XML. Do not publish or package those source motions through this project. The run receipts list exact library versions, source and robot-asset hashes.

The existing environment used for these runs is:

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=2
export OMP_NUM_THREADS=2
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
"$RESEARCH_PY" -m pytest -q
"$RESEARCH_PY" -m hindsight_motion.pilot --config configs/pilot.json --output runs/new_pilot
"$RESEARCH_PY" -m hindsight_motion.proposer --pilot runs/new_pilot --output runs/new_proposer
"$RESEARCH_PY" -m hindsight_motion.validate --pilot runs/new_pilot --output runs/new_geometry
```

Run directories must be new; commands refuse overwrites. The presentation script currently targets the named original pilot runs:

```bash
"$RESEARCH_PY" -m hindsight_motion.present --root /home/linjiw/hindsight-motion-research
python3 -m http.server 8769 --bind 127.0.0.1 --directory /home/linjiw/hindsight-motion-research
```

Then open `http://127.0.0.1:8769/artifacts/viewer.html`, or open the standalone HTML directly; it has no external dependencies or network requests.

## Evidence locations

| Artifact | Location |
| --- | --- |
| Experiment definitions fixed before their respective fits/checks | `docs/*PROTOCOL.md` |
| Input identities and source grouping | `runs/pilot_20260915_v1/inventory.csv`, `data_split.json`, `input_receipt.json` |
| Learned motion codes and event descriptions | `codebook.npz`, `tokens.jsonl`, `events.jsonl` in the pilot directory |
| Scene boxes and status flags | `runs/pilot_20260915_v1/scenes.jsonl` |
| Representation and scene metrics | `representation_metrics.csv`, `scene_metrics.csv`, `aggregate.json` in the pilot directory |
| Six trained proposal models and predictions | `runs/proposer_20260915_v1/models/`, `test_predictions.npz` |
| Model-geometry recheck | `runs/geometry_20260915_v1/per_scene.csv`, `aggregate.json` |
| Scientific plots and interactive replay | `artifacts/` |

All numeric claims in the Chinese result report map to these files. New data and experiments should preserve the distinction between generated scenes, verified model geometry and executed policies.

## Audit the native stage

```bash
cd /home/linjiw/hindsight-motion-research
export PYTHONPATH=/home/linjiw/hindsight-motion-research/src:/home/linjiw/groot-wbc-sonic-sim-trackb
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
STUDY=/home/linjiw/hindsight-motion-research/runs/critical_interventions_20260915_v1
"$RESEARCH_PY" -m hindsight_motion.critical_analysis "$STUDY"
"$RESEARCH_PY" -m hindsight_motion.critical_validate "$STUDY"
"$RESEARCH_PY" -m hindsight_motion.critical_present "$STUDY"
```

Native command arguments, resolved configurations, code snapshots, logs, exits and data hashes are retained for every attempted episode. The native interpreter is `.venv_isaaclab/bin/python` in the SONIC runtime, distinct from the lightweight analysis interpreter above. `interventions.run` resumes only unattempted tasks; it never reruns a launched directory. The original scene runs use a single environment; the expansion uses the separately validated, contact-audited batch runner. Original source data and existing training code were not edited by this project.
