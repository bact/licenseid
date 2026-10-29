---
Created: 2026-10-28
Last-Modified: 2026-10-29
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

Follow-ups left for 0.8:

- Marks inside the grant phrase (`GPLv2 or any *later version`) are read
  (shared with `match`); `"MIT".` and `"MIT",` are
  refused while `MIT,"` is read.
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
   non-string input (`resolve(None)`, bytes, int raise `AttributeError`,
   though the docstring says it never raises on content).
6. Decided, not open: `MIT+` alone is `exact`, and `MIT or later` is `MIT+`
   with `stated_qualifier` (P35); SISSL is decided too (stated SISSL, P52, on
   the T9 branch).
7. Several-word operands (T8, P43).
8. The known T6, T6b and T7 follow-ups above.
9. White space inside a listed name: `resolve("Apache\tLicense 2.0")` is
   unresolved while `Apache\n2.0` resolves; folding in a reason can hide it.
10. `match` from a tag still answers `MIT OR later` for `MIT or later`: P35
    widens the gap between `match` and `resolve` (item 2 covers it).
