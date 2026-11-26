---
Created: 2026-11-17
Last-Modified: 2026-11-26
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

## Items 50, 51, 54 (marks on a value, PR #220, 2026-11-17)

Marks and invisible characters around a declared value. Planned and measured
on `main` 50017cb (SPDX List 3.29.0), with the owner's decisions of
2026-11-17; each one follows the rule "refuse unless the loss is measured and
the reading is safe".

- **Measured**: the PyPI sample (462 values, 10,000 projects), the registry
  inputs of `sbomminbench` (172) and the golden `value` keys (520): 642
  distinct values on four channels (value, text, tag, field). A refused value
  that one stray mark at an end would make readable: 0 real values (the
  parity corpus alone has `#MIT`, `(MIT`, `MIT*`, `Apache 2.0?`,
  `Apache 2.0!`, `GPLv3 +`, `MIT OR GPL-2.0-only+`, all refused since item 48).
  A hidden character anywhere: 3 values, all parity corpus (`MIT\x00`,
  `MIT\u200b`, `\u202eMIT`), none inside quote marks. A backslash in a value:
  0. Tag lines under `~/projects` (14,743): a dash glued to a comment closer
  0; `?`, `!` or `*` glued 0; `)` glued 2 (the Markdown comment
  `[//]: # (SPDX-License-Identifier: EPL-2.0)`). No answer of the 642 values
  moves in this change (the same script before and after).
- **Item 51, decided (a): a lone stray mark stays refused.** `(MIT`, `MIT)`,
  `/MIT`, `MIT/`, `GPL-2.0+)` and the others are the head or the tail of a
  cut compound or list (`(MIT OR Apache-2.0)`, `MIT/Apache-2.0`), so reading
  them would be a guess; a lone quote or an ending (`"MIT`, `MIT,`) is read, a
  weaker answer, as before. Pinned in `tests/test_stray_marks.py` (reason of
  `resolve()`, no `detect()` answer, the tag that reads a `)`), documented in
  `docs/resolve.md`. Rejected: reading a lone trailing `)`, `]` or `/` (it
  moves `value/(MIT`, `value/MIT*`, `value/#MIT` of the golden back to an
  answer for 0 measured values).
- **Item 50, a hidden character inside quote marks (decided (a))**:
  `"MIT​"` is read as `MIT` (steps `unquote`, `trim`; `separator`),
  as `MIT​` already was. `hiddenchars.strip_plain_format` leaves off a
  format character (`Cf`) that is no bidi control; a bidi control, a control
  character (`Cc`), a NUL and one inside a word stay refused, and so do
  brackets (`(MIT​)`) and an operand's quotes. `resolver._read` judges
  `_refusal` on the value without those characters, or the trim would do
  nothing.
- **Item 50, a TOML string with escapes (decided (a))**: the reader skipped
  every basic string with a backslash and stopped an inline table's `text` at
  its first quote, so `license = "\"MIT\""` gave no value at all (the
  roadmap said the backslashes were kept; they were not read). A basic string
  is decoded as TOML 1.0 has it (`\b \t \n \f \r \" \\ \uXXXX \UXXXXXXXX`);
  any other escape (TOML 1.1's `\xHH` and `\e` included), a short `\u12` and a
  surrogate or code point past U+10FFFF is no value, as a parser refuses the
  file; a literal string is never decoded. What it decodes to goes to
  `resolve()` (`MIT\\u0041` decodes to a backslash and letters: refused). No
  `tomllib` (Python 3.10).
- **Item 54, the reference's trailing dash**: `MIT OR LicenseRef-a-` in a tag
  or a `license` field answered `MIT OR LicenseRef-a`, another reference
  (`identifiers._normalize_expression` cut each ID at its last letter or
  digit). It reads each token as `exprtokens.expression_tokens` does, a
  reference with its own dashes and dots. The roadmap said the tag only: the
  field was hit too.
- **Review found** (independent Opus pass): a hidden character between an
  inner mark and the closing quote (`"MIT.\u200b".`) got round the
  two-marks refusal, so the trim is not made when a mark also ends the value
  inside the quotes after an end mark outside (fixed, pinned); a closer glued
  to a reference's trailing dash in a tag (`MIT OR LicenseRef-a-->`, `-}`,
  `--]]`, `-#}`, `-*/`, a lone `LicenseRef-a-->` too) was read into the
  reference (main: dropped the dash); now refused (`dropguard.cut_reference`,
  pinned). Stripping foreign characters then trailing dashes was rejected.
- **Item 54, a comment closer glued to a dash in a tag: kept as is (decided
  (a))**: `MIT-*/`, `MIT-#}`, `MIT-}`, `MIT--]]` read as `MIT`. The pins of
  `tests/test_cut_tags.py` `STAYS` say so on purpose (Haskell, Lua, Jinja).
- **Item 54, reasons**: `LGPL-2 WITH Classpath-exception-2.0+` is `malformed`,
  `plus after an exception`, as `LGPL-2.1 WITH ...+` is; it was `version
  ambiguous`. `LGPLv2 or above` and `Apache-1 or above` are `not found: <value>`
  (prose), as `LGPLv2.1 or above` is: in `resolvecompound` a lower-case
  `or` drops the operands that name nothing, and now a cut operand too. A cut
  version is the reason only when it is the value's first fault. Kept: the
  cut reason beside a grant a text match would read (`LGPLv2 or (later)`):
  without that guard the reason stopped blocking the text tier and 14
  `detect()` answers appeared (`LGPL-2.0-or-later`). An 8,411-value sweep
  (R, text, tag, field) moved 861 reasons and no answer. The investigation
  was done by a read-only Opus subagent.
