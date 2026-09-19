# Composer interface sync and the next representation question

September 18, 2026, local research date. This is a read-only supplement to the
[initial review](REVIEW_SYNC_20260918.md). The current repository began at
`e05c011693f5be2d499fb85bd4f0e6d215071a0e`; fetching origin found no incoming
commits; GitHub lists no open pull requests. The sibling checkout is now at
`7e0da0bb02364179b5eabd18766e5c9337c43546` (`research: qualify composer state and
native reference runtime`). Its uncommitted work was left intact. All 148 inputs
bound by our original continuation packet still matched before admission 02.
This sync does not import a newer controller or change the running experiment.

## Evidence read

Paths below are relative to the separate local
`/home/linjiw/groot-wbc-sonic-sim-trackb/docs/motion2scene/` checkout. They are
provenance pointers, not files distributed by this repository.

| Source | SHA-256 |
| --- | --- |
| `DUCK_COMPOSER_READINESS_20260918.md` | `e3a6267c642efc2fb1ef47b5e72bbff90372e35efc6d943e7d6c0479b5fcbc4a` |
| `DUCK_COMPOSER_INTERFACE_GATE_20260918.md` | `a5adfec4d6080ab2ee27f585eba6c3c2a6eb53a502a2cd74f3f65493fbcc1da5` |
| `evidence/duck-composer-interface-20260918/offline-audit.json` | `cc98d693175e3808f87ffbc6a4c722ac9128bf30b3534fa309cf9ceefe9ce39f` |
| `evidence/duck-composer-interface-20260918/native-audit.json` | `d2f102ad79e48b5586e0f1a10999e7a9f7c086145899cd0ba5c202937db9cef8` |

The sibling's four-recording audit covers 1,468 states: native tokens/actions
reproduce exactly, while maximum reconstructed body-position error is
`1.296722e-6 m`. Two new supplied-reference trials from its existing tick-83
learner prefix both finish; their historical physical arrays and scores match
exactly. Its separate cost is 734 control steps, 2,936 contact frames, 734 teacher
queries, zero retries and zero training updates. These counts are **not added to
our complete-task or continuation ledgers** and add no independent source motion.

## What can be reused, and what remains open

The public state builder uses named measured joints plus localized pelvis pose,
goal, timestamp and declared known map. FK constructs body geometry; simulator
body poses are auditor inputs only. Localization currently means zero-delay
simulator root pose, not a demonstrated onboard estimator. Native execution
retains the pinned 640D reference, normalized 930D history, batch-one
encoder/FSQ/decoder and noisy orientation features.

Its geometry requests remain **shadow requests**: they do not select motion.
The supplied online teacher still provides the reference. Thus exact parity
qualifies this interface on those histories, not a causal composer, a primitive
bank or recovery from new states. Root translation and desired support are not
direct fields in that 640D input; a shared external chunk contract still needs
them and needs an explicit adapter.

The native horizon is ten samples spaced 100 ms apart: the first-to-last span
is 0.9 s, requiring 46 dense frames at 50 Hz. The sibling source convention is
30 Hz, while our continuation inputs are resampled at 50 Hz. A future bank must
carry both source and execution time grids. Clean planned orientations and
noisy teacher features are different treatments; a token change between them
cannot be attributed only to composition.

## Next work package: selected transitions before a learned codec

The [sixteen-case registration](CONTINUATION_PROTOCOL.md) has now
[completed](CONTINUATION_ADMISSION02_RESULTS_zh.md): both methods pass 8/8, with
exactly matched incoming histories and zero continuous-adapter rebuild error.
This moves the question to **choosing a different valid continuation**, with
perturbation recovery registered separately. In that next gate, a continuous
failure, unmatched history or adapter failure stops expansion. A qualified
continuous success paired with Linear29 failure would justify a separate frozen
diagnostic of clipping, temporal interpolation and abrupt replacement.

The next implementation should share the sibling's qualified state/executor
contract rather than create a second autonomous controller. This is a work plan,
not an authorization or budget registration for another native batch:

1. **Build a small local primitive manifest.** Retain source ancestry, named
   q/qdot, root pose/velocity, both clocks and planned support with explicit
   unknown/valid masks. Include approach, lowering, trailing-body clearance,
   recovery and braking transitions. Keep references, measured contacts and
   issued actions separate. Existing authored clips are development material.
2. **Audit selection inputs offline.** Select/align from measured pose, velocity,
   executed history, goal and observed geometry. Task inputs cannot supply the
   correct clip or ground-truth phase. Library IDs and a selector's own cursor
   are internal state, and must be distinguished from hidden answer labels.
   Compare the same selected continuous chunk and its frozen Linear29 encoding;
   log unsupported candidates and abstentions rather than replacing them with
   favorable examples. Do not call an abstention a qualified safe stop.
3. **Register one bounded transition gate.** Freeze an ordered set of reachable
   incoming states and candidate choices before outcomes. Replay identical
   prefixes/history/RNG; qualify the unchanged continuous path, then execute
   an actual selected transition with each representation. Charge the prefix,
   root/phase metadata, padding, adapters and any blending equally. A newly
   anchored or blended Linear29 is a new treatment, not the current frozen one.
4. **Then test causal full episodes.** Remove supplied future and hidden phase;
   share the causal root planner and selector between representations. Keep
   full-reference controls, named transition tests and from-reset outcomes
   separate. Compare geometry rules and conservative crouch followed by recovery
   and stop. Freeze independently varied scenes before evaluating either method.

Selection latency, observed-state age, commitment length and the 0.9 s native
lookahead are interface constraints, not optional implementation details.
Unsupported continuous transitions imply a support/planning problem first;
codec-specific losses imply a representation problem. Learning starts only after
this distinction is measured. LLM retention remains the separate bounded
[interface branch](LLM_INTERFACE_PROTOCOL_zh.md); it does not replace the physical
question or gain motion semantics from copying an ID.
