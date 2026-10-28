---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted session, Pitloom 0.21.0 and the 0.7.0 resolver plan

One Claude Code session (transcript `4cf4bfd0-ee44-5d9b-b623-9693743bbc4e`,
working in the `pitloom`, `lumina`, `ntia-conformance-checker` and `licenseid`
repositories, 2026-10-27 to 2026-10-28; resumed after context compaction)
integrated `licenseid.resolve()` into Pitloom, released Pitloom 0.21.0, and
started the plan for the next `resolve()`. Sources: the transcript, Pitloom PRs
#359 to #362, licenseid PRs #102 and #103, `working-docs/design/`. Labels as
in the other notes: **[observation]** is checkable in the sources; the rest is
the author's reading.

## What was built

- Pitloom reads a declared licence value through `resolve()` (Pitloom #359):
  accepted categories, one `INFO:` per decision, provenance keys, an answer
  cache. Four review rounds. **[observation]**
- The design for compounds, the packaged-list fallback and one entry point
  (licenseid #102), and the evidence for it from 57 real values and a
  4,999-project PyPI sample with a reusable tool (#103). **[observation]**
- A release sweep of Pitloom's docs, comments and skills by three agents, then
  a fresh review of the combined diff (Pitloom #361). **[observation]**
- `network` split from `loopback` tests (Pitloom #362). **[observation]**

## Decisions that came from the human

- Hold the 0.7.0 implementation until 0.21.0 is out; collect evidence first.
- Use the most capable model for planning the resolver and cheaper agents at
  lower effort for simple tasks, so the plan must carry a map, rules of thumb,
  trap warnings and snippets for them.
- Regression and adversarial tests catch wrong behaviour; coverage near 100%.
- Move the flaky live-host tests out of the default CI job.

## Mistakes and how they were caught

- A 4,835-line `uv.lock` was committed with `git add -A` after `uv sync`; the
  fresh review of #359 found it. **[observation]**
- fastText `lr` and `minCountLabel` were recorded from a loader default; the
  `maxn` fix then dropped a stored value for cbow and skipgram models. The first
  was found by the docs sweep, the second by the fresh code review.
  **[observation]**
- A sweep claim ("an invalid `--sbom` is refused") held for SPDX 3 only; the
  fresh docs review found it.
- `pkill -f` killed the agent's own shell twice (the pattern was in its own
  command line).

## Patterns

- **[observation]** In this session the author's own verification (running the
  CLI after each edit) missed what a reviewer with the diff and no summary
  found: over-broad statements, a gate wider than the evidence, a message that
  claimed a verdict never reached. Details: Pitloom
  `working-docs/implementation/recurring-bug-patterns-review-rounds.md`.
- Measuring before choosing: the PyPI sample showed that prose forms of one id
  (16% of the unresolved) are the safest gain, and that the first corpus
  over-weighted trailing parentheses (2% of the unresolved, not 4 of 17).

## 0.21.1 and the start of 0.7.0 (28 October)

- The patch release took six small changes: a log level (#364), two small bugs
  (#365), a docs audit from the parser's option list, and the version bump
  (#366). Four independent reviews over the whole stretch found ten defects in
  code and docs that the suites, linters and per-change checks had passed.
  **[observation]** Two were the same mistake in two places: a helper sets a
  signal, and one path that logs the same failure does not call it.
- The human's decisions were small and exact: defer the assumed readings (Q3),
  remove the `expression` category (Q2), and "the newer list version wins"
  (Q4), which reversed the plan's recommendation. The plan had recorded the
  alternatives with examples, so the reversal cost one edit.
- Four sub-agents launched for the groundwork returned plans and changed
  nothing: the session was in plan mode and they inherited it. The same mode
  stopped two review agents from running mutation checks. The cost was a round
  trip, not a defect. **[observation]** Check the mode before a fan-out.
- A strict network gate in the release workflow failed on two outside hosts
  (a government Forgejo server's DNS, SourceHut's port 443); re-running the
  failed job passed. Pitloom
  `working-docs/implementation/recurring-bug-patterns-review-rounds.md` ("From
  PR #364, #365 and the 0.21.1 release") has the detail.

