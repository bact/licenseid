---
Created: 2026-10-29
Last-Modified: 2026-11-04
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Detection and declared values

Status: draft, 2026-10-29. Nothing here is built. It answers "do we need
both `match()` and `resolve()`?", proposes how they fit together, and
renames them. The names (section 2, D1) and the `match` command (D6) are
decided and land in 0.7.0 as tasks T10a and T10b; the delegation (section
3) is for 0.8.

## 1. Two questions

licenseid answers two different questions. They take different inputs, need
different data and give different kinds of answer.

Today's `match()` asks: what licence is in this thing?

- Input: a file, a licence text, a tag in a source file, a manifest, or a
  short value.
- Method: evidence (markers, IDs and names, full-text search, similarity).
- Answer: ranked candidates, each with a score; a guess is allowed, and
  scored.
- Explains itself with `method`, `exact`, `score`, `similarity`,
  `coverage`.
- Needs the database: licence texts and the full-text index.
- Typical user: a scanner of a source tree or a file.

Today's `resolve()` asks: what does this declared value mean?

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

Revised 2026-11-03, before the 0.7.0 tag (maintainer): the declared-value
call and command are `resolve()` and `licenseid resolve`, not `match`. The
result is a `Resolution` whose category can be `unresolved`, the modules are
`resolve*.py`, and the SPDX matching guidelines use "matching" for licence
texts, which is `detect`'s job. `detect` stays. The rest of this section is
the 2026-10-29 decision as it was taken; read `match` as `resolve`.

The names below are the maintainer's (decided 2026-10-29): `resolve` is
hard to type and remember, and `match` says how, not what. They land in
0.7.0, before the tag. No backward compatibility is owed (private alpha):
no alias, no deprecation period, no release without a `match` command.

- `licenseid detect`: today's `licenseid match`. It finds the licence in a
  file, a text or a tag.
- `licenseid match`: today's `resolve()`. It matches one declared value to
  an SPDX expression (D6).

This works: each command answers one of the two questions, both names are
short, and `detect` is the field's own word (ScanCode calls the same job
"licence detection"). Two things to handle:

- **A file or a text given to `match`.** `licenseid match LICENSE` reads
  the string `LICENSE` as a declared value: `unresolved`, exit 1, which
  says "no licence" when the user meant "detect this file". The new
  `match` refuses what only `detect` can answer, with exit 2 and a line
  such as `ERROR: input: invalid: a file or a licence text; run 'licenseid
  detect'` (wording to fit the grammar): `--text`, a file argument,
  standard input, a value with a line break or one over the length cap.
  This is input validation, not a compatibility shim.
- **SPDX's own use of "match".** The SPDX License List matching guidelines
  use "match" for comparing a licence *text* with a template: that is
  `detect`'s job, not the new `match`'s. Code comments and docs that cite
  the guidelines then say "text matching (the guidelines)" inside
  `detect`, and "match a declared value" for the command. A cost in wording
  only.

The Python names follow the CLI, so one question has one name everywhere:

- `licenseid.detect(...)`: a module-level function, opening the default
  database as `match` opens its list. `AggregatedLicenseMatcher` becomes
  `LicenseDetector`, its method `detect()`; `LicenseMatch` becomes
  `Detection`, `MatchRequest` `DetectRequest`; `matcher.py` becomes
  `detector.py`. `Method` stays. Callers that hold a database keep a
  class; the function is for the rest.
- `licenseid.match(...)`: today's `resolve()`, same signature and result.
  `Resolution` stays (D1); `resolver.py`,
  `resolveleaf.py`, `resolvecompound.py` and `resolvetrove.py` keep their
  file names, which say how, not what the call is named.
- The `is-*` commands and `is_*()` methods keep their names. They take a
  declared value or a text, as now.

Neither old name is kept as an alias: two names for one call is what this
note removes.

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

It also removes code from `matcher.py` (680 lines) and `markers.py`.

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

## 4. Decisions needed

- **D1 names.** Decided 2026-10-29: CLI `detect` and `match`, Python
  `detect()` and `match()`, as in section 2, renamed in 0.7.0 (T10a).
  Proposed for T10a: `Resolution` stays the result type's name (it says
  what the result is: a resolution of a value), and so do the
  `resolve*.py` module names.
