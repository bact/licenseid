---
Created: 2026-10-30
Last-Modified: 2026-10-30
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Declared values in 0.7.0: compounds, prose, trove names, no database

What 0.7.0 built on the 0.6.0 resolver described in
[declared-value-resolver.md](declared-value-resolver.md). A record of what
was built and why, not a user manual: the fields and categories for users are
in `docs/match.md`. Decision numbers (Q for the questions of 2026-10-28, P for
the provisional decisions of 2026-10-29) are in
[`../design/resolver-0-7-review.md`](../design/resolver-0-7-review.md); the
plan and the task list (T0 to T14) are in
[`../design/resolver-0-7-plan.md`](../design/resolver-0-7-plan.md); the
evidence is in
[`../design/resolver-0-7-evidence.md`](../design/resolver-0-7-evidence.md).
Pull requests #102 to #135 landed since the `v0.6.0` tag.

## Shape of the release

- **Why.** In a sample of real PyPI values, 0.6.0 left 848 of 4,757 projects
  with a short value unresolved, and 63 more were compounds with no
  expression (`paper-notes/results-and-findings.md`, section 3.5). The main
  consumer, Pitloom, kept its own parser for what `resolve()` would not read
  (`../design/expression-resolution.md`, #102).
- **What.** Compounds, quoted values, trove classifier names, prose forms of
  one ID, `;` lists, a guard against dropped characters and words, and a
  list that needs no database. The result shape changed (schema 2), and the
  API was renamed in the same release (see "The rename").
- **Order of work.** Evidence (#103), plan (#105), then one pull request per
  task, each reviewed by an agent other than its author. A review of T0 to T4
  (#116 refreshed the plan) set Q10 to Q24 before T5 to T7 began. R7 reviewed
  everything after T7 together; its fixes are #125.

## Module map

`matcher.py` is now `detector.py` (see "The rename"). The resolver is a chain
of small modules; each states its task and decisions in its docstring.

| Module | Role | Task, PR |
| --- | --- | --- |
| `resolver.py` | `match()`: prepares the value, picks the reader, builds the result and its category and trust | 0.6.0, kept |
| `resolvertypes.py` | The result types and the closed vocabularies (categories, step kinds, trust) | 0.6.0, grown |
| `resolveleaf.py` | One value that names one licence: ID, name, loose ID, `+`, grant, `WITH`, `LicenseRef-*`, and the end-mark rule | T4, #112 |
| `resolvecompound.py` | A compound: each operand read by `resolveleaf` as it reads alone | T7, #122 |
| `exprcanon.py` | Leaves of a compound and licenseid's canonical order | T7, #122 |
| `exprtokens.py` | The words of an expression (operators, IDs, references), one definition | T7, #122 |
| `resolvetrove.py` | A trove classifier name or path, and a name with its short form | T9, #126 |
| `trovenames.py` | The `License ::` names as data | T9a, #123 |
| `resolveprose.py` | The prose form of one ID (`BSD 3-Clause License`) | T8, #128 |
| `resolvesemicolon.py` | Licences joined by `;`, no operator stated | T8b, #131 |
| `dropguard.py` | The characters and words a loose reading must not drop | T6, #120 |
| `quotes.py` | Quote marks around a whole value or an operand | T6b, #121 |
| `listlookup.py` | `ListLookup`, the Protocol the resolver reads a list through | T3, #107 |
| `listrules.py` | Which SPDX entries are kept and what a deprecated ID points to | T2, #108 |
| `listindex.py` | The packaged SPDX bundle in memory, a `ListLookup` | T5, #119 |
| `listsource.py` | Which list `match()` reads, and the file stamp of the choice | T5, #119; T5b, #132 |
| `keptdetector.py` | `licenseid.detect()`: one detector per default path and stamp | T10a, #134 |
| `resolverinfo.py` | The resolver, parser and list blocks of a result | T7, #122 |

`resolver.py` fell under 250 lines when T4 moved the single-value reading out
(the exit criterion of T4). The order in which `match()` tries readers is Q18:
one licence, compound, trove table, prose, then `malformed`. The trove table
goes before prose (Q22), so a name the table reads as `none` (`W3C License`)
is not read by a prose rule.

## Schema 2 (T7, #122; R7 fixes, #125)

- `schema` is 2. The `expression` category is gone: a compound is read, or it
  is `malformed` or `unresolved`, and carries `operands`. This is a breaking
  change with a migration line in the CHANGELOG.
- `operands` lists one entry for each licence the value names, each equal to
  what `match()` answers for that text alone (a property test holds it). An
  operand is a licence, so a refusal of the grammar or a cap has `[]` (P28).
- `components` lists the tools that took part: the parser (`py-spdx-license`,
  with its version and purl, P40) appears whenever it parsed the value or
  refused it with its message (P33). It never names the IDs found (P86).
- Each step has `by`: which reader took it. Steps are in order: those before
  the split, then each operand's, then canonicalisation.
- `reason` is `None` unless the value is refused, then one line built with
  `errors.one_line` (P61). T6 added it (P9 to P11); T7 filled it for
  compounds (P29, P32).
- Canonical order is licenseid's own (D1, Q19, Q24, P44): IDs, then
  `LicenseRef-*`, then `X WITH Y`, case-folded, groups after the leaves.
  Pitloom 0.21.1 and `py-spdx-license` sort differently (4 parity rows differ
  in order only); the three upstream defects are listed in section 5 of the
  review.
- What an operand may hold is Q15, made precise by P42 and P43: one token plus
  `WITH`, `+` or a grant. A lower-case `or` between words is prose as often as
  an operator, so a compound with an operand that names nothing is not
  asserted (P42). `AdditionRef-*` is accepted after `WITH` as `LicenseRef-*`
  is (Q20, P27).
- "X or later" on an ID with no `-or-later` form is `X+` when that is valid
  SPDX (`MIT or later` is `MIT+`), the maintainer's decision P35 of
  2026-10-29. It replaced a narrower rule built first and widened again.

## Categories and trust

The category of a result is the weakest of its steps, and of a compound the
weakest of its operands. Trust follows from the category: `identity`,
`list_data`, `author_words`, `resolver_rule`, `none`. The table is in
`docs/match.md`; `tests/test_resolver_shapes.py` checks it. 0.7.0 added
`prose_form` and `trove_name` (both `resolver_rule`) and made three moves of
category, each listed in the CHANGELOG (Q17, P36). A prose or trove rule maps
a step kind to its category and never sets the category itself, or
weakest-wins is lost: `GPL-3.0 License` must stay `assumed_only`. An
unbalanced quote counts as `separator` through a floor on the result (P17,
P21), because the author's text may be cut. No new vocabulary was added for
it.

Nothing is asserted that the author did not write. Three rules follow from
that and recur: a bare deprecated ID is not narrowed (`assumed_only`); a
`;` list names no operator; a mark that could belong to a cut value refuses
the value.

## The packaged list and `source=` (T5, #119)

- `match(value, db=None, source="auto")`. `auto` reads the newer of the
  default database and the shipped list; on a tie the database wins only if
  its build stamp is current (Q10, P3). `database` and `packaged` are
  explicit. `lists[*].source` says which was read.
- No database file under `auto` is silent (Q11, P6). A database that exists
  but cannot be read falls back with `database: <condition>: <detail>; using
  packaged data v<ver>`, said once for each distinct line per process (P2).
  "Usable" means the readiness gate passes read fail-open and the tables
  have rows (P5, P8).
- `source="packaged"` with `db=` is refused (P1). `DatabaseNotReadyError`
  gained `.condition` and `.detail` (P4).
- `listindex.ListIndex` implements `ListLookup`, so the chain does not know
  which list it reads. An equivalence test holds the database and the index
  to one answer. A synthetic bundle tests the kept-rows rule (G8). The first
  load is under 0.5 s (the exit criterion).
- A process keeps one packaged index; `offline` and `release_fakes.ship`
  forget it (see AGENTS.md).

## The auto-choice cache (T5b, #132; P89, P90)

Choosing between the database and the packaged list cost a connection and
12 to 15 ms per value. `listsource` now keeps the last choice of each mode,
keyed by the default path, a file stamp and the packaged index. After the
change a value costs 1.2 ms and one connection, not six
(`paper-notes/ai-sessions-0-7-0.md`).

- **The stamp** is mtime, ctime, size, inode and device, in nanoseconds. The
  first version used mtime and size; review found that a `chmod` or an
  in-place edit with the modification time restored went unseen. A change of
  mode or content updates `st_ctime_ns`, which `utime` cannot set back,
  so the stamp sees what mtime can be made to hide. Keying by
  `last_update_datetime` was rejected: it needs a connection, the cost the
  cache removes.
- **Which fallbacks are kept.** `not found`, `empty` and `invalid` change
  only with the file, so the stamp sees them. An `unreadable` fallback is
  never kept (P90): a lock held by another process, an I/O error or a
  permission passes with no change to the file. The first version kept it,
  and the packaged list was read for the rest of the process after the lock
  was gone. This was the blocker of the review. A choice that raised is not
  kept either.
- A stat error other than "not found" chooses again. `reset_choice()` is the
  one place that forgets; the `offline` fixture and `ship` call it.
- `licenseid.detect()` (T10a) keeps one `LicenseDetector` on the same stamp
  (P91), with a lock for the look-up and the store and the build outside it.

## Quotes and the drop guard (T6, #120; T6b, #121)

- **Drop guard.** A loose reading drops characters (`Apache 2.0?` read as
  `Apache-2.0`). `dropguard.dropped()` returns the characters that are
  neither alphanumeric nor allowed; a refusal has a `drop` step with
  `applied` false and a `reason` (Q13, P9 to P13). The allowed dashes and
  quotes are the sets `normalize_text` folds, not Unicode category Pd (P14).
  The guard also refuses words a reading drops (`REM MIT`, `1. MIT`): the
  value is read with and without the line rules of `normalize_text`, and the
  words only the second reading lacks are the dropped words (P71).
- **Quotes.** Two marks of one kind pair (P15); a mismatch is refused, both
  marks in the reason (P16); one stray mark on one end is read, as
  `separator` (P17, P22); balanced layers come off in one step (P18); a mark
  inside the pair means the value is not read (P19). Per operand, only a
  balanced pair is taken off (P23). The whole-value call is made once, before
  the brackets, and again only if the brackets came off (P20).
- `Q12` is the reason `"MIT"` was refused in T6 (1 project, 843,066
  downloads) and read in T6b.

## Compounds (T7, #122)

An operator is `AND` or `OR` with white space, a bracket or an end on both
sides, in any case (P38); `WITH` stays inside its leaf. Brackets are
properly nested `( )`, `[ ]` and `{ }`, anywhere (Q21, P26); a pair of two
kinds is `malformed`. A repeated operand is dropped after sorting, as a
`dedupe` step (P24). Brackets in the canonical form appear only around an OR
inside an AND (P25). A leaf of several words, such as `Apache License 2.0 OR
MIT`, is not an operand and gives no compound (Q15, P43, P62), and a
`/` or `,` between IDs gets the reason `not an SPDX operator: /` (P31). The
caps (150 operators, 150 levels, 100 characters for each half of a `WITH`,
Q16) keep deep nesting away from the parser on Python 3.10. R7 reviewed
the whole of it against the database and the packaged list; its fixes are #125.

## End marks (T8, #128; P77 to P80)

The maintainer first decided to trim any run of `; : … . , -` at either end.
The reviewer ran the rule against the List and found it would turn a cut
value into another licence: 47 names have the form `X - variant`, where `X`
alone is another ID (16 HPND variants, the GFDL invariants), and 38 IDs end
in another ID (`AGPL-3.0-only` cut to `GPL-3.0-only`, `Rdisc` to `ISC`). The
rule became single marks only:

- one `.`, `,`, `;` or `:` at the end of a value, with white space around
  it, is an ending and is left off (a `separator` step, `end mark`);
- two or more, an ellipsis (`MIT...`, `MIT…`) and a lone dash are refused;
- no mark at the start is trimmed (`-MIT`, `.GPL-3.0-only` are refused,
  `dropguard.lead_marks`). The two spellings had been read on `main` as
  `separator`; the narrowing closed a gap that was already there. No value in
  the sample or the parity corpus moves.

The rule lives in `read_leaf`, so a whole value, a compound operand and a
prose head follow it alone (P79). #131 extended it to a mark after `+`, an
exception or a `LicenseRef-*` (P80) and to a lone dash after a prose form.

## Prose forms and trove names (T8, #128; T9, #123 and #126)

- **Prose (P1 to P3 of the plan, P70 to P76).** `BSD 3-Clause License`,
  `Apache License, Version 2.0` and `The MIT License (MIT)` reduce to an ID
  and go back through the leaf, so the existing proof applies unchanged. A
  doubled article or licence word is refused (P75). A prose form that reaches
  a deprecated ID keeps `deprecated_ambiguous`, as the ID written another way
  does (P74). The reader of an operand lives in `resolveprose`
  (`read_alone`, `read_by_name`) and the compound reader imports it (P70).
- **Trove (Q22, Q23, P47).** `trovenames.py` holds the table as data, and a
  test compares it to the `trove-classifiers` package. A name the table
  reads as `none` stays unresolved: `BSD License`, the bare `BSD` and
  `Apache Software License` are open by decision (Q3, deferred to 0.8), not
  by a missing rule. A name with no version where the List holds one version
  only (`Common Public License`) is `none` (P47). One special case,
  `GNU Lesser General Public License v2 (LGPLv2)`, reads as `LGPL-2.0`,
  `assumed_only` (Q23, the maintainer, 2026-10-28). A trove step lists
  `pypi-trove-classifiers` as a second entry of `lists`, always `packaged`.

## Semicolon lists as an unstated operator (T8b, #131; P81 to P88)

`MIT ; Apache 2` names two licences and does not say AND or OR. The answer
has no expression, category `unresolved`, trust `none`, the reason `operator
not stated: ;` and one operand for each part, each read as that part is read
alone. A property that holds of every operand needs no operator. The rule
is narrow on purpose:

- only a `;` outside brackets splits; no empty part (P82, P85);
- at least two parts must name a licence, or would but for a mark the guard
  drops, and at least one must resolve (P83, P88). So `MIT; Copyright (c)
  2016-2024 Cisco` is a licence and a notice, not a list;
- a part that begins or ends with `AND`, `OR` or `WITH` means an operator was
  stated, so no list (P84); `,` and `/` are not separators;
- a name that reads whole with a `;` in it (`MIT; (MIT)`) is read by name
  first (P87), so nothing that resolved on `main` became a list.

Measured: 2 of 9,353 projects in the frozen sample (0.02%) hold a top-level
`;`, both a licence plus a notice, and neither answer moved. The sample holds
no real two-licence list; the rule rests on the maintainer's decision and
on generated cases: 676 generated `A ; B` equal their parts alone, and 0 of
137,037 generated values lost or changed an expression against `main`
(`paper-notes/results-and-findings.md`, section 3.6;
`paper-notes/ai-sessions-0-7-0.md`).

## Measured effect (frozen sample, SPDX 3.29.0)

From `paper-notes/results-and-findings.md`, section 3.7 (462 distinct
values, 9,353 projects, top 10,000 projects of 2026-10; 0.6.0 tree against
main after #132):

| Result | 0.6.0 | main |
| --- | --- | --- |
| Sample values with an expression | 137 | 241 |
| Projects with an expression | 79.7% | 84.0% |
| Downloads with an expression | 83.3% | 90.2% |
| Parity values with an expression | 51 of 141 | 96 of 141 |

By rule: compounds 66 values (110 projects, 6.6 bn downloads), trove names 20
(115 projects), prose forms 18 (177 projects), quoted values 1. T8b and T5b
changed no answer. The three largest unresolved values (a trove name that
means Apache-2.0 only by usage, `BSD`, `BSD License`) cover 950 projects and
8.3 bn downloads. Section 3.5 used a different sample (5,000 projects), so
counts do not compare across the two.

## The rename (T10a, #134; design #127)

`resolve()` is `match()`; the old matcher is `detect()` (`LicenseDetector`,
`Detection`, `DetectRequest`, `licenseid.detect()`, CLI `licenseid detect`);
`matcher.py` is `detector.py`. The design is
[`../design/match-resolve-0-8.md`](../design/match-resolve-0-8.md); it
carries the reasons for the names.

- **Why in this release.** 0.7.0 already breaks the result shape (schema 2,
  `expression` gone). A caller changes once. There is no alias: private
  alpha, no backward compatibility.
- **Pure rename.** Every answer is unchanged, checked by the T0 pins, the
  characterisation tests and the sample guard. `resolver.match_with` is the
  new name of the internal entry point. Names in AGENTS.md that still say
  "matcher" for the pipeline mean `detector.py`.
- It was done after T8 and T8b, so those pull requests were not rebased
  over a rename.

## Release hygiene

- **Sdist allowlist (#130).** Review before the release found the sdist
  shipped internal notes, CI files, tests without their fixtures and two
  dangling symlinks to the excluded `AGENTS.md`. It now ships an allowlist
  of source, docs and project metadata, and no links to files it leaves out
  (1.67 MB to 1.17 MB). A test pins the list, so a new entry is a decision.
- **Pitloom (#135).** licenseid's build runs Pitloom's hook, and Pitloom
  imports licenseid: a circular dependency. An older Pitloom accepts
  licenseid 0.7, whose renamed API its hook cannot import, so a build from the
  sdist could fail. Pitloom 0.21.2 caps licenseid below 0.7; `build-system`
  floors Pitloom there, and `.github/requirements-release.txt` pins a pair
  that imports. The wheel's SBOM check runs in its own environment, pinned
  the same way (#134). The order and traps are in
  [release-process.md](release-process.md).
- **CI accuracy layers (#124).** The core set (seven licences, about 15 s,
  from 79 s) runs on every commit; the must-have licences on a matching-path
  pull request; the full set weekly.
- A timing test that failed CI under coverage (5.98 s against a bound of 5 s)
  moved to `@pytest.mark.benchmark`, with a small size kept in the
  every-commit run (#121).

## T10b: `licenseid match` and the CLI output pattern

To be written when it is merged. Not described here: it is not built on
`main` at the time of this note.

## Traps

- A cache key is a claim about what can change. T5b's first key missed a
  `chmod` and an in-place edit, and its fallback outlived its cause.
- Run a proposed rule against the List, not only the code: the end-mark rule
  looked safe in the code.
- A test that seeds a database with rows that have no `search_text` passes a
  negative case for the wrong reason (see AGENTS.md).
- Decision numbers clash between parallel branches (P87 and P88 were
  renumbered): take the next number when merging, not when branching.
- The measuring script of section 3.7 was a scratch script and is not in the
  repository; the frozen fixtures are
  (`tests/fixtures/pypi_values_2026-10.tsv`).
