---
Created: 2026-10-28
Last-Modified: 2026-10-29
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Plan for the 0.7.0 resolver

Status: T0 to T4 built (#107, #108, #110, #112); T5 onwards unbuilt.
Drafted on 2026-10-28 by an Opus planning agent from the code of both
repositories, then edited. The maintainer confirmed every answer of section
8 on 2026-10-28. A review of T0 to T4 against T5 to T7, and decisions Q10 to
Q23, are in [`resolver-0-7-review.md`](resolver-0-7-review.md); this plan is
updated to match.

See also: [`expression-resolution.md`](expression-resolution.md) (the design
this executes), [`resolver-0-7-evidence.md`](resolver-0-7-evidence.md) (the
data), `../../tools/pypi_licence_sample/README.md` (the measuring tool),
[`../implementation/declared-value-resolver.md`](../implementation/declared-value-resolver.md)
(what 0.6.0 built).

Goal: `licenseid.resolve()` answers for any single-line declared licence value,
compound or not, with `py-spdx-license` for the grammar, so a consumer such as
Pitloom needs no second implementation. It works with no database, from the
packaged bundle.

How to read this plan: sections 1 to 9 say *what* and *why*; section 10 is the
task list with a suggested model and effort for each task; section 11 is a
guide for the agent that does a task (map, rules, traps, snippets). Names are
as read on 2026-10-28; `grep` before relying on one.

## 1. Findings that change the design

Checked against the code, the `py-spdx-license` 0.0.1 source, and read-only
probes of 0.6.0 on the 3.29.0 database.

| # | Finding | Consequence |
| - | - | - |
| F1 | The library's sort key includes the node class name (`LicenseId`, `LicenseRef`, `UnknownId`). `Foo-1 OR MIT` sorts to `MIT OR Foo-1`, and an id newer than the library's bundled list sorts after every id it knows. | Its `sort()` order depends on its snapshot, not on licenseid's list. Design goal 2 fails. |
| F2 | `WithOp` needs an `ExceptionId` from the library's own list. An unknown exception or an `AdditionRef-` does not parse, even with `allow_unknown=True`. | The same cause as the `+` gap (upstream issue 1). Design 4.6 does not say it. |
| F3 | `sort()` raises `TypeError` on repeats in a flat chain, and also with no literal repeat: `(A AND B) OR (B AND A)`. | Pitloom's flat-chain de-duplication does not cover nested repeats. |
| F4 | `normalize_identifier` skips the sort above 40 operators and on any failure. | "It sorts" is best effort only. |
| F5 | A database keeps only licences that have a text, plus deprecated ones (`records._license_records`). | An in-memory index must apply the same rule, or the answers with and without a database drift on a later list. |
| F6 | Design 4.7 confuses a lone surrogate with U+FFFD. Both are read today: `MIT\udcff` and `MIT�` give `MIT` (`separator`), and so do `Apache 2.0!`, `Apache 2.0?` and an en dash. The surrogate case also leaves an unencodable `input`. | Refuse both (rule R0b). |
| F7 | Goal 2 ("no dependence on whether `update` ran") conflicts with 4.5 ("the database wins when both exist"). | Reword goal 2: the answer depends on the licenseid version and the list version, both recorded in the result. Add a `source=` pin. |
| F8 | The warning a reviewer sees in Pitloom's Hatchling hook comes from licence-**text** detection (the `LICENSE*` second opinion), not from declared values. A declared `Apache-2.0` passes Pitloom's local strict parse and never reaches `resolve()`. | Reading declared values with no database (4.5) does not silence it alone. Pitloom must change its warning policy too (section 7). |
| F9 | The "42-value table" is in neither repository; only its 13 gaps and 26 synthetic values survive in a scratch script. | Task T0 rebuilds the corpus and commits it as a fixture. |
| F10 | `resolver.py` is 443 lines; compounds, the list fallback, prose rules, the trove table and the drop step will not fit under the 800-line limit, and the complexity ratchets must not rise. | The module split in section 3. |
| F11 | The packaged bundle is 0.98 MB gzipped (740 licences, 86 exceptions). `SpdxData.from_bundle` takes about 50 ms; importing `licenseid` about 70 ms. | Loading once per process is cheap. Drop the texts after indexing (about 5 MiB less resident). |

## 2. Scope and non-goals

In 0.7.0:

- Compounds: `AND`, `OR`, `WITH`, brackets, `+`, `LicenseRef-`/`DocumentRef-`,
  operators in any case.
- No database: the packaged bundle, in memory.
- New result keys that say who did what, per operand.
- A guard against reading away a dropped character.
- Three lexical groups measured in the evidence: prose forms of one id, the
  trove classifier table, the trove path and an agreeing parenthesis.

Non-goals: fuzzy matching inside an expression; an operand of several words
(`Apache License 2.0 OR MIT`: `unresolved` with a `reason`; 62 of the 63
compounds in the sample are well-formed SPDX); bare family names (`BSD`,
`GPL`, `Apache`); aliases outside the List (`Expat`, `PSFL`); text detection
without a database (open question Q5); a `licenseid resolve` command (if added,
every rule of "CLI output" in `AGENTS.md` applies, and `tools.cli_matrix`).

## 3. Module changes

Each file stays under about 450 lines; no ceiling is raised.

| File | Contents |
| - | - |
| `listlookup.py` (built, T3, 115 lines) | `ListLookup`, a Protocol of 7 methods (`reading`, `get_license_details`, `get_exception_details`, `get_names_by_key`, `get_active_ids_by_name`, `get_deprecated_mappings`, `get_metadata`), and `fold_case`. Typed to it: `resolver`, `resolveleaf`, `looseid`, `versionkey`, `identifiers` (`normalize_identifier`, `with_expression_details`, `flag_source`). T4b narrows the return types to the fields the chain reads; `with_expression_details` and `flag_source` go back to `LicenseDatabase` (they read the OSI and FSF flags). |
| `listrules.py` (built, T2, 130 lines) | `is_deprecated`, `active_ids`, `active_ids_by_name`, `kept`, `superseded_license`, `kept_licenses` (kept entries with successor), `active_exceptions_by_name`, `exception_successor`. `records.py` calls them; `BUILD_VERSION` stays 2. This is how F5 cannot drift. |
| `listindex.py` (new, T5) | `ListIndex(SpdxData)` implements `ListLookup` from `listrules.kept_licenses`, `exception_successor` and `normalize_text` (IDs and names only, never the texts: `word_count` alone costs 1.2 s). `get_active_ids_by_name` from the kept rows only. `reading()` is a null context. `get_metadata()`: `license_list_version`, `release_date` (`""` if none). `packaged_index()` calls `spdxdata.packaged_bundle()` through the module, caches under a lock with a reset for tests, returns `None` with no bundle. |
| `resolveleaf.py` (built, T4, 275 lines) | `Found`; `read_leaf(db, text, found) -> bool`: False names none; True with `found.category` set is `malformed` or `unresolved`. Gate: `MAX_KEY_INPUT` on the whole text (per `WITH` half from T7, Q16). Private `_with`, `_exception`, `_one`, `_plus`, `_single`, `_qualified`, `_grant`, `_base`, `_spelling`, `_deprecation`. T6 adds `Found.reason`; T7 adds a public `category_of(found)` (from `resolver._category`). |
| `dropguard.py` (new, stdlib, T6) | `dropped(text) -> str`: the characters neither alphanumeric nor allowed (white space, `-`, `_`, `.`, Unicode `Pd`, one trailing `,`). Called in `resolveleaf._base` after the loose read, before `_spelling`; a refusal makes `read_leaf` return True, `unresolved`, a `drop` step with `applied: false` (Q13) and reason `character dropped: '?'`. Not on `listed_name` (`Yahoo! Public License v1.0` keeps its `!`), not on the grant tail (`looseid._RE_GRANT_TAIL`). Quotes are refused (Q12). Surrogates are refused earlier, in `resolver` (T4b). |
| `proseforms.py` (new, stdlib) | Rules P1 to P3 as an ordered table of `(kind, compiled regex, replacement)`. The reduced text goes back through `resolveleaf` and must resolve by id, listed name or loose id. Every regex is timed on `"x" + " " * N`. |
| `trovenames.py` (new, data) | The `License ::` table: name to `(ids, reading)` with `reading` one of `stated`, `assumed`, `none`; `strip_trove_path`. About 90 entries, checked against the `trove-classifiers` package (a test dependency only). Holds the named special case Q23 (`GNU Lesser General Public License v2 (LGPLv2)` as `LGPL-2.0`). |
| `exprcanon.py` (new) | See D1 below. |
| `resolvecompound.py` (new) | Calls `resolveleaf` per leaf. All-or-nothing acceptance; the category is the weakest operand's; builds `operands` and `reason`; tells `malformed` (an operator or bracket and a resolved operand, but the grammar refuses it) from `unresolved`. Must handle `MIT OR GPL-2.0-only+` (`malformed` today). |
| `resolver.py` (190 lines after T4) | Entry point: `resolve(value, db=None, *, source="auto")` chooses the list (4.5, Q4, Q10, Q11), runs the early refusals (empty, over 2000, Cc and Cf, Cs from T4b), tries one licence (`read_leaf`), then a compound, then the trove table, then prose (Q18, Q22), then `malformed`. Builds `Resolution`, `components`, `lists`. T7 removes `_expression_category`, `_is_expression`, `_RE_TOKEN`, `_RE_IDLIKE`, `_RE_SQUARE`. At most 250 lines. |
| `resolvertypes.py` (changed) | New keys, categories, kinds, trust levels (section 4). |
| `identifiers.py` (747 lines) | Type hints only. Do not add to it. `normalize_identifier` keeps its narrowing for `match()`. |
| `tools/pypi_licence_sample/` | `analyze --source packaged` (no database), `--json out` and `--compare base.json` for before and after per rule. |

**D1, the canonical order.** `py-spdx-license` parses (grammar, precedence);
licenseid sorts and de-duplicates the parsed tree itself (about 60 lines):

1. Split the value into leaves with spans, in one linear pass.
2. Resolve each leaf; replace each distinct resolved leaf with a placeholder
   `LicenseRef-licenseid-leaf-NNNN`, numbered by the leaf's sort key.
3. Parse the skeleton with `identifiers.parse_expression`. The library then
   sees only `AND`, `OR`, brackets and `LicenseRef-`, so F1, F2, F3 and the
   `+`/`AdditionRef-` gap do not arise.
4. Flatten same-operator chains, remove repeats, sort, render with precedence
   brackets. Emit the steps `operator_case`, `brackets`, `reorder`, `dedupe`.

The leaf key is `(rank, text)` with ranks: listed id 0, `LicenseRef-` or
`DocumentRef-` 1, `X WITH Y` 2; `text` compares case-folded, then ordinally
(Q24). That reproduces the library's order for every
shape among today's 29 agreements (`MIT OR LicenseRef-x`). The order of a
`WITH` leaf against an `OR` group (`(A OR B) AND X WITH Y`) can differ from the
library's; pin it in a test and list it in the parity table. Why not call
`sort()` with a workaround: this removes F1 and F3 instead of patching them,
costs n log n per chain (the library's `sort()` blows up past about 150
operands), and the drift guard still checks that the library parses every
answer. Needs the maintainer (Q1).

## 4. Public API changes

| Item | 0.6.0 | 0.7.0 | Kind |
| - | - | - | - |
| Signature | `resolve(value, db=None)` | `resolve(value, db=None, *, source="auto")`, `source` one of `auto`, `database`, `packaged` | additive |
| No database | raises `DatabaseNotReadyError` | `auto` uses the packaged index (with a database, the newer list version wins, a tie goes to the database: Q4); raises only with no bundle either (editable install, `LICENSEID_BUNDLE=skip`), message unchanged | behaviour |
| Unusable default database | raises | `auto`: `WARNING: database: <condition>: <detail>; using packaged data v3.29.0` (existing ACTION vocabulary), then the packaged index. An explicit `db=` or `source="database"` still raises. | behaviour |
| `schema` | none | `2` | additive |
| `operands` | none | one per leaf: `text`, `span` (`[start, end)` in code points of the raw `input`), `expression`, `category`, `trust`, `steps`, `expansions`, `candidates`, `reason`. A single value is one operand; a value that cannot be split gives `[]`. | additive |
| `components` | none | `[{name: "py-spdx-license", version, url, purl}]` whenever its parser ran, else `[]` | additive |
| `reason` | none | one line, `CONDITION[: DETAIL]`: `operand not resolved: Foo`, `parse failed: ...`, `not an SPDX operator: /`, `character dropped: ?`, `lone surrogate`, `too many operators`, `family of licences: BSD`; `None` with an expression | additive |
| `steps` (compound) | n/a | operand steps in input order, then whole-value steps | n/a |
| `candidates` (compound) | n/a | `[]`; candidates are per operand | n/a |
| `Step.by` | none | always present, `""` when licenseid did it. With D1 nothing sets it in 0.7.0. | additive |
| `Step.list` | `spdx-license-list` or `""` | may be `pypi-trove-classifiers` | additive |
| `ListInfo.source` | none | `database` or `packaged`; with a usable database only the database entry is listed | additive |
| `lists` | one SPDX entry | plus a `pypi-trove-classifiers` entry (`id_authority: false`, `provides: ["names"]`) when a trove step ran | additive |
| New step kinds | n/a | `operator_case`, `reorder`, `dedupe`, `prose_words`, `trailing_name`, `trove_path`, `trove_name`; `brackets` also inside an expression; `assumed_usage` (an expansion, `applied: false`) | additive |
| New categories | n/a | `prose_form` and `trove_name` (trust `resolver_rule`, after `version_spelling`); `assumed_usage` (trust `none`, no expression, after `assumed_only`) | additive |
| `expression` category | a compound, no expression | **removed**: a compound gets its weakest operand's category (`lexical` when only canonicalised), or `malformed`/`unresolved` | **breaking** |
| `(MIT`, `MIT AND` | `unresolved` | `malformed` | breaking (minor) |

Release as a minor version; `AGENTS.md` says no backward compatibility is
needed yet. `resolver.name` stays `licenseid` (design 4.4). Removing
`expression` drops it from `Category`, `CATEGORY_ORDER` and `TRUST`. Pitloom's
`_ACCEPTED` is an allow-list without it, so nothing it accepts today is lost.
The CHANGELOG gets one breaking bullet with a one-line migration: a compound
now has a category of its own; read `operands`.

## 5. Rule inventory, ranked by the evidence

Numbers are estimates from the evidence until T0 re-measures them. Every rule
PR commits the measured counts, the list of newly resolved values, and an empty
list of values whose answer changed from 0.6.0.

| Rank | Rule | Group (projects) | Correctness argument | Category |
| - | - | - | - | - |
| R0 | Compounds | `expression` 63, about 6.6 G downloads | Commutativity, idempotence and associativity keep meaning. Each operand gets the proof of a single value. One rejected operand rejects the value. | weakest operand's |
| R0b | Drop guard | takes some of today's 136 `separator` back to unresolved (expect under 5) | A discarded `?`, `!`, `*` or U+FFFD carries the author's doubt or corruption. Refusing asserts nothing. | `unresolved` |
| P1 | Trailing word `license`/`licence` after a value that resolves (`Apache-2.0 license`, `BSD 3-Clause License`) | prose 140, about 40 | The word names the kind of document, not the licence. The rest must still resolve uniquely through the existing path. `BSD License` reduces to `BSD`, which does not resolve, so it stays unresolved. | `prose_form` |
| P2 | `<name> License[,] (Version\|v) N` becomes `<name> N` (`Apache License, Version 2.0`) | prose, about 43 | How the licence text titles itself. "Version" and the comma are syntax. The result must resolve through the loose key to the one id with that number. | `prose_form` |
| P3 | A leading `The ` | about 5 | An article; allowed only with P1, P2 or a listed name. | `prose_form` |
| T1 | Full trove path `License :: OSI Approved :: X`: strip the prefix, read `X` | 8 | The path is the classifier's syntax. `X` must resolve by its own rule. `OSI Approved` alone stays unresolved (a category). | `X`'s, plus a `trove_path` step |
| T2 | Trove names that state one licence (`ISC License (ISCL)`, `Mozilla Public License 2.0 (MPL 2.0)`, `GNU General Public License v3 or later (GPLv3+)`, `Eclipse Public License 2.0 (EPL-2.0)`, ...) | trove 224, about 35 | A closed vocabulary; each entry names its version (and grant), checked against `trove-classifiers`. A deprecated bare id follows the existing policy (`assumed_only`). | `trove_name` |
| T3 | An agreeing trailing parenthesis: drop `(...)` only if the head and the inside resolve to the same expression (`MIT License (MIT)`) | 16 | Two independent readings agree, so nothing is chosen. If they differ, or only one resolves, refuse. | head's, plus `trailing_name` |
| T4 | Trove names that imply one licence only by usage: `Apache Software License` (153) gives candidates `[Apache-2.0]`; `Python Software Foundation License` (14) gives `[PSF-2.0]` | about 167 | A usage convention, not a statement: no version is written. | `assumed_usage`, no expression: **needs Q3** |
| - | `BSD License`, `BSD`, `GPL`, `LGPL`, `Apache` | family 348 | Several licences. | stays `unresolved`, `reason: family of licences` |
| - | `Other/Proprietary License`, `Public Domain`, `NVIDIA Proprietary ...` | about 60 | No SPDX id. | stays `unresolved` |
| - | `Expat license`, `PSF`, `ISCL` | 14 | Not in the List's data (no other names); it would be our own table. | defer |

T4: recommended as `assumed_usage` with no expression and the usual id in
`candidates`, at trust `none`. That keeps the 0.6.0 policy: never assert what
the author did not write. The consumer opts in explicitly.

## 6. Test plan

| Area | Test |
| - | - |
| Characterisation first | 0.6.0 answers on every existing resolver test and the corpus, pinned before the move to `resolveleaf.py`. Known bugs (F6, `Apache 2.0?`) get a `# BUG:` pin, flipped later. |
| Parity table | `tests/fixtures/resolver_parity.tsv`: the rebuilt 42 values (26 synthetic plus the real ones) and the 57 real values of the evidence. Columns: value, Pitloom 0.21.0, 0.6.0, expected 0.7.0, why it changed. The 29 agreements stay; the 13 gaps close as section 3 says; the `WITH`-versus-group order is the one listed exception. |
| PyPI sample | `tests/fixtures/pypi_values_2026-10.tsv`: the distinct short values (value, field, projects); if it nears the size limit keep the unresolved and compound values plus a hash of the rest. Per rule: newly resolved set equals the expected set; changed set is empty. |
| With and without a database | Build an in-memory database from the same shipped bundle (`release_fakes.ship`, `update --source packaged`, `make_memory_db_path`). For every listed id, id in lower case, id with `+`, name, deprecated id, exception and every corpus value: `resolve(v, db)` equals `resolve(v, source="packaged")` with `lists[*].source` masked. |
| Determinism | Repeated in a process; across two subprocesses; operands permuted in the input (`A OR B` and `B OR A` give one expression); `PYTHONHASHSEED` varied. |
| Drift guard | Every accepted expression of the corpora and of Hypothesis-generated compounds parses with `py_spdx_license.parse(..., allow_unknown=True)` once `+` and `WITH` are stripped. Every answer is a fixed point: `resolve(answer)` returns `answer`, category `exact`. Pitloom keeps a copy. |
| Adversarial | Repeated terms (`MIT OR ISC OR MIT OR ISC`, `(A AND B) OR (B AND A)`); depth 149/150/151; 150/151 operators; `WITH` (known, unknown, deprecated, `AdditionRef-`); `+` after an id, a qualifier, a bracket, a `LicenseRef-`; `LicenseRef-`/`DocumentRef-` with `OR`; mixed-case operators; `[ ]`, `{ }`; `MIT/Apache-2.0`; an operator inside a `LicenseRef` name; a lone surrogate; U+FFFD; Cf/Cc characters; NBSP; a 50,000-character payload (short test id). |
| Timing | Each prose and split regex on `"x" + " " * N` and `"OR " * N`, with 10 times headroom for CI on Python 3.10, compared with `main` on distinct values. Budget: under 1 ms per leaf, 50 kB under 0.2 s, first packaged load under 0.5 s. |
| Rule tables | `trovenames` against `trove-classifiers` (every key a real classifier; `stated` entries name their version). `PHRASES` unchanged: no new "or later" reader. |
| Option matrix | `source` (3) by database (usable, missing, invalid, outdated, no home) by bundle (shipped, none): raise, warn plus packaged, or silent. `check_diagnostic_grammar` covers the new warning. Goes in `tests/test_option_matrix.py`. |
| Mutation | Break each rule's guard (unique-resolve, agreeing parenthesis, drop set, all-or-nothing, placeholder numbering) on a copy and rerun; clear `__pycache__` between mutants. |

## 7. Migration and release order

| Phase | Repository and version | Change | Exit criterion |
| - | - | - | - |
| 0 | Pitloom 0.21.1 (before 0.7.0) | Warning policy below | The hook on a project that declares `Apache-2.0`, with no database, prints no `WARNING:` and writes SBOM bytes identical to 0.21.0 apart from provenance |
| 1 | licenseid 0.7.0 | Sections 3 to 6 | Parity, sample before and after, database equivalence all green; CHANGELOG |
| 2 | Pitloom 0.22.0, floor `licenseid>=0.7.0,<0.8` | Below | A before and after sweep of Pitloom's licence corpus and the PyPI fixture lists every changed answer, each explained |
| 3 | Pitloom 0.22.x | One `Resolution-n` per operand; list version and source from `lists`; `Tool: py-spdx-license==Y` from `components` | No `py_spdx_license` import under `src/` |

**Pitloom 0.21.1 (the interim).** Do not have the hook build a database: it
would write about 17 MB into the user's `~/.local/share/licenseid/` from inside
a build, against "honour user intent", and cost seconds per build (measure
before ruling it out for good). Change the level instead: when a declared
licence is present, a missing database costs only the `LICENSE`-file second
opinion, so say it once at INFO (`licenseid database not found: licence file
check skipped; run 'licenseid update --source packaged'`). Keep the WARNING when
no licence is declared, when the database exists but is unusable, or when a
declared value needed licenseid's reading. Route it through
`_database_unusable` so the CLI, library and hook agree; this needs the
missing-versus-unusable distinction from the `DatabaseNotReadyError`
condition. Test every surface.

**Pitloom 0.22.0.**

- `resolve_declared_value` calls `resolve(value)` without the matcher; text
  detection keeps `_matcher()`. The cache key adds `lists[0].source` and
  `version`, beside the database-file stamp.
- `_classify` becomes: the early exits (surrogates, `NOASSERTION`, `NONE`,
  `UNKNOWN`, several lines, over 200 characters), then `resolve()`.
- `_ACCEPTED` adds `prose_form`, `trove_name`, `assumed_only` and
  `deprecated_ambiguous` (recorded as written). The `Deprecated-License-Id`
  note comes from `operands[*].candidates`; the broken-expression warning from
  `reason`.
- Delete about 250 lines: `_strict_parse`, `_canonical_string`, `_gap_term`,
  `_gap_expression`, `_GAP_*`, `_successor_id`, `with_successor_ids`,
  `_replace_deprecated`, `_DEPRECATED_SUCCESSORS`, `_looks_like_expression`,
  `_parse_locally`, `_ambiguous_deprecated_ids`, `_FOLDABLE` and the
  `py_spdx_license` imports. `py-spdx-license` moves to the test group.
- Announce: `StandardML-NJ` becomes `SMLNJ`; compounds with a respelt operand
  resolve, in canonical order; `Apache License, Version 2.0` becomes
  `Apache-2.0`; classifier names covered by T2 become ids; hook builds with no
  database still read declared values.

**What to tell the reviewer who reported the hook warning.** (1) A declared
SPDX id was never affected: the warning comes from the `LICENSE`-file second
opinion, which needs the text database. (2) Today, run
`uvx licenseid update --source packaged` (offline) before the build. (3) 0.21.1
lowers it to INFO when a licence is declared. (4) With licenseid 0.7.0,
declared values are read with no database, and the answer records its list
version and source.

## 8. Open questions for the maintainer

| # | Question | Recommendation |
| - | - | - |
| Q1 | Canonicalise with our own code (D1) or `sort()` plus a workaround? | **Decided: our own code** over the library's parse; report the `TypeError` and the class-name key upstream with a reproducer. |
| Q2 | Remove the `expression` category now or keep it a release? | **Decided: remove** (alpha, one consumer, its allow-list lacks it). |
| Q3 | Policy for T4 (assumed trove readings) | `assumed_usage`, trust `none`, no expression, id in `candidates`. **Decided: defer to 0.8**; T10 is not in 0.7.0. |
| Q4 | Which list wins when both a database and the packaged list exist (F7) | **Decided: the newer SPDX list version wins** (a tie goes to the database); `source=` forces one. Always report source and version in `lists`; Pitloom records them in the SBOM. |
| Q5 | Text detection with no database | **Decided: out of scope** for 0.7.0. Measure an in-memory `LicenseDatabase` built from the bundle; if under 1 s, offer it in 0.8. |
| Q6 | `py-spdx-license` is a 0.0.1 library with one maintainer | **Decided: keep `<0.1`.** With D1 we depend on `parse()` only; the drift guard catches a change. Vendor only if upstream goes stale. |
| Q7 | `StandardML-NJ` to `SMLNJ` inside compounds | **Decided: apply per operand**; keep the old id in the step. |
| Q8 | Spans in the raw input or the stripped text | **Decided: raw `input`**, in code points. |
| Q9 | Several-word operands | **Decided: defer**; `reason: operand not resolved`. |
| R1 | Pinned answers churn when rules change | The sample fixture's "changed set is empty" guard. |
| R2 | Two release trains in lockstep | licenseid first; Pitloom 0.21.1 does not depend on it; 0.22.0 floors on it. |
| Q10-Q24 | Taken after the review of T0 to T4 | **Decided**: see [`resolver-0-7-review.md`](resolver-0-7-review.md) section 4 (tie with an outdated build, silence when no database, quotes, refusal steps, "or later" as a grant token, operands, the key cap, operator case, rule order, group order, `AdditionRef-`, brackets, two trove names, the text order of the sort key). |

## 9. Risks

- The `expression` category goes (breaking). One known consumer.
- `py-spdx-license` stays a single point of grammar failure; mitigated by D1
  and the drift guard.
- A rule that reads more values reads some wrongly. The sample's empty
  "changed set" and the near-miss tests are the defence; a rule with no
  written correctness argument is not merged.

## 10. Tasks, in order (one pull request each)

Model and effort are suggestions for the author; every task is reviewed by a
different agent (Opus for tasks marked high). Escalate a task to the next row
if it turns out to change the result shape, a category or the trust policy.

A task that changes what `resolve()` reads or returns (T5, T6, T6b, T7, T8,
T9) updates, in its own pull request, the `README.md` Features section (the
description of the matching strategy) and the `resolve()` part of its Python
API section; its reviewer checks that they match the behaviour.

| # | Pull request title | Exit criteria | Author | Effort |
| - | - | - | - | - |
| T0 | Tests: rebuild the parity corpus and freeze a PyPI sample | Fixtures committed under 800 lines each; 0.6.0 answers pinned; `# BUG:` pins for F6 and `Apache 2.0?` | Sonnet | medium |
| T1 | Pitloom: say a missing database at INFO when a licence is declared (0.21.1) | Tests on all surfaces; hook with no database prints no `WARNING:`; CHANGELOG | Sonnet | medium |
| T2 | Move the list rules out of `records` | `listrules.py`; `records` output byte-identical on 3.29.0; `BUILD_VERSION` unchanged | Sonnet | medium |
| T3 | Type the resolver on a `ListLookup` protocol | mypy strict clean; no behaviour change | Sonnet | low |
| T4 | Move the single-value lookup to `resolveleaf` | Pure move; characterisation green; `resolver.py` at most 250 lines | Sonnet | medium |
| T4b | Tests and types the next tasks need | Review gaps G1 to G4 and H1 to H8 and the parity corrections of `resolver-0-7-review.md`: Cs refused early, `ListLookup` return types narrowed, `spdxdata` refuses an entry with no `name`, `Answer` with `reason` and step targets, the guard tested on the sample | Sonnet | medium (Opus reviews) |
| T5 | `resolve()` reads the packaged list when there is no database | `listindex.py`; `source=`; warning on an unusable default database; `lists[*].source`; option-matrix axes; equivalence test (with a synthetic bundle for the kept-rows rule, G8); first load under 0.5 s; G5 to G7; Q10, Q11 | **Opus** | **high** |
| T6 | Refuse a value whose dropped characters change it | `dropguard.py`; `reason` added; F6 pins flipped; sample: changed set listed and justified (`"MIT"` included, Q12); Q13 | Sonnet | medium (Opus reviews) |
| T6b | Read quoted values | Quotes in their different forms, balanced or not (Q12), as a rule with a correctness argument and a sample run | Sonnet | medium (Opus reviews) |
| T7 | Read compound expressions in `resolve()` | `exprcanon.py`, `resolvecompound.py`, `operands`, `components`, `reason`, `schema: 2`, `by`, `expression` removed; Q14 to Q21 and G9 to G14; parity, adversarial and timing tests | **Opus** | **high** |
| R7 | Review everything since T0 together, after T7 | One independent review of the whole 0.7.0 change on `main`: the database and packaged index give one answer, an operand reads as the same value alone, the README matches; release blockers listed | **Opus** | **high** |
| T8 | Read prose forms of one id (P1 to P3) | Sample before and after committed; regex timing tests | Sonnet | medium |
| T9 | Read trove classifier names and paths (T1 to T3) | `trovenames.py`; `trove-classifiers` check; `lists` entry; sample before and after | Sonnet | medium |
| T10 | Deferred to 0.8 (Q3): offer assumed trove readings as candidates | `assumed_usage`; Pitloom keeps them as text | **Opus** | **high** |
| T11 | Docs: implementation note, evidence update, CHANGELOG 0.7.0, a final pass on the README Features section | Front-matter dates; a migration line for the breaking bullets; Features describes the 0.7.0 matching strategy (compounds in licenseid's own canonical order, not `py-spdx-license`'s sort; no database needed for `resolve()`) | Haiku or Sonnet | low |
| T12 | Release licenseid 0.7.0 | `release-process.md`; the wheel ships the bundle; `resolve()` checked in a fresh venv with no database (the maintainer tags and publishes) | Sonnet | low |
| T13 | Pitloom: read every declared value through `resolve()` (0.22.0) | Floor bump; about 250 lines deleted; drift guard; before and after sweep reviewed | Sonnet | high (Opus reviews) |
| T14 | Pitloom: per-operand provenance and list version | `Resolution-n` per operand; no `py_spdx_license` in `src/` | Sonnet | medium |

## 11. Guide for the agent that does a task

### 11.1 Map

`src/licenseid/` today (re-check with `grep -n "^def \|^class "`):

| Module | Role | Note |
| - | - | - |
| `resolver.py` (190 lines) | `resolve()`, `_lookup` (trim, outer brackets, refusals), `_unbracketed`, `_expression_category`, `_is_expression`, `_has_control`, `_category`, `_list_info`, `_resolver_info`, `_resolution` | Compounds are not read: `_expression_category` only labels them |
| `resolveleaf.py` (275 lines) | `Found`, `read_leaf`; private `_with`, `_exception`, `_one`, `_plus`, `_single`, `_qualified`, `_grant`, `_base`, `_spelling`, `_deprecation` | One licence; reads the list through `ListLookup` only |
| `listlookup.py`, `listrules.py` | `ListLookup`, `fold_case`; the keep and successor rules | The index uses both; `records.py` uses `listrules` |
| `resolvertypes.py` | `Category`, `Trust`, `CATEGORY_ORDER` (weakest wins), `TRUST`, `LIST_PROVIDES`, `Step`, `step()`, `SPDX_LIST`, `ListInfo`, `Resolution` | Keep the tables in step with `Category` |
| `identifiers.py` (747 lines) | `parse_expression`, `parse_declared`, `normalize_identifier`, `_canonicalize_expression` (cap 40 operators), `leading_expression`, `is_simple_expression` | Near the limit: put new code elsewhere |
| `classify.py` | `OR_LATER_PHRASE`, the one reader of "or later" | Import it |
| `plusoperator.py` | `PLUS_OPERATOR`, `strip_plus_operator`, `plus_after_qualifier`, the one reader of `+` | Import it |
| `looseid.py`, `versionkey.py` | Loose ids (`Apache2`, `GPLv3`); one key per spelling | Lexical rules extend these |
| `spdxdata.py`, `releasesource.py` | Reads the packaged, compact or upstream bundle (stdlib only) | The no-database path builds on `spdxdata` |
| `records.py` | Builds database rows from `listrules`; `_metadata_only_record` and `_prepare_license_record` stay private (flags, popularity) | Not for the index |
| `dbcache.py`, `database.py` | `TableCache`; `LicenseDatabase.reading()` | The in-memory index offers the same lookups |
| `tests/test_resolver.py`, `test_resolver_shapes.py`, `resolver_helpers.py`, `ordering_helpers.PHRASES` | Resolver tests | A new phrasing goes into `PHRASES` |
| `tools/pypi_licence_sample/` | `fetch`, `analyze`, `export`; `answer.Answer` | The acceptance number |
| `tests/resolver_corpus.py`, `test_resolver_parity.py`, `test_resolver_sample.py`, `test_resolver_characterisation.py` | The pinned answers and the guard (`EXPECTED_CHANGES`: value to `(Answer, reason)`) | A rule PR lists every changed answer there |

Consumer, Pitloom (its own repository):
`src/pitloom/extract/_license_resolve.py`
(accepted categories, `_FOLDABLE`, notes), `_license.py` (`resolve_declared_value`,
the answer cache), `_license_classify.py` (`_parse_locally`, `_strict_parse`,
`_gap_expression`, `_canonical_string`, `_DEPRECATED_SUCCESSORS`: the code T13
deletes).

### 11.2 Rules of thumb

- Honour intent: never turn the author's doubt into a claim (`Apache 2.0?`
  stays text).
