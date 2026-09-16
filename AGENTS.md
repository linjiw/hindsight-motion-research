# Hindsight Motion Research

This Python workspace studies whole-body motion representations and hindsight obstacle scenes. Implementation lives in `src/hindsight_motion/`, experiment definitions in `configs/` and `docs/`, measured outputs in `runs/`, and presentations in `artifacts/`.

## Working approach

- Carry the requested task through implementation, relevant verification, and any affected documentation. Continue fixing failures caused by your changes without asking for approval at each step; stop when the requested outcome is complete or a concrete blocker remains.
- Use reasonable assumptions for reversible local choices. Ask when missing information materially changes the scientific question, scope, or resource budget and cannot be resolved from the task or its protocol.
- Read documentation relevant to the change, rather than loading the entire project. Keep this file focused on durable project constraints; keep changing results and experiment counts in reports and run receipts.

## Context on demand

- `README.md`: reproduction commands, environment locations, and the evidence index.
- `docs/RESEARCH_PLAN_zh.md` and `docs/ROADMAP_SCENE_BFM_TEXT2NAV.md`: research direction and proposed next stages.
- `docs/PILOT_PROTOCOL.md`, `docs/PROPOSER_PROTOCOL.md`, and `docs/GEOMETRY_VALIDATION_PROTOCOL.md`: offline pilot, ranker, and geometry changes, respectively.
- `docs/CRITICAL_EXPERIMENT.md`: native intervention gates, data contracts, and actor/teacher/target separation.
- `docs/TOKEN_MECHANISM_PROTOCOL.md` and the applicable `configs/*.plan.json`: decoder comparisons, acquisition, frozen controls, and execution budgets.
- For result updates, consult the relevant report and its underlying run evidence. Preserve the existing document's language.

## Local verification

Python 3.11+ is required. The existing lightweight research interpreter is `/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python`. From the workspace root:

```bash
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 "$RESEARCH_PY" -m pytest -q
```

Pytest configures `src` on the import path. Select affected tests for narrow changes; use the full suite for shared behavior changes. Documentation-only edits need link and content checks, not experiment reruns. Direct module commands use `PYTHONPATH=src`; native commands have a separate runtime and import setup documented in the README.

## Experiment and evidence constraints

- Keep licensed source motions and licensed descendants local. Do not package or publish them. This workspace is separate from the existing Motion2Scene training work; external datasets and runtime assets are inputs unless the task explicitly includes changing them.
- Use new run directories and preserve existing receipts, hashes, logs, and failures. Respect runners that refuse overwrites or repeated launches. A failed native attempt remains evidence and may consume budget; consult the applicable registration and budget accounting before replacing it.
- For authorized native experiments, use the existing serial resource gate and registered limits. Native simulation uses the SONIC IsaacLab interpreter, distinct from the analysis environment. Do not launch native experiments merely to validate routine documentation or presentation changes.
- Keep generated candidates, checked geometry, and physically executed outcomes distinct. Derive numerical claims from recorded artifacts; report failures and limitations alongside successes.
- Preserve registered controls, thresholds, source grouping, and ancestry-aware splits. Version intentional protocol changes before new experiments instead of rewriting earlier registrations to match outcomes.
- Keep causal actor observations separate from privileged teacher information and training targets. Preserve support masks and development-only restrictions; correlated descendants do not count as independent evidence or held-out evaluation data.
