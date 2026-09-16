# Research website

Public site: https://linjiw.github.io/hindsight-motion-research/

The page is a dependency-free static research atlas. It explains the current
representation and experimental evidence, then labels proposed navigation, BFM,
language and scene-model extensions. The synthetic trace and obstacle envelopes
are explanatory diagrams, not licensed motion or simulated rollout visualizations.

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
result summaries, and one approved aggregate figure into `_site/`. It validates
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

The Pages workflow builds and checks on matching pull requests, and deploys on
matching pushes to `main` or manual dispatch. GitHub repository Pages settings
must use GitHub Actions. Only `_site/` is uploaded. The page uses relative asset
URLs so it works under the repository's Pages path. Web fonts are optional, with
system fallbacks. No client data is stored and no analytics are included.