- **Paths rejected**: reading a lone mark by category (`separator`); trimming
  a bidi control inside quotes (the closing mark stands beyond it); a second
  escape scanner in `manifest` (`_RE_TOML_STRING` takes an escaped pair as one
  unit).

## Item 47 (PR #219, 2026-11-17)

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
- **Open leftovers**: listed once, with their counts, under item 47 of
  [`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md).

## Grant reader refusals (items 20, 46, 50, 52, 54; PR #221, 2026-11-17)

A value that goes on after an "or later" grant, or a mark glued to one, was read
as the licence with its grant and the rest dropped. Measured on 642
distinct real values (the PyPI sample of 462, sbomminbench 172, the golden
`detect_value` keys, on `main` 50017cb): none holds a joiner run before a
grant, a licence after one, or an `only` after an operand of a list; none
reaches `disambiguate_whole` with a reading `resolve()` refused. Built
under "refuse unless the loss is measured":

- **A run of two or more dashes or `_` glued before a word grant**
  (`GPL-2.0-- or later`, `MIT__ or later`, `GPL-2.0-_ or later`) is
  `character dropped` in every channel; one stays a separator
  (`GPL-2.0- or later`, `GPL-2.0_ or later`: the maintainer's 2026-11-04
  rule and the `STAYS` pins of item 54). `classify.grant_head` keeps the
  run with the head, `dropguard.trailing_joiners(least=2)` refuses it on a
  head (`resolveleaf._base`), and `classify._kept` judges the gap a tag
  sees apart from its ID. A reason of a value already refused moved once:
  `GPL-2.0-only-- or later` was `qualifier stated twice`, now `character
  dropped: U+002D`.
- **A mark glued to the end of a grant** (`GPL-2.0 or later-`, `?`, `!`,
  `*/`, `version-`): `looseid.disambiguate_whole` answered what
  `resolve()` refuses (`GPL-2.0-or-later`, exact, in the argument and a
  field); `dropguard.glued_marks` refuses it. One ending (`.`, `,`, `;`,
  `:`) and a closing bracket pass; the `PROSE` and `WRAPPED` tables stand.
- **A tag refuses `MIT OR GPL-2.0 only`** (`variants.qualify_trailing_only`)
  and **a licence listed after a grant** (`GPL-2.0 or later, ISC`, `;
  MIT`, `/ Apache-2.0`, `, Zlib`: `looseid.lists_after_grant`, from the
  grant's end); `, see COPYING`, `, the same as Ruby`, `, 2009` and `,
  Intel Corporation` keep their answer.
- **`EXACT` of a cut version with a grant in a tag or a field**
  (`LGPLv2 or later`, `Apache-1 or later`, `CDDL-1 or later`, after a WITH,
  in a compound): true since PR #217 (`ruleread.tag_inexact` judged the ID
  before the grant, which `resolve()` refuses), false as the argument now.
  The rule judges the expression with its grant, not `leading + "+"`
  (which is malformed after a WITH).
- **Decisions** (maintainer, 2026-11-17): item 20 is not built (the
  argument and a field read a grant inside an expression since the
  compound reader; a tag refuses it: `MIT AND GPL-2.0 or later AND
  Apache-2.0`, `GPL-2.0 or later OR MIT`; 0 of 642 values); item 50's
  `disambiguate_whole` stays (it reads no corpus value; `resolve()` reads
  no prose).
- **Cost**: a refused value pays the usual no-answer path. `"GPL-2.0" +
  "-_" * 25,000 + " or later"` as a tag took 0.09 s on `main` (answered at
  the grant) and 0.77 s now, the time `main` takes for the same run with no
  grant; it is linear (5,000 to 40,000 pairs: 0.17 to 1.2 s).
- **Review** (independent, Opus, read-only): `dropguard.glued_marks`
  judges the run by `dropped()` (not a list of marks: `>`, `#`, `}`, `\\`
  and `...` were answered), and a licence listed after a grant is refused
  also when another grant ends the value (`GPL-2.0 or later, ISC or
  later`); a refusal warns `too few words for text` as `MIT or later?` does.
- **Left**: `disambiguate_whole` still answers a mark after white space or
  prose after a grant where `resolve()` refuses (`GPL-2.0 or later -`,
  `GPL-2.0 or later, see COPYING`); a field `GPL-2.0 or later-2.1` is read;
  a tag still answers `GPL-2.0 only, ISC` and `(MIT OR GPL-2.0) only`
  (`lists_after_grant` reads an "or" grant only); the argument
  `GPL-2.0 or later, GPL-3.0 or later` has no answer at the bar (a text
  match, 0.45 `MPL-1.1` on the fixture database only; PR B1c checked it);
  `GPL-2.0 WITH Classpath-exception-2.0-- or later` is refused and
  the argument falls to the text tier (0.58, another licence);
  `markers._resolve_gpl_or_later` and `_detect_license_mentions` read a
  grant of any subject (item 52).

## A grant counts for its own licence (PR #222, 2026-11-17)

Items 46, 50, 52 and 54.

`has_or_later_language` read the whole input: `Requires Python 3.8 or later`
beside `GNU General Public License v2.0` turned `GPL-2.0-only` into
`GPL-2.0-or-later` with `VARIANT_STATED=true`, and overrode `--variant only`
(eight override warnings, one per GNU family). The same for "N only"
(`Supports Python 3 only`). Built (`licenseid.grantsubject`):

