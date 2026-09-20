# Motion interface v2 — proposed contract

Design draft, September 18, 2026. **Not an implemented runtime API or a new experiment registration.** Existing v1 collection contracts and masks remain authoritative for recorded data. This document connects the [research plan](RESEARCH_PLAN_zh.md) to a future implementation without making BFM, SONIC, VLA and motion-code IDs interchangeable.

## Semantic boundaries

| Layer | Producer → consumer | Meaning | Compatibility obligation |
| --- | --- | --- | --- |
| Task request | Human / LLM / route manager → behavior planner | Destination, terminal condition, grounded constraints | Units, reference frame, timestamp, object grounding, supported capability |
| Observation | Sensors/state estimator → scene memory and planner | Causal proprioception, action history, observed geometry | Sensor calibration, freshness, visibility and unknown masks; declared localization assumption |
| Motion chunk | Composer / BFM / VLA → reference adapter | A proposed short future whole-body continuation | Time grid, incoming-state alignment, joint/link schema, desired contacts and support bounds |
| Motion code | Optional codec inside the chunk path | Compressed reconstructable motion | Codec version, precision, all side channels, valid lengths, decoder and lookahead |
| Native motor target | Controller-specific encoder / student → motor decoder | Input meaningful to one compatible checkpoint | Checkpoint hash, quantizer/normalization, native ordering/history/rate |
| Action | Motor → actuators | Current 29D scaled joint-target action in this setup | Offsets, scale, gains, limits, actual executed action and timestamp |
| Feedback | Measured execution → planner/agent | Progress, active/blocked/replan/complete, support status | Actual task scorer, sensor validity and reason; clip end is not completion |

A BFM's arbitrary control mask is not a scene-validity mask. Unspecified contact is not forbidden contact; missing geometry is not free space; zero velocity is not a missing velocity instruction.

## A small typed envelope

Illustrative fields, not launchable data:

```text
TaskRequest
  schema_version, request_id, timestamp_s
  goal: {frame_id, position_m, heading_rad?, availability}
  terminal: {profile_id, posture?, speed_limit_mps, hold_s, deadline_s}
  constraints: [{body_or_object_id, type, value, units, availability}]
  allowed_contact_profile, requested_capability

ObservationContext
  timestamp_s, frame_id, pose_estimate, pose_uncertainty
  proprio_history, executed_action_history, sample_times_s
  geometry: {encoding_id, metric_payload, observed_mask, unknown_mask}
  sensor: {calibration_id, source_time_s, latency_s}

MotionChunk
  schema_version, embodiment_id, reference_schema_id, adapter_id
  source_observation_time_s, start_time_s, dt_s, valid_length
  incoming_state_digest, committed_prefix_length
  local_root: {translation_or_velocity, orientation_convention}
  body: {joint_or_link_schema, positions, velocities_or_derivation_rule}
  contact: {desired_state, specified_mask, body_link_ids}
  uncertainty_or_support: {method_id, calibrated_domain, estimate}
  encoding: {kind, codec_hash?, payload, side_channels}

ExecutionFeedback
  request_id, last_executed_chunk_id, timestamp_s
  status: active | blocked | replan | unsupported | complete
  measured_progress, task_component_outcomes, observation_validity
```

Terminal numerical values are bound by a separately registered task profile, not inherited from the old moving-arrival scorer. Stop/recovery profiles must be implemented and qualified before advertising the corresponding capability. A request outside support returns an explicit status; a stop command is only a fallback if stopping is supported from the current state.

## Two adapters, not one latent identity

**Reference adapter:** decode a chunk into metric references, transform the local root consistently, compute velocities under the declared rule, and pack the exact reference history/horizon expected by the frozen tracker. Linear29 is the simple codec baseline. Moving from original full-rate root to predicted root increments is a new information condition, not a free codec improvement.

**Native motor adapter:** predict checkpoint-specific decoder tokens from causal state/context. The recorder currently captures a 64D floating-point vector and 930D decoder proprioception. Floating-point storage does not determine whether the latent was quantized. Inspect the pinned encoder/FSQ/config path and any residual before claiming native token cardinality or coding rate. A new checkpoint invalidates an assumed shared coordinate meaning even if it also accepts 64 values.

Current native actions are scaled joint-target coordinates, not torques. Reuse requires the recorded IsaacLab ordering, default offsets and per-joint action scale. Human motion encodings, reference RVQ indices, native motor vectors and language tokens have separate schemas.

## Timing and replanning

Use actual elapsed timestamps and executed history. Declare the chunk horizon, replanning frequency, encoder lookahead and end-to-end latency. A suggested initial horizon range of 0.3–0.6 s is a design search range, not a tested local setting or permission to change registered 50 Hz control.

