# Public repository scope

This repository publishes project-authored research code, tests, protocols, reports, summary statistics and selected aggregate scientific figures.

The [GitHub Pages research atlas](https://linjiw.github.io/hindsight-motion-research/)
publishes only an explicit subset of these public summaries and figures. Its
interactive motion traces and obstacle envelopes are synthetic explanatory
diagrams, not licensed trajectories or recorded simulation replays. Future BFM,
navigation, language and scene-model interfaces are labeled as proposals. See
[website maintenance](../site/README.md) for its allowlisted build and provenance.

## Local-only materials

The following stay outside Git and are not part of this release:

- Licensed AMASS-derived source motions and G1 retargets.
- Teacher checkpoints, third-party robot assets and the separate SONIC/IsaacLab runtime.
- Raw trajectories, motion codebooks, native rollout arrays, action/latent targets and per-episode archives in `runs/`.
- Interactive viewers containing embedded motion trajectories, screenshots of those viewers and runtime logs.

The source dataset and runtime retain their own access and licensing requirements. Public availability of this repository does not grant redistribution rights to those materials. No new license is assigned to third-party materials or to this repository by this initial Git organization.

## Reproduction boundary

Pure geometry, editing and evidence-gate unit tests run with the declared Python dependencies. The IK integration test is explicitly skipped when its licensed reference or native robot URDF is absent. Native experiments additionally require the compatible external runtime, robot assets, checkpoint and locally generated run lineage.

Set `HINDSIGHT_RUNTIME` and `HINDSIGHT_TEACHER` for a different installation. `HINDSIGHT_PROJECT` defaults to the checkout directory. Historical configurations and reports preserve the original machine paths as provenance; adjust a copy of `configs/pilot.json` for new offline experiments. Do not overwrite historical run directories.

Links in historical reports to `runs/` or excluded viewers are local evidence pointers and will not resolve in a public clone. `results/` contains selected summary JSON snapshots with machine-specific home paths replaced by `<LOCAL_HOME>`. It contains no source motion arrays or checkpoint weights.

All current results are development studies. Simulation repetition and decoded descendants do not increase independent source coverage. No BFM or text-to-navigation student performance is claimed.

The September 18 small-LLM study publishes project-authored synthetic fixture
code and aggregate/per-case interface scores in `results/llm_interface.json`.
Its invented coordinate samples are not licensed motions or qualified robot
trajectories. Raw model responses, downloaded weights and the verbatim user
guidance remain local. This probe is not a language-controlled robot result.

The complete-task pilot additionally publishes aggregate counts, paired initial-state
differences and task durations, plus `artifacts/complete_task.png`. The figure
contains no motion trajectory. All eight native raw runs and source descendants
remain local; they are not additional canonical source pairs or student training.

The continuation registration publishes its unrun/attempt ledger and eight scalar
input-reference difference diagnostics, plus `artifacts/continuation.png`. No native
episode was launched in that closed packet. These offline summaries are not
motion trajectories, trained-model evidence, or physical switching qualifications.

The linked admission 02 publishes `results/continuation_admission02.json` and
`artifacts/continuation_admission02.png`: sixteen physical outcomes, eight
matched-state audits, scalar reference differences and source hashes. Both
methods pass 8/8 under supplied, same-phase references. Raw physical arrays and
licensed descendants remain local. This does not qualify an autonomous composer
or replace the historical zero-launch packet.