- **D2 `exact` of a re-spelt value.** Is `Apache2` in a `license` field an
  exact detection? Proposed: no. `exact` is true only for category `exact`,
  so `--exact` keeps only values read as written. Today every declared value
  answers `EXACT=true`.
- **D3 a refused declared value.** `resolve` refuses `Apache 2.0?`. Proposed:
  `detect` answers nothing for that value, with the reason on a
  `WARNING: resolve: no license found: <reason>` line, rather than turning the
  refusal into a text guess. A file with no declared value at all still goes
  to Tiers 1 and 2.
- **D4 the `resolution` key.** Add it to every `detect` result that came
  from a declared value (null for a text match), in `--json`? Proposed: yes;
  the text line gains `CATEGORY=<category>` only.
- **D5 flags of a compound.** `MIT OR GPL-2.0-only` is neither one licence
  nor the other. Proposed: the flags are false and the `is-*` commands exit
  2 for a compound, as `--id` refuses one now.
- **D6 the `licenseid resolve` command.** Decided for 0.7.0 (T10b, as
  `match`), output proposed: one line
  `EXPRESSION=<expr> CATEGORY=<category> TRUST=<trust>`, then one
  `STEP=<kind> FROM=<from> TO=<to>` line per applied step; `REASON=` for a
  refusal; one `OPERAND=<text> EXPRESSION=<expr> CATEGORY=<category>`
  line per operand when a value names licences without stating how they
  combine (`MIT ; Apache 2`, T8b: unresolved, but every operand read, so a
  caller can still ask whether each is OSI approved); exit 0 when resolved,
  1 when not, 2 for a usage error. `--json`
  prints the resolution as one RFC 8785 object. It needs no database: the
  CLI for SBOM tools.
- **D7 order of work.** In 0.7.0: T10a, the rename alone (pure, one PR,
  tests renamed, every answer unchanged); then T10b, the `licenseid match`
  command. In 0.8: the delegation, which changes answers: a
  characterisation corpus of `detect` on every declared form first, as T0
  did for `resolve()`, with an `EXPECTED_CHANGES` guard.
- **D8 flags of a compound with an unjudged operand.** 0.7.0 gives no flag
  (empty, `null`, exit 1) for `MIT OR LicenseRef-x` whenever an operand
  cannot be judged (review P140). Decided 2026-11-03 (maintainer): normal
  logic, "`OR` requires only one operand to be true". `MIT OR LicenseRef-x`
  is OSI approved; an `OR` is false only when every operand is false; an
  `AND` is true only when every operand is true and false when one is false
  (`CC-BY-4.0 AND LicenseRef-x` is not OSI approved). Anything else stays
  empty (`0BSD AND LicenseRef-x`). Built for 0.7.1 (`exprflags._combined`).
- **D9 the word "matcher".** After the rename to `detect` and `resolve`, the
  README title, `licenseid --help` ("SPDX License ID matcher tool"),
  `codemeta.json`, the keywords and the `tests/test_matcher*.py` names
  still say "matcher". Decided 2026-11-03 (maintainer): reword the
  user-facing text to "A portable SPDX licence identification tool"; the
  keywords may keep "license matcher" for search.
- **D10 a dash beside a grant.** `GPL-2.0 - or - later` was
  `GPL-2.0-or-later` in `resolve()` and `GPL-2.0-only` in a tag, and
  `GPL-2.0 - or later` was refused in both. Decided 2026-11-04
  (maintainer): a dash between words is a separator, and every channel
  gives the same form (`GPL-2.0-or-later`; `MIT - or later` is `MIT+`),
  category `separator`. Built for 0.7.1 (#158): `classify.grant_head` is
  the one rule of the gap.

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
One line each, with the pull request that found it. Gone since: `MIT WİTH`,
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
(d9bbc23) and its review are kept. On `main`, `detect("Foo")` is
`3D-Slicer-1.0` at 1.0; one or two words of a name (`the`, `GPL`, `Apache
License`) answer by name at 1.0; `detect("OR")` is AGPL by name; phrases of
40 or more characters that several licences share still answer 1.0. An
0.8 fix must avoid what the review found on the branch: LGPL names to
`LiLiQ-R-1.1`, `New BSD`, unique title lines, an exact short text scaled.
