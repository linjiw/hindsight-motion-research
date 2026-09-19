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

The subsequent [continuation adapter](CONTINUATION_PROTOCOL.md) implements actual-prefix replay, coherent native-reference replacement and history/RNG audits for eight paired incoming states. Its resource wait expired with **zero native launches**. The CPU conversion/input diagnostics in the [status report](CONTINUATION_RESULTS_zh.md) do not physically qualify the handoff hook or establish the general v2 API.
