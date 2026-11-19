---
Created: 2026-10-29
Last-Modified: 2026-11-18
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Detection and declared values

Status: draft of 2026-10-29, partly built (checked 2026-11-18). It answers
"do we need both `match()` and `resolve()`?", proposes how they fit
together, and renames them. Built in 0.7.0 (T10a, T10b): the names (section
2, D1, D6), D8 (0.7.1) and D10 (#158). Built for a whole input only: the
delegation of section 3 (`resolvefirst.py`, 0.7.2; Tier 0 through
`resolve()`, 0.8.4). Not built: the delegation of a tag and a field
(roadmap item 50), D4 and D5. In this note `matcher.py` is now
`detector.py`, and `docs/match.md` is `docs/resolve.md`.

## 1. Two questions

licenseid answers two different questions. They take different inputs, need
different data and give different kinds of answer.

`match()` (now `detect()`) asks: what licence is in this thing?

- Input: a file, a licence text, a tag in a source file, a manifest, or a
  short value.
- Method: evidence (markers, IDs and names, full-text search, similarity).
- Answer: ranked candidates, each with a score; a guess is allowed, and
  scored.
- Explains itself with `method`, `exact`, `score`, `similarity`,
  `coverage`.
- Needs the database: licence texts and the full-text index.
- Typical user: a scanner of a source tree or a file.

`resolve()` asks: what does this declared value mean?

- Input: one value someone wrote to declare a licence: a `license` field, a
  trove classifier, a model card entry.
- Method: rules only (spelling, separators, qualifiers, quotes, trove
  names).
- Answer: one SPDX expression, or a refusal; never a guess.
- Explains itself with a category, a trust level, every step taken and the
  reason for a refusal.
- Needs only the SPDX License List; the one shipped in the wheel will do.
- Typical user: an SBOM tool recording what a package declares (Pitloom).

Neither can be an alias of the other:

- `resolve()` cannot detect a text. It has no texts and no similarity, by
  design (Q5: no text detection without a database).
- `match()` cannot replace `resolve()`. Its answer is a ranking with no
  steps, and a ranking may hold a guess. A caller who records a declared
  value needs to know whether the value was read as written, re-spelt or
  assumed, and needs a refusal when the value names nothing. A score cannot
  say that.

So keep both. But one question sits inside the other: a source file's
`SPDX-License-Identifier` tag, a `license` field in `package.json`, an `--id`
and a short value such as `GPL-2.0+` are all declared values that `match()`
meets while it detects. Today it reads them with its own code (markers,
Tier 0, the manifest path). That is the duplication to remove.

## 2. Names

Decided 2026-10-29 (maintainer): `resolve` is hard to type and remember, and
`match` says how, not what; the old matcher becomes `detect` (ScanCode calls
the same job "licence detection") and the declared-value call becomes
`match`. No alias, no deprecation period (private alpha). **Revised
2026-11-03, before the 0.7.0 tag (maintainer):** the declared-value call and
command stay `resolve()` and `licenseid resolve`, not `match`: the result is
a `Resolution` whose category can be `unresolved`, the modules are
`resolve*.py`, and the SPDX matching guidelines use "matching" for licence
texts, which is `detect`'s job. `detect` stays. Built in 0.7.0 (T10a), so
only `detect` was renamed:

- `licenseid detect` (was `licenseid match`) finds the licence in a file, a
  text or a tag; `licenseid.detect(...)` is a module-level function that
  opens the default database. `AggregatedLicenseMatcher` became
  `LicenseDetector` (method `detect()`), `LicenseMatch` `Detection`,
  `MatchRequest` `DetectRequest`, `matcher.py` `detector.py`; `Method` stays.
  Callers that hold a database keep a class.
- `resolve()`, `Resolution` and `resolver.py`, `resolveleaf.py`,
  `resolvecompound.py`, `resolvetrove.py` keep their names, which say how,
  not what the call is named.
- The `is-*` commands and `is_*()` methods keep their names. They take a
  declared value or a text.
- Code comments and docs that cite the SPDX guidelines say "text matching"
  inside `detect`, and "read a declared value" for `resolve`.

## 3. Detection delegates declared values

```text
            input (file, text, tag, manifest, value)
                              |
                           detect
                              |
       +----------------------+----------------------+
       |                                             |
  a declared value                              licence text
  (tag, field, --id, short value)               (no declared value)
       |                                             |
  resolve(value, db) --- adapter -----+     Tiers 1 and 2: full-text
       |                              |     search and similarity
  refused: no result,                 |              |
  with the reason (D3)                +------+-------+
                                             |
                                      ranked results
```

- `detect` finds the declared value (where it is, which field, which tag)
  and hands each one to `resolve`, with its own database, so both read one
  list. It no longer reads IDs, `+`, "or later", quotes or expressions
  itself.
- Tier 0's ID and name reading, `MarkerDetector.resolve_license_value`,
  `_synthetic_candidate` and the tag path's
  `identifiers._canonicalize_expression` go. Their rules already live in
  the resolver (`resolveleaf`, `resolvecompound`, `looseid`, `exprcanon`).
- Tiers 1 and 2 stay as they are. They are the part only `detect` has.
- The `is_*` predicates answer from the resolution when the input is a
  declared value, and from the top text match otherwise, as `resolve_record`
  does now.

This closes the gaps R7 found, without a rule of its own for each (items 2
and 10 of the 0.8 list in `resolver-0-7-review.md`):

- `licenseid resolve "Apache 2.0?"`, `"MIT*"` and `'"MIT"'` answer `METHOD=id
  EXACT=true` today, while `resolve()` refuses them or reads them with a
  step (45 synthetic values).
- `SPDX-License-Identifier: MIT OR Apache2` answers `EXACT=true`.
- A tag `MIT or later` answers `MIT OR later`; `resolve()` says `MIT+`
  (P35).
- `markers.py` reads quotes its own way.

It also removes code from `matcher.py` (680 lines then) and `markers.py`.

### The adapter

How a resolution becomes a `detect` result. Each point is a decision
(section 4).

- `expression` goes to `license_id`: an expression for a compound, as a tag
  gives now.
- Category `exact` gives `exact=true`; any other resolved category gives
  `exact=false` (D2). Both score 1.
- `unresolved` gives no result for that value (D3).
- The whole resolution goes into a new `resolution` key (D4).
- `method` stays `tag`, `field` or `id`.
- `is_spdx`, `is_osi_approved` and `is_fsf_libre` come from the record of a
  single ID; for a compound, each is false (D5).

### Built: the whole input first

Built 2026-11-05 (`resolvefirst.py`), for a whole input only; a tag and a
field keep their readers, so the rest of this section is still to do
(roadmap item 50).

- `detect` asks `resolve()` for the whole input first and answers its
  expression. On the goldens this fixed 107 text guesses (`MIT OR
  Apache-2.0` was `ECL-2.0`) and moved no ID answer.
- `exact` keeps `detect`'s meaning, false only for a guess (trust `none`, a
  narrowed `-only`), so a whole input, a tag and a field agree. D2's
  stricter rule moved 71 ID answers and split the channels (`MIT,` exact
  as a field, not as text): it stays open, for every channel at once.
  Settled by roadmap item 52 (PR #212): every channel is exact where a list
  defines the reading and not where a rewrite rule made it
  (`../implementation/item-52-variant-and-exact.md`).
- `method` is `name` when a step read a name, else `id`.
- A refused input under 10 normalised words gets no text match and warns
  `input: too few words for text: <reason>` (D3, for a whole input). Under
  10 words the text tiers were right 19 times in 94 at 0.85 or more; from
  10 words on, every short text was right. The losses (`CC0 1.0
  Universal`, `Mulan PSL v2`, the UPL name, the GPL-3.0 title line) are
  names for `resolve()` to learn.
- Han and kana are not cut (review of PR #161): a word count is no measure
  without spaces. On `main`, slices of the four CJK texts of the List at 4
  to 13 characters were the licence or its other version 592 times in 593
  (1 no answer); 28 of 30 short phrases that are no licence got no answer
  (`版权所有` gave MulanPSL-1.0). An input counts as written without spaces
  when nine letters in ten are Han or kana, so clause letters (`第7条b`)
  stay in and Latin words (`GPL 第三版`, was `AGPL-1.0-only`) are cut.
  90-character slices of CC-BY-SA-2.1-JP: 49 of 50 answered (`main` 50).
- A whole input takes `resolve()`'s order (`MirOS OR MIT`); a tag and a
  field keep `detect`'s (`MIT OR MirOS`) until they go through `resolve()`
  too. A licence URL no longer differs: a tag, a field and a whole input
  read `https://spdx.org/licenses/MIT.html` as MIT with one reader
  (`resolveurl`, issue #14, 2026-11-08; see
  [`licence-urls.md`](../implementation/licence-urls.md)). What is still
  open for URLs: one inside prose (NuGet's expression paths are read since
  issue #187).

## 4. Decisions

- **D1 names.** Built in 0.7.0 (T10a): CLI `detect`, Python `detect()`,
  `LicenseDetector`, `Detection`, `DetectRequest` (now `DetectOptions`),
  `detector.py`. `resolve()`, `Resolution` and the `resolve*.py` modules
  keep their names.
- **D2 `exact` of a re-spelt value.** Proposed: true only for category
  `exact`. Settled otherwise by item 52 (PR #212): exact by list, so `Apache2`
  (a rule) is not exact and a listed name is.
- **D3 a refused declared value.** Proposed: `detect` answers nothing for it,
  with the reason in a `WARNING`, rather than turning the refusal into a text
  guess; a file with no declared value still goes to Tiers 1 and 2. Built for
  a whole input (`input: too few words for text: <reason>`).
- **D4 the `resolution` key.** Proposed: a `resolution` key in every `detect`
  result that came from a declared value (`--json` only). Not built.
- **D5 flags of a compound.** Proposed: false, and `is-*` exit 2 for a
  compound. Not built: D8 gave a rule instead.
- **D6 the `licenseid resolve` command.** Built in 0.7.0 (T10b). Output
  (`docs/output.md`): one `EXPRESSION=<expr> CATEGORY=<category>
  TRUST=<trust>` line, one `STEP=` line per applied step, `REASON=` for a
  refusal, one `OPERAND=` line per operand when a value names licences
  without stating how they combine (`MIT ; Apache 2`, T8b); exit 0 when
  resolved, 1 when not, 2 for a usage error; `--json` prints the resolution
  as one RFC 8785 object. It needs no database.
- **D7 order of work.** In 0.7.0: T10a, the rename alone, then T10b. The
  delegation, which changes answers, needs a characterisation corpus of
  `detect` on every declared form first, as T0 did for `resolve()`, with an
  `EXPECTED_CHANGES` guard.
- **D8 flags of a compound with an unjudged operand.** Decided 2026-11-03
  (maintainer): "`OR` requires only one operand to be true". `MIT OR
  LicenseRef-x` is OSI approved; an `OR` is false only when every operand is
  false; an `AND` is true only when every operand is true and false when one
  is false (`CC-BY-4.0 AND LicenseRef-x` is not OSI approved); anything else
  stays empty (`0BSD AND LicenseRef-x`). Built for 0.7.1
  (`exprflags._combined`).
- **D9 the word "matcher".** Decided 2026-11-03 (maintainer): reword the
  user-facing text to "A portable SPDX licence identification tool"; the
  keywords may keep "license matcher" for search. Built (the README, `--help`
  and `codemeta.json` no longer say "matcher"; the keyword stays).
- **D10 a dash beside a grant.** `GPL-2.0 - or - later` was
  `GPL-2.0-or-later` in `resolve()` and `GPL-2.0-only` in a tag, and
  `GPL-2.0 - or later` was refused in both. Decided 2026-11-04
  (maintainer): a dash between words is a separator, and every channel gives
  the same form (`GPL-2.0-or-later`; `MIT - or later` is `MIT+`), category
  `separator`. Built for 0.7.1 (#158): `classify.grant_head` is the one rule
  of the gap.

## 5. Documentation

The README and the docstrings of both calls open with the two questions of
section 1 and one example of each, so a reader picks the right call before
reading options. The README carries this from 0.7.0; T10a gives it the new
names.

## 6. Not in scope

- Detecting text without a database (Q5 stays).
- Changing the ranking of Tiers 1 and 2.
- Several-word operands of a compound (P43): a resolver rule, which `detect`
  then gets for free.

## 7. Leftovers of the 0.7.0 resolver and readers reviews

Seen in the whole-release review (2026-11-02 to 11-03), not fixed in 0.7.0.
One line each, with the pull request that found it. Checked again on the
0.9.0 candidate (2026-11-18), five of them: `GPL-2.0 or-later OR MIT` in a tag
now keeps MIT; `Intel, GPL-2.0 or later` gives no answer (#221); a field
`Apache 2.0 or later` is `Apache-2.0+`; but a tag `(MIT) or later` is still
`MIT+` (`resolve()` refuses it) and a tag `GPL-2.0 or later ISC` still answers
`GPL-2.0-or-later`. The rest are not re-checked: read each against the code
before acting on it. Gone since: `MIT WİTH`,
the quadratic `classify._RE_NUMBERED_SECTION` and the lone tag
`licenseref-foo` (fixed by 0.7.0); a no-break space or a dash before a
grant (D10) and `++` after an exception (0.7.1).

Readers (#149, #147):

- A tag or field reads `(MIT) or later` as `MIT+`; `resolve()` refuses it.
- A tag or field reads prose `GPL-2.0 (at your option) any later version`;
  `resolve()` refuses it. Tag `Intel, GPL-2.0 or later` is `Intel`, exact (the
  leading ID).
- Field or text `Apache 2.0 or later` is not `Apache-2.0+` as in `resolve()`.
- U+001C to U+001F inside a value: `--id $'\x1fMIT'` is exact, `resolve()`
  refuses it; `detect(license_id='\x1f')` raises nothing in the API; a lone
  `$'\x1f'` gives `empty: argument` (`clicommon`).
- `AdditionRef-*` after `WITH`: tag, field and `--id` refuse it, `resolve()`
  answers it exact. A grant before `WITH` is refused by a tag, answered by a
  field and `resolve()`. `(MIT OR GPL-2.0) or later` is exact in a tag,
  refused in `resolve()`.
- A quoted TOML `EUPL 1.1+` drops the "+". The inline grant regex in
  `markers._name_variants` is a second reader of "or later".
- A tag `GPL-2.0, version 3 or later` is
  `GPL-2.0-or-later` (the grant belongs to version 3); `GPL-2.0-only or not
  later` reads `GPL-2.0-only OR not`; `MIT, see LICENSE or later` is `MIT`.
- `detect` argument or field `GPL-2.0 +` is `GPL-2.0-only`, not exact, with
  a warning (`versionkey`, `shorttext`); `normalize._RE_COPYRIGHT_NOTICE`
  has `IGNORECASE` without `ASCII`.
- `classify.grant_at` repeats `looseid.grant_end`; unify them.
- `Apache2` is refused in a tag, though `resolve()` reads it loosely.
- A tag `GPL-2.0 or-later OR MIT` (and `-or-later`, `, or later`, `(or
  later)`) is `GPL-2.0-or-later`, exact, and drops MIT: the word `or-later`
  is read as an ID, and the comma and the bracket spellings take the
  `qualify_trailing_grant` path, which does not check what follows (review
  of #158). A tag or field `GPL-2.0 or later -` or `GPL-2.0 or later ISC`
  answers too, while `resolve()` refuses it.
- A tag or field answers where `resolve()` refuses, in the plain spelling
  and so, under D10, the dashed one: `GPL-2.0 or later+`, `(GPL-2.0) or
  later`, `GPL-2.0 or later-ish`; a field `(GPL-2.0 or later` and
  `GPL-2.0+- or later` (second review of #158).
- `or-later` is ASCII and takes one dash before it: `GPL-2.0 or–later`
  (U+2013) is no grant, while `or – later` is.
- `detect --text 'MIT or later'` is `CERN-OHL-W-2.0`, not exact (short
  text, below), while `resolve()` answers `MIT+`; a field `Licensed under
  the GPL-2.0 or later, see COPYING` answers, while `resolve()` refuses it.

Resolver values and fixes (#147, fix batch R):

- Trove name plus one end mark, `"" OR MIT` (whole reason), `"" OR ""` and
  `OR` (`not found: OR`; AGPL by name goes to short text), `LicenseRef-a, or
  any later version` (`not found`), `MIT WITH Foo` reasons.
- `GFDL-1.3-invariants or any later version` and `GFDL-1.3-invariants+`;
  `MIT or_later` against `MIT or later`; `(Foo)+ OR ISC` has a vague reason;
  the detect field reading of `GPL-2.0 or_later` (a tag gives `-only`).
- Smaller reason gaps, the 2,000-character limit counting the inner value,
  and `MIT; MIT` (review findings B7 to B9).
- `licenseid resolve` refuses an argument with U+001C to U+001E as a line
  break (`cliresolve`, `splitlines`); exit 2 kept.

BSD-1-Clause (#148):

- A BSD-1 text that is bulleted, unnumbered, `1)`, reflowed or
  comment-wrapped is still missed (a Tier 1 fix); the ISC fixture text reads
  as `Python-2.0` at 0.73 (the Tier 1 query spends its words on copyright
  lines).
- BSD-2-Clause-Patent text distorted 5%: AMPAS reads as BSD-1-Clause (wrong
  before and after).

Short text (maintainer, 2026-11-02): the branch `release-0.7-short-text`
(d9bbc23) and its review were kept, and merged in PR #168 (2026-11-06):
`detect("Foo")` and one or two words of a name (`the`, `GPL`, `Apache
License`) now have no answer, and the LGPL names are the `-only` guess,
said aloud. `New BSD` and the other BSD aliases were lost, for `resolve()`
to read; it reads them since PR #170, from a table (`alias_name`). The rest
are item 47 of [`tech-debt-roadmap.md`](tech-debt-roadmap.md). Phrases of
ten words or more that several licences share still answer 1.0 (item 28 there).