The planner may predict a future chunk from past observations. The offline encoder may read a complete training trajectory. The deployed actor must never read the target's future trajectory, clip ID, reference phase or future-derived event label.

Carry a committed prefix when replanning, but test transition support rather than assuming interpolation preserves balance. Continuity should include incoming posture/velocity and contact/support timing. A chunk cannot silently reset a history buffer. Replanning latency must be measured together with the motor command delay.

## What generalization would mean

Start with a common semantic task/chunk contract and embodiment-specific adapters. Human and robot motions can share event timing and body-relative geometry while retaining robot size, limits and contact identity. Learn alignment only from verified correspondences; normalization alone is not embodiment transfer.

Tests for compatibility, in order:

1. Offline frame/unit/joint/clock roundtrip and finite/mask validation.
2. Identical-input encoder/decoder parity under the pinned checkpoint and complete history.
3. Physical continuation from matched incoming states, including transitions and stop.
4. New task requests produced causally by the planner; recovery on its actual histories.
5. A second encoder/decoder or embodiment with declared adapter training, then unseen tasks. Distinguish zero-shot, adapter-trained and fully retrained results.

An LLM can emit the task envelope through a tool call; a VLM grounds observed entities; a VLA can emit continuous chunks or motor outputs through a typed head. None requires arbitrary integer codes to become natural-language words. Compare any language frontend with the same structured task supplied directly.

## Evidence views and reusable records

Retain chronological episodes and separate actor, teacher-only and target views. Keep original/edited/decoded/reference/executed trajectories distinguishable. Record planned target, actual executed action, teacher query state and support separately. Do not pair a teacher action from a different state with the student's history.

Support is per objective: geometry, empty-scene execution, original-reference fidelity, task completion, motor imitation, relationship and recovery. Missing/unexecuted is not failure. Failed contrast runs remain outcome evidence and are not promoted to successful imitation.

Every descendant inherits source ancestry. Freeze splits before codec training, quantile/range fitting, scene variants, mirror transforms and caption generation. Existing development scenes cannot become held-out because a new tokenizer reads them.

## Contact and perception extensions

First implement obstacle-avoiding whole-body motion with ordinary foot support. Future hand/arm support adds explicit contact roles, timing, measured forces and allowed surfaces. Never reinterpret the current forbidden-obstacle-contact labels as evidence for supported manipulation.

Start scene conditioning with metric object sets and a complete-map flag. A sensed successor needs 3D or layered support/side/ceiling geometry, visibility and unknown state, and memory while overhead obstacles leave view. A floor-only heightmap cannot express general overhead free space. Rich 3D geometry also needs a bounded computational budget; benchmark the simplest representation adequate for the task.

Required feedback for future agents is functional: goal progress, blocked route, replan reason, request completion and observation validity. Raw training identifiers and implementation diagnostics are not mission-level commands.

## Small-LLM validation attachment

The separately versioned [L0 probe](LLM_INTERFACE_PROTOCOL_zh.md) implements a synthetic subset of these semantics. It does not implement this runtime API or qualify robot trajectories. Compare full record relay with ID selection plus immutable sidecar. Bind IDs to the current observation/catalog and reject invented IDs or altered frames, clocks, support and terminal fields. Sidecar integrity and semantic choice are separate gates. Null means a declared unsupported/unknown request, not a physically qualified emergency stop. See the [measured CPU probe](LLM_INTERFACE_RESULTS_zh.md).

## Complete-reference support attachment

The [registered reference pilot](COMPLETE_TASK_PROTOCOL.md) implements a narrow adapter comparison under the existing goal050 complete-task profile. [Both routes pass 4/4](COMPLETE_TASK_RESULTS_zh.md) with exact matched reset/history/dynamics; Linear29 includes two charged reset-anchor frames and the original root. This establishes no general v2 API, arbitrary-state switching or causal-composer qualification.

The subsequent [continuation adapter](CONTINUATION_PROTOCOL.md) now has [physical qualification on eight paired incoming states](CONTINUATION_ADMISSION02_RESULTS_zh.md): continuous and Linear29 each pass 8/8; reset, prefix and incoming state/history errors are zero, RNG matches, and native continuous reconstruction is exact. This establishes same-phase, unperturbed supplied-reference handoffs on two development clips. A general v2 API, cross-family transitions and disturbance recovery remain unqualified. The original zero-launch deferral is retained separately.

The [sibling interface sync](COMPOSER_SYNC_20260918.md) adds a compatible measured-state/executor contract to reuse. Its native horizon spans 0.9 s, requiring 46 dense frames at 50 Hz; retain source and execution clocks explicitly. Planned support validity and root translation remain external composition constraints. Preserve the distinction between clean planned orientations and native noisy reference features.

