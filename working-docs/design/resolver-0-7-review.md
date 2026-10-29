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
| P20 | T6b | Where it runs | In `resolve()`, once per whole value: trim, `unquote`, `brackets`, and `unquote` again only if the brackets came off (`("MIT")`). `"(MIT)"` and `("MIT")` read; deeper alternation (`("(MIT)")`) does not | Only before the brackets; a loop until nothing changes | One reader of the value before the leaf, so `+`, `WITH` and grants inside compose; a loop invites a quadratic path |
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
| P31 | T7 | A mark used as an operator | Reason `not an SPDX operator: /` (also `|`, `&`, `;`, `,`) only when every part is one ID word (`MIT/Apache-2.0`, `zlib/libpng`); still `unresolved` | Read `/` as OR; give the reason for any text with a mark | `zlib/libpng` is one licence; a URL or prose has commas and slashes |
| P32 | T7 | New reasons | `too many operators`, `too deeply nested` (the caps of `identifiers`, 150 each), `mismatched brackets`, `parse failed: <the parser's message>`, the placeholders shown as the leaf texts | A generic `not an expression` | Say what the parser said; the caps keep deep nesting away from it |
| P33 | T7 | When `components` lists the parser | When it read the answer: a compound, or a refusal with its `parse failed` message; never for a single value or a value no reader claims | Whenever it ran; always | The answer rests on it only then |
| P34 | T7 | `GPL-2.0 +` (a `+` after a space) inside a compound | Read as it is alone (`GPL-2.0-or-later`, with a `whitespace` step) | Refused in a compound | An operand reads as the same text alone; found by the adversarial tests |
| P35 | T7 | A grant on an ID with no `-or-later` form (`MIT or later`) | Amended after review: `X+`, `stated_qualifier`, only when the ID ends in a version (`-\d+(\.\d+)*`: `Apache 2.0 or later` is `Apache-2.0+`, `MPL-1.1 or later` is `MPL-1.1+`); an ID with no version (`MIT`, `BSD-3-Clause`, whose 3 counts clauses, `StandardML-NJ`, a `LicenseRef-*`) stays unresolved, as in 0.6.0. First built as `+` for any ID (`MIT or later` was `MIT+`) | `+` for any ID; unresolved for every ID | The `+` operator means this version or a later one: an ID with no version has no later version to grant |
| P36 | T7 | The hyphenated grant after a version (`GPL-2.0 or-later`) | A grant: `stated_qualifier` (was `separator` through the version key); `-or-later` after an ID is still part of it | Leave it to the version key | One reader of the grant (`classify.OR_LATER_PHRASE`), and the step says a grant was stated |
| P37 | T7 | Case of `LicenseRef-*` when deduplicating | Case-sensitive: `LicenseRef-a OR licenseref-a` keeps both; the sort is case-folded, then as is | Fold the case | SPDX leaves the idstring of a reference to its author; folding would assert they are one |
| P38 | T7 | What counts as an operator | `AND` and `OR` with white space, a bracket or an end on both sides, in any case; `WITH` stays inside its leaf | Any `or` between words | `MIT"OR"ISC` and `and_mask` hold no operator |
| P39 | T7 | A grant in brackets inside a compound (`GPL-2.0 (or later) OR MIT`) | Read with its licence, as alone | Refuse it | The same reader as a single value |
| P40 | T7 | The component URL of the parser | `https://pypi.org/project/py-spdx-license/<version>/`, its purl `pkg:pypi/py-spdx-license@<version>`, the installed version | The repository URL | The released artefact, as the resolver names its own release |
| P41 | T7 | A grant after `WITH` (`GPL-2.0 WITH X or later`) | Moved to the licence: `GPL-2.0-or-later WITH X`, the step `from` the moved text | Refuse; give it to the exception | An exception takes no version grant |
| P42 | T7 | A lower-case operator and an operand that names nothing (`GPL-3.0 or higher`, `proprietary and confidential`, `MIT or Foo`) | No compound: unresolved with no reason and one operand, the whole value, unless the operand has a reason of its own (a dropped mark) or is `malformed` | `operand not resolved: higher` | Never assert what the author did not write: a lower-case `or` between words is prose as often as an operator |
| P43 | T7 | A leaf of several words (`Apache License 2.0 OR MIT`, `W3C Software and Document Notice License`) | No compound, whatever the operator case; left to the prose rules of T8 and T9, which read the whole value first | `operand not resolved: Apache License 2.0` | The same reason; and T8 can then read such operands without undoing a split |
| P44 | T7 | Sort order of the leaves | IDs, then `LicenseRef-*`/`DocumentRef-*`, then `X WITH Y`, each case-folded (`MirOS` before `MIT`); groups after the leaves by rendered text (Q19, Q24). Pitloom 0.21.1 sorts case-sensitively and puts groups first: 4 parity rows differ in order only | Pitloom's order | Q24; a fixed key over the resolved leaves, so the order is the same from every spelling |

### Follow-ups found in T7

Not fixed in T7.

- T8: a compound of prose names (`Apache License 2.0 OR MIT`) is not split
  (P43); once T8 reads names, it may read such operands.
- T8: an all-capitals prose name with `AND` (`W3C SOFTWARE NOTICE AND
  LICENSE`) would be read as a compound if its words were IDs; none are.
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
