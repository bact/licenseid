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