- **The subject rule.** `grants(text)` reads a bounded stretch before each
  `OR_LATER_PHRASE` match (120 characters, 24 tokens, never a rescan: 20,000
  phrases 0.2 s, long runs of digits, dots, dashes, brackets, words as on
  `main`): a version number and the word before it (a licence name, `version`,
  `v`; "General Public License", "Lesser", "Library", "Affero", "FDL" give the
  family), or `the License`, with "as published by the Free Software
  Foundation", an escaped `\n`, a version split by white space (`v2 0`),
  a name cut short (`gnu public v2.0`) and `WITH <exception>` read through.
  A `Grant` keeps the family as the letters of the word: `python 3.8`
  grants no licence of the List (`grants_licence`: the family and the version
  of the ID, `2` is `2.0`). `version N` after a tool (`Python version 3 or
  later`) is covered by the same compare: 0 such phrases in the sweep.
  `ranking.or_later_signal` and `only_signal` are per licence, read at the
  first question, once per input (`lru_cache`), one question per kind of grant.
- **The settle rule** (D-B8, option a). The name tier matches the words "or
  later" of the Python line against the List name, and `markers` read any
  phrase in 1000 characters, so a signal alone would only turn a wrong but
  stated `-or-later` into one guessed under `auto`. `variants.settle_text`
  settles an `-or-later` top of a text or name match to its `-only` twin where
  the input grants none of that licence and the ID is not written in it (not
  under `or-later`; `as-written` too, where the twins did not collapse).
  Only the top result is settled: pure texts keep their lists (golden `long`,
  `short`: no move). `markers._resolve_gpl_or_later` and
  `_detect_license_mentions` stay a bias of the score.
- **Measures.** 19 grants in 211 distinct READMEs: 11 a tool's, 8 a licence's
  (`working-docs/paper-notes/results-and-findings.md` 3.12). The 28 standard
  headers of List 3.29.0 that grant later versions all still grant their
  licence; the 18 `-or-later` answers of the sweep stay. Timing: `detect()` on
  a 200 KB README with 6,500 "or later" lines 2.45 s to 2.75 s (noise).
- **The exemption** (decided by the maintainer, 2026-11-17, "C"). With the
  settle rule alone one golden answer moved:
  `mixed-content-curated/GPL-3.0-or-later/README.md` ("GPL License version 3.0
  or any version later") went to `GPL-3.0-only`. `OR_LATER_PHRASE` does not
  read "or any version later", so `main`'s `-or-later` was a guess from the
  marker's own regex, but `-only` would be a wrong claim. The settle rule now
  stays off where the input holds a later-version phrase no subject owns
  (`grantsubject.has_unowned_phrase`: `any later version`, `any version later`,
  `or later version`, not negated, not starting inside a grant that `grants`
  read, a tool's included: `Python 3.8 or any later version` is the tool's and
  still settles). `OR_LATER_PHRASE` is not widened (that would move `resolve()`
  and the tag and field readers). Measured on the 250 distinct files of the
  sweep: one holds such a phrase (that README), 12 grants of a tool all still
  settle; golden: unchanged. Limit: an unowned phrase of a tool elsewhere in
  the text (`Needs Python 3.8 or later. Plugins may use any later version.`)
  also keeps an `-or-later` answer, as `main` did.
- **Moved with it**: `variants.py` shrank by moving the reader of a declared
  value's stated words to `variantstated.py` (no change); `classify` exports
  `RE_OR_LATER_SHORTHAND` with groups and a text-based `same_version` (an
  `int()` of 5,000 digits raised).
- **Review** (independent, Opus, read-only): the owner of a number after "the
  Free Software Foundation" was `foundation`; an escaped line break (JSON)
  lost a GPL notice; `WITH Classpath-exception-2.0 or later` took the
  exception's name; a superscript digit and a 5,000-digit number raised
  `ValueError`; 100,000 `GPLv2+` made each question O(grants). All fixed with
  rows in `tests/test_grant_subject.py`.
- **Second review** (independent, Opus): a wrapped notice under the comment
  leaders of autoconf (`dnl`), TeX (`%`), Texinfo (`@c`), man pages, batch
  files and mail quotes lost its owner (`_LEADER` drops them); `and` and `at
  your discretion` before "any later version" were no preamble; the written
  check ignored an ID with a `WITH` exception (it reads the head only); the
  `as-written` collapse kept the GPL twins because an LGPL grant stood
  somewhere (now per licence); a pure licence text (COPYING, LICENSE) with a
  notice and a tool's grant was flipped to `-only` (`ranking.leave_signal`
  is true for a pure text: its answer is left). Rows in
  `tests/test_grant_subject.py` and `tests/test_grant_signal.py`, each
  mutation-checked.
  The full golden then moved one answer: `short/LGPL-2.0-only/tail_1000` (a
  text cut at "or (at your option) any later version", no subject) went to
  `-only`, as the tie-breaker read only a phrase a grant owned; an unowned
  phrase now counts as a grant there too, as on `main`
  (`test_the_tie_breaker_keeps_an_unowned_phrase_as_granting`). Rerun the
  full golden after every change on the answer path, not only at the end.