- Absent is not a default: a field the source lacks stays absent; do not read
  a value from something that returns a default (Pitloom 0.21.0: fastText `lr`).
- A guess is not a statement: `GPL-3.0` stays `assumed_only`; an assumed
  reading, if adopted, has its own category and trust, never `exact` or
  `listed_name`.
- Weakest operand wins (`CATEGORY_ORDER`); compounds are all or nothing.
- Same value, same answer with or without a built database, for list-only
  categories; the list version and source are in the result.
- One reader per concept (`+`, "or later", version key): import it.
- Output is deterministic: sort; no set or dict order; no clock.
- A rule is promised only after a run of the sample with it (changed set empty).
- The README says what the code does: a change to what `resolve()` reads updates
  its Features section in the same pull request.

### 11.3 Traps

- `normalize_identifier()` on prose upper-cases "or" (`... v3 OR later`),
  narrows `GPL-3.0` to `GPL-3.0-only`, keeps unresolved operands, and returns
  its input when `sort()` raises: never the first step on a whole value.
- `py-spdx-license` 0.0.1: no `+` or `AdditionRef-` grammar; `WITH` needs an
  exception from its own list; its sort key includes the class name; `sort()`
  raises `TypeError` on repeats, also nested ones; the tokeniser is quadratic
  on a long token; deep nesting raises `RecursionError`; keep `<0.1`.
