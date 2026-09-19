# Research review and repository sync — September 18, 2026

This receipt records a documentation, literature and website reassessment. No model was fitted, no native batch was launched, and no existing run, registration or result summary was rewritten.

## Repository state inspected

- This repository began clean on `main`, at `fc85b01082c703fa31b3c7776152677adbee7c3b`. `git fetch --all --prune` found no new upstream commits; HEAD matched `origin/main`. GitHub reported no open PRs. No pull/merge was needed.
- The two latest research commits were `e739001` (CMU original/tuck acquisition and bounded wide/tuck follow-up) and `fc85b01` (clarified the fixed-wide hypothesis). The follow-up remains `deferred_resources`, not running.
- The separate local `groot-wbc-sonic-sim-trackb` checkout was inspected read-only at `33e4257c6f27f57549873f2fbb5acb00b5cea38d`, with tracked/untracked local work. After fetching its origin, its research branch was 99 commits ahead and 35 behind its tracking branch. That is divergence, not a fast-forward update; no merge, reset, stash or runtime change was performed.
- The sibling's current working documents include `docs/motion2scene/PROGRAM_REASSESSMENT_20260918.md`, its literature reassessment, and the dated goal-conditioned traversal plan. Their proposed complete-task composer/tracker direction informs this repository's representation role. Their current text includes uncommitted changes and is not a clean-release snapshot. No sibling score is pooled into our result ledger.

## Official SONIC upstream

Queried the official GitHub default-branch commits and PR bodies/files. The observed tip was `7f151314d4d1606544bf249d2a7a1cb754c64582` (September 15).

| Upstream change | Practical implication |
| --- | --- |
| [PR 240: motion_lib → deployment reference exporter](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/240), merged September 15 | Relevant to format/parity audits. The PR describes the missing training-motion-to-deploy conversion path. Its author-reported checks are not our local validation. |
| [PR 232: observation aliases](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/232), merged September 15 | Relevant to release-derived C++ deployment config names. Do not assume it fixes our IsaacLab experiment failures. |
| [PR 267: control and adaptive sampling fixes](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/267), merged September 3 | Includes deployment gain options and sampling changes. Applying them would change a controller/training contract; evaluate in a separate qualification lineage. |

Official upstream state and local research-branch history are different comparisons. We did not replace the frozen experiment teacher with the newest public release. The official [VLA interface documentation](https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vla_inference.html) also ties motion tokens to their checkpoint. The latest paper version checked is [SONIC v4](https://arxiv.org/abs/2511.07820v4), revised August 13; the former site linked v1.

## Evidence review scope

Read the pilot, critical, expansion, second-family, decoded execution, mechanism and carrier-scene results, their relevant protocols, the existing plans, dataset inventory, public release rules, and website sources. Inspected representation/instrumentation code for logical rates and the distinction between RVQ and native motor capture. This was not a line-by-line review of every simulator module or every raw episode.

The public `token_mechanism`, `decoder_execution` and `critical_dataset` JSON objects exactly matched their local run aggregates after the documented home-path sanitization. All four carrier-summary provenance hashes matched their referenced local files. The carrier geometry summary records 145 candidates, zero admissions and zero native episodes. Original receipts remain the source of truth.

| Public evidence snapshot | SHA-256 |
| --- | --- |
| `results/token_mechanism.json` | `743a709ad569a04a086b0b6134bca8bdda0919ba4b7d2095ad2fdd5cece05d17` |
| `results/decoder_execution.json` | `18fba6d7d7927ba63b310b6d505141ae77ed0a793477abdbdd9d6ff64bebb5b8` |
| `results/critical_dataset.json` | `0ec1e36c841a5aea77700965a5f4c28f95c19b1dc1711098f517b8e1772374db` |
| `results/carrier_scene.json` | `2b4d4062f262847a9e7386d3fdaef97e84c401f5112283dabe73509ee6650304` |

## What this revision changes

The plan prioritizes a complete traversal task, explicit interface contracts and a comparison with simple continuous and native motor representations. Hindsight acquisition remains a data/diagnostic method. The website adds a decision explorer, a whole-body task/interface diagram, a total-information-rate comparison, a revised roadmap and current primary-paper connections. The interface v2 document is a design proposal; no new controller capability is claimed.

The literature review records source versions and access scope. It is a targeted review, not an exhaustive survey. Website diagrams are explanatory, never recorded motion or new simulated outcomes. Public deployment uses the existing GitHub Pages allowlist, with no raw or licensed motion added.

## Verification of the revised artifacts

- Static allowlist build and HTML/asset/repository-link checks passed.
- JavaScript syntax and smoke checks passed: eight methods, five metrics, eight intervention states, six interface views, four research decisions, total-rate arithmetic and missing-evidence handling.
- Chromium checks passed at 1440 px, 390 px and 320 px: no page errors or horizontal overflow. Decision buttons, total-rate values and feedback view were exercised; desktop/mobile screenshots were visually inspected.
- All 41 local Markdown targets across the edited plans, review, interface, sync and index/maintenance documents resolved. Eighteen primary-paper entries were counted against the website description.
- Evidence snapshots and carrier provenance remained unchanged. Native experiments were not rerun. Local validation used the relevant documentation/site checks; the normal GitHub Actions public unit suite subsequently passed (25 passed, 1 skipped).

Publication: commit `4d848f6ce72c20d3cb52ce9966259e7505e77bf7` was pushed to `main`; [Pages build/deployment](https://github.com/linjiw/hindsight-motion-research/actions/runs/35410871947) and [unit tests](https://github.com/linjiw/hindsight-motion-research/actions/runs/35410871891) succeeded. The live HTML, JavaScript and CSS hashes matched the local allowlisted build; live provenance reports review/page date September 18 and evidence date September 16.
