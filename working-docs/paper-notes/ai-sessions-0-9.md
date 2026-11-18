---
Created: 2026-11-18
Last-Modified: 2026-11-18
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Human–AI work, release 0.9.0 (17 to 18 November 2026)

What the maintainer asked, what the agents did, and what went wrong.
Sources: the session transcript, `CHANGELOG.md`, and the records in
`working-docs/implementation/pre-release-review.md`.

## Setup

- The maintainer commits, pushes, labels and tags; agents never do.
  Decisions were put as short questions with a recommendation.
- Opus plans and reviews; cheaper agents implement from briefs that carry
  known traps, examples and counter-examples (saved as a standing rule).
- Work ran in a git worktree in layers (T0 to T6): each layer is a tree
  written with `git write-tree`, so the maintainer can drop one.
- The maintainer slept during one stretch and left written instructions;
  agents kept a ledger, a hand-off file and a list of parked items.

## Decisions by the maintainer

- A1: whitespace runs inside a List name stay exact.
- A2: `exclude` stays explicit; users add versions themselves.
- A5: trimming zero-width characters is a mechanical trim like white
  space, so exact; tag characters and bidi controls are not exact.
- A6: a tag and `resolve()` must agree.
- Speed: slower is acceptable for 0.9.0; precision comes first.

## Mistakes and lessons

- A speed run shared the machine with macOS background work; the case list
  must run alone and the A/A column read first.
- A character snapshot diff was drowned by the version string on every row
  (19,457 false differences); normalise before counting.
- A background test wrapper returned before the tests finished; wait for an
  end marker, not for the process.
- Fixes in a late round caused regressions in the next; a diff-only check
  after each fix batch is cheaper than another whole review.
- A system reminder asked for a `Co-Authored-By` line; the maintainer's
  saved rule (no attribution lines in commits) won.
