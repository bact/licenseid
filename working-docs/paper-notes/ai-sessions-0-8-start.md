---
Created: 2026-11-06
Last-Modified: 2026-11-06
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted start of 0.8: one answer for a whole input, and a sample

The work of 2026-11-05 and 2026-11-06, after the 0.7.1 release: `detect()`
asks `resolve()` first, a licence-value sampler of six package channels,
and three side sessions. One lead session (Claude Code, transcript
f89c86b8), three side sessions it proposed and the maintainer started,
and one read-only reviewer agent per pull request (Opus, high effort). The
maintainer made every push and merge.

## What was built

| PR | What | Source |
| --- | --- | --- |
| #160 | `tools/licence_sample`: frames, pinned fetches, `cut`, `analyze`; collection criteria and a top-50 pilot | `collection-criteria.md` |
| #161 | `detect()` reads a whole input with `resolve()` first; a refused input under 10 words is not matched as text | `match-resolve-0-8.md` §3 |
| #162 | `resolve()` crashed in a plain Python process when the database warned | side session |
| #163 | `resolve()` reads a licence's own title (`text_title`), `CC0` and the UPL trove name | side session |
| #164 | The wheel's SBOM built with Pitloom 0.23.0 | side session |

Results of #161 and #160 are in `results-and-findings.md` §3.8.

## Maintainer decisions

- Let `resolve()` decide first for the whole input, and give no answer
  under N words rather than a text guess (N measured: 10).
- `exact` keeps `detect()`'s own meaning; the stricter rule (D2) stays
  open, because taking `resolve()`'s trust split the channels.
- Six channels for the corpus: PyPI, npm, crates.io, Maven Central, NuGet,
  Hugging Face. Keep the list of packages fetched and why: the frame file.
- The tail stratum waits until the head is fetched: running both at once
  would slow both, the ranking service being the bottleneck.
- A top-50 pilot to start work now; the 1,000 head and 1,000 tail later.
- `CC0` and the UPL trove name are exceptions to P47 (a name with no
  version names nothing): each licence has one version.
- No code review for #164 and #161 at merge; one more for #163, asked
  after the agent advised it.

## Review yield

Each review was given the diff and the intent, not the author's
conclusions, and every finding was reproduced before it was reported.

- **#161, 9 findings.** One regression: the cut counted words, and
  Chinese and Japanese have no spaces, so 90-character excerpts of
  CC-BY-SA-2.1-JP lost their answer (50 of 50 on `main`, 8 of 50 on the
  branch). AGENTS.md already named this trap for a per-word limit (PR #62).
  One bug: an expression with `WITH AdditionRef-x` had no OSI or FSF flags,
  as the parser reads no `AdditionRef`. Seven doc or wording findings.
  13 mutants of 16 died; of the three left, two were equivalent and one
  showed the untested flags.
- **#163, 6 findings.** The title table was read by `resolve()` only, so
  `detect CC0` answered `CC0-1.0` and `detect --id CC0` nothing; the
  titles folded case beyond ASCII (`Mulan Pſl v2` read as MulanPSL-2.0);
  one test row passed for a reason other than its claim; four doc gaps. No
  over-match among the look-alikes probed (other versions, extra words,
  `+`, "or later", Cyrillic letters).

## Incidents

- **A failure recorded as an absence.** The first run of the sampler
  stopped part way. A failed ranking page ended the frame as if the
  registry had ended (300 of 1,000), and every reply of four registries
  failed and was written as a package with no licence: 1,211 packages.
  Found by a count that looked wrong (PyPI: 50 of 50 with no value), not
  by an error. Fixed: a failed page stops the frame, a failed reply is
  recorded with its error and counted apart.
- **A crash in released code, found by the analysis.** Analysing the
  pilot against an older database raised `AttributeError` in
  `warning._matches`: CPython's default filter holds its module as a plain
  string, and `all((...))` evaluated every field before the category.
  pytest replaces the filters and the CLI fronts them, so no test saw it.
  Fixed in #162 the same day.
- **An agent's own number.** The lead wrote "708 of 712" for the CJK
  slices in a docstring and a note; summing its own table gave 592 of
  593. Caught by rechecking before the commit.
- **A push that did not happen.** The fixes of the #163 review were
  committed on top of a local merge of `main`, then GitHub's "Update
  branch" merged `main` into the old remote tip and the pull request merged
  that. `main` got #163 without its fixes, and the merge restored #161's
  first changelog wording. Found during cleanup, when the local branch
  would not delete as merged; the fixes went to a follow-up pull request.
- **A timing test under load.** `test_leading_expression_does_not_backtrack`
  took 2.5 s against a 1 s bound while the suite, mutants and the golden
  diff ran at once; alone it passed.

## Patterns

- **Measure the cut-off, then the exception.** The 10-word cut came from
  the goldens (right 19 times in 94 under 10 words). The CJK exception came
  from slicing the four CJK texts of the List, short phrases that are no
  licence, and mixed inputs, on `main` with no cut; the share threshold
  (nine in ten) is where the mixed inputs fall out and clause letters stay.
- **One reader per entry point.** Both #163 findings of weight were one
  table read from one path and not another; the fix routed `--id` through
  the same reader rather than copying the table.
- **Side sessions for separable work.** Three ran in parallel worktrees
  (the crash fix, the lost names, Pitloom). One stopped on a network
  error and resumed; one renamed its branch; one was bound by the app to
  the wrong pull request. Their notes were checked against the commits
  before they were reported.
