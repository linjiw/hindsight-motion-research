# Continuation admission 02

The user explicitly requested resuming the research plan after the first resource deferral. This new admission preserves the [scientific protocol](CONTINUATION_PROTOCOL.md) and all sixteen ordered cases. Its [registration](../configs/continuation_admission_02.plan.json) was saved before execution.

The parent packet `runs/continuation_20260918_v1/` is closed: zero native launches, sixteen unrun cells, a 300-second resource timeout. Its registration, plan, aggregate and timeout receipts remain immutable. All 148 old bound inputs and source files matched their hashes before preparing the successor. No source/reference/controller/seed/scoring change is introduced.

The successor is `runs/continuation_20260918_admission02/`. It records links and hashes to the parent and copies the already measured offline input diagnostics. The attempt ceiling across these admissions remains sixteen, with no retries or training. Each launch still requires two resource checks twenty seconds apart; each wait is bounded at 300 seconds. Behavioral, matching, infrastructure and timeout stopping rules are unchanged. This does not resume or consume the unrelated historical 168-attempt balance.

Preparation rejects any parent with an actual launch, changed input or changed scientific registration. The native runner remains the pinned implementation. The current admission is not permission to repeatedly renew waits or replace a failed trial.

```bash
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
PYTHONPATH=src "$RESEARCH_PY" -m hindsight_motion.continuation_admission \
  configs/continuation_admission_02.plan.json
PYTHONPATH=src "$RESEARCH_PY" -m hindsight_motion.continuation \
  run runs/continuation_20260918_admission02
```

These are single-use packet commands, not instructions to overwrite completed evidence. Outcomes are published separately from the first deferral in `results/continuation_admission02.json` once the queue stops or completes.

Completed: all sixteen attempts ran once; [both methods pass 8/8](CONTINUATION_ADMISSION02_RESULTS_zh.md). No further native budget remains in this registration.
