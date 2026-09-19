# Frozen representation at the controller's support boundary

Registered September 19, 2026, before this study's native launches. The user requested continuing the [research plan](RESEARCH_PLAN_zh.md). This separate six-attempt development registration leaves previous experiments unchanged.

The neighboring project at commit `5184085c` has completed a 24-trial frozen-controller screen. Its public controller succeeds on four of six beam variations and all six clear rows; a 10 cm lower beam causes contact and a 60 cm farther goal causes a deadline failure after recovery. The clear rows represent four distinct actor requests. These outcomes were known when selecting this follow-up. The prior tentative ±5 cm/shared-clear six-case proposal is superseded: smaller shifts would add less information about representation versus controller limitations.

## Question and fixed comparison

Does frozen Linear29 preserve a supported shifted traversal, and does it change either known failure? Execute these contexts in order, continuous then Linear29 within each:

1. `earlier200-beam`: beam 20 cm earlier relative to the familiar earlier-100mm pilot; sibling continuous succeeds.
2. `lower100-beam`: ceiling 10 cm lower than that pilot; sibling continuous contacts the beam.
3. `farther600-beam`: requested destination 60 cm farther, with the beam unchanged; sibling continuous stops short.

Reuse the exact sibling task/scene files and immutable decoded banks from [the familiar-selector pilot](SELECTION_CODEC_PROTOCOL.md). Retain the same continuous planner, motor/checkpoints, seed, simulator reset, goal050 tolerance, recovery/stop ordering, contact rules and 500-control-tick deadline. The sole representation intervention is decoded joint position/velocity after the selector chooses its corrected dense source indices; root rotation, continuous planner bounds/support and candidate scoring stay unchanged. Each arm subsequently visits its own measured states. The former shared clear control is not rerun; earlier clear evidence remains separate and does not establish Linear29's clear behavior at the farther goal.

The implementation reuses the frozen native callback. Bind all active sources, commands, configs, inherited bank/decoded files, source assets, scenes, checkpoints and parent evidence; snapshot new orchestration code and this protocol. Before physics, exactly replay the corresponding parent references and source indices. A continuous run must then exactly reproduce its corresponding sibling references, proprioception, motor tokens/actions, body/root/joint trajectories, dynamics and contacts. **A reproduced behavioral failure is a valid control and must not censor its codec pair.** Require exact paired initial state/history/dynamics/RNG and initial choice/costs. Resource or process failure, missing evidence or mismatch stops the queue and preserves every attempt.

## Budget and analysis

At most six native attempts, no retries, 500 control steps per attempt, 3,000 control steps / 12,000 physics samples total, 600 seconds per native process, and the existing serial 300-second resource admission per case. No teacher-action queries, fitting, source editing, calibration changes or historical-main-budget charge. The new immutable packet has its own ledger; parent trials are not counted as new evidence or independent replicas.

Recompute every task score from measured body envelopes and pair-resolved substep contacts. Replay every issued reference, candidate choice and source index from actual histories. Report all six scheduled cases, including unrun/process failures, forbidden contact, final goal error, recovery, fresh ordered hold, steps and paired gains/regressions. Stop time for a contact failure is not completion time. Report codec retention on successful continuous controls separately from success over the whole selected set. No confidence interval over correlated states or claim of statistical equivalence.

If both methods retain the two failure types, prioritize missing motion coverage and distance-responsive exit/stop composition. If Linear29 alone fails the supported shift, isolate clipping versus temporal loss before changing architecture. If it unexpectedly succeeds on a failed control, investigate the physical and reference changes; do not label that a general compression benefit. All outcomes remain in the denominator.

This screen was selected using previous development outcomes and contains one ancestry/seed. It does not test generalization, deeper-duck feasibility, qualified blocked-state behavior, perception, or language. The farther-goal scene also changes floor extents, so between-scene physical differences are not a pure goal intervention; the sibling's same-history goal diagnostic provides the narrower response test. Full continuous planner storage and float640 motor transmission remain; do not claim end-to-end compression from this comparison.
