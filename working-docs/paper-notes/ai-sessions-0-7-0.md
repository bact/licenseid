---
Created: 2026-10-29
Last-Modified: 2026-10-29
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted release 0.7.0: one lead, author agents and reviewers

The work of 2026-10-28 and 2026-10-29 that built the 0.7.0 resolver from the
plan in `ai-sessions-0-7-plan.md`: one lead agent delegated each task to an
author agent, an independent reviewer read each diff, and the maintainer
opened and merged every pull request. Source: the lead's record of the
session (a facts file kept in the session's scratch directory, not in the
repository), licenseid PRs #106 to #132, `../design/resolver-0-7-plan.md`,
`../design/resolver-0-7-review.md`, `../design/resolver-0-7-evidence.md`.
Labels as in the other notes: **[observation]** is checkable in the sources;
the rest is the author's reading. The release itself (tag, PyPI) is not
covered: this note stops before it.

## Process

- One lead agent (Opus). Each task went to an author agent (Sonnet at medium
  effort; Opus at high effort for T5 and T7), then to an independent reviewer
  (Opus, high effort), who was given the diff and the brief, not the author's
  conclusions. The author made the fixes. The lead then re-ran the whole check
  list itself, probed values by hand, merged `main` and pushed. The
  maintainer opened and merged every PR. **[observation]**
- Characterisation tests first. A frozen PyPI sample (462 distinct values,
  9,353 projects) and a parity corpus pinned the 0.6.0 answers, and an
  `EXPECTED_CHANGES` guard failed any value whose answer moved without a
  listed reason. **[observation]**
- The pull requests, in the order of the work: T0 to T4 #106 to #112
  (groundwork: pins, list rules, the `ListLookup` protocol, `resolveleaf`);
  T5 #119 (packaged list, `source=`); T6 #120 (drop guard); T6b #121 (quotes);
  T7 #122 (compounds, schema 2); T9a #123 (trove table); CI accuracy layers
  (#124); fixes from the whole-change review (#125); T9 #126 (trove names);
  design note on `match` and `resolve` #127; T8 #128 (prose forms, dropped
  words, end marks); README split #129; sdist allowlist #130; T8b #131
  (semicolon lists, marks after `+`); T5b #132 (cache the `auto` list choice).
  **[observation]**
- Measured effect on the frozen sample: values with an expression 137 to 241,
  projects 79.7% to 84.0%, downloads 83.3% to 90.2%
  (`results-and-findings.md`, section 3.7). **[observation]**

## What independent review caught that the author had not

| Task | Found by the reviewer |
| --- | --- |
| T8 | Names of deprecated licences read with no decision; doubled words read only when the inner part is a List name; a surviving mutant (`TheMIT License` would read as MIT) |
| T8, end marks | The proposed rule would turn a cut value into a different licence (below) |
| T8b | Five values that resolved before became "lists" (`MIT; (MIT)`); an operator-word check that the author deleted as redundant was needed for three parts (`MIT; OR ISC; Apache-2.0`), a surviving mutant; one reason lost (`MIT License &`) |
| T5b | A blocker (below); a `chmod` or in-place damage with the modification time restored went unseen |

- T8 end marks. The maintainer first decided to trim any run of `; : … . , -`
  at either end of a value. The reviewer tested the rule against the List
  itself: 47 names have the form `X - variant` where `X` alone is another ID
  (16 HPND variants, the GFDL invariants), and 38 IDs end in another ID
  (`...GPL-3.0-only` cut from AGPL-3.0-only, `...ISC` from Rdisc). Trimming
  would turn a cut value into a different licence. The maintainer narrowed
  the rule to single marks only: one `.`, `,`, `;` or `:` at the end; an
  ellipsis, a lone dash and every leading mark are refused. The narrowing
  also closed a gap already on `main`, where `-MIT` and `.GPL-3.0-only` were
  read. **[observation]**
- T8b. After the fixes, 0 of 137,037 generated values lost or changed an
  expression against `main`. **[observation]**
