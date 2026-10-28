---
Created: 2026-10-28
Last-Modified: 2026-10-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# AI-assisted session, release 0.6.0

One Claude Code session (transcript `9e234326-49eb-4b48-874d-dc0760ee7129`,
repository `licenseid`, 2026-10-24 to 2026-10-28; resumed after context
compaction several times) built loose IDs, reviewed and fixed `resolve()`,
and took both to PyPI. Sources: the
transcript (timestamps in UTC), PRs #96 to #101, `CHANGELOG.md`,
`../implementation/declared-value-resolver.md`,
`../design/tech-debt-roadmap.md` items 43 to 45. Labels as in the other
notes: **[observation]** is checkable in the sources; the rest is the
author's reading.

## What was built

- Loose IDs (#96): `Apache2`, `GPLv2 or any later version` and
  `GPL2 WITH <exception>` resolve; a bare family (`GPLv3`) is `-only`, not
  exact, with a warning. **[observation]**
- `licenseid.resolve()` (#97, opened and merged on 2026-10-27 between this
  session's turns, so built elsewhere): a declared value to an SPDX
  expression, with each step taken, a category and trust level in
  weakest-wins order, and the resolver and list version behind it. This
  session's review of `v0.5.0..main` (#96 and #97) found nine issues and
  fixed them (#98, #99). **[observation]**
- Three roadmap items before the tag (#99): a "+" after a short ID
  (`GPL-2+`), a missing file named as an argument, and parse caps that
  hold on every Python. **[observation]**
- Fixes from an outside review after the last planned merge (#101).
  Released 2026-10-27 22:35, GitHub and PyPI. **[observation]**

## Decisions that came from the human

- The release planned as 0.5.1 became 0.6.0 once the agent pointed out
  that `resolve()` is new public API (SemVer minor)
  [9e234326 2026-10-27T18:55].
- A narrow guess, said aloud: a bare `GPLv3` is the `-only` variant, not
  exact, with a warning, rather than the broader `-or-later`
  [9e234326 2026-10-25T08:59].
- Three small roadmap items went into a separate PR before the tag, not
  into the version-bump PR [9e234326 2026-10-27T19:23].
- After the outside review: fix three findings before the tag, keep 0.5.0's
  behaviour for the fourth (wrong text answers for URLs and `MIT/Apache-2.0`),
  and ask whether the related roadmap item would help
  [9e234326 2026-10-27T21:59]. The agent checked and said no (below).
- Every fix comes with regression and adversarial tests, mutation-checked;
  the human asked for it in words during #96 and again for #101
  [9e234326 2026-10-27T21:59].
- The human did all git and GitHub writes, and asked for every commit
  message, PR title and summary ready to paste; no AI attribution lines
  [9e234326 2026-10-26T22:49].

## Review yield

| Round | When (UTC) | Found | Of which caught by |
| --- | --- | --- | --- |
| Agent, v0.5.0..main | 10-27 17:05 | 9 | probing the CLI and API |
| Agent, PR #99 | 10-27 20:25 | 7 | probing against `main` |
| Outside reviewer, after merge | 10-27 21:53 | 4 | the full 3.29.0 database |

- The agent's own review of PR #99 found that the PR's fix made new wrong
  refusals: `www.apache.org/licenses/LICENSE-2.0` answered Apache-2.0
  before and exited 2 ("not found") after. **[observation]**
- The outside review, run after all the agent's rounds and mutation
  checks, found a wrong licence from `match(text="GPL-2.0-only+")`:
  `LGPL-3.0-only` at 0.755. The agent's test had asserted "no answer" on a
  database of four rows, which the bug could not show on. **[observation]**

## Mistakes the agent made, and what caught them

- A seeded test database too small to fail: rows with no searchable text
  never reach Tiers 1 and 2, where the wrong answer came from. Caught by
  the outside reviewer on the real database. Mutation testing then showed
  the new test still passed with the fix removed, until the neighbour rows
  were given text. **[observation]**
- A rule for "looks like a path" (one word with "/" or an extension) also
  caught scheme-less URLs and Cargo's `MIT/Apache-2.0`. Caught by the agent's
  next review, comparing answers with `main`.
- Build stamps compared with `!=`: a database built by a newer licenseid was
  called "outdated", and the new automatic rebuild would downgrade it.
  Caught by the outside reviewer.
- A public method removed without a changelog line. Caught by the outside
  reviewer.
- A redundant check in a new predicate (a parse on top of a shape test):
  its mutant survived, which showed it changed nothing but the 150-operator
  cap, where it let an over-long malformed expression through. Removed.

## Findings worth a paper

- **Small fixtures hide ranking bugs.** "Answers no licence" holds trivially
  on a database where nothing can be retrieved. A negative test needs the
  near neighbours a real corpus has, and a mutant of the fix to prove the
  test can fail.
- **Entry points that disagree.** For one value, `GPL-2.0-only+`, four
  readers gave three answers before #101: a tag gave none, `resolve()` said
  `malformed`, `--id` exited 2, and text answered `LGPL-3.0-only`. The same
  pattern held for compound expressions after the release: in a tag,
  `MIT OR Apache-2.0` is exact; as text it answers `ECL-2.0` at 0.76
  (roadmap item 43). **[observation]**
- **A feature request answered by a probe.** Asked whether reading Cargo's
  "/" as OR would fix the `MIT/Apache-2.0` answer, the agent ran the OR form
  first: it was wrong too, so the "/" rule would gain nothing until a lone
  expression is read as a tag is [9e234326 2026-10-27T21:59].
- **Version stamps are numbers.** As strings, "10" sorts before "2"; as
  `int()`, a stamp of 5,000 digits raises on Python 3.11 and later (the
  integer string conversion limit, 4,300 digits by default). Both are
  adversarial rows in the stamp tests now. **[observation]**
- **A fix's own regressions.** Refusing a missing path (to stop a confident
  wrong text match) refused URLs that answered right; exempting URLs let
  `opensource.org/licenses/MIT` answer `any-OSI-perl-modules` again, as in
  0.5.0. The trade-off was left to the human and recorded (item 45).

## Verification used as evidence

- Before the tag: `latest.json` on the `data` branch; `update --source
  compact` from a clean `HOME` (17 MB database); wheel and sdist built with
  the bundle (980,375 bytes); `update --source packaged` with the network
  blocked; the README's `resolve("Apache2")` JSON equal to the wheel's
  output; CLI matrix NEW=0. **[observation]**
- Full suite: 4,244 tests before the PR #99 review, 4,364 at PR #101; all
  linters clean; mutants of each fix killed (10 in #99, 16 in #101).
  **[observation]**

## Process notes for the write-up

- Six PRs in four days, five on the release day. An outside review after
  the agent's last round still found a medium bug, on data the tests did
  not have; the agent had not run its probes against the full database for
  that input.
- The human steered by short questions ("should we merge?", "anything
  needed to fix before release?"); the agent answered with the evidence
  checked, and the human made each merge and the tag.
