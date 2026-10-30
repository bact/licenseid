---
Created: 2026-10-28
Last-Modified: 2026-10-30
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Review of T0 to T4 before T5 to T7

Status: decisions taken by the maintainer on 2026-10-28; the task changes
below are folded into [`resolver-0-7-plan.md`](resolver-0-7-plan.md)
(sections 3, 8, 10 and 11).

T0 (#110), T2 (#108), T3 (#107) and T4 (#112) were each reviewed on their
own. This round reviewed them together, at `main` f514ca1, against what T5,
T6 and T7 need. Two independent Opus reviews: one of the seams (with a
throwaway in-memory index), one audit of the parity corpus's
`expected_0_7_0` column and of the T0 fix commit 50a8e2e, which had had no
second review.

## 1. What the seams review proved

- T5 is buildable from public pieces. A scratch `ListIndex` built from
  `listrules.kept_licenses`, `active_exceptions_by_name`,
  `exception_successor`, `normalize_text`, `fold_case` and `SpdxData`
  (the 3.29.0 tarball round-tripped through the bundle format) gave the same
  `resolve()` answer as the 3.29.0 database on 4,322 values (every ID, ID in
  lower case, ID with `+`, every name, three `WITH` forms per exception,
  every parity and sample value): 0 differ, 0 raise. The bundle loads in
  0.069 s, the index in 0.030 s.
- It cannot honestly fill the whole `LicenseDetails`: `pop_score` and
  `is_high_usage` need `popularity.csv`, and `word_count` costs 1.2 to
  1.6 s. The resolver chain reads only `license_id`, `is_deprecated` and
  `superseded_by` (and `license_id`, `is_deprecated` of name rows).
- No import cycles; `listindex` needs only the standard library,
  `normalize`, `listrules`, `listlookup` and `spdxdata`.

## 2. Defects and gaps found

| # | Where | Finding | Goes to |
| - | - | - | - |
| G1 | `resolver.py:126-133`, `database.py:474-485` | A lone surrogate after `WITH` (`MIT WITH Classpath-exception-2.0\udcff`) raises `UnicodeEncodeError` with a database (`_has_control` misses Cs), and would be `unresolved` with an index | T4b: refuse Cs among the early refusals, reason `lone surrogate` |
| G2 | `listlookup.py:57-72`, `types.py:138-153` | The Protocol promises `LicenseDetails` fields an index cannot give | T4b: narrow the return types to the fields read; `with_expression_details` and `flag_source` back to `LicenseDatabase` (they read the OSI and FSF flags) |
| G3 | `listrules.py:39,80,117,130`, `spdxdata.py:152-178` | A bundle entry with no `name` raises `KeyError` (predates T2) | T4b: `spdxdata` refuses a `name` that is not a string (`BundleError`) |
| G4 | `listlookup.py:71-72` | `get_deprecated_mappings` returns only IDs with a successor (licences in table order, then exceptions, an exception winning a clash), not "all deprecated IDs"; `release_date` is `""` when absent | T4b: docstrings |
| G5 | `errors.py:22`, `dbcheck.py:262` | `DatabaseNotReadyError` carries no condition, so "missing" cannot be told from "unusable" | T5 |
| G6 | `releasesource.py:298-313` | The version compare imports `spdx_source`, which imports `requests` | T5: move `is_older` and `_numbers` to `spdxdata` |
| G7 | `conftest.py:95-99`, `release_fakes.py:172-178` | A process-wide `packaged_index()` cache would leak between tests that patch the bundle | T5: call `spdxdata.packaged_bundle()` through the module; `offline` and `ship` reset the cache |
| G8 | `listrules.py:94-100` | 3.29.0 has no ID in use without a text, so real data cannot test the kept-rows rule of `get_active_ids_by_name` | T5: a synthetic bundle with such an ID, the successor of a rename |
| G9 | `resolver.py:136-142,176-179`; `resolveleaf.py:47-55` | Category, trust and the "clear steps when nothing resolved" rule are private to `resolver`; `Found` has no `reason` | T6 adds `reason`; T7 makes `category_of(found)` public in `resolveleaf` |
| G10 | `resolver.py:76-95`, `identifiers.py:731-747` | Stripping and outer brackets keep no offsets; Q8 spans need them | T7, outside `identifiers` (747 lines) |
| G11 | `resolver._RE_TOKEN`, `identifiers._RE_TOKEN` | Two tokenizers already | T7 reuses `identifiers`' (made public or moved), no third |
| G12 | `looseid.py:37` (`WITH_OPERATOR`) | A single `X with Y`, a tab or a double space answers `exact` with no step | T7 (Q17) |
| G13 | `looseid._RE_GRANT_TAIL` (`looseid.py:32-35`) | The grant tail accepts `; : ) ]` | T6: guard the ID part only |
| G14 | `tests/test_listlookup.py:20` | Imports the private `_lookup` and `_list_info` | T7 rewrites it |

Audit of the T0 test harness (commit 50a8e2e):

| # | Where | Finding | Goes to |
| - | - | - | - |
| H1 | `tests/resolver_corpus.py:196-203` | No test checks that the guard covers the PyPI sample: dropping `sample_rows()` survives every test | T4b |
| H2 | `tools/pypi_licence_sample/__main__.py:330` | The sample's header hash covers expression, category and candidates only; re-pinned steps or trust pass | T4b: hash every answer column, re-export |
| H3 | `tools/pypi_licence_sample/answer.py` | `Answer` pins step kinds only, not a step's targets or `applied`, nor the planned `reason` | T4b: add `reason` (`None` for 0.6.0) and step targets |
| H4 | `resolver_corpus.py:219-228` | The report prints keys escaped twice; a pasted key then fails | T4b: print `{value!r}` |
| H5 | `answer.py` | `Answer` is a positional 7-tuple; two swapped tuple fields pass mypy | T4b: keyword construction, a field-by-field diff in the report |
| H6 | `__main__.py:448` | Every `ValueError` (a bad JSONL line) is reported as a usage error | T4b |
| H7 | `release-process.md:62-70` | "Regenerate the fixtures" has no generator for the parity file | T4b: document hand re-pinning at a release boundary |
| H8 | `resolver_corpus.py:167` | `read_rows` does not check the field count | T4b |

## 3. Parity corpus audit

Of 140 rows: 120 agree with the plan and the decisions, 1 prediction was
wrong, 10 rows waited for a decision (now taken, section 4), and 9 `?`
rows were in fact decided by the plan. Corrections, made in T4b:

| Row (value) | Was | Now | Why |
| - | - | - | - |
| `W3C License` | `W3C [trove_name]` | `- [unresolved]` | Q22: the trove table comes first, and this name states no version |
| `GNU Lesser General Public License v2 (LGPLv2)` | `LGPL-2.0 [assumed_only]` | prediction kept | Q23, changed by the maintainer on 2026-10-28: a special case, only the `why` is new |
| `(MIT OR ISC) AND GPL-2.0-only WITH Classpath-exception-2.0` | listed as undecided | prediction kept | Q19: groups after all leaves |
| `MIT WITH AdditionRef-x` | `?` | `MIT WITH AdditionRef-x [exact]` | Q20 |
| `[MIT OR ISC]` | `?` | `ISC OR MIT [lexical]` | Q21 |
| Parenthesised abbreviations (`(GPLv2)`, `(MIT)`, `(Unlicense)`, ...) | assumed a fall-through | prediction kept | Q18 |
| `3-Clause BSD License`, `Artistic License`, `BSD (3 clause)`, `CC0 1.0 Universal`, `GNU GPLv3+`, `LGPL with exceptions`, `Modified BSD License`, `W3C SOFTWARE NOTICE AND LICENSE`, `W3C software and Document Notice License` | `?` | `- [unresolved]` | No rule reads them; Q9 and Q15 for the last two |
| `Apache-2.0 WITH Foo-exception` | `why` cites F2 | `why`: licenseid's exception lookup refuses it | Under D1 the library never sees `WITH` |
| `MIT\udcff` | `why`: reason `lone surrogate` | kept | G1: surrogates are refused before the drop guard |

No row told an ordinal key from a case-folded one in D1; T4b added one
(`MirOS OR MIT`, expected `?`: the plan gives the key as `(rank, text)` and
does not say which; T7 decides).

## 4. Decisions (2026-10-28)

| # | Question | Decision |
| - | - | - |
| Q10 | A tie between database and bundle when the database's build is outdated | The packaged list wins unless the database's build stamp is current (the `build vN outdated` warning still prints). A newer database list still wins (Q4) |
| Q11 | `source="auto"` with no database file | Silent; `lists[*].source` says `packaged`. A database that exists but is unusable warns `database: <condition>: <detail>; using packaged data v<ver>`. An explicit `db=` or `source="database"` still raises |
| Q12 | `"MIT"` with quotes under T6 | Refused in T6 (1 project, 843,066 downloads; reason `character dropped`). Follow-up task T6b reads quoted values in their different forms, balanced or not, as a rule with its own evidence |
| Q13 | Steps of a value the drop guard refuses | A `drop` step, `applied: false`, naming the dropped characters and the reading it stopped (`Apache 2.0?` to `Apache-2.0`), plus `reason` |
| Q14 | "or later" inside a compound | `OR`/`or` is an operator unless a grant phrase follows; then the phrase is one grant token equal to `+` on the ID before it. The phrase is the one reader, `classify.OR_LATER_PHRASE`, anchored at the `or` token. Extend it: the hyphenated `or-later`; and the grant reader writes `ID+` for an ID with no `-or-later` form (`Apache 2.0 or later` to `Apache-2.0+`; 0.6.0 answers unresolved although the phrase already matches). New phrasings go into `PHRASES` in `tests/ordering_helpers.py` |
| Q15 | What an operand may contain (Q9 made precise) | One token, plus `WITH` and its exception, a `+`, or a grant token (Q14). No other inner white space: `Apache License 2.0 OR MIT` is unresolved, reason `operand not resolved: Apache License 2.0` |
| Q16 | The 100-character key cap | Per `WITH` half; a `LicenseRef-` is exempt. The answers it moves are listed in the guard |
| Q17 | Operator case and spacing in a single `X WITH Y` | An `operator_case` or `whitespace` step: `exact` means the input equals the expression. Such values move to `lexical`, listed in the guard |
| Q18 | A value the compound stage refuses (`MIT License (MIT)`) | Falls through to the trove and prose rules first; `malformed` only when no rule reads it (`(MIT`, `MIT AND`). Order: one licence, compound, trove table, prose, malformed |
| Q19 | Where a bracketed group sorts (D1) | After all leaves, groups by their rendered text. Differs from `py-spdx-license` for `(A OR B) AND X WITH Y`; report upstream with the sort issues (section 5) |
| Q20 | `AdditionRef-` exceptions | Accepted as `LicenseRef-` is, unchecked against the list; the `WITH` leaf's rank (2) |
| Q21 | `[ ]` and `{ }` in a compound | Read as parentheses, with a `brackets` step; unbalanced or mixed stays `malformed` |
| Q22 | Trove table or prose rules first | The trove table first: a trove name the table reads as `none` (`W3C License`) is not read by P1 |
| Q23 | `GNU Lesser General Public License v2 (LGPLv2)` | Special case for this one trove name, because LGPL is widespread: read as written, `LGPL-2.0`, `assumed_only` (bare deprecated ID, candidates `-only` and `-or-later`). The misspelt "Lesser" (LGPL-2.0 is the "Library" GPL) does not block it, as the version is clearly 2. Not a general rule: another self-contradicting name stays unresolved unless listed the same way. Changed by the maintainer on 2026-10-28, replacing "reading none" |
| Q24 | Text order of the D1 leaf key | Case-folded, as the SPDX License List orders its IDs (licence expressions are case-insensitive, SPDX 3.1-dev); ordinal as a tie-break so the order is total: `MirOS OR MIT`. `py-spdx-license` and Pitloom 0.21.1 sort ordinally (`MIT OR MirOS`); announce in Pitloom 0.22.0 |

Technical choices taken without a question, from the reviews:

- `ListLookup` return types narrowed to the fields the chain reads (G2): a
  placeholder `pop_score` would be a value a later caller trusts.
- `dropguard.dropped(text) -> str`, the characters neither alphanumeric nor
  allowed; a diff against the resolved ID would refuse `GPLv3` and the `.0`
  the version key folds. Called in `resolveleaf._base` after the loose read,
  before `_spelling`; a refusal makes `read_leaf` return True with
  `unresolved`, so a compound reader does not retry the text.
- `reason` first lands in T6 (`Found.reason`, `Resolution.reason`, `None`
  by default); T7 fills it for compounds.
- Steps in a result: steps taken before the split first, then each
  operand's, then canonicalisation steps.
- A prose or trove rule maps a step kind to its category; it never sets
  `found.category` directly, or weakest-wins is lost (`GPL-3.0 License`
  must stay `assumed_only`).

## 5. For upstream (`py-spdx-license`)

Report with reproducers, not blocking 0.7.0 (D1 avoids all three):

1. `sort()` raises `TypeError` on repeated terms, also nested ones
   (`(A AND B) OR (B AND A)`) (F3).
2. The sort key includes the node class name, so an ID newer than the
   library's list sorts after every known one (F1).
3. A bracketed group sorts before a `WITH` leaf; licenseid puts groups after
   all leaves (Q19). Propose one documented order.

## 6. Provisional decisions (2026-10-29)

Taken during the overnight run, where the plan and Q1 to Q24 do not answer.
Provisional: the maintainer may reverse any of them.

| # | Task | Question | Chosen | Other options | Why |
| - | - | - | - | - | - |
| P1 | T5 | `resolve(value, db, source="packaged")`: a database given and the packaged list asked for | Refused: `InvalidInputError`, `option: invalid: source: 'packaged' with db; pass db or source` | The database wins (`source` ignored); the packaged list wins (`db` ignored) | Either silent choice ignores something the caller wrote; refusing is the narrower choice and easy to relax |
| P2 | T5 | How often `database: <condition>: <detail>; using packaged data v<ver>` is said | Once per process for each distinct line (a new condition is said again) | Once per call, as the `build vN outdated` warning of an opened database is; never | A consumer resolves hundreds of values; one line says the state. A changed condition still shows. The same goes for the stamp warning of the default database `resolve()` opens (`build vN outdated`, `build vN newer`), which 0.6.0 said on every call; a `db=` the caller built warns as it always did |
| P3 | T5 | Q10's "current" build stamp, for a database built by a newer licenseid (`build vN newer`) | Not current: a tie goes to the packaged list; the stamp compares as a number (`02` is `2`) | Newer counts as current | This licenseid cannot vouch for rows built by rules it does not know; the packaged list is its own. Narrower |
| P4 | T5 | `source="packaged"` with no bundle, or an unusable one | `DatabaseNotReadyError` `spdx-bundle.json.gz: not found` (or `invalid: <detail>`, after its warning), with `condition` and `detail` set | `LicenseIdError`; `InvalidInputError` | One `except` for "no list to read", as a caller already catches for a missing database |
| P5 | T5 | What "usable" means for the default database under `auto` | `check_database_ready` passes, read fail-open (a lock is no verdict), and the database opens. A file with the schema and no rows falls back, with `database: empty`, and `source="database"` refuses it (P8) | Whatever `LicenseDatabase(create=False)` opens | An empty database would answer `unresolved` for every value the packaged list resolves; it is the matcher's readiness gate |
| P6 | T5 | An account with no home directory under `auto` | Silent, like a missing file (Q11): both are `not found` | Warn | No database file to repair; the condition is the same |
| P7 | T5 | A deprecation flag that is not a JSON boolean (`"false"`) in a bundle | Read as `bool()`, as `listrules.is_deprecated` reads it, for licences and exceptions | Mimic SQLite's `is_deprecated = 1` for the exceptions' mappings | Every SPDX release has booleans; `spdxdata` does not check the type. The two can differ only on such a flag |
| P8 | T5 | `source="database"` on a default database that `auto` calls unusable (the tables, no rows) | Refused with the same `DatabaseNotReadyError` (`database: empty: ...`): `check_database_ready` runs first. A `db=` object is read as the caller built it. Narrows P5 | Read it as 0.6.0 did, answering `unresolved` for every value | Q11: an explicit database source raises rather than answering from a database that cannot answer; one verdict for both sources |
| P9 | T6 | Refused values of the early gate (control or format character) | Get a `reason` too: `control or format character: U+200B`; a lone surrogate gets `lone surrogate`. No `drop` step: nothing was read | Leave them without a reason until T7 | The plan names `lone surrogate`; a refusal with no reason is the odd one out, and the gate is one function |
| P10 | T6 | What `dropped()` returns | The dropped characters, each once, in order of first appearance; the `drop` step's `detail` and the reason's quoted text are that string (code points, `U+003F U+0021`, from S2 of the T6 review; first a repr, `'?!'`) | Every occurrence; only the first | A run of 2,000 `?` must not make a 2,000-character reason |
| P11 | T6 | Steps of a refused value | Only the `drop` step: a `trim` or `brackets` step before it is not kept, as no step is kept for any value with no expression | Keep the earlier steps | They would show applied changes that led to nothing; `from` is the text the leaf saw |
| P12 | T6 | `GPLv2 or later!` and `GPLv2? or later` | Refused (`!` and `?` are no grant tail; the tail `. , ; : ) ]` is read as before). 0.6.0 read the first as `GPL-2.0-or-later` | Leave the grant path unguarded | Same doubt as `Apache 2.0?`; only `looseid._RE_GRANT_TAIL` is exempt, as the plan says |
| P13 | T6 | Dropped character inside an operand that no leaf reads whole (`Apache 2.0?+`, `MIT? WITH X`) | The whole value is refused through the same exception: `unresolved` with the `drop` step and reason | `malformed`, or the `+`/exception read on its own | One rule at the one place (`_base`); T7 may refine it per operand |
| P14 | T6 | Is the minus sign U+2212 a dash for the drop guard? | Yes: the allowed dashes and the quotes are the sets `normalize_text` folds (`normalize.RE_DASHES`, `RE_QUOTES`, now public), not Unicode category Pd. So `Apache−2.0` is read; modifier letters U+02B9 to U+02BD are marks (quotes); a wave dash U+301C is a mark | Category Pd | One definition, independent of the Python Unicode version; SPDX matching guideline 4 calls the minus sign a dash |
| P15 | T6b | Which marks pair | Two marks of one *kind* pair, whichever opens: `double` (`" « » “ ” „ ‟ ″ ʺ ‴`) or `single` (`' ‘ ’ ‚ ‛ ‹ › ′ ʹ ʻ ʼ ʽ` and the grave accent). `normalize.QUOTE_KIND` holds them and `RE_QUOTES` is built from it, minus the ASCII apostrophe and the grave accent (`normalize_text` output is unchanged: a hash over every 3.29.0 licence text is the same before and after). Whitespace inside the marks (`" MIT "`) is trimmed | Strict open and close pairs (`“”`, `„“`, `«»`); any mark closes any mark | Languages disagree on which mark opens (German `„x“`, Swedish `”x”`, Danish `»x«`), so direction says nothing; a double mark closing a single one is a typo whose stray end is unknown (P16) |
| P16 | T6b | Mismatched marks (`"MIT'`, `“MIT’`) | Not read: the drop guard refuses them with both marks in the reason | Read as unbalanced on one end; read as a pair | Two marks and no way to say which is the stray one; refusing is narrower and easy to relax |
| P17 | T6b | One mark on one end only (`"MIT`, `MIT"`) | Read, with the step detail `unbalanced, start` or `unbalanced, end`, and the answer counts as `separator` (`resolver_rule`), not `lexical`, because the value may be cut. Only one stray mark is taken off: `""MIT` is not read. `"MIT'"` is read (unbalanced, end) while `"MIT'` is refused (P16) | `lexical` (`identity`); refuse | The author's text was not complete (a typo or a cut value): the maintainer asked to read it, and a weaker trust is the narrowest answer. A pair, then a stray (`""MIT"`) is read the same way |
| P18 | T6b | Nested or doubled pairs (`""MIT""`, `'"MIT"'`) | Every balanced layer comes off, one step, `balanced, N layers`; the kinds may differ between layers | One layer only (the rest then refused by the guard) | CSV and YAML escaping double the marks; each layer is a pair by the same argument |
| P19 | T6b | A mark left inside what the pair encloses | The value is not read, unless the mark is an apostrophe between two letters or digits (`AMD's`). So `"MIT" or "Apache-2.0"` is never read as one text, and a quoted `BSD 3-Clause "New" or "Revised" License` stays unread (0 in the sample) | Take the pair off anyway and let the guard and the List decide | The outer marks are a pair only if no mark closes them earlier; ASCII marks cannot say, and the List names with marks are not at either end (a test checks) |
| P20 | T6b | Where it runs | In `resolve()`, once per whole value: trim, `unquote`, `brackets`, and `unquote` again only if the brackets came off (`("MIT")`). `"(MIT)"` and `("MIT")` read; deeper alternation (`("(MIT)")`) reads too, through the compound reader, so `components` lists the parser (a value read twice by two readers; R7 found the text said "does not") | Only before the brackets; a loop until nothing changes | One reader of the value before the leaf, so `+`, `WITH` and grants inside compose; a loop invites a quadratic path |
| P21 | T6b | The step kind and its category | `unquote` is in `LEXICAL_KINDS` (a change of form, like `brackets`); an unbalanced one sets `Found.floor = "separator"` (from `Unquoted.balanced`), which `_category` adds to the step kinds, so the category stays the weakest of the steps and the floor | A new category; a second step kind; matching the detail text | No new vocabulary: the closed `Category` set and the consumers stay as they are |
| P22 | T6b | Which marks may stand alone on one end (narrows P17) | Quotation punctuation only (`STRAY_MARKS`: ASCII `"` and `'`, the grave accent, curly, low-9, guillemets). The primes U+2032 to U+2034 and the modifier letters U+02B9 to U+02BD pair but are never the stray: `GPL-2.0′`, `Apache 2.0″`, `ʻMIT` (the okina is a letter) and `MITʼ` are refused by the guard | Every mark of `QUOTE_KIND` may stray | A prime is a unit or a footnote and a modifier letter is a letter: neither is a quote left over |
| P23 | T7 | Quotes around one operand (`MIT OR "Apache-2.0"`) | `unquote` on each leaf, a balanced pair only, after the whole-value call; an `unquote` step per operand | Also an unbalanced mark; no per-operand unquote | A lone mark may be one end of a pair around several operands (`"MIT OR "Apache-2.0"`); the drop guard refuses it |
| P24 | T7 | A repeated operand (`MIT OR MIT`, `(A AND B) OR (B AND A)`) | Dropped after sorting, by rendered text, as a `dedupe` step (lexical); a group left with one operand is that operand | Keep the repeat; `malformed` | Idempotence changes no meaning; the step says it happened |
| P25 | T7 | Brackets in the canonical form | Only around an OR inside an AND; an AND inside an OR has none (`MIT OR 0BSD AND ISC`) | Brackets around every group | Precedence decides it; this is how `py-spdx-license` and the SPDX annex render it |
| P26 | T7 | Mixed bracket kinds | Properly nested `[ ]`, `{ }` and `( )` are brackets anywhere (Q21), around the whole too (`exprcanon.unbracketed`); a pair of two kinds (`[MIT)`) is `malformed`, reason `mismatched brackets`, not parsed | Refuse any bracket but `( )` | Q21; a mismatched pair has no reading to choose |
| P27 | T7 | Key cap and `AdditionRef-*` | Exempt from the 100-character cap, as `LicenseRef-*` is (Q16) | Cap it | Read as written, never through a key |
| P28 | T7 | `operands` when nothing is read | `[]` for a refusal of the grammar or a cap (`too many operators`); one unresolved operand, the whole value, for a value no reader claims | Always one operand per leaf | An operand is a licence the value names; a grammar error names none |
| P29 | T7 | The reason of a compound with an operand that names nothing | That operand's own reason and its `drop` step (P13 kept), else `operand not resolved: <operand text>`; the first such operand in input order | List every operand; no reason | One line, the grammar of `reason`; the operands say the rest |
| P30 | T7 | `malformed` or `unresolved` for a value the grammar refuses | `malformed` when every leaf is operand-shaped (Q15), no two operands stand side by side, the operators are in upper case, and one leaf names a licence (`MIT AND`, `(MIT`); else no compound at all | Always `malformed`; always `unresolved` | `BSD (3-clause)` and `MIT License (MIT)` are prose for T8 and T9, not broken expressions |
| P31 | T7 | A mark used as an operator | Reason `not an SPDX operator: /` (also `|`, `&`, `;`, `,`) only when every part is one ID word (`MIT/Apache-2.0`, `zlib/libpng`); still `unresolved` | Read `/` as OR; give the reason for any text with a mark | Every part is a listed ID, so the join is clear (`zlib/libpng` is two IDs, not one licence); a URL or prose has commas and slashes |
| P32 | T7 | New reasons | `too many operators`, `too deeply nested` (the caps of `identifiers`, 150 each), `mismatched brackets`, `parse failed: <the parser's message>`, the placeholders shown as the leaf texts | A generic `not an expression` | Say what the parser said; the caps keep deep nesting away from it |
| P33 | T7 | When `components` lists the parser | Amended after review (wording): whenever the parser parsed the value, a compound read or refused for an operand (`MIT OR Foo`), or a refusal with its `parse failed` message; never for a single value or a value no reader claims | Only for an answer with an expression; always | The answer, or its refusal, rests on the parse |
| P34 | T7 | `GPL-2.0 +` (a `+` after a space) inside a compound | Read as it is alone (`GPL-2.0-or-later`, with a `whitespace` step) | Refused in a compound | An operand reads as the same text alone; found by the adversarial tests |
| P35 | T7 | A grant on an ID with no `-or-later` form (`MIT or later`) | Decided by the maintainer on 2026-10-29: any ID with no -or-later form takes `+` when the result is valid SPDX (`MIT+`, `BSD-3-Clause+`, `Apache-2.0+`); the version-only rule is withdrawn. A `LicenseRef-*` takes no `+` and stays unresolved; `-only`/`-or-later` IDs stay refused | `+` only for an ID with a version (the rule between T7 and R7); unresolved for every ID | Maintainer's decision. Built first as `+` for any ID, narrowed after the T7 review, widened again here (reason: P35 decided by the maintainer) |
| P36 | T7 | The hyphenated grant after a version (`GPL-2.0 or-later`) | A grant: `stated_qualifier` (was `separator` through the version key); `-or-later` after an ID is still part of it | Leave it to the version key | One reader of the grant (`classify.OR_LATER_PHRASE`), and the step says a grant was stated |
| P37 | T7 | Case of `LicenseRef-*` when deduplicating | Case-sensitive: `LicenseRef-a OR licenseref-a` keeps both; the sort is case-folded, then as is | Fold the case | SPDX leaves the idstring of a reference to its author; folding would assert they are one |
| P38 | T7 | What counts as an operator | `AND` and `OR` with white space, a bracket or an end on both sides, in any case; `WITH` stays inside its leaf | Any `or` between words | `MIT"OR"ISC` and `and_mask` hold no operator |
| P39 | T7 | A grant in brackets inside a compound (`GPL-2.0 (or later) OR MIT`) | Read with its licence, as alone | Refuse it | The same reader as a single value |
| P40 | T7 | The component URL of the parser | `https://pypi.org/project/py-spdx-license/<version>/`, its purl `pkg:pypi/py-spdx-license@<version>`, the installed version | The repository URL | The released artefact, as the resolver names its own release |
| P41 | T7 | A grant after `WITH` (`GPL-2.0 WITH X or later`) | Moved to the licence: `GPL-2.0-or-later WITH X`, the step `from` the moved text | Refuse; give it to the exception | An exception takes no version grant |
| P42 | T7 | A lower-case operator and an operand that names nothing (`GPL-3.0 or higher`, `proprietary and confidential`, `MIT or Foo`) | Amended after review: no compound, unresolved with no reason and one operand, the whole value, unless some operand (any, not only the first refused) has a reason of its own or is `malformed`: then the compound is refused for the first such (`Foo or MIT?` gives `character dropped: U+003F`) | `operand not resolved: higher` | Never assert what the author did not write: a lower-case `or` between words is prose as often as an operator; a dropped mark is the author's doubt wherever it is |
| P43 | T7 | A leaf of several words (`Apache License 2.0 OR MIT`, `W3C Software and Document Notice License`) | Amended after review: no compound, whatever the operator case (Q18: the later rules read the whole value first), judged before the operator cap. When no later rule reads it, the reason is the first refused operand's (Q15, as P29): its own reason with its `drop` step (`Apache 2.0? OR MIT`), else, with the operators in upper case, `operand of several words: Apache License 2.0` when the leaf resolves alone (R7 S1; `operand not resolved: X` only for a leaf that does not); with a lower-case operator only an operand's own reason (P42). First built with no reason at all | Read the leaf as a name; no reason | Q15's reason, and T8 can still read such operands without undoing a split. Known: an all-capitals name (`W3C SOFTWARE NOTICE AND LICENSE`) gets `operand not resolved: W3C SOFTWARE NOTICE` |
| P44 | T7 | Sort order of the leaves | IDs, then `LicenseRef-*`/`DocumentRef-*`, then `X WITH Y`, each case-folded (`MirOS` before `MIT`); groups after the leaves by rendered text (Q19, Q24). Pitloom 0.21.1 sorts case-sensitively and puts groups first: 4 parity rows differ in order only | Pitloom's order | Q24; a fixed key over the resolved leaves, so the order is the same from every spelling |
| P61 | R7 | A detail built from input in a `reason` | One helper, `errors.one_line` (already the DETAIL helper of diagnostics): white space, so any line break (LF, CR LF, NEL, U+2028, U+2029), folded to one space; `;` made `,`; cut to 60 characters with `...`. The one exception is `not an SPDX operator: ;`, which keeps its `;` (folding it to `,` would make the reason false). Used for `operand not resolved`, `operand of several words` and the leaf in `parse failed` | A second helper in `resolve`; `looseid.shown` (`?` for each non-printable); a cap of 80 | One helper for every detail of one grammar; other control characters never get here, `read_leaf` refuses them first |
| P62 | R7 | A leaf of several words that resolves alone (`BSD 3-Clause OR Apache-2.0`) | Reason `operand of several words: BSD 3-Clause`; the value stays unresolved (P43) | `operand not resolved` (false); read the leaf (T8) | The reason says what is true: the leaf reads, but it is no operand (Q15) |
| P89 | T5b | How many list choices `resolve()` keeps, and when `ship` forgets them | The last one of each mode (`auto`, `database`), keyed by default path, file stamp (mtime ns, ctime ns, size, inode, device) and packaged index; a stat error but "not found" chooses again; `ship` and the `offline` fixture call `reset_choice()` | A choice per path; keep a raised choice; key by `last_update_datetime` (needs a connection) | One default path per process in practice; a stamp costs one `stat` and no connection. A raise or an unreadable stamp never leaves a stale hit |
| P90 | T5b | Which fallbacks to the packaged list `resolve()` keeps | `not found`, `empty`, `invalid` (they change only with the file, so the stamp sees them); never `unreadable` (a lock held elsewhere, I/O, permissions: it passes with no change to the file) or a raised choice | Keep every fallback; keep none | A kept `unreadable` read the packaged list for the whole process after a lock was released (review of T5b, B1) |

### Follow-ups found in T7

Not fixed in T7.

- T8: a compound of prose names (`Apache License 2.0 OR MIT`) is not split
  (P43); once T8 reads names, it may read such operands.
- T8: an all-capitals prose name with `AND` (`W3C SOFTWARE NOTICE AND
  LICENSE`) gets the reason `operand not resolved: W3C SOFTWARE NOTICE`
  (P43); T8, which reads names first, should answer it before that.
- `parse failed` quotes the parser, which sees round brackets only: `[MIT`
  gives `Unexpected '('`.
- Upstream (`py-spdx-license`): with `allow_unknown=True` the parser refuses
  `WITH` and `+` (the drift guard strips them first).

### Follow-ups found in T6

Not fixed in T6; for T8 or R7.

- R7: `licenseid match "Apache 2.0?"`, `"MIT*"` and `'"MIT"'` still answer
  `METHOD=id EXACT=true`: the Tier 0 loose ID has no drop guard, so `match`
  and `resolve` disagree.
- R7: `normalize_text` drops letters and digits too, so `REM MIT`, `x. MIT`
  and `1. MIT` still resolve.
- T8: trailing punctuation is uneven: `MIT;` is refused but
  `GPLv2 or later;` is read; `MIT...` is read but `MIT…` is refused.
- T8: marks inside the grant phrase (`GPLv2 or any *later version`) are still
  read.

### T9a: the trove table

Numbering starts at P45: the T7 branch takes P23 to P44.

| # | Task | Question | Chosen | Other options | Why |
| - | - | - | - | - | - |
| P45 | T9a | `GNU Lesser General Public License v2 or later (LGPLv2+)`, the sibling of the Q23 name | `none`, no ID | `LGPL-2.0-or-later` as `stated` | Q23 says it is not a general rule: another self-contradicting name stays unresolved unless listed. "Lesser v2" is 2.1 in the List, so "or later" is not clearly 2.0. `resolve("LGPLv2+")` already gives `LGPL-2.0-or-later` (`version_spelling`), so the table is stricter than the leaf; the maintainer decides (2 projects, 1,054,898 downloads); if extended, `stated` with `LGPL-2.0-or-later`. **Decided by the maintainer on 2026-10-29: `stated` `LGPL-2.0-or-later`** (the grant is written in the name); the text above is the earlier provisional choice |
| P46 | T9a | A name equal to the SPDX name of an ID that has no version (`Nokia Open Source License`, `Nethack General Public License`, `Attribution Assurance License`, `PostgreSQL License`, `Sleepycat License`, `Aladdin Free Public License (AFPL)` and more) | `stated` | `none` | The name writes the licence as the List does; there is no version to leave out |
| P47 | T9a | A name with no version where the List holds one version only (`Common Public License`, `IBM Public License`, `Sun Public License`, `Universal Permissive License (UPL)`, `Qt Public License (QPL)`) | `none` | `stated` | The name does not write the version; "only one exists" is a fact about the List today, not about the name (Qt is also not "Q Public") |
| P48 | T9a | Names with two readings or a short name that differs (`zlib/libpng License`, `W3C License`, `Python License (CNRI Python License)`, `Mozilla Public License 1.0 (MPL)`) | `zlib/libpng`, `W3C` and the CNRI name are `none`; the MPL 1.0 name is `stated` (`MPL-1.0`, the number is written) | CNRI as `stated` `CNRI-Python`; all `none` | `zlib/libpng` is `Zlib` (OSI titles it "The zlib/libpng License") or `zlib-acknowledgement` ("zlib/libpng License with Acknowledgement"); the W3C name has three IDs and no date (Q22); the head "Python License" points to `Python-2.0` and the bracket to `CNRI-Python`, and reading the bracket alone is the choice rule T3 refuses |
| P49 | T9a | Bare `v2`/`v3` GPL, AGPL and LGPL names | `assumed`, the deprecated bare ID | `stated` as `-only` | The existing policy and the parity rows: "v3" is not "only" |
| P50 | T9a | `strip_trove_path`: case and form | The prefix `License ::`, `OSI Approved` and the name are case-sensitive; spaces and tabs round `::` are free, a line break or other white space is refused; a deeper path, an empty name and `OSI Approved` alone give `None` | Case-insensitive; `\s` round `::` | A classifier is exact syntax on one line; `\s*::\s*` is quadratic on a long run of spaces |
| P51 | T9a | `strip_trove_path` and a path that is no classifier (`License :: MIT License`, `License :: OSI Approved :: Aladdin Free Public License (AFPL)`) | `None`: a path is accepted only in the real form of its classifier; each table entry records whether it is under `OSI Approved` (`TroveEntry.osi`), and a test checks that against `trove_classifiers` | Accept any path whose last segment is a key | A value that no tool writes is not a classifier; narrower, and reversible by ignoring the flag |
| P52 | T9a | The five deprecated `License ::` classifiers (`deprecated_classifiers`: Intel, Jabber, MITRE CVW, SISSL, X.Net) | In the table, decided like the rest (`Intel` and `Xnet` `stated`, the others `none`) | An explicit skip set | Old projects still declare them; the table and its test then cover all 89. SISSL decided by the maintainer on 2026-10-29: `stated` `SISSL`, the ID is written in the name (listed, not deprecated) |

### T9: reading the trove names

Numbering continues at P53.

| # | Task | Question | Chosen | Other options | Why |
| - | - | - | - | - | - |
| P53 | T9 | Where the rules sit | `resolvetrove.read_named`, called by `resolver._read` after the one-licence and compound readers and before any rule of prose (Q18, Q22). A name the table reads as `none` returns True with `unresolved`, so a later rule (P1 of T8) cannot read it | Inside `read_leaf`; after the prose rules | The order of the plan; the same contract as `read_leaf`; `resolveleaf` stays under its size |
| P54 | T9 | How a `stated` or `assumed` name gives its ID | The table's ID goes through `read_leaf` as if the author had written it: an ID the list lacks leaves the value unresolved, a renamed one is followed, a deprecated one without successor is `assumed_only` with candidates. A `trove_name` step comes first | Assert the table's ID without the list | One reader of IDs and of the deprecation policy; the answer is the list's, with or without a database |
| P55 | T9 | A path (T1) | The name is read as it is alone: the leaf lookup first (`MIT License` is `listed_name`), then the table. The answer is the same as the bare name, plus a `trove_path` step first | Always the table (`trove_name`) | A path is only the classifier's syntax (P50, P51): the name then has the answer it has alone |
| P56 | T9 | Kind and category of `trove_path` and `trailing_name` | Both are lexical kinds (`LEXICAL_KINDS`): the category is the weakest of the other steps (the name's, the head's), and `lexical` when there is none (`MIT (MIT)`) | A category of their own | They change the form and choose nothing: the two readings of T3 agree |
| P57 | T9 | The list of a trove step | `Step.list` is `pypi-trove-classifiers` for `trove_name` and `trove_path`; `lists` gets a second entry (`name` "PyPI trove classifiers", `version` None, `source` `packaged`, `url` `https://pypi.org/classifiers/`, `license` Apache-2.0, `provides` `["names"]`, `id_authority` false) only when such a step is in the result | The trove-classifiers version the table was checked against as `version`; always list it | The table is licenseid's data, not read at run time; the version of the check is a test fact |
| P58 | T9 | The shape of T3 | `head`, white space, one `(inside)`, no other bracket; head and inside each read by `read_leaf` alone and equal as expressions; the category is the head's, the steps `trailing_name` then the head's. Neither part is read through the trove or prose rules | Read the head through every rule | Narrow, and T8 can widen it by plugging its reader in one place (`_trailing`) |
| P59 | T9 | A `none` name | `unresolved`, no `reason`, no step. The `family of licences` reason of the plan has no task and no wording rule for names like `BSD License` | Reason `family of licences: BSD` | Left to the task that owns it; a reason invented here would be undecided vocabulary |
| P60 | T9 | How exactly a name matches | Amended after review: `stated` and `assumed` names match exactly and case-sensitively, after trimming, quotes and outer brackets. A name the table reads as `none` is refused when it matches case-folded with white space collapsed (`w3c license`, `Python   License (CNRI Python License)`), so no later rule can read round Q22 | Case-insensitive for every name; exact for `none` too (first built) | A closed vocabulary for reading; a looser match is safe only for refusing |
| P63 | T9 | Order of the trailing name (T3) and the table (T2) | T3 first: `Boost Software License 1.0 (BSL-1.0)` is `listed_name` (`list_data`) with a `trailing_name` step and no trove list entry, as is its lower-case form; the table reads the names the List does not back. 13 table names move (CeCILL-B and C, BSL-1.0, MIT-CMU, CDDL-1.0, EPL-1.0 and 2.0, HPND, MPL 1.1 and 2.0, OSL-3.0, OFL-1.1, The Unlicense). A `none` name is claimed before both | Table first (first built) | A reading the SPDX List backs is stronger than the table's, as P55 reads a path; the same name no longer reads weaker in its exact form than in lower case |

### T8: prose forms of one ID and the dropped-word guard

Code: `licenseid.resolveprose` (P1 to P3), `dropguard.dropped_words` and
`dropguard.without_end_marks`. Measured on the frozen sample: 18 values, 177
projects and 1.16 bn downloads read (unresolved 239 to 221, `prose_form` 0
to 18); the dropped-word guard moves no value of the sample or of the
parity corpus. Three parity rows now give their `expected_0_7_0`
(`Apache License, Version 2.0`, `BSD 3-Clause License`, `The MIT License
(MIT)`).

| # | Task | Question | Chosen | Other options | Why |
| - | - | - | - | - | - |
| P64 | T8 | Trailing `.`, `,`, `;`, `:`, `…` after a value | **Replaced by P77.** First built: a prose form left off what the drop guard lets pass (white space, dots, one comma) and refused `;`, `:` and `…` | See P77 | The grant tail (`GPLv2 or later;`) is shared with `match` and `markers` and is left as it is |
| P65 | T8 | Names of the step and the category | Step kind and category are both `prose_form` (the brief; the plan said `prose_words` for the step). Weakest-wins order: after `version_spelling`, before `trove_name`; trust `resolver_rule`. The step cites no list; the steps of the reduction do | `prose_words` for the step | One name for the kind and the category, so `category_of` needs no map |
| P66 | T8 | Steps of a prose form | One `prose_form` step for each reduction, from the text to what remains (`detail`: `leading article`, `licence word`, `version`), then the steps of the reduction read alone. `The MIT License` is article, then `listed_name` | One step for the whole | Each step is true by itself and the chain from value to ID shows |
| P67 | T8 | P3 and a listed name; P3 with T3 | After `The`, the rest is read by P1, P2, or as a List name (a `listed_name` step); an ID alone is not (`The MIT`). The head of T3 may be a prose form (`The MIT License (MIT)`): `resolveprose` reads `head (inside)` with `resolvetrove.trailing_parts`, the one parser of the shape, the head by the prose rules and the inside by `read_leaf` | `The` before any reading; no prose head in T3 | The plan asks for P3 only with a rule or a name; the parity row `The MIT License (MIT)` expects it |
| P68 | T8 | P2 target | Decided by the maintainer (replaces the first build, `<name> N` only): P2 reads `<name> N` through the loose key and, where `get_active_ids_by_name` holds exactly one ID for the exact name `<name> License N`, that too; if the two give different expressions the value is unresolved. `Mozilla Public License, Version 2.0` is `MPL-2.0` (`listed_name`); `GNU General Public License, Version 3` stays unresolved (no such name, and no loose key over names) | `<name> N` only | The exact name is a List name the author wrote in other words; a loose key over names would reach one they did not |
| P69 | T8 | A name that states no licence | Claimed (`resolvetrove.is_no_licence`, folded) also with a leading article, an end mark and as the head of a trailing name: `The W3C License`, `W3C license.`, `W3C License (W3C)` stay unresolved | Claim only the exact folded name | Q22 and P60: no later rule may read round it |
| P70 | T8 | Where the reader of an operand lives | `read_alone` and `read_by_name` (trove names, then prose) are in `resolveprose`; the compound reader and `resolver._read` import them. A prose form reads alone, so `BSD 3-Clause License OR MIT` is `operand of several words: BSD 3-Clause License` (P62), not `operand not resolved`. A reduction that the drop guard refuses gives that refusal (reason and `drop` step), as the head would alone | Keep `read_alone` in `resolvetrove` | `resolvetrove` cannot import prose without a cycle |
| P71 | T8 | R7 item 3: which words are dropped | The words that `normalize_text` takes off a line: the value is read twice by `version_key`, with and without the line rules (comment prefix, repeated separators, bullets and list markers; `normalize_text(..., line_rules=False)`), and the words of the second reading that the first lacks are the dropped words. No list of markers. Reason `word dropped: rem 1` (lower case, through `errors.one_line`), `drop` step not applied. Checked on 9,912 spellings of the List's IDs and names: none drops a word | A list of markers; refuse at `normalize_text` | One reader (`normalize_text`) says what it drops. `rem MIT` (lower case) is not a marker for it and stays unresolved without a reason, as `not MIT` |
| P72 | T8 | Dangling dash or dots | **Amended by P77 and P78.** A lone dash at either end (`MIT -`, `-- MIT`) and a first token of dashes or dots (`. MIT`, `... MIT`) are dropped marks; a lone dot at the end is an ending (`MIT .`). Ellipsis: `MIT...`, `MIT…` refused | Read `MIT...` | A single mark is an ending; a run is a list or a cut |
| P73 | T8 | Marks after a prose form | **Amended by P77.** One mark at the end is left off first, as for a leaf (`MIT License;`); any other mark stays on the reduction, so the drop guard refuses it with its reason (`MIT License...`, `MIT License?`), and a mark never helps a reading (`Apache-2.0 License+` stays unresolved) | Leave all marks off | One reason, from the reader that knows the mark |
| P74 | T8 | P1 and P2 reach a deprecated ID through the loose key (`Net-SNMP License`, `Nunit License`, `BSD 2-Clause FreeBSD License`, `eCos license version 2.0`) | Kept: `deprecated_ambiguous` (`list_data`), as the same ID written with other separators is. 31 List spellings, none in the sample | Refuse | It names the right licence; the deprecation policy already keeps the ID as written |
| P75 | T8 | A doubled article or licence word | Refused: `The The MIT License`, `MIT License License`; P3 needs the rest not to start with an article, P1 a head that does not end in a licence word. `GNU General Public License v2.0 only License` still reads (its head ends in `only`) | Read when the inner part is a List name | Even rule, no dependence on the List |
| P76 | T8 | What P1 reads | One licence, a simple expression: `MIT+ License` is `MIT+`, `LicenseRef-Proprietary License`, `X WITH Y License`; docs say "one licence" | "One ID" | `read_leaf` is the reader; no second grammar |
| P77 | T8 | Marks at the end of a value (replaces P64) | Maintainer, 2026-10-29, single marks only: one `.`, `,`, `;` or `:` with white space around it is an ending. `.` and `,` pass in the drop guard as before; `;` and `:` are read again without it when the value is refused for them (`resolveleaf.read_leaf`, a `separator` step `end mark`, category `separator`; a grant tail that already reads is not touched). Two or more marks (`MIT;;`, `MIT.;`, `MIT..`), an ellipsis (`MIT...`, `MIT…`) and a lone dash are refused with `character dropped`. A prose form trims one mark the same way (`trim_end_mark`). Compound operands follow the rule alone, so `MIT; OR ISC` is `ISC OR MIT`. `MIT..` and `MIT...` were read before (P72) | Trim runs; trim nothing | Narrow: a run could be a list or a cut value. `MIT+;` stays unresolved without a reason (R7 item 4, the plus path has no guard) |
| P78 | T8 | Marks at the start | Nothing is trimmed: `-- MIT`, `; MIT`, `... MIT` are refused. A dot or dash touching the ID (`.GPL-3.0-only`, `-MIT`) was read on main as `separator`; it is refused now (`dropguard.lead_marks`): 38 IDs end in another ID (`AGPL-3.0-only`), so it is a cut value. No sample or parity value moves | Leave it | The cut value would resolve to a licence the author did not write |
| P79 | T8 | Where the end rule sits | In `read_leaf`, so a whole value, a compound operand and a prose head follow one rule; only after the first reading was a refusal, so values that read today keep their steps | In `resolver._prepared` (whole value only) | Operands read as the same text alone |
| P80 | T8b | A mark after a `+`, an exception or a `LicenseRef-*`, and a lone dash after a prose form (R7 item 4) | One end mark `.`, `,`, `;` or `:` is an ending, read without it (`MIT+;`, `GPL-2.0+.`, `MIT WITH X;`, `LicenseRef-a;`: a `separator` step, `end mark`); any other mark, or two or more, refuses the value with the marks in the reason (`GPL-2.0+?`, `MIT+;;`, `MIT WITH X?`, `LicenseRef-a?`), and only when the core reads (`Foo+?` stays silent); the `+` itself is never in the reason (`resolveleaf._after_core`). A dot stays an ID character in `LicenseRef-a.`. A prose form keeps the white space before its marks (`MIT License -` is `MIT -`, dangling, `character dropped: U+002D`) | Refuse every mark after an exception and a `LicenseRef-*`, ending or not; `+` only | The maintainer asked for the ending after `+`; R7 names the cause (these readers return before the guard), so one rule serves the three shapes and the guard of an ID is the model |
| P81 | T8b | What a `;` list answers | `expression` None, category `unresolved`, trust `none`, reason `operator not stated: ;`, `operands` one for each part, `candidates` and `expansions` empty. The steps are the ones taken before the split (`trim`, `unquote`, `brackets`), as for `(MIT; ISC)` before. A part is read by the whole-value reader without the list rule, trimmed (no `trim` step), so a compound part is read as that compound and a prose part as prose; its operand is that reading, with the text and span of the part, quotes included. Run after the one-licence reader and after a compound that resolves | Run before the compound reader; give the whole the first part's steps | Nothing that resolves today may change (`MIT; OR ISC` is `ISC OR MIT`); a value refused today may change reason and operands |
| P82 | T8b | An empty part, and the `;` at the end | `MIT;;Apache-2.0`, `;MIT;ISC`, `MIT; ;ISC` are no list: refused as before. One `;` at the very end is an ending (T8, P77) and left off first: `MIT; ISC;` is two parts, `MIT;;` is refused by the guard | Drop empty parts; read `;;` as one separator | Two marks may be a cut or a typo (P77); dropping them guesses |
| P83 | T8b | When a `;` list is a list of licences | At least two parts name a licence, or would but for a mark or word the guard drops (`Apache 2.0?`: a `drop` step). With one, the value is refused as before: `MIT; Copyright (c) 2016` and `MIT; foo` | Any two parts; every part named | `MIT; Copyright ...` names one licence and a notice: "operator not stated" would say it names two. A doubted part still counts, as the author wrote a licence there |
| P84 | T8b | `,`, `/`, quotes and operator words with a `;` | `,` and `/` are not separators here (T7's `not an SPDX operator` stays). Quote marks are not tracked: a `;` inside quotes splits. A part that starts or ends with `AND`, `OR` or `WITH` in any case (`MIT; OR ISC; Apache-2.0`, `MIT;OR;ISC`) means an operator was stated: no list, the old refusal stays (`resolvesemicolon._operator_beside`; with two parts the compound reader reads it first). Prose at a part's edge (`MIT; ISC; and others`) blocks a list too: the narrow side. A lower-case `and` or `or` inside a part is that part's own reading. An earlier commit removed the check as redundant; the review showed it matters with three parts | Case-sensitive upper case only; track quotes; split `,` when every part is an ID | A comma is common inside names; `/` is T7's; saying "no operator stated" when one was is a false statement |
| P87 | T8b | A name that reads whole, with a `;` in it | `MIT; (MIT)`, `MIT License;\t(MIT)` are the name and its short form, read as before (`MIT`, `trailing_name`): the by-name reader runs before the list rule and wins when it gives an expression (a refusal of it does not) | List first (the first T8b commit did; 5 values of the base moved) | Nothing that resolves on `main` may become a list |
| P88 | T8b | A list where no part resolves | Not a list: `-MIT ; -MIT`, `MIT...; MIT -` keep the reason they had. A list needs two parts that name a licence and at least one operand with an expression | Two doubted parts are enough | Maintainer-style narrowing (the review found 113 such lists): "operator not stated" about two refused parts says more than the resolver read |
| P85 | T8b | Brackets and nesting | Only a `;` outside every bracket splits; a bracket that does not close, or closes before it opens, makes no list. A `;` inside a bracket is the compound reader's, as before (`(MIT; ISC) OR GPL-2.0` is `not an SPDX operator: ;`). The brackets around the whole come off first (`(MIT; ISC)` is a list). A part is read without the list rule, so a list inside a part is not split again: depth one, and no recursion on `(((MIT; ISC); X); Y)` | Recurse with a depth cap | Bounded cost and stack; the case is not in the sample |
| P86 | T8b | `components` of a list | The tools that took part, as before: the parser is listed when a part needed it (`MIT OR ISC; Apache-2.0`), else `[]`. No field of "IDs found": they are the `expression` of each operand | A new field for the licences found | The brief said `components` the IDs found; the field means tools since T7, and the operands already carry the IDs |
| P91 | T10a | Whether `licenseid.detect()` builds a detector per call | It keeps one `LicenseDetector` per default path and file stamp (`listsource.file_stamp`, the stamp of P89), looked up and stored under a lock and built outside it, never one that raised or one on a path with no file; it says each build warning once per process (`listsource.warn_once`); `keptdetector.reset()` forgets it | A detector per call; a module-level detector made at import | A detector costs 5 connections and about 59 ms against 13 ms kept, and an outdated database warned on every call, where `match()` says it once (#119) |
| P92 | T10b | How `licenseid match` writes a value that holds a space (`FROM=Apache License, Version 2.0`) | **Superseded by P102.** One rule for every value, `EXPRESSION` included: Python's `unicode_escape` and a space as `\x20` (`result.text_field`, read back by `read_text_field`), the fields joined by one space as on `detect`'s line; ASCII only; `=` kept, a key ends at the first one | A tab between fields and the values as written (a readable expression, but a second separator in the CLI); values as written, as `text_line` writes them; shell quoting | `text_line` has no quoting rule to reuse: its values are IDs, numbers and expressions whose only spaces are around operators, and `awk` splits those. With the escape every field is one word for `awk`, `cut -d' '` and `read -r` on any locale and code page, reversed by the decoder Python ships and by `--text`'s own (`cli.unescape_text`); the PyPI sample writes its fields so (`\x2c` for its own separator). The cost is `EXPRESSION=MIT\x20OR\x20ISC`; `--json` has the strings as written |
| P93 | T10b | Which steps get a `STEP=` line | The applied steps of `steps`, in order, then the applied `expansions` | `steps` only, as D6 words it | `GPL-2.0+` has no step but its `plus_to_or_later` expansion: without it the text would not show the `+` read as `-or-later`. A declined step (`drop`, `assumed_only`) prints nothing; the category and `REASON=` say it |
| P94 | T10b | When `OPERAND=` lines are printed | Only when `reason` is `operator not stated: ;` (`resolvesemicolon.REASON`) | For any value with several operands, an unresolved compound too | D6 names the `;` list; a compound's reason already names the operand refused, and `--json` has every operand |
| P95 | T10b | Exit 1: what goes on standard error | **Superseded by P108.** Nothing: the result lines are printed on standard output, as `is-*` prints `false`. `assumed_only` (`GPL-3.0`) has an expression and exits 0 | `ERROR: match: no license found`, as `detect` prints | The lines are the answer (category, reason, operands); an `ERROR` line says the command failed |
| P96 | T10b | The wording of a refusal | **Superseded by P103 for a path.** `option: invalid: --text: a licence text`, `input: invalid: file: <value>`, `input: invalid: standard input`, `input: invalid: line break: <value>`, `input: invalid: over 2000 characters`, each ending `; run 'licenseid detect'`; an empty argument `input: empty: argument` and a lone surrogate as `detect` words them; no value from a terminal or a closed standard input `input: missing; pass one declared licence value`. `--text` is a hidden option, so it is refused with that pointer, not as unknown | A CONDITION of its own (`not a value`); `--text` left to click (`option: not found`) | Existing conditions, no addition to AGENTS.md; the DETAIL says which |
| P97 | T10b | What counts as a file, and as a line break | **Superseded by P103 for a path; the line break stands.** `os.path.exists`, the test `detect` makes (a file, a directory, a FIFO); any `str.splitlines` boundary, at the end too (`MIT\n`, `\r`, `\x1c`, U+2028) | `os.path.isfile`; `\n` and `\r` only | `detect` would read what exists; `match()` reads `\x1c` and U+2028 as white space, so a value that breaks lines anywhere is refused rather than joined |
| P98 | T10b | The length cap | **Superseded by P104.** The raw argument over `resolver.MAX_EXPRESSION_CHARS` (2000; made public) | The cap on the trimmed, unquoted text, as the resolver applies it | Refusing more is the narrow side; a 2001-character value that trims to 2000 is refused, not read. Reading it would put the resolver's preparation in the CLI |
| P99 | T10b | Standard input beside a value, and the order of the checks | **Superseded by P103 for the path check only.** A piped standard input is refused only with no argument (a script's stdin is seldom a terminal); the input is checked before the list is chosen, so a refusal is the same with or without a list | Refuse any piped stdin; the database first, as `detect` | `match` needs no database: the list is chosen inside `match()` |
| P100 | T10b | `--db` with `--source packaged` | Exit 2 `option: invalid: --source: packaged with --db; pass --db or --source`, in the CLI's names, before the database is opened | Leave it to `match()` (P1) | P1's `InvalidInputError` would reach the group as a traceback: it catches database and output errors only |
| P101 | T10b | One JSON writer for both commands | `json_line(result: Detection \| Resolution)` dumps the mapping as it is (a detection holds exactly its nine keys, so its bytes are unchanged); a resolution's characters outside ASCII are written as UTF-8 (RFC 8785) | A second function beside it | The brief's proof is `json_line(match(V))`; one canonical writer |
| P102 | T10b | How a text line of `detect` and `match` separates and writes its fields (maintainer, A) | One tab between fields; a value as written, but a tab, CR, LF and backslash as `\t`, `\r`, `\n`, `\\` (`result.text_field`, read back by `read_text_field`); the README and both `--help` texts say once to read with `cut -f` or `awk -F'\t'`. AGENTS.md's field separator is a tab | P92's `unicode_escape` and `\x20` | A readable expression (`EXPRESSION=MIT OR ISC`) that still splits on one character; four escapes keep a value on its line and its field |
| P103 | T10b | A value that is also a path (maintainer, B) | Read the value first: one that resolves is answered even when a file or directory of that name exists (`match MIT` beside `MIT`, on a case-insensitive file system too); refuse only one that resolves to nothing and `os.path.exists` (`.`, `/`, a directory, Windows `NUL`): exit 2, `input: invalid: path: <value>; run 'licenseid detect'`, nothing on standard output. `--text`, piped standard input, a line break, the cap and an empty value are still checked before the list is chosen | P97's refusal of every existing path, worded `file:` | A licence ID is a common file name (`MIT`, `LICENSE`-like names); `path:` fits a directory |
| P104 | T10b | What the length cap counts (finding 3) | The value as `match()` reads it: `resolver.read_length` (the length after its own preparation: trimmed, unquoted), checked only when the raw length is over 2000 | P98's raw length | One count for the CLI and the API: a padded 2001-character value that `match()` reads as 2000 characters is read, not refused. The raw check first keeps the preparation off short values |
| P105 | T10b | No argument and an empty piped standard input (finding 2) | `input: missing; pass one declared licence value`, exit 2: `climatch._piped_something` reads one byte, and a pipe that brings none (`</dev/null`, `printf ''`), or fails, is no input | `input: invalid: standard input` for any pipe | Nothing was brought, so nothing is refused as a text; the pointer to `detect` would be wrong |
| P106 | T10b | The name of `detect`'s answer (maintainer, C) | `EXPRESSION` on the text line, `expression` in `--json`, `Detection["expression"]` and `result.public_result`; `--id`, `license_id=`, `is-*`, the raw records and the database columns keep `license_id` | Keep `LICENSE_ID` | One key for the answer of both commands; the input names stay, as they name what is asked |
| P107 | T10b | The diagnostic subject of `detect`'s lines (maintainer, D) | `detect`, `looseid`'s `WARNING: detect: variant not stated` included: only `detector` and `shorttext` call it, so `match GPL2` warns nothing (a test pins it) | `match` | The subject names the command; `match` is now another command |
| P108 | T10b | Exit 1: standard error (maintainer, E) | Nothing, for `detect` and `match`; `detect` prints nothing at all, `match` its lines. `no license found` leaves the AGENTS.md conditions: nothing else used it | P95 for `match` only; `ERROR: match: no license found` on `detect` | Exit 1 is an answer ("no"), not a failure; an `ERROR` line says the command failed |
| P109 | T10b | How the README shows the two commands (maintainer, F) | A table of `detect GPL2` (`GPL-2.0-only`, with a warning) beside `match GPL2` (`GPL-2.0`, `assumed_only`), saying what each means | Examples that agree | They answer different questions; a reader must not expect one answer |
| P110 | T10b | A character the locale cannot write (lead, G; provisional) | `--json` of both commands is UTF-8 bytes on every locale (`output.echo_json`, to the stream's buffer; RFC 8785); a text line is written in the stream's encoding, a character it cannot hold as `\xHH`, `\uHHHH` or `\UHHHHHHHH` (`output.echo`, the one place; `read_text_field` reads them back). `cli.main`'s stream-wide `backslashreplace` goes | Leave both to the stream's error handler; UTF-8 for text too | JSON is bytes by its RFC; a text line stays readable on its own locale and loses nothing. Tests: latin-1, cp1252, ASCII with é and an emoji, text and `--json`, through the runner and a child with `PYTHONIOENCODING`; matrix cells F5 |
| P111 | T10b | The matrix cell for a reader that closes the pipe (finding 6) | `( licenseid ... ; echo "[rc=$?]" >&2 ) \| true` records the command's own status, which must be 141 | The pipeline's status (always `true`'s) | The cell passed whatever the command did |
| P112 | T10b | What the matrix's judge reads (finding 7) | A `detect` line or object (no `schema`) apart from a `match` resolution (`schema`, the head line), split on tabs; `detect`'s exit 1 must print nothing on either stream. `tools/pypi_licence_sample/answer.py` keeps its own `\x2c` rule: it writes a fixture TSV from the Python API and reads no CLI output | One shape for both | The two results differ; a judge that mixed them would pass a wrong one |
| P113 | T10b | The result of `is-*` and `update` (maintainer, H; provisional) | One record of `KEY=VALUE` fields, tab-separated and escaped as P102, through one writer (`clicommon.echo_record`: `result.fields_line`, or with `--json` `result.record_json`, keys in lower case, a flag a JSON boolean, nothing `null`), which both commands now take; exit codes unchanged | `true`/`false` and a sentence, as before | One shape on every command, for a script and an agent alike; the `--json` writer is the one RFC 8785 writer of P101 |
| P114 | T10b | The fields of an `is-*` record | `EXPRESSION=<the ID judged>` and one flag named as `detect`'s JSON names it (`IS_OSI_APPROVED`, `IS_FSF_LIBRE`, `IS_SPDX`), or by the command where `detect` has none (`IS_OPEN`, `IS_FREE`: the alias names its own question). EXPRESSION is the record `resolve_record` judged: its canonical ID (`is-fsf GFDL-1.3` judges `GFDL-1.3-only`, an expression is in canonical order), empty (JSON `null`) when the input names no licence (below the 0.85 bar), with the flag `false` and exit 1 | `OSI=`, `FSF=`; `IS_OPEN` for the alias too; the input as given | The keys match the JSON a user already reads from `detect`; the ID judged says what the answer is about, which the input may not |
| P115 | T10b | The fields of `update`'s record | `STATUS=updated` or `unchanged`, `VERSION=` the list version the database now holds (`db_metadata`; empty when none), `PATH=` the database path as given; a failed update prints nothing on standard output, as before | The version asked for; a `STATUS=failed` line | The result is the state the database is left in; a failure is an `ERROR` line and exit 1 |
| P116 | T10b | Where `detect --diff` writes its word diff | Standard error, through `console.status` (progress, not a result): standard output holds only result lines. Coloured only when standard error is a terminal. The grammar checker (`tests/conftest.py`) judges only lines that start `ERROR:` or `WARNING:`, and no diff line does (` `, `+`, `-`, `@`, `WORD DIFF:`) | Standard output, as before; colour by click's rule, which a runner can force | A reader of standard output parses one shape; the diff is for a person |
| P117 | T10b | `--clear-cache` | Unchanged: it prints no result, only progress on standard error, so the record rule has nothing to apply to | A `STATUS=cleared` record | Nothing to parse; a script reads its exit status |
| P118 | T10b | The matrix cells for H | `--json` leaves B3 (predicates take it now); B6 runs `is-* --json` found, not found and from standard input, D8 `update --json` updated, unchanged and failed; the judge reads the predicate record (flag agrees with the exit status) and the update record, text or JSON, and lets the word diff of a `--diff` cell through on stderr (`judge.WORD_DIFF`), nothing else. With these the full run (1,283 cells) has NEW=0 FIXED=0: the baseline is unchanged | Keep the old contracts beside the new | Each command's cells hold it to its documented shape |
| P119 | T10b | Exit codes across the commands (maintainer, I; provisional) | 0 an answer, yes or done; 1 no answer, no, or an action that failed; 2 usage, input, a database not ready, or a result that could not be written. Audited: `detect`, `match`, `is-*`, `update`, `--version`, `--help` and the bare group follow it; `--clear-cache` exited 2 for a delete the system refuses (`database: delete failed`), now 1, as a failed update does. Its refusal of another program's file stays 2 | Keep 2 for every `--clear-cache` failure | A refused delete is no usage error: the command was understood, and running it again unchanged may work once the directory is writable |
| P120 | T10b | Where the output pattern is written down, and how it is held (maintainer, J; provisional) | Once, in AGENTS.md "CLI output": the separator, the escaping, uppercase keys that are the JSON keys in lower case, an empty value (JSON `null`) for nothing, the exit codes, the three exceptions (`detect --bold`, `--version`, `--help`), and the maintainer's rule in his words: "--json and any JSON output will always write with RFC 8785: JSON Canonicalization Scheme (JCS)". `tests/test_output_pattern.py` runs every command (`cli.list_commands`, so a new one fails it until added), text and `--json`, pins each run's exit status so none passes by printing nothing, holds every text line to the pattern and every JSON line to its own JCS bytes (`rfc8785.dumps(json.loads(line)) == line`), and for `update` and `is-*` requires the JSON keys and values to be the text record's. The README has "Reading the output" with `cut -f`, `awk -F'\t'` and `jq` examples, each run by hand on 3.29.0 | A pattern per command; a test per command | One reader for every command; a test that sees every command finds the next one that strays |
| P121 | T10b | Where the new options are tested in combination | `is-* --json` is an axis of `test_predicate_matrix` (PREDICATES x SOURCES x --json x found); `update --json` an axis of `test_update_matrix` (--source x --cache x --version x --force x --json), which `test_option_matrix`'s table now names; matrix cells B6 and D8 (P118) | Every axis in `test_option_matrix.py` | The update matrix already holds the network fakes; one place per surface |
| P122 | T10b | JSON written outside `result.json_line` (the JCS rule) | None on standard output: `output.echo_json` is the only JSON writer of the CLI. Left out of scope, all files on disk, none CLI output: `spdxdata.py` (the bundle's payload, sorted and compact, gzipped), `spdx_source.py` (the cached `licenses.json`, as served), `tools/build_bundle.py` (`latest.json`, published beside the bundle), `tools/pypi_licence_sample` (its raw sample, JSON Lines), `tools/cli_matrix` (`results.json`, the launcher's fakes) | Write those through `json_line` too | A data file's bytes are a format of their own, read back by licenseid; a change there is a data-format change, not an output one |
| P123 | T10b | The line ending of a result (lead; provisional) | Every result line on standard output ends in `\n` on every platform, text and JSON alike (JSON Lines). `output.echo` and `echo_json` write bytes under the text stream through `console.emit`, the one writer, so Windows' text layer cannot add `\r`; `--help` (`output.EchoHelpCommand`) and `--version` go through `echo` and follow it (tested) | The platform's ending for text and `\n` for JSON, as 0.7.0's first build did on Windows CI (one run mixed them) | `awk` in Git Bash keeps a `\r` in the last field; one ending for one stream |
| P124 | T10b | The line ending and encoding of a diagnostic | The same rule: `console._write` writes through `console.emit`, so a diagnostic ends in `\n` on Windows too and a character the stream cannot hold is a backslash escape (as Python's stderr handler did). The grammar checker (`tests/conftest.py`) now wraps `console._write`; it wrapped `print` | Leave stderr to `print` (`\r\n` on Windows) | One rule for every line licenseid writes; a script greps stderr as it reads stdout |
| P125 | T10b | How a diagnostic writes a path, a file name or a value (sweep, class C; provisional) | On one line, but not escaped as a result: a name through `errors.shown` (moved from `dbcheck._shown`: a control character as an escape, `;` as `,`, a backslash as it is), a value through `one_line`. The input's file name in `input: binary file`, `not UTF-8, read as Latin-1`, `empty` and `unreadable` went raw, so a file name with a line break split the diagnostic in two; it now goes through `shown` (`tests/test_shown_path.py`, the CLI part POSIX only, the function on every OS) | The result escaping (`text_field`) for a DETAIL too | A diagnostic is for a person and its grammar is `: `-separated, not tab-separated; a Windows path should read as typed. The one-line rule is what a parser needs |
| P126 | T10b | Files licenseid writes in text mode (sweep, class B) | `popularity.csv` is cached as the bytes served (`write_bytes`); text mode on Windows turned a served CRLF into CR CR LF (harmless only because `csv` skips the blank rows it read back). `licenses.json` and `latest.json` stay `json.dump` in text mode: JSON written so has no raw line break. Nothing compares a hash of a file licenseid wrote (the bundle and tarball are bytes) | Leave the CSV in text mode | The cache should hold what was served, on every OS |
| P127 | T10b | The rest of the Windows sweep (classes A, D, E, F) | A: expected result lines are built by `fields_line`/`record_json` (`conftest`); a diagnostic built from a path stays raw by P125, so those tests hold on Windows. D: both streams escape through `console.emit`, so cp1252, cp932 and `PYTHONIOENCODING=ascii` raise nothing and never exit 120 (child-process tests for both streams). E: a path is printed as the OS spells it, escaped by rule A (`\\` doubled, UNC included); no SPDX ID or exception ID is a Windows device name (`CON`, `PRN`, `AUX`, `NUL`, `COMn`, `LPTn`, checked on 3.29.0), and `match` path-checks only a value that resolves to nothing, so `NUL`, `mit` beside `MIT` and a trailing dot cannot hide an answer. F: the POSIX-only delete-refusal test has a simulated twin that runs on Windows | — | One record of what was checked and found sound |
| P130 | Small | Non-string input (`match(None)`, `match(b"MIT")`, `match(1)`, and `match_with`) | Maintainer-approved narrow choice: `TypeError("value must be str, not bytes")` at the one entry, in `match` before the list is chosen and in `match_with` before it is read (`resolver._require_text`); a `str` subclass passes. The docstring says so. Not an `unresolved` result | An `unresolved` result with a reason; decode `bytes`; `str(value)` | A caller's mistake is not content: `unresolved` would hide it, and decoding or `str()` would guess. It raised `AttributeError` from `strip` before |
| P131 | Small | A dash joined to the end of a `+`, an exception, a `LicenseRef-*` or a prose form (`MIT+-`, `MIT+--`, `MIT License--`) | Refused with `character dropped: U+002D` (the dashes it would drop, each once, as for `MIT -`), one `drop` step. `dropguard.end_dashes` names them; `resolveleaf._after_core` adds them to the marks it refuses, and `resolveprose._by_rule` refuses a reduction whose marks end in a dash (`resolveleaf.refuse_dropped`, the one place a refusal is made). `MIT-` and `MIT--` still read (a loose ID takes a dash as a separator). (Widened by P136: `MIT+-?`, `MIT License-.` and an underscore too.) | Read the dash off; add dashes to `dropguard.dropped` for every reading | R7 item 4 named the cause (these readers return before the guard); `dropped` must keep a dash a separator where a loose ID read it. Nothing that resolves moved |
| P132 | Small | One end mark after a `LicenseRef-*` that ends in a dot (`LicenseRef-a.;`) | An ending, as after any ID (`MIT;`, P77/P80): read as `LicenseRef-a.` with a `separator` step `end mark`. `trim_end_mark` refuses a mark before the last one, and the dot of the ID looked like one; `resolveleaf._ref_without_end` found the case (replaced by `dropguard.ends_in_ref`, P134). `LicenseRef-a.;;`, `LicenseRef-a;;` and `LicenseRef-a.?` stay refused with their reasons | Teach `trim_end_mark` about IDs (it is standard library only and knows no grammar); trim every mark | One rule: P80 makes the dot an ID character, and an ending is one mark. A run stays refused (P77) |
| P133 | Small | Quote marks, then one end mark (`"MIT".`, `"MIT",`, `"MIT";`, `'MIT'.`), against `MIT,"` | Read, in the order the steps apply: a `separator` step `end mark` (`"MIT".` to `"MIT"`), then the `unquote` step, so the category is `separator`. `quotes.ended_quote` finds the case and `resolver._unquoted` takes the step, in both runs of `_unquoted` (after the brackets too). **Marks on one side only read too (maintainer, 2026-10-30, as built):** `MIT".`, `MIT'.`, `Apache-2.0'.`, `GPL-2.0".`, `MIT+".` are read, with the `unquote` detail `unbalanced, end`, as `MIT,"` is; the marks need not pair. It applies when exactly one end mark ends the value (`trim_end_mark`), the mark before it is a quote mark `unquote` takes off, and what the marks enclose does not end in a mark (P135). `"MIT"..`, `"MIT".,`, `"MIT.".`, `"MIT;".`, `"MIT'.` (two kinds, P16) and `"MIT"+` stay refused | Unquote first, then the mark (a `separator` step after `unquote`); read only a balanced pair; refuse the end mark after the marks | The end mark stands outside the marks, so it comes off first; the same rule as `MIT;` (P77) decides, and the order of the marks is not the writer's meaning. A mark on each side of the marks is two marks, as `MIT;."` is. Nothing that resolves moved. Operands of a compound (`"MIT" OR "ISC".`) are not read |
| P134 | Small | Which end marks a `LicenseRef-*`, `AdditionRef-*` or `DocumentRef-*` ending leaves alone | The characters an ID may end in (`.` and `-`; SPDX has no `_` there) are not marks: `trim_end_mark` takes one end mark off after them (`LicenseRef-a-;` and `MIT WITH AdditionRef-x.;` read, with a `separator` step), through `dropguard.ends_in_ref`, which asks `exprtokens` alone. `resolveleaf._ref_without_end` is gone: one reader. `LicenseRef-a-;;`, `LicenseRef-a-?` and `MIT WITH AdditionRef-x;;` stay refused, and the dot or dash of the ID is not named in the reason (`LicenseRef-a.;;` is `U+003B`, as it was `U+002E U+003B`) | A second function in `resolveleaf` per ending; widen `trim_end_mark` to any word | P80 and P132 made the dot an ID character; the dash was the same case. One reader in the module that owns end marks |
| P135 | Small | Whether a mark stands inside the quote marks | `dropguard.ends_in_mark`: the text ends in `. , ; :` or an ellipsis, white space and closing brackets after it left out, and a dot that ends a `LicenseRef-*` is no mark. `"(MIT;)".`, `"(MIT.)".`, `"[MIT,]";` and `"LicenseRef-a.;".` are refused (no reason: the quote marks reach no guard that names them); `"LicenseRef-a.".` and `"LicenseRef-a.";` read as `LicenseRef-a.`. The check `unquote(text) is not None` in `ended_quote` was unreachable (the text ends in a mark, so the mark inside a core makes `unquote` refuse) and is removed | Ask `trim_end_mark` of the inside (it answers `None` for none and for two) | The question is "is there a mark", not "is there exactly one". Reason for these values: a 0.8 follow-up |
| P136 | Small | Dashes and underscores joined to the end, in more shapes | `dropguard.joined_marks` (replaces `end_dashes`) names the dashes and underscores of the marks after a prose form, and of the body after a `+`, an exception or a `LicenseRef-*`: `MIT+-?`, `MIT+-!`, `MIT+ -;`, `MIT+_`, `MIT License-.` and `MIT License_` are refused with the marks in the order they stand (`U+002D U+003F`; `MIT+?-` is `U+003F U+002D`). The dash or dot that ends a `LicenseRef-*` is the ID's (`LicenseRef-a-?` names `U+003F` only). `MIT-`, `MIT_`, `GPL-2.0-only-`, `Apache-2.0--`, `BSD-2-Clause-` and `BSD 3-Clause-` read as before | Dashes only; refuse every shape | The same cause as P131: no loose ID ran, so the mark is dropped. Underscore is a separator for a loose ID as the dash is |
| P137 | Small | Dash endings left silent | Pinned as they are, each needs a path of its own (0.8): `(MIT)-` and `(MIT+)-` (a bracket in the middle is read by no leaf reader), `License :: OSI Approved :: MIT License-` (the trove path reads a name only), `The MIT License (MIT)-` and `MIT License (MIT)-` (no bracket at the end), `LicenseRef-a+-` (malformed, no expression to name), `MIT+ WITH X-` (X names no exception) | A new reader per shape | The brief forbids a new reader; none of these reads on `main` |
| P140 | Contract | F1: the flags of a compound with an operand that cannot be judged (`MIT OR LicenseRef-x`) | None (`IS_OSI_APPROVED=`, JSON `null`, exit 1) whenever any operand cannot be judged, an `OR` with a judged true operand included (`licenseid.exprflags`) | Kleene logic (`MIT OR LicenseRef-x` true, `0BSD AND LicenseRef-x` false) | The maintainer's rule says None "when an operand cannot be judged"; the narrow answer, easy to relax to Kleene later |
| P141 | Contract | F1: `--id` with a compound for `is-*` | Still refused (exit 2, `pass one license ID`); a compound is judged from a tag, a field or a file (`is-osi --text 'SPDX-License-Identifier: MIT OR ISC'`) | Allow it for `is-*` only | One reader of `--id` (`is_simple_expression`) for `detect` and `is-*`; widening it again was rejected before (AGENTS.md: `MIT OR Apache-2.0` declares neither licence) |
| P142 | Contract | F1: what `LicenseDetector.is_osi()`/`is_fsf()` return | `bool \| None`: the top match's flag, None when it cannot be judged, False when no licence is found (as the CLI's `false` for no licence) | False for both | The API says what the CLI says; None is the no-false-no answer |
| P143 | Contract | F2: what "on the SPDX License List" is judged against | The rows of the database read (the List licenseid installed): every licence ID a row of `licenses`, every exception a row of `exceptions`; a deprecated ID is on the List; `LicenseRef-*`, `DocumentRef-*:LicenseRef-*` are not | `py-spdx-license`'s own list (`UnknownId`) | One List per answer, the one `lists` names; the library's list can be older or newer than the database |
| P144 | Contract | F1: the synthetic `X WITH Font-exception-2.0` candidate of the text path | Takes `X`'s flags and is on the List only when `X` is (it said `false`, `true`) | Leave it | The WITH rule of F1 in its one other place |
| P145 | Contract | F3: where a bare deprecated ID narrowed to `-only` is caught | One check, `looseid.narrowed_ids(value, reading)`, in `markers.resolve_license_value`, the reader of every declared value (an argument or text that is one expression, `--id`, a tag, a manifest field): not exact, `WARNING: <subject>: variant not stated: <value>; using <reading>`, in a compound too (`MIT OR GPL-2.0`). `looseid.narrowed` drops the "written as is" exemption. `--id` also reads a loose ID (`match_version_key`, then `loose_with`), never a name | A check per caller; exempt the tag | Maintainer rule (guess narrow, mark not exact, warn; one shared check); a tag declaring `GPL-2.0` is the same guess |
| P146 | Contract | C11: the subject of `variant not stated` | `input`, for `detect` and `is-*` and the API alike (replaces P107): the subject names the thing affected, never a command; `detect` leaves the subject list | Keep `detect:` for `detect` only | One rule for every line |
| P147 | Contract | P5: the reasons of the refusals no reader explained | `resolvereason.no_reading` once every reader has declined: `empty`, `too long: N characters`, `special value: NONE` or `NOASSERTION` (case-sensitive, as SPDX writes them: `none` is `not found: none`), `exception not found: Y` (only when the licence half reads), else `not found: <value>` (one line, cut at 60, P61); the leaf's own: `qualifier stated twice: <leaf>`, `qualifier on a reference: <leaf>`, `plus after a bracket: <leaf>`. Each refused operand gets one too. A compound's reason is its first refused operand's own when it has one (P29), so `MIT OR GPL-2.0-only+` says `qualifier stated twice: GPL-2.0-only+` (was `operand not resolved: ...`). The steps of a refusal with no reader's reason are still not kept (P11) | A reason only where a reader knows one | The maintainer's rule: a reason for every refusal. Sample guard: 220 values gain a reason, no expression, category, step or trust moved (`resolver_changes_contract.py`) |

Follow-ups left for 0.8:

- T10b: `json_line` of a `match()` result for a value with a lone
  surrogate (the API answers `lone surrogate`) raises
  `rfc8785.CanonicalizationError`; the CLI refuses such a value first.

- T8b: a list inside a part is not split again, so its operand says `not an
  SPDX operator: ;` (P85); ~~`MIT+-`, `MIT+--` and `MIT License--` are
  silent~~ (done, P131); ~~`LicenseRef-a.;` is refused though P80 calls the
  dot an ID character~~ (done, P132);
  quote marks after a `+` are not read; split `resolveleaf.py` (489 lines
  after P134; the limit is about 500) on its next addition.

- Marks inside the grant phrase (`GPLv2 or any *later version`) are read
  (shared with `match`); ~~`"MIT".` and `"MIT",` are
  refused while `MIT,"` is read~~ (done, P133).
- A compound of prose names (`Apache License 2.0 OR MIT`) is not split (P43);
  `W3C SOFTWARE NOTICE AND LICENSE` still gets
  `operand not resolved: W3C SOFTWARE NOTICE`.
- `<name> License N` for a List name (P68).
- A dropped word that is no line marker (`MIT draft`) is not a drop: it
  names no licence.

## 7. T6b: reading quoted values

Decision Q12 refused `"MIT"` in T6 (the drop guard names every quote mark) and
left the reading to T6b. The code is `licenseid.quotes.unquote`, called by
`resolver._prepared`; the pairs are `normalize.QUOTE_KIND` (P15 to P21).

### The rule

1. Skip white space at both ends.
2. While the first and last mark are of one kind, remove both (a layer).
3. If one end has a quotation mark (not a prime or a modifier letter, P22)
   and the other none, remove it (unbalanced). Two marks of different
   kinds: stop, read nothing.
4. The rest must be non-empty and hold no mark except an apostrophe between
   two letters or digits. Otherwise the value is as it was.

### Why it asserts nothing the author did not write

A quote delimits a text; it does not qualify it. `"MIT"` and `MIT` mean the
same in JSON, TOML and YAML strings, Markdown and prose, so taking off the
marks that enclose the whole value drops no word, no doubt and no condition:
the trust stays `identity` (`lexical`), as for brackets. The marks that do
qualify are inside: `MIT "or" Apache-2.0`, `GPL "2.0"`, `Apache "2.0"` quote
a word of a longer text, and what the writer meant by it (a term, a
quotation, scare quotes) is unknown. Step 4 keeps them out and the drop guard
refuses them as before. Step 4 also separates a pair that wraps the value
from two quoted words that merely start and end it (`"MIT" or "Apache-2.0"`).
A mark on one end only means the text was typed wrongly or cut; the inside is
still what was written, so it is read, but the answer says so (detail) and
counts as a rule of the resolver (`separator`).

### Sample run

The 10,000-project sample (`sample-2026-10.jsonl`, SPDX 3.29.0), `analyze`
before and after: `unresolved` 1,784 to 1,783, `lexical` 10 to 11, nothing
else moved. Of the 9,998 values, three hold a quote mark:

| Project | Downloads | Value | Now |
| - | - | - | - |
| artifacts-keyring | 843,066 | `"MIT"` | `MIT`, `lexical`, `identity` (T6: refused; 0.6.0: `MIT`, `separator`) |
| proxy-py | 525,301 | `'BSD'` | `unresolved`, as `BSD` is (it names no one licence) |
| redfish | 318,109 | `BSD 3-clause "New" or "Revised License"` | `unresolved`, as before (marks inside) |

The 3.29.0 names with a quote mark: `AMD's plpa_map.c License`, `Do What The
F*ck You Want To But It's Not My Fault Public License` (apostrophes) and the
names of `BSD-2-Clause`, `BSD-3-Clause` and `BSD-4-Clause` (double marks
inside). None starts or ends with a mark; a test reads the List fixtures.
`EXPECTED_CHANGES` lists one value, `"MIT"`; the parity corpus (140 values)
and the PyPI fixture (462) move nowhere else.

### For T7 (compounds)

`unquote` takes the whole value. T7 reads each operand as a value of its own
and should call `unquote` on an operand too, after the whole-value call:
`"MIT OR Apache-2.0"` is then unquoted once, and `MIT OR "Apache-2.0"` per
operand. A pinned gap: the parser accepts quotes around an operand, so
`"MIT" or "Apache-2.0"` and `MIT OR "Apache-2.0"` are labelled `expression`
today (`tests/test_resolver_quotes.py`, `BUG (T7)`); T7 must refuse a mark
inside an expression or unquote each operand, not read two quoted words as
one text.

### Follow-ups found in T6b

- T7: the quoted operand above.
- T8: `"MIT".` and `"MIT",` are refused but `MIT,"` and `"MIT,` are read
  (the comma ends the value, or is inside it); trailing punctuation is T8's.
- Not read (no pair, or a mark `QUOTE_KIND` does not hold): fullwidth
  `＂MIT＂`, CJK `「MIT」`, `['MIT']`, an escaped `\"MIT\"`, `"MIT" License`, and
  a quoted listed name with inner marks.
- R7: `markers.py` (lines 66 and 78) reads quotes its own way on the match
  path; it should call `licenseid.quotes`.
- There is no length cap before `unquote`: it is linear and `_lookup` still
  caps the result at 2,000 characters, as before (not a regression).
- R7: `licenseid match '"MIT"'` still answers by the Tier 0 loose ID, as for
  T6's follow-up.
- A quoted listed name that holds marks (`"BSD 3-Clause "New" or "Revised"
  License"`) and deeper alternation of brackets and quotes are not read.

## 8. R7 combined review (2026-10-29)

Verdict: no blocker. An independent review of `main` at a5400a7 found three
small defects (S1 to S3) and a list for 0.8. The S fixes are made on
`resolver-0.7-r7-fixes`.

### Measured

- 24,773 values, database against packaged list: 0 differ.
- `auto` on 13 database states: answers as designed.
- 27,767 values for the operand property: every operand span equal to its
  text in the input; 97 operands differ from the same text alone, all with a
  stray quote (P23, by design).
- Time per value in ms, 0.7.0 against 0.6.0 (values of three kinds):

| Source | 0.7.0 | 0.6.0 |
| --- | --- | --- |
| `source=database` | 0.9 / 1.0-1.2 / 2.8 | 0.9 / 0.9 / 1.3-1.5 |
| `source=packaged` | 0.11 / 0.13 / 1.5 | |
| `auto` | 11.6-12.3 / 20.8-23.8 / 17.0-17.8 | 9.9-10.1 / 19.1-19.4 / 10.0-10.4 |

- CLI matrix: NEW=0, FIXED=0.

### Fixed here

- S1: `operand of several words: <leaf>` for a leaf that resolves alone but is
  no operand (P62); `operand not resolved` only for one that does not.
- S2: every detail built from input in a `reason` is one line, cut to 60
  characters (P61).
- S3: README and `Operand` say one-word operands, and per operand only a
  balanced pair of quotes; README says `resolve()` orders operands
  differently from `match`.
- P35 decided by the maintainer (`MIT or later` is `MIT+`); P20 and P31
  wording made to match the code.

### For 0.8

1. Cache the `auto` choice per file stamp (`listsource.py:93-121`; 6
   connections per value).
2. Route `match`'s tag and declared-value path through `resolve()`, and
   `markers.py:66,78` through `licenseid.quotes`. The tag path canonicalises
   with `identifiers._canonicalize_expression`, not `exprcanon`. Tier 0 has
   no drop guard: 45 synthetic values are refused by `resolve` but EXACT by
   `match` (0 in the sample); `SPDX-License-Identifier: MIT OR Apache2`
   answers EXACT.
3. A dropped-word guard for `normalize_text` (`REM MIT`, `1. MIT`, `MIT -`).
4. Reasons for refusals that have none: a mark after `+`, after an
   exception or after a `LicenseRef` (`GPL-2.0+?`; `resolveleaf.py:348`
   returns before the guard).
5. Decide line breaks (`MIT\nOR ISC` reads, with a whitespace step) and
   ~~non-string input (`resolve(None)`, bytes, int raise `AttributeError`,
   though the docstring says it never raises on content)~~ (done, P130).
6. Decided, not open: `MIT+` alone is `exact`, and `MIT or later` is `MIT+`
   with `stated_qualifier` (P35); SISSL is decided too (stated SISSL, P52, on
   the T9 branch).
7. Several-word operands (T8, P43).
8. The known T6, T6b and T7 follow-ups above.
9. White space inside a listed name: `resolve("Apache\tLicense 2.0")` is
   unresolved while `Apache\n2.0` resolves; folding in a reason can hide it.
10. `match` from a tag still answers `MIT OR later` for `MIT or later`: P35
    widens the gap between `match` and `resolve` (item 2 covers it).
