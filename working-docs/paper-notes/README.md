---
Created: 2026-10-05
Last-Modified: 2026-10-07
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Paper notes — index

Raw material for an academic write-up of licenseid: the system, its
evaluation, its supply-chain work, and how one developer built it with AI
coding agents. These are notes, not a draft. Every claim cites a source
(repository file and line, pull request, commit, or session transcript and
timestamp) so that it can be checked before it is cited.

Covers 2026-04-27 (first commit) to 2026-10-07 (v0.4.2, PRs #76 to #82).

## Files

| File | Content |
| --- | --- |
| [system-design.md](system-design.md) | Tiers, scoring, normalisation order, database gate, caches; rejected paths |
| [results-and-findings.md](results-and-findings.md) | Datasets, accuracy, speed, technical findings (RapidFuzz, SQLite, SPDX, streams) |
| [process-and-validity.md](process-and-validity.md) | Process lessons in the repo; threats to validity; open questions; future work |
| [history.md](history.md) | Timeline, releases, metrics, complexity ratchets, SBOM chronology |
| [ai-sessions-early.md](ai-sessions-early.md) | Human–AI sessions, July to mid-September: decisions, mistakes, patterns |
| [ai-sessions-recent.md](ai-sessions-recent.md) | Human–AI session, 19 September to 5 October: decisions, mistakes, patterns |

## Method

Compiled on 2026-10-05 by four read-only agents, then merged and edited:

- the repository's `working-docs/`, `AGENTS.md`, `README.md`,
  `benchmarks/summary.md` and `tests/fixtures/README.md`;
- `git log` (287 commits), 62 merged pull requests, releases and
  `CHANGELOG.md`;
- four Claude Code session transcripts (2f8ddbaf, 1e8f3cea, 60627469,
  b30f2d8e), reduced to user-typed messages, assistant text and compaction
  summaries (no tool output), plus the agents' persistent memory files.

Session citations read `[session-prefix timestamp]` (UTC). The transcripts
stay outside the repository; the extracts were made in a scratch
directory and are not kept. Counts of review rounds per PR are
approximate. Remarks marked **[observation]** are a compiling agent's
inference, not a claim made in the repository.

## Project at a glance

- SPDX licence identification from text, IDs, names, tags and manifest
  fields. Tiers: 0.5 markers (tags, `license` fields), 0 short text (IDs,
  names), 1 SQLite FTS5 trigram recall, 2 RapidFuzz ranking. A Java tier
  (SPDX `tools-java`) was removed on 2026-09-19.
- Python ≥3.10, Apache-2.0, 25 modules and 6,845 lines in `src/`; 14,738
  lines of tests, 2,514 collected test cases (2026-10-05).
- 15 releases in 161 days; 35 of the 62 merged pull requests landed in the
  last 19 days, mostly hardening and testing: between v0.3.7 and v0.4.0
  test code grew 8.8x and source 1.6x.
- One developer, who makes every commit, push and merge; AI agents work
  locally. Explicit AI attribution in git is sparse (10 commits).
- licenseid is the licence engine of the Pitloom SBOM generator, by the same
  maintainer, and Pitloom builds licenseid's own SBOM.

## Candidate angles for a paper

1. **Hybrid licence identification.** Recall by FTS5 trigrams, precision by
   RapidFuzz, a cheap probe gate before the costly alignment, and markers
   for declared licences. Evaluated on 59,738 queries over 695 licences;
   mixed-content Recall@1 +55.2 pp from marker detection.
2. **The SPDX matching guidelines in practice.** The order of
   normalisation steps matters (idempotence). Guideline 9 (remove copyright
   notices) cost 0.72% recall, because the copyright boilerplate was
   accidental signal between near-duplicate licences. Identical bodies
   (`-only`/`-or-later`, GFDL) can only be told apart by the grant.
3. **Performance traps in fuzzy matching.** RapidFuzz cost follows
   characters, not words; a per-word limit tuned to clear every fixture lost
   Japanese text. Each fix to input reading added the next quadratic path.
   A `score_cutoff` that is provably identical for the winner cut
   Recall@30 by 7.93 pp, and only the full benchmark showed it.
4. **AI-assisted engineering by one developer.** Review loops with a
   different strategy per round, characterisation tests before refactors,
   mutation checks, differential tests, a real-shell CLI matrix that found
   what pytest could not, exact complexity ratchets, and a taxonomy of agent
   mistakes by who caught them (the agent's own reviews, tests, CI, the
   matrix, the user). The human kept the design decisions, the git writes
   and the accuracy-versus-speed trade-offs.
5. **SBOM correctness.** Re-embedding an SBOM into a finished wheel left
   stale `RECORD` and self hashes while a schema validator still passed;
   the fix was to ship the build hook's SBOM, check the hashes, and sign
   it. The findings went upstream into Pitloom 0.20.0.

## Headline findings (details in the files above)

- Probe gate: about 93% of match time was RapidFuzz; benchmark wall time
  4,925 s → 1,394 s (secondary source: agent memory, see below).
- CLI cold start 125 ms → 31 ms (lazy imports). 4,000 distinct tags
  9.0 s → 1.85 s → 0.52 s (one connection per call, then a table cache).
- A 2,000-character token 5.0 s → 0.04 s once guards counted characters.
- The real-shell CLI matrix (about 1,200 cells, five shells): every flag it
  raised was a defect the test suite could not reach, including a locale
  crash in a dependency (`py-spdx-license` under eucJP), fixed upstream.
- Characterisation tests found pre-existing bugs in 3 of 5 refactors.
- Agent incidents worth reporting honestly: a CLI-matrix cell with `HOME`
  unset deleted the developer's real licence database (2026-09-19); in July
  an agent ran `update --force` against the real cache unnoticed; an agent
  committed and force-pushed unasked (2026-09-17), which led to the
  "user does all git writes" rule.
- The agent pushed back with data when the user's premise was wrong (the
  Action's SBOM "looked richer" but had stale hashes and lost fields).

## Before citing anything

- **Run a fresh full benchmark** (`bench_compare.py`, about 2 h). The
  latest recorded run is from 2026-07-20, before PRs #53 to #76.
- `benchmarks/summary.md` labels both columns `main` while its tier tables
  say `license-marker`; its "precision 1.85%" is not defined anywhere; it
  still shows `id_casing` 80% and `id_deprecated` 0% after the case-fold
  fix landed. Fix or explain these.
- The 4,925 s → 1,394 s figure is only in agent memory; confirm it from a
  benchmark output or re-measure.
- Fixtures come from the same SPDX texts the system indexes (closed world),
  and the mixed-content templates were generated with LLM help from
  proportions with no stated method.
- Check quoted user messages and session details with the developer before
  publishing them.
