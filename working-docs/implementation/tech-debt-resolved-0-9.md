---
Created: 2026-11-17
Last-Modified: 2026-11-17
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolved tech debt, from 2026-11-17

Items of [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md)
resolved from 2026-11-17 on, in the order they were resolved. The earlier
ones are in [`tech-debt-resolved-0-5.md`](tech-debt-resolved-0-5.md); this
part was split from it when it passed the file size limit. Item numbers are
the roadmap's.

## Item 47 (2026-11-17)

Leftovers of the name tier on a few words. Token set scoring reads an input
as a set of words, so an input that holds a whole List name answers it
whatever else the input says. `namehits.settle()` now drops a name hit of
Tier 0 (`shorttext.match_name_tier`) that the rest of the input doubts.

- **Rules** (a doubted hit gives no name answer):
  - Ties: where several names that the input holds whole tie for the top
    score, the longest wins if the names nest (`Licensed under the Apple
    Public Source License 1.2` is APSL-1.2, was APSL-1.1 by ID order); two
    names that do not nest are two licences and give no answer
    (`zlib/libpng License`, `MIT -or- Apache License 2.0`). The other tied
    names are dropped, so `exclude` of the winner leaves no less specific
    one. `namehits.GENERIC` (license, licence, see, file) is no evidence
    (`MIT No Attribution (see LICENSE)` is MIT-0).
  - Cut version: the input's number starts the licence's version and the
    rest is not all zeros (`Apache License 1`, `MVT-1`, `Sendmail-8`); `2`
    for `2.0` is no cut. Read through `versionkey`. A grant read off the
    text exempts it (`GNU Lesser General Public License v2 or later`).
  - Fragment of a longer name (`MIT Future License`).
  - `with <exception>`: the word "exception(s)" after `with`, or the words
    that tell one exception of the `exceptions` table from the rest
    (`Apache License 2.0 with LLVM`); one word of a longer exception name is
    not enough (`works with Linux`). New read
    `database.exception_words()`, cached in `dbcache.TableCache`. "with"
    alone is no doubt ("in compliance with the License").
  - Another ID written whole: an ID with a digit or a dash, or an upper-case
    ID as written (`BSD-3-Clause, Apache License 2.0`, `MIT, ISC`), not an
    ID that is an ordinary word (`Intel`, `Unlicense`).
  - A dash or underscore glued to a word end (`License: MIT-`), read by
    `dropguard.trailing_joiners`.
- **Final refusal**: a dropped hit that scored above 1 stops Tier 1 too for
  10 words and more (`detector._short_text_refused` returns `[]`). Under 10
  words the `too few words for text` warning still shows. A dropped hit below
  1 lets Tier 1 run. Mixed-content sections (`match_short_text`) only lose
  the hit.
- **Also**: `GNU Lesser General Public License v3` and `GNU General Public
  License v3` (`vN` for `vN.0`) answer the `-only` guess with `variant not
  stated`; a stray "＋" no longer leaves the `-only` guess in a
  mixed-content section (`shorttext._grant_left_out_alone` uses
  `resolvereason.ends_a_word_with_plus`).
- **Decided** (owner, 2026-11-17): the most specific nested name wins and
  non-nested names give no answer; the refusal is final only when the
  removed hit scored above 1, and the `with` rule is narrowed to an
  exception of the table or the word; cut versions get no answer and the
  warning stays under 10 words; name-plus-words answers stay except the
  cases above. Defaults: `vN` is `vN.0`; name + "+" and the manifest field
  unchanged; `Open Database License` and the Mulan title stay closed (no
  measured count); the grant-tie refusal in `shorttext.py` stays not final
  (0 moves when made final).
- **Measured** (real 3.29.0 database copy, `main` 50017cb against the
  branch):
  - PyPI sample (462 values, 9,353 projects): 6 values (10 projects)
    change. Four values (7 projects) go from a wrong answer to none
    (`MIT -or- Apache License 2.0` 3, `Universal Permissive License 1.0 or
    Apache License 2.0` 2, `MIT License, Apache License, Version 2.0` 1,
    `zlib/libpng License` 1); two values (3 projects) gain the `-only`
    guess (`GNU Lesser General Public License v3` 2, `GNU General Public
    License v3` 1). No right answer lost. `resolve()` changes 0 values.
  - `Licensed under the <name>` over the 708 names in use: right 588 to
    704, wrong 118 to 0, none 2 to 4. `<name> (see LICENSE)` and
    `License: <name>`: 576 right and 130 wrong to 706 and 0. Pairs of two
    names (134 probes): wrong 134 to 8. Cut names wrong 51 to 1, cut IDs
    8 to 3, glued dash 10 to 0.
  - 10,570 windows of 10 to 29 words from every List text: 4 right answers
    lost (MPL-1.0 and Motosoto heads of 24 and 29 words, which hold the
    names of several versions whole), 55 wrong to right, 44 wrong to none,
    25 wrong to another wrong. A prototype whose refusal is final whatever
    the score lost 313 right answers; final above 1 with a broad `with`
    rule lost 55.
- **Golden moves** (`tools.golden`, listed in
  `tests/harness_changes_nametier2.py`): `id` 1, `name` 1, `value` 6,
  `mixed` 19; `short`, `long`, `cli` unchanged. `GNU Lesser General Public
  License v3` is back to its golden answer. sbomminbench (194 distinct
  values): 0 moves.
- **Breaking**: `detect` gives no answer where it gave a name hit for
  tied names of two licences, a cut version, `with <exception>`, a fragment of
  a longer name, another ID written whole or a dash glued to a word end.
  Migrate: declare an SPDX expression (`MIT OR Apache-2.0`) or the full
  version (`Apache-1.1`).
- **Leftover found by review**: only tied names are weighed against each other:
  `GNU General Public License v2.0 or MIT License` and `MIT License or BSD
  3-Clause` still answer MIT (pinned `# BUG: (item 47)`).
- **Not verified**: Windows and Python 3.14 (no run in this session; CI
  decides).
- **Open leftovers** (roadmap item 47): a pair where one name nests in the
  other (1 of 134 probes); a one-word ID that is an ordinary word is no
  second licence (7 of 134); a version the name lacks (`MIT License 2`;
  refusing it lost 10 right `mixed` golden answers for 0 PyPI gain); wrong
  answers no rule touches (`Licensed under the GNU Lesser General Public
  License v2.1` gives BSD-Protection at 0.867, `... Affero ... v3.0` gives
  MPL-2.0 at 0.86, `GNU Lesser General Public License v2.0 or later`,
  `Apache License 1 or later`); `<name> Plus` (706 of 708 probes); name +
  "+" (1 project); a manifest field with a name less its grant (1 project).
