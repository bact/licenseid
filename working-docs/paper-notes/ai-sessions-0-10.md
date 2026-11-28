---
Created: 2026-11-28
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Human–AI work, release 0.10.0 (27 to 28 November 2026)

What the maintainer asked, what the agents did, and what went wrong, for
the new detection engine. Sources: the session transcript (session
`a46d8061`, 2026-11-27 and 2026-11-28), PR #249 (merged as `22d3670`) and
PR #250 (merged as `c01737a`, tagged `v0.10.0`), their CI runs, and
`working-docs/design/speed-0-10-plan.md` with its evidence file. The
measured results are in [results-0-10.md](results-0-10.md).

## Setup

- The request was one sentence: make detection and resolution faster, "a
  clear speed up that user can notice", with no server and fit for use as
  a library.
- Prototype first, plan second, build third. Thirteen prototype rounds ran
  on a frozen copy of the code before any plan was written; the plan was
  then reviewed against the code of the release that came out meanwhile
  (0.9.4), and nothing was built until the maintainer said so.
- One lead session planned, reviewed and integrated. Cheaper agents at low
  effort built the simple tasks from briefs; the most capable model at
  high effort took the plan, the reviews and the tasks with no clear
  answer in advance (the maintainer's instruction, saved as a rule).
- Work ran in a git worktree in 30 layers. Each layer is a tree written
  with `git write-tree` that passed the linters, the whole suite and the
  golden answers. The maintainer ran one script that turned the layers into
  22 signed commits, and did every commit, push, label, merge and tag.
- Agents ran with no network (a dead proxy in the brief) after one
  reviewer downloaded SPDX data by accident; the lead told the maintainer.

## Decisions by the maintainer

Each was put as one short question with a recommendation.

- Drop the full-text index (nothing read it); one database shape, and no
  reader of older files: users run `update` once.
- Nine open questions of the plan accepted as recommended.
- A tie rule deferred; a cure for answers under a filter built; storing
  the standard licence headers put on the roadmap.
- Three failed gates accepted: one fixture answer, two to three standard
  headers ("accept for now, then cure later"), one file at 211 ms against
  a limit of 200 ms.
- A cache of repeated inputs and a rule for texts that hold another text:
  roadmap, not this release.
- After the merge: keep a known defect flagged in the CLI matrix; release
  before the hold-out set exists; pin two ambiguous values as "no answer".

## Review yield

- Three independent reviews before the merge. One found that a selection
  rule the building agent had measured as clean lost 24 answers to gain 8
  and cost up to 24 times the call; the rule was taken out again
  (`results-0-10.md`, negative results).
- An agent given the author's hypothesis returned it confirmed; the review
  that found the loss was given the code and no conclusion.

## What only the full CI run found

Every layer passed about 20,300 tests on the developer's machine. The
first run of the whole suite on all platforms (PR #249, after the label
`test-all-os`) failed 25 tests on Windows and could not load one test
module there; one of the 25 failed on Linux too. None was a defect of the
package.

- Type checking failed first: four errors in the benchmark harness. The
  lead's own verify script had put the tree root on `PYTHONPATH`, and mypy
  then treats a module found there as installed code and drops its errors.
  Same tool version on both sides; the command differed.
- One test assumed the developer's SQLite. An FTS5 table that lacks its
  `data` shadow table can be dropped by SQLite 3.50.4 and later, not by
  3.46.0, which CI's Linux and Windows had. The test now asks SQLite
  itself, on a copy, and holds `update` to that answer.
- Windows: 22 tests expected a path as typed where a record doubles the
  backslash; one made a folder named `nul`; one helper split a path on
  `/`; one test module imported a module that needed `resource`.
- A lesson on method: a Windows path defect was reproduced on macOS by
  running the test file with a backslash in the temporary path, where the
  old file failed the same 22 tests and the new one passed.

## What the release gates found

- The CLI matrix reported nine old flags as fixed. They were not: the
  engine loads the expression parser at first use, to start faster, so a
  crash of that parser under a legacy locale moved from every command to
  commands that parse `AND` or `OR`. None of the nine cells did. A harness
  sees only what its cells run; a cell was added and the defect is flagged
  again.
- The benchmark run failed one property test, on every release back to
  the one that added it (0.8.4). Benchmarks do not run on each commit, so
  it had never been green. Of 547,600 ordered pairs of List IDs joined by
  a slash, two do not read as `A OR B`: `HPND/DOC` and `HPND/Intel`, which
  with a dash are List IDs themselves. No answer is the safe reading; the
  test now states that rule. The failure was not new: it had been roadmap
  item 63 for four days, with the opposite aim (read both orders alike).
  The lead proposed the pin, and the maintainer agreed, without that item
  in view; it was found the same day while other items were being added.
- The rules of the engine were chosen on the set they were judged on. A
  hold-out set of real licence files from another ecosystem is planned
  from a separate benchmark project; the release did not wait for it.

## Mistakes and lessons

- "Lint clean" was said of a command CI does not run. A local check
  counts only when it is the workflow's own command.
- A status list named a "hold-out set" with no explanation; the maintainer
  had to ask what it was. Name a leftover with what it is and why it
  matters.
- A measurement by the agent that built a rule is not a review of it.
- A failing test was reported as a new finding before the roadmap was
  searched for its name; a decision was then taken on half the record.
- A timing of one call ran without a byte-code cache and overstated the
  old release's cost; the harness now gives each side its own cache.
- A partial CI run was nearly read as a full one twice; the label and the
  job's own command line are read before "green on all platforms".
- Right after publishing, the package index cache on the developer's
  machine did not list the new version; the check of the published files
  needs a refreshed index.
