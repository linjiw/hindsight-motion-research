# Distance-exit continuous / Linear29 comparison

Registered 2026-09-19 before new native outcomes, following the user's request to continue the saved research plan. [Machine registration](../configs/distance_codec_v1.plan.json). This is a four-case development simulation experiment, separate from the exhausted six-case boundary screen and the offline preflight.

## Question and comparison

Does the existing raw Linear29 interface preserve actual goal-dependent exit choice and complete beam traversal/recovery/stop on the frozen `DistanceExitComposer`? Compare original-beam and farther-beam (+0.60 m) × continuous/Linear29, in that order and continuous first within each pair. All four are new attempts; the two historical continuous executions are parity controls, not additional observations in the denominator.

Keep the exact parent task JSON and identical scene bytes across goals, seed 96161, measured reset, proprioceptive history, dynamics, motor/decoder, normalization, goal/geometry access, scorer, 500-tick deadline and fixed composed clock. No supplied family/count at runtime. Family choice uses the full continuous bank; at internal tick 126 the composer uses measured clearance and root position plus frozen displacement estimates to choose short or one loop. Each method subsequently visits its own states. No future observations or online teacher actions enter that decision.

Only the issued joint position/velocity changes. Reuse and independently reconstruct all four decoded arrays from the prior [preflight](DISTANCE_CODEC_PREFLIGHT_zh.md): 12-bit named scale, offset 2 / stride 5, two exact reset anchors, frozen wrist clipping, native finite-difference velocity. Continuous retains the analytic blend's supplied velocity. Root, clean rotations, support proposal, synthetic observed-support invalidity, metadata, planner and references are unchanged. This is an interface-package comparison; a difference cannot be assigned solely to quantization.

Five committed frames must agree between decoded short/loop choices. Earlier forecast but uncommitted frames can differ: preflight first q/qdot differences move from composed frame 172 to 168/167, and goal-dependent packed reference from control tick 127 to 126. No reference changes before the decision. Record this convention; do not silently add boundary anchors, smooth qdot, change scales or repair the baseline after observing outcomes.

## Admission, budget and stopping

Before simulation, pin current source and data hashes, copy registration/protocol/source snapshots, re-derive decoded arrays exactly, check both options' commitment, and reconstruct historical continuous references/indices/family/decision on all 792 original/farther beam states. Check same-scene bytes and public-mode configuration. Preserve source calibration provenance and typed synthetic masks. Existing nominal-loop qualification in the sibling is not extra evidence for Linear29 here.

At most **4 new native attempts, 2,000 control steps, 8,000 physics/contact frames**, 500 control ticks and 600 wall seconds per attempt. Use the existing serial resource gate (two samples 20 seconds apart, ≥12,000 MiB GPU and ≥16,384 MiB host); wait at most 300 seconds for each admission. Zero retries, teacher-action queries, training updates or old main-budget consumption. Record every launch, failure and resource deferral in a new immutable packet.

Each continuous run must exactly reproduce its parent references/proprio/tokens/actions, trajectories/dynamics/contacts/features and decision before the paired codec launch. Reproducing a behavioral failure is still valid. The pair must have exact reset/history/dynamics/RNG and initial family/costs. Infrastructure failure, parity failure or resource timeout stops remaining launches; no automatic rerun. Contact, fall and deadline outcomes remain in the denominator. Existing packets and source contracts are not rewritten.

## Analysis and decisions

Independently reconstruct full-body envelopes and all four substep contact samples, rescore passage/duck/recovery/fresh 50-tick hold and terminal success, and replay the emitted references, composed indices, family, count and recorded decision on each actual pre-action history. Keep elapsed time for failures distinct from successful completion time. Report final signed route error, XY error and 3D distance separately, with the frozen **0.50 m XY** goal radius and ≤0.10 m/s speed threshold.

Report all four scheduled cases and two paired task gains/regressions, success-conditioned retention, actual clearance gate/count/requested count, stopping margins, cost and provenance. Also compare goal-dependent first reference/token/action/state differences across each method's two free-running runs, explicitly verifying their common prefix; do not substitute the prior continuous-history shadow for actual codec choice. Exact replay of many frames is not many independent demonstrations.

If only Linear29 fails, register a small velocity-convention or temporal-boundary diagnostic addressing the observed failure before enlarging the tokenizer. If both succeed, keep the simple codec and use subsequent controller/reset coverage to locate the next informative representation test. If both fail, inspect controller support. Matching two outcomes establishes neither equivalence nor robust coverage.

The sibling's newly read `7b416f76` envelope has public 9/10 versus short-only 5/10, five gains and one regression at beam/+0.45 m. It resolves the previously missing same-scene +0.60 m short-only baseline and qualifies nominal-loop execution. It leaves an endpoint-prediction boundary problem; its proposed calibration is not adopted in this frozen comparison. This new knowledge is disclosed before our runs, without expanding the four-case panel or changing its controller.

Licensed motions, decoded arrays and raw trajectories remain local. Publish scalar summaries, hashes and figures only. Full continuous planning banks, root and float640 motor input remain in both arms; logical joint payload is not end-to-end storage or wire savings.
