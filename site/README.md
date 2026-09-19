# Research website

Public site: https://linjiw.github.io/hindsight-motion-research/

The page is a dependency-free static research atlas. It explains the current
representation and experimental evidence, then labels proposed navigation, BFM,
language and scene-model extensions. The synthetic trace and obstacle envelopes
are explanatory diagrams, not licensed motion or simulated rollout visualizations.

The September 18 research revision puts a complete traversal task and competing
motion interfaces first. The decision explorer separates current evidence from
proposed tests; the roadmap and typed-interface document are design proposals.
The literature section points to 20 primary papers with explicit reading scope.
Historical mechanism evidence remains dated September 15–16. The subsequent
September 18 complete-task pilot adds a separate physical ledger, described below.
A separate September 18 CPU-only Qwen3-0.6B probe has 24 synthetic
interface responses, 0/12 relay and 2/12 sidecar successes. Its two-route
explorer and JSON summary are explicitly separate from physical evidence. Keep the review date separate from the evidence date in provenance.

Build and check from the repository root:

```bash
python3 scripts/build_site.py
node --check site/app.js
node scripts/check_site.mjs
python3 -m http.server 8765 --directory _site
```

Open http://localhost:8765. The build requires only Python's standard library;
the JavaScript smoke check requires Node. No native experiments are launched.

`scripts/build_site.py` copies an explicit allowlist of static sources, public
result summaries, and approved aggregate figures into `_site/`. It validates
local asset/section links and repository file links, writes SHA-256 provenance,
and guards the dated narrative against changed headline evidence. It never reads
`runs/`, licensed data, codebooks, teacher weights or embedded motion viewers.
Do not replace this with a recursive repository upload.

Charts and intervention outcomes load the public JSON summaries. Update the
dated prose and snapshot guard together when publishing new evidence. Preserve
the distinction between canonical acquisition pairs and representation repeats,
between the decoder and mechanism studies, and between results and proposals.
The source summaries remain the authority; hard-coded tokenizer payload rates
are defined in `clearance_tokens.py` and the mechanism report.
The total-rate view adds the common 11,200 bit/s root stream and still excludes
entry/model/container costs. The build guards acquisition and canonical coverage
as well as mechanism totals. Run the smoke check for all metrics, decisions,
interfaces and the unavailable-evidence state after editing the app.

The Pages workflow builds and checks on matching pull requests, and deploys on
matching pushes to `main` or manual dispatch. GitHub repository Pages settings
must use GitHub Actions. Only `_site/` is uploaded. The page uses relative asset
URLs so it works under the repository's Pages path. Web fonts are optional, with
system fallbacks. No client data is stored and no analytics are included.

A separate September 18 complete-reference native pilot adds eight episodes,
2,079 control steps and 8,316 physics contact frames. Both continuous and Linear29
with reset anchors pass 4/4 under the existing goal050/recovery/stop profile.
The new task matrix/table and aggregate figure are separate from the historical
440-preflight / 312-main ledger and from the synthetic LLM probe. The remaining
matched-state and causal-composer matrix rows stay proposed.

The matched-state continuation subset is now implemented and registered. Its
300-second resource gate expired: 16 planned cells, 0 native attempts, all unrun.
`continuation.json` and the aggregate figure separate offline input-reference
differences from physical outcomes. Do not turn an unrun cell into a failed task
or merge it into the prior eight-episode complete-reference ledger.
