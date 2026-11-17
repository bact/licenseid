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

- **Rules** (a doubted hit gives no name answer). `namehits` weighs the
  names tied at the top score; `namerules` judges the words that touch one
  name, never the whole input:
  - Ties: of the names the input holds as words, the one it writes whole
    (its words in order and close; a number a title or an acronym and
    "Version" away; `License` up to three words after a one-word name) is
    the licence named. A name made of words from here and there is not
    (`This library is free software under the GNU General Public License
    v2.0 only` also holds the Library GPL's words; `Apache License 1.1,
    release 1.0` also holds Apache-1.0's: token set reads `1.1` as the word
    1). Of names written whole the longest wins where they nest (`Licensed
    under the Apple Public Source License 1.2` is APSL-1.2, was APSL-1.1 by
    ID order); two that do not nest are two licences and give none
    (`zlib/libpng License`, `MIT -or- Apache License 2.0`); two that differ
    only by a number give the one written in fewer words (`Open Software
    License version 2.1 1) Grant` is 2.1). Where none is written whole the
    names nest by their words, never by a number alone. The other tied names
    are dropped, so `exclude` of the winner leaves no less specific one. A
    name that the input writes whole as well and that scores below the hit
    only for its `v` (`Universal Permissive License 1.0 or Apache License
    2.0`) is another licence: no answer. `namerules.GENERIC` (license,
    licence, see, file) is no evidence (`MIT No Attribution (see LICENSE)`
    is MIT-0).
  - Cut version: the input's number starts the licence's version and the
    rest is not all zeros (`Apache License 1`, `MVT-1`, `Sendmail-8`); `2`
    for `2.0` is no cut. Read through `versionkey`. A grant read off the
    text exempts it only right after the cut number (`GNU Lesser General
    Public License v2 or later`; not `Apache License 1. Requires Java 8 or
    later`).
  - Fragment of a longer name (`MIT Future License`).
  - `with <exception>`: a "with" that follows the name (within three words)
    and the word "exception(s)" in the five words after it (not "no
    exceptions"), or the words that tell one exception of the `exceptions`
    table of two words or more from the rest (`GPL-2.0 with Linux syscall
    note`). One word is no exception: `built with GCC`, `compatible with
    Swift`, `works with Linux`. New read `database.exception_words()`,
    cached in `dbcache.TableCache`. "with" alone is no doubt ("in
    compliance with the License").
  - Another ID written whole: an ID with a digit or a dash
    (`BSD-3-Clause, Apache License 2.0`), or an upper-case acronym ID as
    written beside the name (`MIT, ISC`, `MIT and ISC`; not `MIT License,
    (c) 2020 The IPA Group`), not an ID that is an ordinary word (`Intel`,
    `Unlicense`).
  - A dash or underscore glued to a word that is, or stands beside, a word
    of the name (`License: MIT-`, `MIT -or- Apache License 2.0`; not
    `Copyright 2015- present`), read by `dropguard.trailing_joiners`.
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
  branch, after review round 2):
  - PyPI sample (462 values, 9,353 projects): 6 values (10 projects)
    change. Four values (7 projects) go from a wrong answer to none
    (`MIT -or- Apache License 2.0` 3, `Universal Permissive License 1.0 or
    Apache License 2.0` 2, `MIT License, Apache License, Version 2.0` 1,
    `zlib/libpng License` 1); two values (3 projects) gain the `-only`
    guess (`GNU Lesser General Public License v3` 2, `GNU General Public
    License v3` 1). No right answer lost. `resolve()` changes 0 values.
  - `Licensed under the <name>` over the 708 names in use: right 588 to
    704, wrong 118 to 0, none 2 to 4. Pairs of two names (134 probes):
    wrong 134 to 8. Cut names wrong 51 to 1, cut IDs 8 to 3, glued dash
    10 to 0.
  - 12,723 windows of 10 to 29 words from every List text (five lengths, up
    to four offsets): right 8,183 to 8,255, none 225 to 251; no right
    answer lost; 72 wrong to right, 26 wrong to none, 27 wrong to another
    wrong. Round 1 (commit 2795fd5) on the same windows: right 8,221, and
    it flipped the `copyleft-next-0.3.0` text heads to 0.3.1 (now 0 flips).
  - 5,560 slices of List texts (the reviewer's): 76 answers differ from
    `main`, none a right answer lost (wrong to right, none to right, wrong
    to none).
  - A prototype whose refusal is final whatever the score lost 313 right
    answers on the first window set; final above 1 with a broad `with` rule
    lost 55.
- **Golden moves** (`tools.golden`, listed in
  `tests/harness_changes_nametier2.py`): `id` 1, `name` 1, `value` 6,
  `mixed` 21; `short`, `long`, `cli` unchanged. Twelve `mixed` rows that
  round 1 refused answer the right licence now (`AFL-1.2`, `APSL-2.0`,
  `OFL-1.1-no-RFN`: a name written whole beats scattered words), and two
  golden answers that were wrong are right (`Apache-1.1`, `CDDL-1.1`
  pubspec rows). `GNU Lesser General Public License v3` is back to its
  golden answer. sbomminbench (194 distinct values): 0 moves.
- **Breaking**: `detect` gives no answer where it gave a name hit for
  two licences, a cut version, `with <exception>`, a fragment of a longer
  name, another ID written whole or a dash glued to a word end. Migrate:
  declare an SPDX expression (`MIT OR Apache-2.0`) or the full version
  (`Apache-1.1`).
- **Review round 2** (PR #219, commit 2795fd5; all confirmed, all fixed):
  1. Nesting by digits (`Licensed under copyleft-next 0.3.0, see section
     1`, `Reciprocal Public License 1.1, see section 5`, EUPL 1.1, APSL 1.1
     flipped to a later version; `Apache License 1.1, release 1.0` showed
     one wrong version): names now nest by words in order, not by word
     sets, and versions that differ by a number only never nest.
  2. `glued_dash` read the whole input (`Copyright 2015- present`,
     `pre- and post-processing`, `__version__`): now only a word that is
     or stands beside a word of the name counts.
  3. `with <exception>` fired on ordinary English (`built with GCC`,
     `compatible with Swift`, `with the font of your choice`): the
     exception must be of two words or more, or the word "exception"
     within five words, and the "with" must follow the name. Measured on
     the 86 exceptions of the List, `Apache License 2.0 with <exception
     name>` and `Licensed under the Apache License 2.0 with the <name>`:
     86 of 86 still refused; `with <name without "exception">` (`with
     LLVM`): 56 of 86 refused, the 30 one-word names answer Apache-2.0
     now. `with <ID>` is read by `resolve()`, not this rule.
  4. The standard OFL notice and `GPL-2.0-only` with "library" in the text
     were refused: a name written whole now beats one made of scattered
     words (OSL-1.1, LGPL-2.0-only).
  5. Upper-case acronyms as IDs (`MIT License, copyright (c) 2020 The IPA
     Group`, `TCL`, `NCSA`): an acronym ID counts only beside the name
     (`MIT, ISC`, `MIT and ISC`); an ID with a digit or a dash counts
     anywhere. `ICU`, `NTP`, `DOC` read as `<acronym> License` count only
     where the two words stand together.
  6. The cut-version rule was switched off by "or later" or "+" anywhere
     (`Apache License 1. Requires Java 8 or later` gave Apache-1.1): the
     grant counts only right after the cut number.
  Independent review of the round-2 diff (Opus, read-only) found and fixed:
  two versions written apart (`Apache License, Version 2.0; earlier the
  Apache License 1.1`) answered the one in fewer words (the tightest-span
  rule now needs both names to stand from the same word); an ID with a
  digit or a dash anywhere (`Depends on python-ldap`, `Uses X11`) and an
  acronym opening the next sentence (`MIT License. TCL scripts included`)
  counted as a second licence (an ID now counts only joined to the name by a
  comma, semicolon, slash, "and", "or" or "&", or in brackets for an ID
  with a digit or a dash or an acronym alone in brackets); "License" ended
  a name and tied a "with" three words on (`MIT License. Use it with the
  exception of the logo`; the tie now reads the name's distinctive words);
  the exception words are read from the first eight only (was quadratic on
  an input of thousands of "with"). Left: a "with" more than three words
  after the name (`GPL-2.0-only as published by the FSF with the Classpath
  exception` answers GPL-2.0-only); `Modified Apache 2.0 License ...` (the
  Pixar head) answers Apache-2.0; `MIT License, with the exception of the
  fonts directory` stays refused (owner decision D47-2). 42 mutants killed.
  Also: a second licence whose name lacks the `v` of its version
  (`Universal Permissive License 1.0 or Apache License 2.0`,
  `... GNU Affero General Public License v3.0 or the MIT License`) is
  another name: no answer. New pins kill the mutants of `namehits` and
  `namerules`, among them the six that survived round 1.
- **Not verified**: Windows and Python 3.14 (no run in this session; CI
  decides).
- **Open leftovers** (roadmap item 47): a pair where one name nests in the
  other (1 of 134 probes); a one-word ID that is an ordinary word is no
  second licence (7 of 134); a version the name lacks (`MIT License 2`;
  refusing it lost 10 right `mixed` golden answers for 0 PyPI gain); wrong
  answers no rule touches (`Licensed under the GNU Lesser General Public
  License v2.1` gives BSD-Protection at 0.867, `... Affero ... v3.0` gives
  MPL-2.0 at 0.86, `GNU Lesser General Public License v2.0 or later`,
  `Apache License 1 or later`); two licences in prose that are not tied
  (`GNU General Public License v2.0 or MIT License`, `MIT License or BSD
  3-Clause` answer MIT; pinned `# BUG: (item 47)`); a list of two licences
  that names one whole (`Eclipse Public License v. 1.0 - Cecill v. 2.0`
  answers EPL-1.0 as `main` did; round 1 refused it, 4 windows);
  `<name> Plus` (706 of 708 probes); name + "+" (1 project); a manifest
  field with a name less its grant (1 project); `with <one-word exception
  without the word>` (30 of 86 exceptions).