## Public-selector representation attachment — September 19

The [selected-reference pilot](SELECTION_CODEC_RESULTS_zh.md) now completes two
familiar known-map tasks per method from reset. A fixed continuous planner bank
chooses nominal or duck and retimes from measured state; Linear29 changes only
the q/qdot sent to the motor. Both paired entries and historical continuous
controls match exactly. All 1,451 new issued references and true committed source
indices replay exactly on actual histories. This qualifies a narrow nonlearned
controller, not arbitrary-state switching or a general composer.

Retain dense source indices through commitments: a new-tail scalar cursor can
mislabel the current committed frame. The planner still stores full continuous
motions, root, collision and support metadata, and the motor receives decoded
float references. This is no measured system-memory or wire-rate reduction.

The [completed scene screen](SELECTION_BOUNDARY_ADMISSION02_RESULTS_zh.md) now
contains six executed cells: both methods pass the shift, contact the lower beam,
and time out outside the farther goal. Its earlier 719-state no-response diagnosis
remains scoped to that old selector. The sibling's new one-decision exit composer
has continuous support; our [offline codec preflight](DISTANCE_CODEC_PREFLIGHT_zh.md)
replays all 1,528 public-history states but does not qualify Linear29 execution.

Treat commitments and forecasts separately. The raw codec preserves the five
committed frames between short/loop options, while interpolation shifts branch
changes into earlier forecast samples and the first goal-dependent output from
tick 127 to 126. The analytic blend velocity also differs from position finite
differences. Declare these semantics before a new native comparison; charge any
boundary anchors or velocity sidecars in separately versioned adapters. Keep
composed indices, donor ancestry and synthetic support masks distinct. A valid
ID or intact language sidecar does not establish free-running goal response.


The [distance-codec comparison](DISTANCE_CODEC_ADMISSION02_RESULTS_zh.md) now passes continuous 2/2 and Linear29 1/2. The farther-goal Linear29 request correctly prefers loop, but actual clearance misses the fixed decision at tick 126; clearance opens at 134 without a second query. The two Linear29 goal runs have identical references/actions/states throughout their shared 368 ticks. Continuous-history shadows therefore overstate the free-running response. The original zero-launch deferral remains immutable.

## Request lifetime and state-dependent admission — registered diagnostic

Record `requested_at`, requested route, measured clearance and its units, `pending_reason`, `accepted_at`, commitment deadline, selected route and actual completion separately. A valid request or motion ID is not an accepted physical transition. Preserve the five committed frames and an explicit expiration rule; do not reset the composed clock or falsify history to accept a late request. Missing a window should be reported as unsupported, not as successful execution or a qualified safe stop.

The [registered temporal-admission wrapper](PENDING_EXIT_RESULTS_zh.md) latches the old request at 126 and rechecks clearance only through the proven common deadline 162. Three physical retention controls exactly preserve their old trajectories; the only case that would exercise delayed acceptance remains unrun after queue SIGTERM during memory waiting. Its 134-acceptance shadow changes physical horizon q/qdot samples 7–9, beginning +0.70 s ahead, while preserving the five dense committed frames. Use the official native unpacker: 640D storage blocks are not physical frames. Neither the shadow nor the successful no-delay controls qualify delayed execution. [Admission 02](PENDING_EXIT_ADMISSION02_RESULTS_zh.md) also closed without launch, this time on its normal 300-second resource timeout (15 samples, zero qualifying). Preserve both closures; check capacity before a fresh admission for the same remaining case. The sibling’s calibrated continuous success is recorded [separately](PENDING_CONTROLLER_SYNC_20260920_zh.md), with a different tick-167 deadline.

The sibling's executed-endpoint model now has separate continuous-controller evidence, 12/12 versus 11/12. Endpoint estimates must declare controller, reference/codec, state and execution provenance. Our exploratory shadows still find the Linear29 gate closed; continuous calibration after decoding remains a compatibility hypothesis. Prediction errors use XY, whereas the frozen task scorer uses 3D goal distance; see the [metric correction](DISTANCE_METRIC_CORRECTION_20260919.md). Neither field fidelity nor a continuous calibration fit qualifies a decoded loop or broader reset support.

A subsequent sibling actual-reset screen also loses the loop with continuous
references after moving the start backward 10 cm. The proposed timing profile
must distinguish five committed control ticks from revisable later forecasts;
it does not preserve every future sample previously visible to the motor.
Identical current frames can yield different actions when forecasts change.
See the [separate reset snapshot](../results/reset_controller_sync.json).
