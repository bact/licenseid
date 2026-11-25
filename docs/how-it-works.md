---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# How it works

What `licenseid` does inside: the normalisation of IDs, the reading of
declared values, SPDX expressions and the matching pipeline.

- **Deprecated ID normalisation**:
  - `GPL-2.0+` → `GPL-2.0-or-later` (SPDX `+` operator, unambiguous).
  - `Apache-2+` → `Apache-2.0+` (abbreviated base canonicalised, `+` retained).
  - Bare deprecated IDs (e.g. `GPL-2.0`): `detect()` keeps a declared one as
    written, as `resolve()` does ([Resolve a declared
    value](cli.md#resolve-a-declared-value)), with `VARIANT_STATED=false`; a
    text or a List name without its grant (`GNU General Public License
    v2.0`) answers `-only` first, then `-or-later`, with `WARNING: input:
    variant not stated: GPL-2.0; using GPL-2.0-only`, unless the input
    grants later versions of that licence (then `-or-later` first, stated). A
    grant is the licence's it names: `GPL-2.0 or later` is, `Requires Python
    3.8 or later` grants nothing. `-only` is the
    licensee's careful reading: it understates a licensor's "or later" grant.
    `VARIANT_STATED` says whether the input stated the variant, and
    `--variant` changes the choice
    ([Detect](cli.md#detect-a-licence-or-resolve-a-declared-value)); a name
    with a "+" (`v2.0+`), or without its version too, is no answer.
- **Declared-value resolution** (`resolve()`, and `licenseid resolve` on the
  command line): turns one declared licence value (a `license` field, a
  model card, a trove classifier) into an SPDX expression and the steps
  taken, without fuzzy matching, with or without a database. It reads loose
  IDs (`Apache2`, `GPLv3`), the List's names, a licence's own title (`CC0
  1.0 Universal`, `Mulan PSL v2`), the BSD aliases (`New BSD`, `BSD-3`),
  prose forms (`BSD 3-Clause License`), licence URLs
  (`https://www.apache.org/licenses/LICENSE-2.0`, `spdx:MIT`; a URL of
  several licences is refused),
  quote marks, trove classifiers and compounds of one-word
  operands, and refuses, with a reason, what it would read only by dropping
  a mark or a word. What it reads, rule by rule, is in
  [resolve.md](resolve.md#what-resolve-reads), and the lists it reads, row by
  row, in [lists.md](lists.md); the order the readers run in
  is traced in [resolve-flow.md](resolve-flow.md), and the canonical form
  of an expression in
  [expression-canonicalisation.md](expression-canonicalisation.md).
- **SPDX License Expression support** (via
  [`py-spdx-license`][py-spdx-license]):
  - Structural normalisation of `AND`/`OR` expressions, in a tag or a
    manifest field, and in a whole input `resolve()` reads (`--id` takes one
    licence): duplicate operands collapse (`MIT AND MIT` → `MIT`)
    and operands are put in a consistent order, making equivalent expressions
    compare equal. A whole input takes `resolve()`'s canonical order
    (`MirOS OR MIT`); a tag, a field and a variant `--variant` chose keep
    the detector's own (`MIT OR MirOS`; `--variant only` reads
    `MirOS OR GPL-2.0` as `GPL-2.0-only OR MirOS`).
  - The flags of an expression are judged operand by operand: `AND` is
    OSI-approved (or FSF-libre) when every operand is, `OR` when any is,
    `X WITH Y` when `X` is. An operand that cannot be judged (a
    `LicenseRef-*`) leaves the flag empty (`null`), never a false "no",
    unless a judged operand decides it: `MIT OR LicenseRef-x` is
    OSI-approved, `CC-BY-4.0 AND LicenseRef-x` is not. `is_spdx` is true
    only when every licence and exception ID is on the List: a
    `LicenseRef-*` makes it false.
  - `WITH <exception>` expressions are validated and matched against the
    SPDX exception list, not just the licence list — e.g.
    `licenseid detect --id "MIT WITH Font-exception-2.0"` resolves correctly
    even though it isn't a single licence row.
  - A `SPDX-License-Identifier` tag, and the `license` field of a JSON, TOML
    or INI file, are read as whole expressions, parentheses, `LicenseRef-*`
    and all: `MIT OR (Apache-2.0 AND BSD-3-Clause)` in a file resolves to
    one answer. `--id` is narrower on purpose (see `--id` under
    [cli.md](cli.md#detect-a-licence-or-resolve-a-declared-value)). A tag or field
    names only IDs on the List, or `LicenseRef-*`: an operand that is none
    (`MIT OR Apache 2.0`) gives no answer, as `resolve()` refuses it. A
    bare "or later" after an ID is the grant (`MIT or later`, `MIT, or
    any later version` are `MIT+`); a "+" apart from its ID (`MIT +`) names no
    licence. A tag gives no answer, as `resolve()` does, for a licence listed
    after a grant (`GPL-2.0 or later, ISC`) or an "only" after an operand of a
    list (`MIT OR GPL-2.0 only`); a tag that goes on with an operator after a
    grant (`MIT (or later) AND Apache-2.0`) reads as `resolve()` does.
  - Package manifests are read for their `license` field, however small:
    `package.json` (with npm's old `license` object and `licenses` array),
    `pyproject.toml` (`license = "..."` or `license = {text = "..."}`, and
    Poetry's; a TOML basic string is read with its escapes undone,
    `"\"MIT\""`, a literal one as written), `Cargo.toml` and `setup.cfg`.
  - In other text, a `License:` line is read too: each distinct value once,
    the first 256 of them, and the first 48 licences that resolve.
- **Hybrid matching pipeline**:
  - **A whole value first**: an input that is, as a whole, one declared
    value (`MIT OR Apache-2.0`, `Apache License, Version 2.0`, `GPLv3+`) is
    read by `resolve()`, so `detect` answers its expression, a bare split
    ID as written (see the deprecated ID item above). What a value
    `resolve()` refuses gets (under 10 words, often no text match and
    `WARNING: input: too few words for text: <reason>`) is in
    [how `detect()` uses `resolve()`](resolve.md#how-detect-uses-resolve).
  - **Tier 0 (Shortcut)**: Fast path for short inputs (names, IDs, brief
    expressions). Includes:
    - Case-insensitive exact ID match.
    - Prose-context disambiguation for bare deprecated IDs (e.g.
      `"GPL-2.0 or later version"` → `GPL-2.0-or-later`).
    - For a licence name with no grant, `-only` first, said with a warning
      (see the deprecated ID item above).
    - A name the input holds whole is dropped when the words beside it name
      something else: a tie of two licences, a cut version, an exception, a
      fragment of a longer name, another ID or another licence's name written
      whole (its grant aside), a dash glued to a word end, the LGPL's or
      AGPL's name for the GPL's. Of tied names the one written
      whole (its words in order) beats one put together from scattered words,
      and the most specific of nested names wins. A dropped name that scored
      above 1 gives no text answer from 10 words on; under 10 words the input
      still gets the `too few words for text` warning.
  - **Tier 0.5 (Marker detection)**: Detects `SPDX-License-Identifier` tags and
    structured markers (name fields, headings). An exact SPDX tag returns
    immediately with full confidence.
  - **Tier 1 (Recall)**: Candidate retrieval using SQLite FTS5 trigram index,
    queried with the input's first 20 words, plus its last 20 for an input
    over 200 words (at most 25 more candidates), for consistent performance.
    When removing the copyright notices changes those first 20 words (a
    title and a long copyright line can fill them), a second head query
    runs without the notices. When its first 10 results hold a licence the
    first query did not find, it adds all of its 50 results the first query
    lacks; otherwise it adds none.
    A word is cut to its first 128 characters (the longest word of the List
    is 70), so one very long word stays fast.
    Comment prefixes (`//`, `#`, `*`, `;`) are stripped before querying.
  - **Tier 2 (Precision)**: Adaptive ranking with RapidFuzz. An input of at
    least 80% of a text's words (or a very long one) is compared with the
    whole text by sorted words; a shorter one is aligned with the best part
    of the text, a fragment. An input of about a licence's core length is
    compared with its core as well: the text without its optional parts (an
    appendix, or the GPL-3.0 text quoted in the LGPL-3.0), which the SPDX
    matching guidelines allow for optional text. The higher similarity
    counts, and coverage is counted over the words of the text that won;
    `EXACT` is still a whole-text match. The score then adds small terms for
    coverage, for marker confidence (applied only from 0.85) and for a
    fingerprint. A marker's confidence floor stays only where the input is
    no longer than the marker's licence text (coverage up to 1.05) or the
    search of whole texts (`TEXTS`, below) finds no text but that licence's.
    What `SCORE`, `SIMILARITY` and `COVERAGE` measure, and
    their ranges, is in [output.md](output.md#default-and-verbose-text).
  - **Whole texts (`TEXTS`)**: After the ranking, the input is searched for
    every whole text of the List, without a database query per text. Words
    become one code each; a text is first sampled by its word 5-grams, and
    one that the input holds has most of them. The word 5-grams of such a
    text vote for an offset, and neighbouring offsets with enough votes make a
    window (each copy of a repeated text gets one). The words are aligned in
    the window and the ends trimmed while that raises the fit; the character
    similarity of the text and its trimmed span must be 0.95 or more. A copy
    that drops a critical word such as "not", or misses 150 characters or
    more of the text in one run (a clause), is not counted. Hits are kept
    best first, and one that overlaps a kept hit by more than a tenth of the
    shorter span is dropped; copies of one text are then named once. Every
    cost is bounded by a count (characters, tokens, votes, windows, cells):
    past one the field is empty, never a partial list. A text that a close
    look-alike (character fit 0.93 or more) fits about as well is named only
    at a fit of 0.98 or more; else its part names nothing. A text refused
    only for a critical word still counts as that look-alike's rival.

[py-spdx-license]: https://github.com/JPEWdev/py-spdx-license