- **Left** (the name tier's part is the next section): `markers`' two grant
  readers; a tool's `version N` is still a grant of `(N, None)` where no word
  names it (`Compatible with version 3.0 or later`: grants every GNU licence of
  version 3); `GFDL-1.3+` is no shorthand grant; "or any version later" is no
  phrase (the exemption above only keeps the answer); `variants._supports`
  still reads any grant phrase in a declared value (`has_or_later_language`).

## Small leftovers of items 35, 46, 50, 53 and 55 (PR #223, 2026-11-18)

Planned and measured on `main` da544cb with a copy of the real database
(SPDX List 3.29.0). No answer of the library moves: tools, tests and notes.
PR #223.

- **Item 35, `exclude` read only by Tier 1** (PR #211): verbatim MIT,
  Apache-2.0, BSD-2-Clause and 0BSD texts with `exclude=[ID]` no longer list
  the ID. **A deprecated row with no text answering a GPL README** (PR #212):
  the README "GNU General Public License version 2" gives `GPL-2.0-only`
  0.915 under `auto` and `as-written`, warning `variant not stated`. The
  repeated-text bullet stays open.
- **Item 46, condition words for empty input**: right already. `--text ""`,
  `--text "   "`, an empty file and `resolve ""` print `ERROR: input: empty:
  <where>`, exit 2. **The METADATA of a dev build**: a dev version is written
  in PEP 440 normal form (`0.9.0.dev0`) at the version bump, a line in
  `release-process.md`. Open still, among others (roadmap item 46): `hint`
  against the filters, the API names, `is-*` on several tags, a garbage
  `--db`, `update --source packaged` samples, and the `wal_copy_without_wal`
  and `damaged_fts_shadow_table` failures (8 on `licenseid310` with SQLite
  3.51.0, on `main` too).
- **Item 50, no-section `license = "MIT OR ISC"`** (PR #219): no answer, with
  `too few words for text: operand not resolved` (the line is a `key = value`
  line, and no measured value has that shape). **`disambiguate_whole`**
  (decided 2026-11-17, PR #221): it stays. **The harness database**: the
  `value`, `id` and `name` golden kinds run on the full List
  (`tests/harness_db.py`, `DECLARED_KINDS`); `long`, `short` and `mixed` stay
  on the long-text fixtures, because the full List moves 10 of their rows,
  two of them losses (`libpng-1.6.35` in mixed content, a name hit lost to a
  text match under 0.5: a finding for the name tier). On the full List 3 of
  the 6 `id_deprecated` rows equal the golden and 3 answer the bare ID
  (`GPL-2.0`, `LGPL-3.0`, `AGPL-1.0`: `yes`, as a bare deprecated ID stays as
  written, #212), listed in `tests/harness_changes_variant.py`. The golden
  headers still say "long-text fixtures" until the release regeneration.
- **Item 53, a cut `-shm` of a legacy WAL database**: closed as a known
  limit (`cross-platform.md`). It needs a database built before 0.4.2 and
  never `update`d since, a connection held open, and a `-shm` cut by another
  program; private alpha, one user. Rejected: refusing a WAL file with a
  `-shm` in the readiness check, and `locking_mode=exclusive`.
- **Item 55, the four URL pages without a count** (`mozilla.org/mpl/2.0`,
  `opensource.org/license/mpl-2-0`, `opensource.org/license/ofl-1-1`, the SIL
  `ofl_web` page): kept. The List gives each to the licence and its variants
  (`MPL-2.0` and `MPL-2.0-no-copyleft-exception`; `OFL-1.1`, `OFL-1.1-RFN`,
  `OFL-1.1-no-RFN`), which is the evidence, so the page computes it (column
  "The List gives the page to", `measure.list_owners`) and the test checks
  the four of `evidence.LIST_PAGES` against the List. A fifth row still needs
  a survey count. **A trove name with no count shows a dash**: correct, as the
  page says "A dash is no count recorded".

## `hint` obeys the filters; the API names (PRs #224, #227, 2026-11-18)

Item 46.

Built in PR #224 (branch `hint-obeys-filters`). Planned and measured
on `main` f28fa39 against a copy of the real database (List 3.29.0, 740
rows), then reviewed twice (Opus). The owner decided D1 a, D2 a (with the cap
below) and D4 a.

- **H1 to H5, built.** `retrieval.get_candidates` no longer adds a hint;
  `retrieval.hinted_candidates` builds the hint candidates and passes them
  through `_filter_candidates`, and `detector._run_tier1_and_tier2` adds them
  last (`add_unseen`), after the markers and the mixed-content search. So
  `exclude`, `only_common` and `only_spdx` drop a hint (H1, H2); a marker's
  candidate with text is kept (H3); a hint no longer counts towards the
  fewer-than-5 gate of the mixed-content search (H4); a hint ranks on its
  text (H5).
- **Measured, before and after** (real database): MIT text with `exclude`
  and `hint` of MIT: MIT at rank 49 of 50 (0.0805) to no MIT. JSON text,
  `only_common` and `hint=["JSON"]`: JSON at rank 17 of 18 (0.0805) to JSON
  first, 1.0, exact (its heading's candidate; the hint adds nothing).
  `GPL-3.0-only` hinted on the MIT text: rank 50 (0.0) to rank 46 (0.5256).
  A bare `GPL-2.0` hint under `auto`: its twins from rank 50 and 51 (0.005
  and 0.0) to 41 and 46 (0.548 and 0.538). The top 4 of the GPL-2.0, MIT,
  BSD-3-Clause and Apache-2.0 texts, under `auto`, `as-written`, `only` and
  `or-later`, with and without a bare `GPL-2.0` hint, keep their order. No
  golden answer uses `hint`: 0 moves.
- **Cost, and the cap.** A hint's text costs a Tier 2 pass. `detect()` of
  the MIT text on the real database: 0.8 s with no hint (the same with a
  hint of no text), 1.6 to 2.0 s with 50 hints with text, 3.4 to 3.8 s with
  200, about 10 s with all 740. So `retrieval.MAX_HINTS_WITH_TEXT` is 50: the
  first 50 IDs of `hint` (after the deprecated-ID upgrade, in the order
  given) carry their text, the rest are added with none and score 0, as
  before. A deprecated row has no text (`GPL-2.0` kept as written under
  `as-written`, the `-with-` IDs): it scores 0 too. Documented in
  `docs/python-api.md`.
- **Which candidates each filter drops** (documented): a hint passes the
  filter function of full-text search, but marker candidates and the names of
  mixed-content sections pass `exclude` only. So `only_common` drops a hint
  and keeps a heading's answer.
- **A1, built.** `ToolInfo` (one `TypedDict`: `name`, `version`, `url`,
  `purl`) replaces `Resolver` and `Component` (the same four keys; no user
  outside the package, grepped over `~/projects`), for `Resolution["resolver"]`
  and `["components"]`. `licenseid` exports `ToolInfo`, `DetectOptions` and
  `Variant` (the type of `DetectOptions.variant`). JSON keys and values do not
  change.

## Grant subject in the name tier (B1c, PR #225, 2026-11-18)

Tier 0's `namerules.cut_version` took the number before any "or later" or
"+" as the licence's grant: `Apache License 1. Requires Java 1 or later`
answered `Apache-1.1`. It reads grants through `grantsubject` now, and the
name tier doubts a GPL hit for a Lesser, Library or Affero name.

- **Cut rule** (`namerules.cut_version`): only a grant of the hit's own
  licence (`grants_licence`) exempts a cut number, and only where the hit's ID
  carries a grant (`-or-later`, `+`): `GNU Lesser General Public License v2 or
  later` stays LGPL-2.1-or-later, `Apache License 1 or later` names no row
  of the List and gets no answer (`resolve()` refuses it too). A grant
  exempts one written number, compared with `classify.same_version` (`GNU Free
  Documentation License v1 or later. Requires Java 1 or later` is none: the
  tool's `1` was the minor that tied GFDL-1.1-or-later above its twins).
  `namerules` reads no `OR_LATER_PHRASE` and no `PLUS_OPERATOR` any more.
- **Whole version** (decided D-6): the version written in full exempts the
  cut only where the name has it: a run that follows, within three words,
  the word the name's run follows (`license` of `Apache License 1.1`;
  `through` of `PNG Reference Library License v1 (for libpng 0.5 through
  1.6.35)`; `AGREEMENT Version 1.1.0` of the eGenix title). `Requires Java
  1.1`, `built with Ant 1.1`, `Python 2.1` (AFL-2.1 for `Academic Free
  License v2. Requires Python 2.1`) no longer count. The first form, "right
  after the name's last word", lost `libpng-1.6.35` for eight sentence
  templates and one `eGenix` text window in the sweeps: the rule is per run
  of the name, with a reach of three words (`_NAME_REACH`).
- **Family rule** (D-2 c, `namerules.names_other_gnu_licence`): a `GPL-*` hit
  is doubted where every "General Public" of the input has Lesser, Library or
  Affero before it, a `GNU` between aside (`grantsubject.MODIFIERS`, now
  exported). It needs no grant: `GNU Lesser General Public License v2.0 only`
  was `GPL-2.0-only`. An input that writes the plain GPL's name too (`GNU
  General Public License v3.0 or later. Not the GNU Affero General Public
  License`) keeps its answer: the first form of the rule scanned the whole
  input and lost seven such right answers (found in review). The first design
  (`grant_of_another`, a grant of another family on the hit's number) needed a
  second number reader and missed the `only` form.
- **Not changed**: D-3 (`with` over three words) and D-4 (`Modified
  <name>`), recorded in roadmap item 47 with the wrong answers found on the
  way; `General Public License (Lesser) v2.0 or later` and `General Public
  License, Lesser, v2.0 or later` (the modifier not before "General Public")
  still answer `GPL-2.0-only`.
- **Measured** (the real 3.29.0 List, `main` against the branch, top at
  0.85): raw licence texts and headers, 19,723 windows: 0; phrase
  windows 1,548: 0; the name in 14 templates, 10,360: 0; PyPI sample 463: 0;
  the 12-template cut and full-name probe, 5,619: 407 to none, every one a
  cut version that #219 decided gets no answer; `tools.golden`, every part:
  as the golden.
- **Tests**: `tests/test_name_tier_grants.py` (the List's names), made-up
  rows in `tests/test_namehits.py` (`Cutg`, `Plusg`, `Rng`, `Egx`,
  `GPL-9.0-*`); two rows of `test_a_cut_version` flipped (`Cut Name 1 or
  later`); two rows left `BUGS` of the leftovers for `DECIDED`, with five
  new ones. Mutants of the cut rule, the reach and the family rule are all
  killed.

## A List name wrapped in marks (item 50, PR #226, 2026-11-18)

`*Apache License 2.0*`, `# Apache License 2.0` and `*Mozilla Public License
2.0*` answered exact by name in `detect` while `resolve()` said `not found`.
The same marks round `MIT License` were already refused
(`character dropped: U+002A`): a name a loose ID reads met the guard against
dropped marks, a name of the List-name table did not. Decided (D5 a): refuse,
precision over recall. PR #226.

- **Built**: `dropguard.edge_marks`, `resolvereason.wrapped_name` and
  `resolveleaf._refuse_wrapped_name`, called in `_base` after the List-name
  lookup fails and before the `+`/bracket early return. One guard in the
  resolver; no change to the name tier: `detect` refuses through
  `resolvereason.refuses_text_match` (no answer, warning `too few words for
  text` under 10 words; from 10 words on, see the review finding below).
- **The rule** (the first plan, "strip everything that is no letter,
  separator, bracket or quote", was wrong: it refused `Apache License 2.0,`,
  `MIT License:` and `MIT License++`, and missed `- Apache License 2.0`):
  from the start every character that is no letter, digit, bracket or quote
  mark (white space, dashes and dots too: it subsumes `lead_marks`); from the
  end the same, but a `+`, a dash, `_` or `.` stays. Quote marks (`'` and
  the grave accent too) and corner brackets stay at both ends: a name with
  quote marks inside (`BSD 3-Clause "New" or "Revised" License`) is not
  unwrapped by the quotes step and stays read. The reason names the cut
  marks only (`*Sun PPP License (2000)*` is `U+002A`). The core must be a List
  name of exactly one ID, and what was cut more than one end mark of `.,;:`
  at the end, or anything at the start.
- **Measured** on `main` f28fa39 and the branch (SPDX List 3.29.0): 0 of 520
  golden and PyPI values move; the full golden moves 0 answers; the
  linear-time check on `"*" + "x " * N + "*"` and `"*" * N + "Apache License
  2.0"` is the same as `main`.
- **Moves**, besides `resolve()` and the `detect` text channel: a `license`
  field `*Apache License 2.0*` or `# Apache License 2.0` goes from
  `Apache-2.0` exact to no answer; `MIT OR *Apache License 2.0*` has the
  reason `character dropped: U+002A` (was `operand not resolved`);
  `*Apache License 2.0*; MIT` has `operator not stated: ;` (was `not found`).
- **Left** (known gaps; roadmap item 50): `*Apache License 2.0*.` (marks
  after an end mark) and `1. Apache License 2.0` (a list number) still answer
  `Apache-2.0`, exact, by name.
- **Review finding, fixed** (long names): from 10 words on, a refused
  wrapped name went on to the text tiers, as `Name*` did on `main`, and the
  text could answer another licence (`*European Space Agency Public License
  (ESA-PL) - V2.4 - Strong Copyleft (Type 1)*`: `ESA-PL-strong-copyleft-2.4`
  exact on `main`, `ESA-PL-weak-copyleft-2.4` at 0.8722 on the first branch).
  Measured on the 708 List names of one ID, each in 8 wraps (`*N*`, `# N`,
  `- N`, `~N~`, `|N|`, `<N>`, `*N`, `N*`; 5664 values; 128 of them names of
  10 words or more), `detect()` top answer, `main` against the first branch:
  at the 0.85 bar 3486 went to none, 56 kept the ID but turned inexact
  (35 of them 10 words or more), 7 went to another licence (all the ESA-PL
  name), 2115 stayed; with no bar (the top of the API list) 84 went to
  another licence. `main` answered another licence for 1 (`N*`). Now
  `detector._short_text_refused` asks `resolvereason.no_text_answer`: a
  refused value that is a listed name in marks (`resolvereason.wrapped_name`,
  the guard's own test) has no answer from 10 words on, and under 10 the
  `too few words for text` warning as before. All 5664 values have no answer,
  with or without the bar; 0 another licence; the 35 inexact right answers
  are lost (precision over recall, as under 10 words). Any other refused
  value of 10 words or more is matched as before.
- **Left**: `_Sun PPP License (2000)_` is `not found` (was `character
  dropped: U+005F`; refused either way), and a `license` field with a mark
  only at the end (`Apache License 2.0*`) still answers.

## 0.9.1 (PRs #230 to #235, 2026-11-19 to 2026-11-20)

Small fixes, each with its tests, mutation check, golden and a `probe_real`
run against the last tag (0 moves of a right answer). Plan: roadmap item 58.

- **#230**: Tier 2 candidate scoring moved to `similarity.py`; `detector.py`
  735 to 675 lines. No change in answers.
- **#231**: `urls_as_ids` reads an encoded "+" (`GPL-2.0%2B`) as the literal
  one: `exact` and `VARIANT_STATED` true.
- **#232, #234**: a bare `MIT++`, `MIT +`, `GPL-2.0-only+`, `(MIT)+` warns
  `too few words for text`. The predicate of a stray "+" lives in
  `detector._match_text`. Review finding fixed in #234: a stray-plus value of
  10 words or more reached Tiers 1 and 2 and could answer; now none.
- **#233**: `MIT or later.` is `separator` with an `end mark` step, not
  exact (`resolveleaf._single`, `resolvefirst.was_cut`). Known gaps are in
  `docs/resolve.md`.
- **#235**: bug 4. `GNU General Public License version 2.0, requires Python
  3.8 or later` answered `Python-2.0`: `token_set_ratio` ignores order and
  gaps, and "written whole" was checked only for tied names. A class: 133 of
  672 probes of `... version 2.0, requires <word> 3.8 or later` answered a
  wrong name, 0 now. Fix: `namehits._names_another` reads the other name
  without its grant (`_without_grant`, shared with `_stands_apart`); no new
  rule. Rejected: a gap or order measure on one hit (22 right scattered hits
  are out of order), a coverage share (right and wrong answers overlap), a
  scorer change (changes Tier 0 for every input). Moves on the 34 grant-row
  names: 30 of 121 inputs, all answer to none, each naming two licences
  (`MIT License, GNU General Public License v2.0` gave `MIT`). Review: no
  right answer moved over about 10,000 inputs; stripping the hit's own name
  too changed nothing and was dropped. Time: 3.4 ms per call, as `main`.
  Left: no "GNU" in the text; `GNU General Public License v2. Requires
  Python 2.0 or later to build`; `PSF License version 2.0 requires Python
  3.8`.

## Item 60: copies of the Apache-2.0 text answered BSD-4-Clause (2026-11-25)

Found 2026-11-23. Cause: `bsdclauses.bsd_clause_id` took the highest number
of the lines `N. Redistribution|Neither|...`, and the Apache-2.0 section "4.
Redistribution. You may reproduce..." alone read as BSD-4-Clause. The marker
(0.95, floor 0.9025) beat the text score of two or more copies (SIMILARITY
0.155 at two, 0.017 at twenty). Fix, two rules:

- The keyword is `Redistributions?` followed by `of` or `in` (`_RE_CONDITION`):
  the BSD conditions read "Redistributions of source code", "Redistributions
  in binary form"; the Apache heading "Redistribution." matches neither.
- The numbers found must be exactly 1 to N with no gap (a repeated text keeps
  its answer); otherwise no reading. Review found the case the gap rule alone
  misses: an Apache-2.0 text and a BSD-3 text in one file (grpcio, torch,
  numpy) give 1, 2, 3 and the Apache "4.", so 1 to 4 and BSD-4-Clause at
  0.9402. The keyword rule leaves 1 to 3, BSD-3-Clause.

- **Measured** (build 6 database; base is `main`; 16,803 texts: the 826 List
  texts of the 3.29.0 tarball as written, not `search_text`, which is
  normalised and has no "N." lines; `license-text-long` and `-short` with
  their distortions; mixed-content fixtures; 499 real LICENSE files):
  `bsd_clause_id` moved on 371 texts against base, 289 for the gap rule
  alone. `detect()` moved the top answer of 16 against base (7 long, 2
  short, 7 real) and 4 against the gap rule alone (real files: grpcio, torch
  and numpy BSD-4-Clause to BSD-3-Clause; pandas `CATOSL-1.1` to
  BSD-2-Clause, 0.9377, still not BSD-3-Clause).
  Of the 16, 3 are now right (`BSD-2-Clause-Views`, `BSD-3-Clause-Tso`,
  `xinetd`), 13 another wrong or below-threshold answer; 0 right answers
  lost. 38 List texts lost their marker (Apache-2.0, Apache-1.1, OLDAP-2.2.2
  to 2.6, Sendmail, ...; OLDAP-2.7 and 2.8 BSD-3 to BSD-2) with the top
  answer unchanged. Two are BSD-named: BSD-Inferno-Nettverk (numbers 2, 3)
  and BSD-Mark-Modifications (1, 2, 4); their top answer is unchanged. No
  plain BSD-N-Clause text moved; no mixed-content fixture moved.
- **Left**: a marker floors a text's score at 0.95 times its confidence
  whatever its similarity; on a multi-licence file another marker now
  answers (Pillow `GPL-2.0-or-later` 0.874, scikit-learn `Apache-2.0`
  0.884): item 67.

## Item 67: a marker floor answered a file of several licence texts (2026-11-25)

Found in the fix of item 60. Cause: a marker of confidence `c` (0.85 or
more) sets a candidate's score to at least `0.95c`
(`similarity.calculate_final_score`), whatever its similarity, on every input
but a pure long text with `c` under 0.94. In a file of several licence texts
the marker reads one of them and answers for the file: Pillow 11.2.1's
`LICENSE` (11 texts, none GPL) `GPL-2.0-or-later` 0.874; pandas 3.0.6
`BSD-2-Clause` 0.9377; grpcio 1.65.5 `BSD-3-Clause` 0.9402.

- **Rule** (owner's choice of five measured, 2026-11-25): the floor stays
  unless the input is longer than the marker's licence text (`COVERAGE` above
  1.05, the top of the "whole text" band) and the whole-text search of
  `TEXTS` finds texts that are not all the marker's licence's (its same-text
  group, an `-only`/`-or-later` twin, a deprecated ID's replacement, an
  exception dropped). Then the candidate keeps the additive `0.05c` only. It
  acts on positive evidence alone: a search that finds nothing keeps the
  floor, so a text the search cannot confirm (PyTorch's BSD-3-Clause with a
  copyright block inside, item 64) answers as before.
- **Code**: `similarity.floor_lift` (what the floor added; the score keeps its
  five arguments) is stored as the internal `floor_lift`; `markerfloor`
  takes it back in `LicenseDetector._rank_candidates`, before the
  fingerprint bonus and the sort. The search runs once per input, only where
  a floor binds above coverage 1.05, and calls `wholetexts.found_rows`
  directly, not `textnames.held_texts`: terse `detect`, `is-*` and `is_*()`
  give the same answer as `-v`.
- **Rules rejected** (measured on the plan's probe): no floor at all loses 55
  right fixtures and 4 right real files (sphinx's `LICENSE.rst` would answer
  Sleepycat); a similarity bar (0.5 to 0.8) loses 40 to 55 right notices,
  whose similarity (0.22 to 0.6) is that of Pillow's misfire (0.53); coverage
  alone (1.05 to 2.0) loses pytorch.txt and sphinx; "the texts found must
  hold the marker's licence" loses pytorch.txt, whose text the search misses.
  Any bound from 1.05 to 1.3 gives the same answers.
- **Measured, the plan** (`main` 4c5d13e with the rule patched in; build 6,
  List 3.29.0): of 6,543 inputs (499 real licence files, 6,044 fixtures), 94
  have their top on the floor; every misfire of the item is above coverage
  1.05, and under 0.8 the floor lifts 60 right notices and pointers. 16 answers
  at 0.85 move, golden none: Pillow, pandas, grpcio and the Saxpath
  `tail_2000` fixture lose a wrong answer; numpy 1.26.4 to 2.2.6 and scipy
  1.13.1, 1.15.2 (`LGPL-2.1-or-later` 0.9472), numpy 2.4.6 and scipy 1.17.1
  (`BSD-3-Clause-Open-MPI` 0.9525) now answer `GPL-3.0-only` 0.92 to 0.93
  (bundled, wrong either way: item 59); four files lose a partial answer
  (numpy MT19937 and highway `BSD-3-Clause`, tensorboard `Apache-2.0`, the
  torch 2.6.0 `NOTICE` `BSD-3-Clause`: each names one licence of a file that
  holds several). Right answers lost: none. Cost: the search on 25 of 499
  real files, +23 ms each (+4.5 percent) on terse `detect`.
- **Measured, the build** (b98707d against 4c5d13e, a build-6 database of
  List 3.29.0): the 6,044 fixtures (1,665 long, 4,170 short, 183
  mixed-content, 26 curated) move one top answer, the Saxpath `tail_2000`
  (`BSD-3-Clause` 0.9025 to `OpenSSL` 0.8376, `TEXTS` `Saxpath`), as the plan
  says; `python -m tools.golden`: no row moves. The 499 real files were not
  run again: their scratch copy was lost; the plan's 15 real changes stand
  from the patched probe.
- **Review fix: look-alikes held back** (2026-11-26). With the floor gone a
  look-alike the file does not hold could win: a BSD-3-Clause and a
  BSD-2-Clause text answered `Sleepycat` 0.9103 (on 4c5d13e `BSD-3-Clause`
  0.9472), BSD-3 and BSD-4 `Sleepycat` 0.9264, BSD-4 and BSD-2 `Sleepycat`
  0.9149. Now, where `doubt_floors` takes a floor back, it drops from the
  ranking every candidate whose licence is none of the texts found
  (`markerfloor.found_in`: same-text group, replacement ID, exception
  dropped); one of them stays as scored (numpy `GPL-3.0-only`, item 59). The
  same search, no second one; text candidates only (Tier 0 and declared
  values never reach `_rank_candidates`). Measured against 4e11b37 (build 6,
  List 3.29.0): 596 real files, no answer at 0.85 moves; seven tops under
  0.85 change, six from a look-alike (`APL-1.0`, `CATOSL-1.1`, `NPL-1.1`,
  `RPSL-1.0`, `LGPL-3.0-or-later`, `GPL-3.0-only`) to one of the texts
  found, and a numpy 2.4.6 `LICENSE.md` from `BSD-3-Clause` 0.7375 (its text
  not found) to `MIT` 0.5688. 6,044 fixtures: one moves, the Saxpath `tail_2000`
  (`OpenSSL` 0.8376 to no result: its one text found, `Saxpath`, is no
  candidate, so `TEXTS` is empty too). The reviewer's 31 synthetic files:
  every look-alike top (`Sleepycat`, `FSL-1.1-MIT`, `XFree86-1.1`) is gone,
  none answers at 0.85. `python -m tools.golden`: no row moves. Time
  (100 real files, base, 4e11b37 and the fix interleaved, best of 3): median
  ratio to base 1.00 for both; the 1.15 of the earlier run came from running
  base and branch one after the other. The search runs on 27 of 596 files.
- **Left**: floor misfires under coverage 0.8 (docutils `COPYING`
  `GPL-3.0-or-later`, a GPL "Secondary Licenses" clause in a distorted EPL-2.0
  copy); scikit-learn `COPYING` `Apache-2.0` 0.884 is similarity, not the
  floor (item 59). A record of no answer has `TEXTS` empty (item 59).
- **Left, no-answer record**: the Saxpath `tail_2000` fixture now gives
  `REASON=no match` and empty `TEXTS`, though the search found `Saxpath` (not
  a candidate); tied to item 59.
- **Left, old database**: a database older than build 5 has no `same_text`
  groups, so `--top` drops the other `-only`/`-or-later` twin of a text found
  (the printed answer is unchanged; the database warns `build vN outdated`).

Item 35's last open bullet (`LICENSE`, Apache-2.0, three times over answered
`BSD-4-Clause` 0.9025 through the floor) was fixed by PR #242: on 4c5d13e and
on this branch it answers `RPSL-1.0` 0.7267, no answer at 0.85 (`TEXTS`
`Apache-2.0`); twice, `Apache-2.0` 0.7444. No marker floor binds. Item 35 is
closed.

## Item 59: a file of several licence texts (2026-11-26)

A text answer stands only when its text is the first whole text found
(`firsttext`); a record of no answer carries `TEXTS`, with `REASON=several
texts`; `TEXTS` is in file order; `texts()` in the API. On 596 real files the
14 answers of the plan move to none (13 wrong: numpy, scipy, scikit-learn,
mypy, roman_numerals; 1 right lost: pytype), terse and `-v` agree. Details,
the options rejected and the numbers:
[`whole-texts.md`](whole-texts.md), section 9.
