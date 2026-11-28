---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# How it works

What `licenseid` does inside: how it reads IDs, declared values and SPDX
expressions, and how it finds the licence of a text.

## Deprecated IDs and variants

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

## Declared values

`resolve()`, and `licenseid resolve` on the command line, turns one
declared licence value (a `license` field, a model card, a trove
classifier) into an SPDX expression and the steps taken, without fuzzy
matching, with or without a database. It reads loose IDs (`Apache2`,
`GPLv3`), the List's names, a licence's own title (`CC0 1.0 Universal`,
`Mulan PSL v2`), the BSD aliases (`New BSD`, `BSD-3`), prose forms (`BSD
3-Clause License`), licence URLs
(`https://www.apache.org/licenses/LICENSE-2.0`, `spdx:MIT`; a URL of
several licences is refused), quote marks, trove classifiers and compounds
of one-word operands, and refuses, with a reason, what it would read only
by dropping a mark or a word. What it reads, rule by rule, is in
[resolve-values.md](resolve-values.md#what-resolve-reads), and the lists
it reads, row by row, in [lists.md](lists.md); the order the readers run in
is traced in [resolve-flow.md](resolve-flow.md), and the canonical form of
an expression in
[expression-canonicalisation.md](expression-canonicalisation.md).

## SPDX expressions

Expressions are parsed with [`py-spdx-license`][py-spdx-license].

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

## Finding the licence of an input

`detect()` reads an input in this order. The first three steps read what
the input declares and answer at once; the others match it as text.

1. **A whole value.** An input that is one declared value is read by
   `resolve()`, with no matching.
2. **A tag or a field.** An `SPDX-License-Identifier` tag, or the `license`
   field of a manifest, is the answer. Other markers (a name field, a
   heading) are not final: in an input of 30 words or more their
   licences join the candidates of step 4, with a confidence that the
   scores of step 6 count.
3. **A name or an ID.** An input under 30 words, its tags taken out, is
   looked up among the List's IDs and names.
4. **Candidates by shared words.** Every run of three words of the input
   is looked up in an index of the List's licence texts that `licenseid
   update` stores. The texts that share most with the input are the
   candidates.
5. **Whole texts.** The input is searched for candidates that it holds
   whole (`TEXTS`). A text found whole comes first, and a look-alike of
   it that nothing names is no result.
6. **Scores.** RapidFuzz compares the input with each candidate left, a
   fragment where its words place it in the text, and the results are
   ranked.
7. **First text.** In a file of several licence texts, the answer stands
   only if its text is the first one found.

Steps 4 to 6 are the matching engine. It reads no licence text until that
text is a candidate, and it has no full-text index: the index of word runs,
one code per word of each text, the texts themselves and a fingerprint of
each are plain tables of the database. A lookup never writes to them; an
index that does not fit its texts is built again in memory.

### A whole value first

An input that is, as a whole, one declared
value (`MIT OR Apache-2.0`, `Apache License, Version 2.0`, `GPLv3+`) is
read by `resolve()`, so `detect` answers its expression, a bare split
ID as written (see the deprecated IDs above). What a value
`resolve()` refuses gets (under 10 words, often no text match and
`WARNING: input: too few words for text: <reason>`) is in
[how `detect()` uses `resolve()`](resolve.md#how-detect-uses-resolve).

### Tags and markers

Detects `SPDX-License-Identifier` tags and
structured markers (name fields, headings). An exact SPDX tag returns
immediately with full confidence.

### Names and IDs

A fast path for inputs under 30 words (names, IDs, brief expressions):

- Case-insensitive exact ID match.
- Prose-context disambiguation for bare deprecated IDs (e.g.
  `"GPL-2.0 or later version"` → `GPL-2.0-or-later`).
- For a licence name with no grant, `-only` first, said with a warning
  (see the deprecated IDs above).
- A name the input holds whole is dropped when the words beside it name
  something else: a tie of two licences, a cut version, an exception, a
  fragment of a longer name, another ID or another licence's name written
  whole (its grant aside), a dash glued to a word end, the LGPL's or
  AGPL's name for the GPL's. Of tied names the one written
  whole (its words in order) beats one put together from scattered words,
  and the most specific of nested names wins. A dropped name that scored
  above 1 gives no text answer from 10 words on; under 10 words the input
  still gets the `too few words for text` warning.

### Candidates by shared word grams

Comment
prefixes (`//`, `#`, `*`, `;`) are stripped and the input normalised;
each run of three words (each Han or kana character is a word) is looked
up, once, in the postings `licenseid update` stores. Every List text that
shares a gram scores `shared / min(grams of the input, grams of the
text)`. `exclude`, `only_spdx` and `only_common` take their licences out
first, and with them every text that one they took out beats on both
counts, more grams shared and a higher score: it fits the input less
than a text the caller ruled out.

A best score under 0.1 gives no candidate. Else the input is
first searched for whole texts (`TEXTS`, below) among the texts of the
first 20 scores and every text it holds half of the runs of three words
of (or of its core's, where that is smaller), whatever the filters.

Where that search finds one text alone, the scoring takes the
licences of that text that the filters leave and three others, the next
by score that reach 0.1. Those three are look-alikes of a text the input
holds whole, so none of them is a result, whatever it scores: a verbatim
Apache 2.0 file answers `Apache-2.0` and does not list `Pixar`. One of
the three that a marker or a hint names (either twin of an `-only` and
`-or-later` pair) stays where it scores under the text found, and so
does a licence that only a marker or a hint brings in. The scoring does
not narrow
when another text shares more than 1.1 times the runs of words the text
found shares (a short text held whole inside part of a longer one), nor
when the filters took the text found out. Otherwise RapidFuzz
scores the first 3 texts by score and every text within 0.05 of the
best, at most 20 (equal scores in table order). The candidates of
markers and hints join after them. Only the first 50,000 distinct grams
of an input are looked up; past that, `TEXTS` is empty.

### Whole texts (`TEXTS`)

Before the scoring, the input is searched
for the whole texts among the candidates above (one set an
input: a text the input holds whole shares every run of its words with
it), without a database query per text. Words
become one code each; a text is first sampled by its word 5-grams, and
one that the input holds has most of them. The word 5-grams of such a
text vote for an offset, and neighbouring offsets with enough votes make a
window (each copy of a repeated text gets one). The words are aligned in
the window and the ends trimmed while that raises the fit; the character
similarity of the text and its trimmed span must be 0.95 or more.

The parts
of a text that its template lets vary (SPDX matching guidelines B.3.3: the
copyright line, the holder named in a disclaimer, a project's name in clause
3 of BSD-3-Clause) are left out of that similarity, on both sides, wherever
the words the input holds there match the part's pattern, are at most 150
characters longer than the List's words and sit between words that match
the text; a part whose words do not is compared as written. So a clause
of fewer than 150 characters written into such a part (a restriction in
the disclaimer's holder of BSD-3-Clause) is left out with it, and the
text is named: a known limit. The key that
ranks hits is found less missing, the words of a part found up to the length
of the List's: an exact copy keys the text's length whatever its parts hold.
Two texts that differ only in such parts, both fitting as closely with keys
within 2 percent, name neither, unless the input holds one's own words there
and not the other's. A longer text around such a hit doubts it with its
own parts left out whatever their length: a long clause in a part of X11
names neither X11 nor the MIT text inside it.

A copy that drops a
critical word such as "not", or misses 150 characters or more of the
text in one run (a clause), is not counted. Hits are kept
best first, and one that overlaps a kept hit by more than a tenth of the
shorter span is dropped; copies of one text are then named once. Every
cost is bounded by a count (characters, tokens, votes, windows, cells):
past one the field is empty, never a partial list. A text that a close
look-alike (character fit 0.93 or more) fits about as well is named only
at a fit of 0.98 or more; else its part names nothing. A text refused
only for a critical word still counts as that look-alike's rival.
The texts are named in the order the input first gives each.

### Scores

Ranking with RapidFuzz. An input of at
least 80% of a text's words (or a very long one) is compared with the
whole text by sorted words; a shorter one is aligned with the best part
of the text, a fragment. Its words find that part first, on the word
codes `licenseid update` stores; its characters are then aligned there,
with 4 words more on each side, not along the whole text (where the
words agree too little, or a text has no codes, along the whole text).

An input of about a licence's core length is compared with its core as
well: the text without its optional parts (an appendix, or the GPL-3.0
text quoted in the LGPL-3.0), which the SPDX matching guidelines allow
for optional text. The higher similarity counts, and coverage is
counted over the words of the text that won;
`EXACT` is still a whole-text match.

The score then adds small terms for
coverage, for marker confidence (applied only from 0.85) and for a
fingerprint. A marker's confidence floor stays only where the input is
no longer than the marker's licence text (coverage up to 1.05) or the
search of whole texts finds no text but that licence's;
where it does not stay, a candidate whose text is not among those found
is dropped. The ranking reads the coverage as counted, above 1 for an
input longer than the text; only the result caps it at 1. What `SCORE`,
`SIMILARITY` and `COVERAGE` measure, and their
ranges, is in [output.md](output.md#default-and-verbose-text).

### First text

When the top result is a text match, not exact, of an
input of 40 words or more, the search of whole texts is read for every
output (the `is-*`
commands and the terse `detect` too). Where it finds the texts of two
licences or more (licences of one text count as one), the results stand
only when the first text found is the answer's; otherwise there is no
answer (`REASON=several texts`). In a file of several texts the longest
tends to rank first, though a licence file gives, by habit, the
project's own text first and the bundled ones after it. The rule only
takes an answer away, never gives one, and only on texts found: a file
that holds one text whole besides an own text not found keeps its
answer; with two or more found, the first decides. It has no coverage
gate: a short text before a long one (MIT, then the GPL-3.0) gives the
long one a coverage of about 1.03 before the cap.

[py-spdx-license]: https://github.com/JPEWdev/py-spdx-license