- T5b. The blocker: a packaged fallback chosen because the database was
  momentarily locked by another process was kept for the life of the process,
  although the database was readable on the next call. The reviewer also
  found that a `chmod` or an in-place edit with the modification time
  restored went unseen; the fix added `st_ctime_ns` to the cache key. The
  change itself took a value from about 12 to 15 ms to 1.2 ms and six
  connections to one. **[observation]**
- T6b (CI, not review). A timing test failed CI under coverage (5.98 s
  against a bound of 5 s). Large timing tests moved to
  `@pytest.mark.benchmark`; a small size stays in the every-commit run.
  **[observation]**
- A review of the sdist before the release found that it shipped internal
  notes, CI files, tests without their fixtures and two dangling symlinks to
  the excluded `AGENTS.md`. An allowlist fixed it (#130; 1.67 MB to 1.17 MB).
  **[observation]**

## Decisions that came from the maintainer, and why

- `MIT ; Apache 2` (semicolon). The operator is unknown (AND or OR), so no
  expression is returned, but the operands are still recorded: a property
  that holds for every operand (OSI approval) needs no operator. The author
  narrowed the rule so that at least two parts must name a licence and one
  must resolve, because the real sample values with a `;` were a licence plus
  a notice (`MIT; Copyright (c) ...`). **[observation]**
- "X or later" becomes `X+` whenever that is valid SPDX (`MIT or later` to
  `MIT+`; decision P35, widened on 2026-10-29).
- End marks: single marks only, after the reviewer's evidence (above).
- The name. `resolve` is hard to type and remember. 0.7.0 renames `resolve()`
  to `match()` and the old matcher to `detect()` (CLI `licenseid detect`), in
  the release that already breaks the result shape, so callers change once;
  no alias (private alpha, no backward compatibility). The design is #127; the
  rename is task T10a.
- CI cost. The per-commit accuracy run was cut to a seven-licence core (about
  15 s, from 79 s); the full sweep runs weekly and on manual dispatch (#124).
  **[observation]**

## Incidents

- A merge was committed with conflict markers: `set -e` does not stop inside
  an `&&` list. Fixed by follow-up commits; no history was rewritten.
- A session restart wiped the scratch directory. The environments and the
  reference database were rebuilt.
- zsh does not word-split `$VAR` and reads `$b:r` as a modifier; two push
  loops failed harmlessly until they were rewritten.
- `git checkout <file>`, used to undo a mutation, also undid an uncommitted
  edit. The next diff showed it and the edit was redone.
- An author agent sat idle "waiting on background work" for over an hour
  after its process had ended. The lead stopped it.
- Decision numbers clashed between two parallel branches (P87, P88) and were
  renumbered.
- Release dry run by the lead: the bundle (980,375 bytes) ships in the wheel
  and the sdist; a wheel built offline from the sdist has it; `resolve()`
  works with no database on Python 3.10 and 3.14.

## Findings worth a paper

- **Review against the data, not only the code.** The end-mark rule looked
  safe in the code; the List showed 47 and 38 names it would break. The
  reviewer ran the proposal against the List. **[observation]**
- **Surviving mutants as review evidence.** In T8 a mutant survived
  (`TheMIT License` would read as MIT); in T8b an operator-word check that
  the author had deleted as redundant was needed for three parts, and a
  surviving mutant showed it.
- **A cache key is a claim about what can change.** T5b's key (modification
  time and size) missed a `chmod` and an in-place edit with the time
  restored, and its fallback outlived the cause that chose it. Both were
  found in review.
- **Generated values as a regression oracle.** 137,037 generated values
  compared against `main` for T8b; 676 for the semicolon property
  (`results-and-findings.md`, section 3.6).
- **The author's own verification under-reaches.** The review findings
  above were in code whose author's tests passed; the reviewer had the diff
  and the brief and not the author's account. This repeats the pattern of
  `ai-sessions-0-7-plan.md` and `ai-sessions-0-6-0.md`. Do not turn it into a
  rate: the counts above are cases.

## Before citing

- The facts file is the lead's record and is not in the repository; check
  quoted figures (137,037; 47 and 38 names; 12 to 15 ms to 1.2 ms; 5.98 s)
  against the PRs and their test output.
- The model names and effort levels are those the lead assigned.
