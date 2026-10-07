---
Created: 2026-10-05
Last-Modified: 2026-10-07
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Development history

Timeline, releases, metrics, notable changes and the supply-chain (SBOM) story,
from git, pull requests and the CHANGELOG.
See [README.md](README.md) for the index, method and caveats.

Sources: `git log` of `main` at `b2a4dac` (2026-10-05), `gh pr list`/`gh pr
view`, `gh release list`/`view`, `CHANGELOG.md`, `pyproject.toml`, `.flake8`,
`codemeta.json`, `.github/workflows/`, `working-docs/implementation/`, the
pitloom `CHANGELOG.md` (local checkout). Dates are commit author dates or PR
merge dates (UTC). "PR #N" is a GitHub pull request; hashes are short SHAs.
Numbers marked (approx.) come from `git --shortstat` and include test fixtures.

## 1. Timeline

### 1.1 Phases

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Phase | Dates | Merged PRs | Commits (non-merge) | Theme |
| --- | --- | --- | --- | --- |
| P1 Bootstrap | 04-27 to 04-29 | 4 (#3, #4, #5, #8) | 40 | 3-tier matcher, cache, typed package; v0.1.0-v0.2.2 |
| P2 Markers and benchmark | 04-30 to 05-14 | 4 (#10, #11, #12, #16) | 43 | Exit codes, `is-*` commands, SPDX tag/marker detection, fixture corpus; v0.2.3 |
| (gap) | 05-15 to 07-05 | 0 | 0 in June | no activity |
| P3 Speed, normalisation, first SBOM | 07-06 to 07-20 | 6 (#19, #21-#25) | 16 | Probe gate, SPDX matching guidelines, Pitloom SBOM; v0.3.0-v0.3.2 |
| P4 Expressions and release hardening | 07-21 to 08-21 | 13 (#26-#39; 3 Dependabot) | 43 | SPDX expressions, release SBOM, Sigstore; v0.3.3-v0.3.7 |
| (gap) | 08-22 to 09-16 | 0 | few | no PRs |
| P5 Tech debt and robustness | 09-17 to 09-21 | 19 (#40-#60; 4 Dependabot) | 43 | Complexity refactors, CI gates, stderr grammar, Java removal, DB gate |
| P6 Input reading and output contract | 09-22 to 10-02 | 13 (#61-#73; 2 Dependabot) | 41 | Expressions in tags, blob perf, manifests, JSON Lines, exit codes |
| P7 Supply chain and release | 10-03 to 10-05 | 3 (#74-#76) | 4 | Build-hook SBOM, v0.4.0, SBOM signing |

<!-- markdownlint-restore -->

Commit counts are by author date; PR counts by PR number range (merge dates
fall within the phase). Merged PRs per month (GitHub `mergedAt`): Apr 4,
May 4, Jul 9, Aug 10, Sep 23, Oct 12. 56% of all
merged PRs (35 of 62) landed in the last 19 days (2026-09-17 to 10-05).

### 1.2 Releases (tags; GitHub release dates)

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Version | Date | Headline (PRs) |
| --- | --- | --- |
| 0.1.0 | 2026-04-28 | First release; known issue Apache-2.0 vs Pixar confusion |
| 0.1.1 | 2026-04-28 | Local caching of SPDX data, popularity data (#3) |
| 0.2.0 | 2026-04-28 | Revised matching for short vs long inputs; fixes Apache-2.0/Pixar (#4, issue #1) |
| 0.2.1 | 2026-04-28 | `--bold` (#5) |
| 0.2.2 | 2026-04-29 | PEP 561 typed package (#8) |
| 0.2.3 | 2026-05-13 | Predictable exit codes (#10), `is-spdx`/`is-open` (#11), licence marker detection (#12), default DB (#16) |
| 0.3.0 | 2026-07-09 | Query speed (#19), SPDX matching-guideline normalisation (#21), SBOM in wheel (#22) |
| 0.3.1 | 2026-07-09 | SBOM build actually enabled ("Forgot to enable in 0.3.0", #24) |
| 0.3.2 | 2026-07-20 | SQLite connection and import optimisation (#25) |
| 0.3.3 | 2026-07-28 | SPDX expression support with canonicalisation (#28) |
| 0.3.4 | 2026-08-11 | Operator casing `and`->`AND` (#31) |
| 0.3.5 | 2026-08-18 | Pitloom `embed-wheel` in PyPI workflow (#32) |
| 0.3.6 | 2026-08-19 | SBOM attached to release (#33); `GPL-2.0` -> `GPL-2.0-only` for bare text (#34) |
| 0.3.7 | 2026-08-20 | sdist/wheel attached, SBOM validated in-wheel (#36); SQLite connection leak (#37) |
| 0.4.0 | 2026-10-05 | 34 PRs (#38-#75); many breaking changes; tag `v0.4.0` points at `7085b66` (merge of #75), i.e. before #76 |
| 0.4.1 | 2026-10-06 | Signed release SBOM and provenance (#76); pinned release tooling, Windows database paths (#77) |
| 0.4.2 | 2026-10-06 | Lookups never create or write the database; read failures raise `DatabaseNotReadyError` (#80) |
| 0.4.3 | 2026-10-07 | An overlong licence ID ending in `+` is no match, not `DatabaseNotReadyError` (#82) |

<!-- markdownlint-restore -->

Eighteen releases in 163 days; five on the first two days (04-28/29), and
three patch releases in two days after 0.4.0 (10-06/07), driven by the
Pitloom integration. The
0.4.0 CHANGELOG section lists 5 Added, 22 Changed (8 marked **Breaking**),
2 Removed (both breaking), 25 Fixed, 1 Security bullet.

## 2. Quantitative metrics (as of `b2a4dac`, 2026-10-05)

### 2.1 Activity

- Commits: 287 total (230 non-merge, 57 merge). Active days with a
  non-merge commit: 48.
- Authors (git): Arthit Suriyawongkul 267, `Claude <noreply@anthropic.com>`
  10, `dependabot[bot]` 9, `bact` (GitHub web UI) 1 (`cd9f03d`, CITATION.cff
  regenerated).
- 228 commit messages carry `Signed-off-by` (DCO sign-off).
- Pull requests: 66 opened, 62 merged, 4 closed unmerged (#2 normalisation,
  #9 normalisation in SQLite, #42/#43 superseded Dependabot bumps). 9 merged
  PRs are Dependabot bumps (#26, #27, #30, #40, #41, #44, #45, #63, #64).
- Lines changed in merged PRs (GitHub counts): +85,155 / -18,552. Non-merge
  commits (`git --shortstat`, approx.): +146,322 / -59,789. PR #12 alone is
  +50,492/-10,432 over 2,066 files, of which 2,019 files (+33,051/-9,897)
  are under `tests/fixtures/` (benchmark corpus).
- Merge style: merge commits up to #68; squash merges for #69-#74
  (`81a747d`, `101dc57`, `cb19f5e`, `cb0e689`, `5cc90dd`, `4af5621`).

### 2.2 Size now

- `src/licenseid/`: 25 Python modules, 6,845 lines. Largest: `database.py`
  864, `markers.py` 773, `identifiers.py` 694, `matcher.py` 644, `cli.py`
  596.
- `tests/`: 49 `test_*.py` files; 14,738 lines of test Python (excluding
  70 `.py` fixtures); 662 `def test_` functions; 255
  `@pytest.mark.parametrize` decorators; **2,514 test cases collected**
  (`pytest --collect-only`, 2026-10-05). `tests/fixtures/`: 1,465 tracked
  files.
- `tools/`, `benchmarks/`, `scripts/` Python: 6,350 lines.
- `working-docs/implementation/`: 9 docs, 2,204 lines.
- Test-to-source ratio 2.15:1 (lines).

### 2.3 Growth by release (computed from tags)

| Tag | src lines | src modules | test lines (no fixtures) | `def test_` |
| --- | --- | --- | --- | --- |
| v0.1.0 | 734 | 5 | 333 | 9 |
| v0.2.3 | 3,181 | 8 | 1,172 | 44 |
| v0.3.0 | 3,928 | 11 | 1,248 | 51 |
| v0.3.7 | 4,236 | 12 | 1,682 | 72 |
| v0.4.0 | 6,845 | 25 | 14,738 | 662 |

Between v0.3.7 and v0.4.0 test code grew 8.8x and test functions 9.2x,
while source grew 1.6x and modules doubled (12 -> 25): the 0.4.0 cycle
was mainly refactoring, hardening and testing, not features.

### 2.4 Complexity ceilings (ratchets) over time

`.flake8` (McCabe `max-complexity`, `max-cognitive-complexity`):

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Commit | Date | McCabe | Cognitive | Trigger |
| --- | --- | --- | --- | --- |
| `30238d9` | 2026-08-19 | 23 (set) | 49 (set) | ceilings introduced at repo max |
| `138c6ec` | 2026-09-18 | 23 -> 19 | 49 | #47 `_normalize_single_id`: McCabe 23->11, cognitive 48->15 |
| `05b0764` | 2026-09-18 | 19 | 49 -> 46 | #48 `_detect_gpl_headers`: McCabe 14->8, cognitive 49->18 |
| `07d8b70` | 2026-09-18 | 19 -> 13 | 46 -> 29 | #49 `match()` McCabe 19->6, `_get_candidates` 13->1 |
| `80fb7d5` | 2026-09-18 | 13 -> 12 | 29 | #51 `fetch_popularity_data` McCabe 13->4 |

<!-- markdownlint-restore -->

Current: McCabe 12 (target 10), cognitive 29 (target 15; holder is a test
helper, `tests/test_accuracy.py::run_accuracy_test`).

`pyproject.toml` pylint:

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Setting | 04-28 (`9638d6c`) | 08-19 (`30238d9`) | 09-17 (`7e0070e`) | 09-19 (`ffaafab`) | now |
| --- | --- | --- | --- | --- | --- |
| max-args | 10 | 6 | 5 | 5 | 5 (target) |
| max-positional-arguments | 10 | 6 | 5 | 5 | 5 (target) |
| max-locals | 25 | 23 | 23 | 23 | 23 (target 15) |
| max-branches | 15 | 15 | 15 | 13 | 13 (target 12) |
| max-statements | 60 | 50 | 50 | 50 | 50 (target) |
| max-module-lines | none | 977 | 921 | 942 | 864 (target 800) |

<!-- markdownlint-restore -->

`max-module-lines` was lowered in ten steps from 977 (`30238d9`, 08-19)
to 864 (`cb0e689`, #72, 10-02); it briefly rose 921 -> 944 when
`matcher.py` grew during the #49 refactor (`07d8b70`), then fell as
`matcher.py` was split 888 -> 544 lines into `ranking`, `retrieval`,
`shorttext` (#58, 2026-09-21). The project rule is "don't raise a ceiling
to make a change pass; refactor instead" (`AGENTS.md`). PR #52 (09-19)
made strict mypy blocking in CI (it had been non-blocking) and added
flake8 complexity and pylint-on-tests to CI.

## 3. Notable changes and rationale

### 3.1 Architecture and accuracy

- Initial three tiers plus optional Java: Tier 0 short-text ID/name, Tier 1
  SQLite FTS5 trigram recall, Tier 2 RapidFuzz; Tier 3 SPDX `tools-java`
  validation, present from the initial commit `e7ae188` (04-28).
- #4 (04-28): separate logic for short inputs (<20 words) and long texts;
  CLI escape handling; resolves issue #1 (Apache-2.0 vs Pixar).
- #12 "License marker" (05-01 to 05-07, issue #6): Tier 0.5 detection of
  `SPDX-License-Identifier` tags and structured `license` fields; mixed-
  content fixtures; full benchmark. `threshold-optimizations.md` records a
  head_300 top-1 regression of -5.5 pp (597 vs 635 of 695 fixtures) fixed
  by lowering the Tier 0 threshold to 30 words and suppressing markers for
  short inputs (`fe67442`, 05-07). `accuracy-optimizations.md`: on 695
  SPDX licences, head top-50 recall 98.7% -> 99.9%, tail top-1 39-46% ->
  52-57%, union top-50 99.4% -> 100%.
- #21 (07-07): normalisation follows SPDX License List Matching Guidelines
  (spec v3.0.1 annex).
- #28 (07-27): SPDX expressions, structural canonicalisation via
  `py-spdx-license`; cap of 40 operators against super-linear cost.
- #34 (08-19): bare deprecated ID text redirects (`GPL-2.0` ->
  `GPL-2.0-only`).
- #58 (09-21): one sort key and one "or later" phrase reader
  (`classify.OR_LATER_PHRASE`); tie window exactly 0.01; "or any later
  version"/"or newer" -> `-or-later`.
- #60 (09-21): an unknown SPDX tag is no longer a certain match; `is-*`
  agrees with `match`.
- #61 (09-21 to 09-28): a tag is read as one whole expression; old regex
  read `(MIT OR Apache-2.0)` as nothing and
  `MIT OR (Apache-2.0 AND BSD-3-Clause)` as a certain `MIT` (PR body).
  `--id` narrowed to one licence (breaking).
- #65 (10-01): licence fields from package.json, pyproject.toml (PEP 621,
  PEP 639, Poetry), Cargo.toml, setup.cfg; `MIT/Apache-2.0` no longer read
  as MIT.
- #66, #67 (10-01): short inputs answer from their tag; lone expression
  `GPL-2.0+` read as `GPL-2.0-or-later` from any input; classpath and GFDL
  deprecated IDs redirected.

### 3.2 Performance (with numbers)

- Baseline (`speed-optimizations.md`): ~13,333 s over 59,738 benchmark
  queries (~0.22 s/query); target <100 ms for full texts.
- #19 (07-06) probe gate: profiling showed ~93% of `match()` time in
  RapidFuzz `partial_ratio`, ~5% SQLite; a 60-word mid-query probe with
  gate 0.52 skips full alignment for weak candidates. Benchmark wall time
  4,925 s -> 1,394 s (~3.5x), recall unchanged except small deep-N dips
  (source: developer's agent memory note `perf-probe-gate.md`, not in the
  repo; treat as secondary). A chunked-FTS5 alternative was prototyped and
  was slower.
- #25 (07-20) `speed-optimizations-round-2.md`: CLI cold start ~125 ms ->
  ~31 ms (lazy `requests`/`bs4` imports); a lookup ~3x (0.676 s -> 0.220 s
  over 1,317 calls); connection+query 0.51 -> 0.33 ms; one path 66 -> 11
  ms; accuracy within 0.18 pp on 675 fixtures. `score_cutoff` on
  alignment tried and reverted.
- #62 (09-30) blobs: 27 words plus one 2,000-char token took 5 s; 5,000
  chars ~60 s. Guards counted words, cost follows characters. First fix
  (chars-per-word limit) lost Japanese CC-BY-SA-2.1-JP (a 1,570-char slice
  fell from certain to 0.5), caught in review (`b9c315e`). Final: probe
  capped at 500 chars (partial_ratio 15 ms/candidate at 500, 43 ms at 600,
  136 ms at 1,000), scan capped at 6,000 chars
  (`tech-debt-resolved.md` item 16).
- #69 (10-02): one SQLite connection per `match()`: 4,000 distinct tags
  9 s -> 1.9 s; Tier 0 `score_cutoff` early stop: one 200,000-char word
  2.7 s -> 0.3 s; no answer changes.
- #72 (10-02): ID lookups from an in-memory table cache: 4,000 tags
  1.73 s -> 0.52 s; unknown ID costs no query; cache invalidated on
  `last_update_datetime` change. CHANGELOG sums #69/#72 as ">20x faster"
  for thousands of tags, ~9x for one very long word.

### 3.3 Security and robustness

- #51 (09-18) data fetching: `User-Agent`, single attempt, stale-cache
  fallback with warning, `--no-cache` never stale; atomic cache writes;
  version strings validated before use in a path or URL; tarball extracted
  with path-traversal checks (CWE-22); fixes for short CSV rows, corrupt
  caches, single-licence `ZeroDivisionError`. +1,603/-147.
- #50 (09-18): `RecursionError` on deeply nested JSON fixed; 69 tests.
- #37 (08-20): one SQLite connection leaked per query.
- #55 (09-19 to 09-20) database readiness gate (`dbcheck.py`): read
  commands exit 2 on missing/empty/invalid/unreadable DB; `update` and
  `--clear-cache` refuse a DB licenseid did not build (fail-closed on
  write, fail-open on read). Traps documented: a named pipe hangs a
  read-only open forever; `file::memory:NAME` is a disk file; URI and
  path spellings (`x`, `x/`, `x/.`). +3,353/-142, 35 files. Review rounds
  4-7 each found something (`database-readiness-gate.md`).
- #59 (09-21): one decoder (`textinput.py`) for CLI and API: UTF-8 with
  BOM dropped, else Latin-1 with warning, NUL = binary.
- Quadratic paths: `\s+[\s/*#]*` regex quadratic on long space runs (5 s
  at 32,000 spaces), rewritten `\s[\s/*#]*`; per-bracket re-slicing and
  per-tag rescans removed in #61; deep nesting kept from the parser (#61,
  #66; `spdx-expression-reading.md`).
- #70 (10-02) exit codes: Ctrl-C 130 (was 1, read as "no"), closed pipe
  141 quietly, unwritable stdout exits 2 with `ERROR: output: write
  failed` (was 0 or 120), closed stdin is no input, failing stderr no
  longer turns status into 120; 10 CLI-matrix cells fixed.
- #57 (09-20): `match()` rejects unknown keyword options (e.g. removed
  `enable_java`).

### 3.4 Removal of the Java tier

PR #54 (merged 09-19, `b92a2be`): removed `--java`, `licenseid[java]`,
`SPDX_TOOLS_JAR`, `enable_java`, `java_verified`. Rationale
(`tech-debt-resolved.md`): off by default, untested in CI, silent on
failure, so "removed instead of fixed"; match results unchanged. Same PR
added `tools/cli_matrix` (real shells, locales, stdio states vs a baseline
of known flags) and brought `cli.py`/`matcher.py` to 100% coverage
(+6,108/-286, 50 files).

### 3.5 CLI output grammar and result format

- #10 (05-01) predictable exit codes; #11 `is-spdx`/`is-open` for scripts/CI.
- #53 (09-19): stdout carries only results; diagnostics to stderr in
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`; `LicenseIdError`,
  `InvalidInputError`; a conftest guard fails any test printing a
  non-conforming line. +1,519/-257.
- #73 (10-02): click's usage errors reworded into the same grammar
  (`ERROR: option: not found: --bogus; did you mean --bold`); bare
  command prints help to stderr with exit 2.
- #68 (10-02): every result has the same nine keys, `score` capped to
  0-1, `method`, `exact`; `--json` prints JSON Lines canonicalised per
  RFC 8785 (JCS, new dependency `rfc8785`); text line adds `METHOD=`,
  `EXACT=`, `SCORE=`; `--exact`; `--threshold` 0-1. Four breaking bullets
  in CHANGELOG. +1,891/-907, 34 files.

### 3.6 Metadata consistency

- `CITATION.cff` added 04-29 (`45cf9c2`), DOI 10.5281/zenodo.19881009
  (`bffa85d`). Since 09-19, `codemeta.json` is the source and
  `.github/workflows/codemeta2cff.yml` (caltechlibrary/codemeta2cff,
  cff-validator) regenerates `CITATION.cff` (`cd9f03d`, `dc9c336`).
- #71 (10-02): one description and one keyword list (same order) across
  `pyproject.toml` and `codemeta.json`.

## 4. Supply chain and SBOM

### 4.1 Chronology

<!-- markdownlint-capture -->
<!-- markdownlint-disable MD013 -->

| Date | PR / commit | Change |
| --- | --- | --- |
| 07-07 | #22 `8f5649f` | SBOM generated by Pitloom as a Hatchling build hook and embedded in the wheel (fixes issue #20) |
| 07-09 | #24 `f52991a` | Hook actually enabled ("Forgot to enable in 0.3.0"); v0.3.1 |
| 07-10 | `faf72ed` | pitloom 0.12.0 |
| 08-18 | #32 `d552033` | Pitloom 0.16.0 GitHub Action `embed-wheel` in PyPI workflow "for more complete SBOM"; v0.3.5 |
| 08-18 | `71aba0e` | Pitloom content-type detection enabled |
| 08-19 | #33 | SBOM (`licenseid-<v>.spdx3.json`) attached to GitHub release; v0.3.6 |
| 08-19 | #36 | sdist/wheel attached; SBOM validated as extracted from the wheel, not the pre-embed file; v0.3.7 |
| 08-21 | #39 `5c203bb` | Sigstore signing and `actions/attest-build-provenance` for release files |
| 09-17 | `4c49802` | hatchling capped below 1.32.1: it made `BuildHookInterface` a 2-type-parameter generic and pitloom's hook (<=0.18.0) crashed at registration, breaking every CI job (co-authored by Claude Sonnet 5) |
| 09-17 | `9731876` | pitloom 0.18.0 |
| 09-30 | #64 | Action bump to pitloom 0.19.0 |
| 10-03 | #74 `4af5621` | Build hook only; re-embed dropped; magika; checks in `build.yml` and `pypi-publish.yml` |
| 10-05 | v0.4.0 | Released from `7085b66`, pre-#76: assets are wheel, sdist, their `.sigstore.json` bundles and `licenseid-0.4.0.spdx3.json` (no SBOM signature bundle) |
| 10-05 | #76 `22da8f4` | SBOM signed and attested; release checks mirrored from Pitloom |

<!-- markdownlint-restore -->

### 4.2 What was wrong (through 0.3.5-0.3.7 and up to #74)

The release SBOM came from a second step: the Pitloom Action's
`embed-wheel` rescanned the finished wheel and re-embedded an SBOM.
Per #74 and the comment it added to `pypi-publish.yml`, the rescan recorded
hashes for `RECORD` and for the SBOM itself that the embedding then made
stale, and the re-embedded SBOM "lost fields". Pitloom's own 0.20.0
CHANGELOG (released 2026-10-05) lists the corresponding upstream fixes:
"`embed-wheel`, `wheel --embed`: embedded hashes stay valid"
(pitloom #271); "`embed-wheel` with a project directory emits the concluded
licence, as `loom project` does" (pitloom #243, #248); "Release SBOM is
the build hook's, not a re-embedded one; checked, attached to the release
byte-identical, signed and attested" (pitloom #275); also wheel SBOMs
list payload only, not `.dist-info` (#271). The old licenseid workflow
also only checked presence at the PEP 770 path with a shell `unzip`
loop, then ran `spdx3-validate`.

### 4.3 How it was fixed

- #74 (2026-10-03, +92/-60): the SBOM is embedded only by the Pitloom
  Hatchling build hook (`[tool.hatch.build.hooks.pitloom]`); the Action
  re-embed step is removed; build requirement
  `pitloom[content-type]>=0.19.0` with `[tool.pitloom.content-type]
  method = "magika"` (detect file content type from bytes; fail the build
  rather than guess from extension); new `check-wheel-sbom.sh` run in both
  `build.yml` and `pypi-publish.yml`; the release attaches that same SBOM.
- v0.4.0 bump (`e143562`, 10-05): build floor raised to
  `pitloom[content-type]>=0.20.0`.
- #76 (2026-10-05, +496/-73): copies Pitloom's
  `scripts/extract_wheel_sbom.py` and `scripts/check_sbom_license.py`
  (replacing the shell script). Release job now: exactly one
  `*.spdx3.json` in the wheel, matching its `RECORD` hash, every file's
  content type from magika (`--require-magika`); `loom verify-wheel
  --fail-on-mismatch` (PEP 770 location); SBOM declares and concludes
  Apache-2.0, in both embedded and extracted copies; `loom
  validate-wheel`; `spdx3-validate` 0.0.7 as a hard gate (schema/SHACL).
  Sigstore signs wheel, sdist and SBOM; build provenance attestation over
  all three; `.sigstore.json` bundles attached. Same checks in
  `build.yml` (Python 3.10-3.14 build matrix). First real run is the next
  release (signing runs only on a published release).
- Other supply-chain hygiene: all Actions pinned by commit SHA;
  OpenSSF Scorecard workflow with CodeQL SARIF upload; PyPI trusted
  publishing (OIDC, `environment: pypi`); Dependabot for Actions;
  `py-spdx-license<0.1` upper bound (#56).
- The SBOM format is SPDX 3 JSON-LD (`.spdx3.json`); README states
  licenseid is the licence detection engine used by Pitloom, same
  maintainer, so the two projects co-evolved (licenseid is both a Pitloom
  user and a Pitloom dependency).

### 4.4 Release SBOM tooling pinned (PR #77, 2026-10-06)

- Prompted by ntia-conformance-checker PR 462 (publish only after the SBOM
  is validated; attach, sign and attest after the publish; re-runnable).
  licenseid already had that order (#76), so the PR kept only the gaps:
  artifact retention 3 → 60 days (so "Re-run failed jobs" works after a
  failed sign; a full re-run rebuilds a different wheel that PyPI rejects),
  a pin file, and `SECURITY.md` (how to verify release files).
- Release SBOM generator unpinned was a reproducibility gap: the hook ran
  whatever Pitloom was newest (`>=0.20.0`). `.github/requirements-release.txt`
  pins Pitloom, magika and spdx3-validate via `PIP_CONSTRAINT`.
  **Measured**: a constraint reaches the isolated build (a conflicting
  `pitloom==0.19.0` made `python -m build` fail against the `>=0.20.0`
  floor); the pins resolve on 3.10 and 3.14.
- Design choice recorded: hook-embedded SBOM, extracted byte for byte, not
  re-embedded by the Pitloom Action. Re-embedding rescans the finished wheel
  and would record stale `RECORD` hashes (workflow comment, from Pitloom).
- Tested in a scratch copy that `pip install -e .` was not needed in the
  release build job; all SBOM checks passed without it (Python 3.14).
- The SBOM check on pull requests runs once (3.14) instead of per matrix
  entry; the SBOM does not depend on the interpreter.

## 5. AI-assisted development evidence

- Agent instruction file: `AGENTS.md` (184 lines at initial commit
  `e7ae188`, 04-28; 498 lines now), with `GEMINI.md` (04-28) and
  `CLAUDE.md` (08-19, `e5a580e`) as symlinks to it, plus
  `.github/copilot-instructions.md`. 43 commits touch `AGENTS.md`, 39 of
  them in Sep-Oct: it accumulates a "Traps and test patterns" section of
  lessons from earlier sessions (quadratic regex, CJK limits, SQLite
  in-memory lifetimes, `HOME` and the real cache).
- Explicit attribution is sparse: 10 commits authored by
  `Claude <noreply@anthropic.com>` (all 2026-07-27, PR #28, branch
  `claude/spdx-license-parsing-stmj2p`, PR body links a claude.ai/code
  session), each with `Co-Authored-By: Claude Sonnet 5`; one more
  co-authored commit `4c49802` (09-17, hatchling cap). PR #61 body ends
  "Generated with Claude Code". All other commits are authored by the
  developer; the developer commits and pushes (agents work read/write
  locally only), so most agent work is not attributed in git metadata.
- Review loops visible in history: "Fix crash and regression found in
  independent review" (`8ed15a7`, 07-27), "Fix per review" (`ba0e6dc`,
  09-20), "Fix bugs from review" (`c2b0e1d`, `92dc12a` 09-21; `706e7c3`
  09-23). `database-readiness-gate.md` (#55) records review rounds 4-7
  and the lesson "count findings per surface, not per round"; #62's
  Japanese regression was caught by a review round after the first fix
  passed all tests (`b9c315e`). PR #48 notes characterization and
  adversarial tests; `AGENTS.md` mandates characterization tests first
  (`# BUG:` pins), mutation checks, and `tests/test_option_matrix.py`.
- PR bodies follow the `AGENTS.md` format (What changed? / Why? /
  Breaking changes?, or short bullets); several cite measured numbers
  (#47-#51, #69, #72).
- Effect on the codebase: the 0.4.0 cycle (09-17 to 10-05, 35 PRs, #40-#76)
  produced 590 new test functions and 2,514 collected cases, against
  1.6x source growth (Section 2.3).

## 6. Dependencies (now, `pyproject.toml`)

Runtime: `beautifulsoup4>=4.15.0`, `click>=8.5.0`,
`py-spdx-license>=0.0.1,<0.1`, `rapidfuzz>=3.14.5`, `requests>=2.33.0`,
`rfc8785>=0.1.4,<0.2` (#68), `typing_extensions>=4.16.0`. Build:
`hatchling>=1.32.3`, `pitloom[content-type]>=0.20.0`. Python >=3.10;
classifiers 3.10-3.14; CI tests 3.10 and 3.14, builds 3.10-3.14;
`Development Status :: 4 - Beta`. Licence Apache-2.0.
