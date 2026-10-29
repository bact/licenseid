---
Created: 2026-10-29
Last-Modified: 2026-10-29
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Detection and declared values in 0.8

Status: draft for the maintainer, 2026-10-29. Nothing here is built. It
answers "do we need both `match()` and `resolve()`?", proposes how they fit
together, and renames them.

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

The names below are the maintainer's proposal (2026-10-29): `resolve` is
hard to type and remember, and `match` says how, not what.

- `licenseid detect`: today's `licenseid match`. It finds the licence in a
  file, a text or a tag.
- `licenseid match`: today's `resolve()`. It matches one declared value to
  an SPDX expression.

This works: each command answers one of the two questions, both names are
short, and `detect` is the field's own word (ScanCode calls the same job
"licence detection"). Two things to handle:

- **The same command, a new meaning.** A script that runs
  `licenseid match LICENSE` today would get a value reading of the string
  `LICENSE` in 0.8, which is `unresolved`: exit 1, "no licence", not an
  error. No backward compatibility is owed, but a silent change of meaning
  is the worst kind. Proposed: the new `match` refuses what only `detect`
  can answer, with exit 2 and
  `ERROR: input: invalid: a file or a licence text; run 'licenseid detect'`
  (wording to fit the grammar). That is a value with a line break, one over
  the length cap, `--text`, a file argument and standard input that is a
  file. CHANGELOG gives the migration in one line.
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
  `detector.py`. `Method` stays.
- `licenseid.match(...)`: today's `resolve()`, same signature and result.
  `Resolution` becomes `MatchResult`, or stays (D1); `resolver.py`,
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
  match(value, db) ----- adapter -----+     Tiers 1 and 2: full-text
       |                              |     search and similarity
  refused: no result,                 |              |
  with the reason (D3)                +------+-------+
                                             |
                                      ranked results
```

- `detect` finds the declared value (where it is, which field, which tag)
  and hands each one to `match`, with its own database, so both read one
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

- `licenseid match "Apache 2.0?"`, `"MIT*"` and `'"MIT"'` answer `METHOD=id
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

- **D1 names.** CLI `detect` and `match`, Python `detect()` and `match()`,
  as in section 2? Keep `Resolution` as the result type's name, or rename it
  `MatchResult`?
- **D2 `exact` of a re-spelt value.** Is `Apache2` in a `license` field an
  exact detection? Proposed: no. `exact` is true only for category `exact`,
  so `--exact` keeps only values read as written. Today every declared value
  answers `EXACT=true`.
- **D3 a refused declared value.** `match` refuses `Apache 2.0?`. Proposed:
  `detect` answers nothing for that value, with the reason on a
  `WARNING: match: no license found: <reason>` line, rather than turning the
  refusal into a text guess. A file with no declared value at all still goes
  to Tiers 1 and 2.
- **D4 the `resolution` key.** Add it to every `detect` result that came
  from a declared value (null for a text match), in `--json`? Proposed: yes;
  the text line gains `CATEGORY=<category>` only.
- **D5 flags of a compound.** `MIT OR GPL-2.0-only` is neither one licence
  nor the other. Proposed: the flags are false and the `is-*` commands exit
  2 for a compound, as `--id` refuses one now.
- **D6 the output of `licenseid match`.** Proposed: one line
  `EXPRESSION=<expr> CATEGORY=<category> TRUST=<trust>`, then one
  `STEP=<kind> FROM=<from> TO=<to>` line per applied step; `REASON=` for a
  refusal; exit 0 when resolved, 1 when not, 2 for a usage error. `--json`
  prints the resolution as one RFC 8785 object. It needs no database: the
  CLI for SBOM tools.
- **D7 order of work.** First the rename alone (pure, one PR, tests renamed,
  answers unchanged). Then the new `licenseid match` command. Then the
  delegation, which changes answers: a characterisation corpus of `detect`
  on every declared form first, as T0 did for `resolve()`, with an
  `EXPECTED_CHANGES` guard.

## 5. Documentation

The README and the docstrings of both calls open with the two questions of
section 1 and one example of each, so a reader picks the right call before
reading options. The README carries this from 0.7.0 with today's names
(`match()` and `resolve()`); 0.8 renames them.

## 6. Not in scope

- Detecting text without a database (Q5 stays).
- Changing the ranking of Tiers 1 and 2.
- Several-word operands of a compound (P43): a resolver rule, which `detect`
  then gets for free.