- A regex with `\s+` followed by a class that also matches white space is
  quadratic: write `\s[...]*`. Time every new prose regex on
  `"x" + " " * N`.
- `str.splitlines()` splits on `\r`, `\x0b`, `\x1c` and U+2028; `"\n" in s`
  does not.
- A negative test ("answers no licence") on a seeded database passes trivially
  when its rows have no `search_text`: seed the real near neighbours with a
  text, mutate the fix to see the test fail, and probe the input on the full
  database too (PR #101).
- Mutating a copy of the tree: the editable install hides it unless
  `PYTHONPATH=<absolute copy>/src` and `-o pythonpath=.`; clear `__pycache__`
  between mutants.
- Set `UV_PROJECT_ENVIRONMENT` for `uv sync` and `uv run`, or `uv.lock` and a
  `.venv` land in the checkout and `git add -A` commits them.
- `pkill -f 'uvicorn app.main'` kills the caller (the pattern is in its own
  command line): write `[u]vicorn`.
- A static import cycle fails pylint R0401 even inside a function; use
  `importlib.import_module("pkg.mod")` with an annotated result, or split the
  module.
- A cache keyed on a file stamp: include the inode, take a lock, and do not
  store an answer computed across a change.
- Live hosts (PyPI, GitHub) are slow or flaky: the sampler is a tool, never a
  test; mark any test that needs one `network`.
- A file over about 800 lines, or a complexity ratchet breach, fails CI: split
  first. Judge pylint by its exit code. `ruff check --select I` for imports.
- `AGENTS.md` itself is near its size limit: put a lesson in the implementation
  docs and link it.

### 11.4 Snippets (illustrative; check names against the code)

A lexical rule is a table row plus a test pair, not a new branch:

```python
# proseforms.py: ordered table; each reduced text goes back through the leaf
# lookup, so the existing id / name / loose-id proof applies unchanged.
_RULES: Final = (
    ("prose_words", re.compile(r"(?P<head>.+?) licen[cs]e\Z", re.I), r"\g<head>"),
    ("prose_words", re.compile(r"(?P<n>Apache) License,? (?:Version|v) ?(?P<v>\d[\d.]*)\Z"),
     r"\g<n> \g<v>"),
)

# The kind maps to the category prose_form; never set found.category, or
# weakest-wins is lost (GPL-3.0 License must stay assumed_only).
def read_prose(text: str, lookup: ListLookup) -> Found | None:
    for kind, pattern, replacement in _RULES:
        match = pattern.fullmatch(text.strip())
        if match is None:
            continue
        reduced, found = match.expand(replacement), Found()
        if read_leaf(lookup, reduced, found) and found.expression:
            found.steps.insert(0, step(kind, True, text, reduced))
            return found
    return None
```

```python
# Regression and adversarial tests for it: near misses must stay unresolved.
@pytest.mark.parametrize("value", ["Apache License, Version 2.0", "Apache-2.0 license"])
def test_a_prose_form_of_one_id_is_read(value, db):
    got = resolve(value, db)
    assert (got["expression"], got["category"]) == ("Apache-2.0", "prose_form")

@pytest.mark.parametrize("value", ["Apache License, Version 3.0", "BSD License",
                                   "Apache License, Version 2.0?", "MIT license\nx"])
def test_a_near_miss_is_not_read(value, db):
    assert resolve(value, db)["expression"] is None

def test_the_prose_regexes_do_not_backtrack(db):
    start = time.monotonic()
    resolve("Apache" + " " * 32_000, db)
    assert time.monotonic() - start < 1.0
```

Compound: resolve the operands first, canonicalise second (D1):

```python
leaves = split_leaves(value)       # [(text, start, end)], raw offsets (Q8);
                                   # a grant phrase is part of its leaf (Q14)
founds = [Found() for _ in leaves]
read = [read_leaf(lookup, t, f) for (t, _, _), f in zip(leaves, founds)]
if not all(read) or any(f.expression is None for f in founds):
    return unresolved(value, operands(leaves, founds),
                      reason="operand not resolved: ...")
categories = [category_of(f) for f in founds]   # weakest wins
skeleton = render_skeleton(value, leaves, placeholders(founds))
tree = identifiers.parse_expression(skeleton)   # only AND, OR, (), LicenseRef-
canonical = render(dedupe(sort_chains(flatten(tree))), placeholders(founds))
```

With and without a database, and the sample as acceptance:

```python
@pytest.mark.parametrize("value", CORPUS_VALUES, ids=str)
def test_the_answer_is_the_same_with_and_without_a_database(value, memory_db):
    with_db = resolve(value, memory_db)
    without = resolve(value, source="packaged")
    assert _masked(with_db) == _masked(without)    # drop lists[*].source only
```

```shell
# Acceptance: the same sample before and after a change
python -m tools.pypi_licence_sample analyze sample.jsonl --json before.json   # on main
python -m tools.pypi_licence_sample analyze sample.jsonl --json after.json    # on the branch
python -m tools.pypi_licence_sample analyze after.json --compare before.json  # explain every change
# Mutation check on a copy
rsync -a --exclude .git ./ /tmp/mut/ && sed -i 's/<guard>/False/' /tmp/mut/src/licenseid/<file>.py
PYTHONPATH=/tmp/mut/src pytest -o pythonpath=. tests/<file> -q                 # must FAIL
```
