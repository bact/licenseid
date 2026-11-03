---
Created: 2026-10-30
Last-Modified: 2026-11-03
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
Pull requests #102 to #152 landed since the `v0.6.0` tag. The sections up
to "Release hygiene" were written on 2026-10-30; the sections from "The
CLI and the contract" on record what the closing weeks added (2026-10-31
to 2026-11-03).

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

## The CLI and the contract (T10b, #138; #141)

`licenseid match` (#138) prints the resolution as `KEY=VALUE` lines or
`--json`, needs no database, and exits 0 for an answer, 1 for none and 2 for
a text or path that resolves to nothing. #141 then held every command to one
pattern before the freeze (`tests/test_output_pattern.py`). The pattern
itself is in AGENTS.md ("CLI output"); the decisions are P130 to P175 of the
review. What changed, and what was rejected:

- **No answer is a record (P150).** `detect` with no answer prints one
  record, every field empty (`null` in JSON), exit 1; `--id-only` an empty
  line. Rejected: printing nothing, because `$(...)` then reads a different
  number of lines for an answer and for none.
- **Conflicts are refused (P151).** Two inputs, or `--json` with `--id-only`
  or `--diff`, exit 2 with `option: invalid: ...; pass one input`. Before, one
  won unsaid.
- **`-` is standard input (P152)** for `detect` and `is-*`, even from a
  terminal; `match` reads no standard input and `match -` exits 2.
- **`--text` is taken as written.** No escape is decoded (`\n` stays two
  characters).
- **`is-open`, `is-free` and `LicenseDetector.is_open()` are removed.**
  `is-osi` or `is-fsf` do the same work. The CLI matrix relation B5 now holds
  each predicate to the flag of `detect --json --id X` (P153).
- **The flag of an expression (P140 to P144, P159).** `AND` is true when all
  operands are, `OR` when any is, `WITH` takes the licence's. A compound with
  an operand that cannot be judged (`MIT OR LicenseRef-x`) gives `None`,
  even for an `OR` with a true operand (P140; the maintainer kept it, and a
  three-valued `OR` stayed an open choice). No licence found is `None` too
  (P159), not `False`, so a flag is never a false "no". `is-*` still takes
  no compound through `--id` (P141): a compound is judged from a tag, a field
  or a file.
- **A deprecated ID that states no variant (P145, P160).** `GPL-2.0`, and the
  `-with-` IDs, are read as the `-only` form, `EXACT=false` and `WARNING:
  input: variant not stated` in an argument, `--id`, a tag and a field alike,
  one check (`looseid.narrowed_ids`) in the one reader of a declared value
  (`markers.resolve_license_value`). Rejected: a second guess in the CLI.
- **Every refusal has a reason (P147).** `resolvereason.no_reading` is called
  once every reader has declined: `empty`, `too long: N characters`,
  `special value: NONE` (case-sensitive, as SPDX writes it), `not found:
  <value>`. `reason is None` now means the value was read.
- **`update --list ID[@VERSION]` (P148).** `ID` is the one `lists[*].id`
  shows; the record starts with `LIST=`. Replaces `--version V`.
- **`clear-cache` prints a record (P149):** `STATUS=cleared` or `nothing`,
  and `PATH`. The cache files it deletes are only those beside a database
  licenseid built (P163).
- **The API (P154 to P157, P165, P166, P174).** `licenseid` exports the
  result types and `json_line`; `match(db=)` takes a `LicenseDatabase` or a
  path (`str` or `os.PathLike[str]`), checked ready and opened with
  `create=False`; `detect()` raises `InvalidInputError` for none or two of
  `text`, `license_id`, `file_path`, and `TypeError` for a non-`str` text,
  both before it opens a database (`detector.check_request`); a blank path
  is `InvalidInputError`, not the default database. A step's `list` and
  `detail` are `None` when empty (they were `""`) and `by` is gone. `schema`
  stays 2: schema 2 is new in this release.
- **`variant not stated` has the subject `input` (P146)**, for every command
  and the API; a subject names the thing affected, never a command.
- **Exit 1 may warn (P164).** The rule is "no `ERROR` line" on exit 1 of
  `detect`, `match` and `is-*`; a `WARNING` about the input or database can
  still come.
- **Two reviews of the contract (R1 to R10, S1 to S7; P159 to P175).** The
  second review found a regression of the first: the "+" of a deprecated
  `-with-` ID answered itself, exact (S2, P170). P199 reversed it, below.

## Library warnings and `Detection.lists` (#146; P176 to P191)

- **One emitter.** `licenseid/warning.py`: `LicenseIdWarning(UserWarning)`
  with `subject`, `condition`, `detail` and `action` (None when not stated),
  and `warn(subject, condition, detail, action)` as the one emitter, and
  `parts()` the one reader of `SUBJECT: CONDITION[: DETAIL]` where a fallback
  follows an error. The library never writes a warning to a stream itself; it
  gives one through Python's `warnings`. The `report=` parameter of
  `LicenseDatabase` and `LicenseDetector` is gone. Rejected: parsing the
  grammar text in the emitter, and the class in `errors.py`; the action is
  passed apart, so a `;` in a raw detail cannot move it.
- **The CLI prints them.** `clicommon.printed_warnings()` is entered in
  `DatabaseErrorGroup.main` (so `CliRunner` and `cli.main()` alike): filter
  `always`, so none is deduplicated, and a `showwarning` that prints ours
  through `console.warn` in order with the other lines. Other warnings are
  left to Python.
- **`stacklevel` (P177, P189).** The warning is attributed to the caller of
  the outermost licenseid frame. `warning._caller` walks the stack and
  judges a frame by its module name, not its file path: the first version
  compared `co_filename` with the package path, and in a frozen or sourceless
  install no frame matched. Rejected: 3.12's `skip_file_prefixes` (the floor
  is 3.10) and a fixed level per call site (a stdlib frame between two
  licenseid frames breaks it).
- **"Once per process" (P178, P188).** `warning.once()` (a `ContextVar`)
  keeps a text given inside its block from being given again. Review found
  it counted a warning as given before `warnings.warn` ran, so one the
  caller's filter had raised or ignored was never given again in the process.
- **Tests (P182, P190).** `pyproject.toml` sets `filterwarnings =
  ["error::licenseid.LicenseIdWarning"]`: a test states each warning it
  gives, with the `given` fixture, `pytest.warns`, or `printed` for a step of
  `update` called alone.
  Two mutants survived the suite and got tests (P191). The progress of
  `update` and `clear-cache` still goes to standard error from the library
  (P181).
- **`Detection.lists` (P183 to P186).** Built once per `detect()` call, inside
  its `reading()` block, by `resolverinfo.list_info`, the builder of
  `match()`'s `lists`; each result carries a deep copy. The no-answer record
  of `detect --json` has `lists` as `null`, like every other key. No text
  field: the text line did not change (the maintainer's decision), so `lists`
  is in JSON and the API only.
- **The `--json` rule (P185).** Reworded: every text key is there in lower
  case, a value empty in text is `null` in JSON and no other, and JSON may
  hold more than the text line.

## Resolver values (#147; P192 to P194)

A review of values at the edges (an empty quote, control characters, a
surrogate, marks after a bracket) turned into fixes that move no PyPI value:

- Quote marks around nothing give the reason `empty`; a reason keeps the `;`
  of the value it quotes (only a diagnostic line turns it into `,`).
- A prefix is written in SPDX's case (`licenseref-foo` is `LicenseRef-foo`,
  step `id_case`), the idstring as written. The case fold is ASCII only
  (`LicenseRef-ſ` is no reference).
- U+001C to U+001F are control characters, refused; they had read as white
  space. A refused value with a lone surrogate shows U+FFFD in `input`, so
  `json_line` does not fail.
- One end mark after a bracket, a trove name or path, a listed name or a
  prose form is an ending, with its `separator` step; marks that would be
  dropped after them are named `character dropped`, and a malformed core
  (`LicenseRef-a+-`) gives its own reason (P131 to P137). P137 lists the dash
  endings left silent (`(MIT)-`), each needing a path of its own, for 0.8.
- **Letters that cut an ID (P194).** An ID followed by a letter of a script
  written without spaces (CJK, Hiragana, Katakana, Hangul, Thai, Lao, Khmer,
  Myanmar, Tibetan, Yi) is read again, as the letter cannot be a word
  boundary. A compound passes up only a malformed core's reason; an operand
  and its value get the same reason. `licenseid match` names the line-break
  character it refuses (`invalid: line break U+001C: MIT`); it keeps exit 2.

## One value, read alike everywhere (#149; P195 to P199, P198)

Until #149 a tag, a `license` field, a text, `--id` and `match()` read the
same value in different ways. The maintainer's rule: they agree, and where
`match()` refuses, the others give no answer. Four rounds of work and review:

- **F2 retired (P198; maintainer, 2026-11-02).** A tag or field with an
  operand the List lacks (not `LicenseRef-*`) gives no answer: `MIT OR Apache
  2.0` and `Apache2 OR isc` are refused, as `match()` refuses them. F2 had
  been a partly known tag answered as a non-SPDX match, often `EXACT=true`.
  This is a breaking change (migration: write SPDX IDs).
- **A bare "or later" is the grant (P197).** `MIT or later` in a tag is
  `MIT+`, not `MIT OR later`. `classify.grant_end` is the one probe for "is
  there a grant here", read by `looseid` and `markers`. On an ID with no
  `-or-later` form the grant is `+` (P35); a grant after another version
  number is not the ID's, and "another version number" includes the one the
  phrase starts with unless it is the ID's own.
- **S2 / P170 reversed (P199).** A grant after a renamed ID follows the
  rename (`StandardML-NJ or later` is `SMLNJ+`), and a "+" on a deprecated
  `-with-` ID is no longer exact (`match()` calls it
  `deprecated_ambiguous`). The deprecated-ID tables moved to
  `deprecatedids.py` to stay under the module-lines ceiling.
- **Spaced "+" refused (P195; reverses P34).** `GPL-2.0 +` is no operator:
  `match()` gives `plus after a space`, and a tag with one names no licence;
  the "+" used to be read as or-later, or the rest dropped. Likewise a "+"
  apart from its ID (`MIT +`, `(MIT)+`, `MIT ++`). The operator has one
  reader (`plusoperator`), which `tests/test_plus_readers.py` holds to one
  table.
- **Keywords ignore case in ASCII only (P196).** `(?a:...)` on the keyword,
  not `re.ASCII` on the whole pattern: a dotted capital I, a dotless i, a
  long s and the Kelvin sign no longer read as i, s or k (`MIT WİTH X` is
  refused), while NBSP stays white space. `tests/test_readers_case.py` guards
  it.
- **The grant gap.** Between an ID and its grant only white space, one `.` or
  `,`, and a `(` or `[` before the "or" may stand; "or" must be a word
  (`MIT ora later` is no grant, in `match()` too: the only `match()` answers
  that moved in round 3). A mark `match()` would drop (`MIT; or later`) gives
  no answer from a tag or field. `classify.grant_head` is the one helper of
  that gap.
- **List items, not every ID (round 4).** Round 3 refused a field or short
  text naming another listed ID beside a granted deprecated ID. That broke
  prose: `Copyright Intel Corp. GPL-2.0 or later` lost its answer, because
  `Intel` is an SPDX ID. The re-review of round 3 found it. Round 4 counts
  another ID only as a list item (joined by `,` `;` `/` or and/or, no prose
  word between), plus any listed ID that holds a digit wherever it stands
  (`GPL-2.0 or later; docs under the GFDL-1.3` is refused); plain-word IDs
  (`Intel`, `Ruby`) count only as list items. It also fixed comment-wrapped
  grants (`#`, ` * `) round 3 had refused. No further review round for
  round 4: small, covered by the suite, the CLI matrix and 3.14 runs.
- **Other readers.** `detect` reads a run of blank lines in linear time
  (20,000 took 7 s); `detect --text`, standard input and a file read U+001C
  to U+001F as white space, as `match` does; a refused `--id` that shows no
  character names its code points. `match()` names the trove list version
  (`2026.9.21.13`) in `lists`.
- **Recorded, not fixed (0.8).** The text path still disagrees with
  `match()` on short grants (`MIT or later` as a text gets no CLI answer);
  a field `Licensed under the GPL-2.0 or later, see COPYING` answers where
  `match()` does not; `(MIT) or later` in a tag reads as `MIT+`; a tag
  `MIT/Apache-2.0` or `MIT, Apache-2.0` answers `MIT` (as 0.6.0 did);
  `AdditionRef-*` after WITH is refused by a tag and exact in `match()`; the
  inline grant regex in `markers._name_variants` is a second reader.

## The golden harness (#150)

`python -m tools.golden` records the CLI and API answers for a fixed set of
inputs; a change that moves one lists the value in
`tests/harness_changes.py`. It is the guard for the readers above, which the
PyPI sample cannot be (it holds licence values only). Windows CI found two
platform differences (`8c27c60`): the long and short cases were picked from
fixture files sorted as `Path`s, which Windows compares without regard to
case, so the every-n-th pick named other licences (now sorted by name); and
the CLI golden kept backslashes in the scratch path of a database error (now
written with `/`). The golden file held the package version, so the release bump
would have moved 11 records; it now writes `<VERSION>`.
`python -m tools.golden` with no kind failed on Python below 3.12
(`argparse` choices with `nargs="*"`).

## The database handle (#151; P201)

A review of packaging and files found that `LicenseDatabase(path)`, public
with `create=True` by default, wrote licenseid's tables into any SQLite file
it was given and made a missing file from a mistyped name.

- **Refuse a foreign file, whatever `create` is** (`invalid`), as `update`
  already did; the write rule stays fail-closed. **Create a missing file at
  its first write**, in `_ensure_schema`, not on opening or reading: a
  mistyped name is `not found`. The signature is unchanged and no
  public method was added for creation.
- **A locked licenseid database** now fails a `create=True` open, as `update`
  already did.
- **`DatabaseNotReadyError.condition` and `.detail`** are `str | None`, `None`
  when nothing was said, not `""`: new in 0.7, and the API never uses `""` for
  nothing. A type change after the freeze; the alternative, keeping `""` and
  documenting it, was rejected. Pitloom may need to know.
- **`file_path` and `db_path`** take a `str` or `os.PathLike[str]`, else
  `TypeError`: an `int` had been read, and closed, as a file descriptor.
- **A cache file with an odd name** gets the subject `cache`; `clear-cache`
  names the file it could not delete (`licenses.json: delete failed: ...`).
  An `update` into a missing folder fails at once with `database: update
  failed: OperationalError: unable to open database file` and creates
  nothing (round 3 of #151; every write of the handle also refuses a file
  licenseid did not build, a locked one included).
- **The publish workflow** checks that the tag equals the built version.

Left for 0.8: readers see `database: empty` while `update` rebuilds the file
(1,074 errors over a 13 s update with four reader threads; since 0.6.0). The
fix is to build beside the file and swap it in, which needs care on Windows,
where `os.replace` fails on an open file. The sketch is
[`../design/concurrent-update.md`](../design/concurrent-update.md).

## Refusal reasons and categories (#152; P202)

From the resolver review of the whole release. No answer moved on the sample
or the golden files; edge inputs got the right words.

- `lists` names `pypi-trove-classifiers` when only an operand cites it
  (`MIT; ISC License (ISCL)`).
- A "+" after a listed exception (`MIT WITH Classpath-exception-2.0+`) or a
  bracket in a compound (`(MIT)+ OR ISC`) has its own `malformed` reason
  (`plus after an exception`, `plus after a bracket`); a grant on a
  `LicenseRef-*` is `malformed` in every spelling (rejected: `unresolved` for
  some, which differed with the spelling).
- `GPL-2.0 or_later` stays `separator` (an earlier round of #152 made it
  `stated_qualifier`; reverted in round 3).
  `GFDL-1.3-invariants or later` keeps its reading as the listed ID; only a
  base that spells no listed ID is refused (`... or any later version` and
  `MIT or_later` wait for 0.8).
- `exception not found` is kept for the words after `WITH`
  (`Apache-2.0 with LLVM exception` keeps its informative reason). It is
  `not found: <value>` only when the words hold AND/OR in capitals or a
  listed exception plus more. Rejected: one word only, which would move four
  PyPI values to a vaguer reason. A prose "and" in `... to build and
  distribute ...` keeps `exception not found`.
- Quote marks around a bracketed operand (`"(MIT)" OR Zlib`) are refused as
  `character dropped: U+0022`: reading them would widen the grammar.
- Pushed without a second review round: no corpus or golden answer moved,
  guards and mutants passed, and the findings came from an independent review.

## Other changes of the closing weeks

- **Pinned list in the wheel (#144; P200).** The wheel and sdist ship the one
  SPDX list pinned for the release (`BUNDLE_VERSION`, `BUNDLE_SHA256`), not
  the newest on the build day; `LICENSEID_BUNDLE=skip` with
  `LICENSEID_REQUIRE_BUNDLE=1` fails the build. Rejected: the newest at build
  time, which made a release depend on the day it was built.
- **Blank `HOME` (#145; P192).** `HOME=` on Python 3.10 put the default
  database in `/.local`; a blank home variable (Windows: `USERPROFILE`) is
  now "no home directory", exit 2. Rejected: treating `Path.home() == "/"` as
  none, and an unset variable as blank.
- **BSD-1-Clause (#148; P193).** A text with its copyright line filled in
  read as a BSD-2-Clause variant. It is BSD-1 only with the source-code
  wording, the disclaimer after it and no wording of a later condition, at
  score 0.95; the new module is `bsdclauses.py`. The same change removed a
  quadratic scan on a long run of blank lines (20,000 lines took about 3 s).
  Rejected: a lower score, a rule on how the text ends, and a Tier 1 fix
  (0.8).
- **Short text deferred (P203; maintainer, 2026-11-02).** A branch that
  scaled the score of a text under 40 characters (so `Foo` or `copyright
  notice` is no answer) and required a name holding the input's words to be
  the only one was kept for 0.8, with its review: 0.7.0 ships on program-flow
  correctness, accuracy later unless severely worse. Known on `main`:
  `detect("Foo")` answers 3D-Slicer-1.0 at 1.0, and one or two words of a
  name answer by name at 1.0.
- **Module count and ceilings.** The module-lines ceiling is 738 (`markers.py`
  is the largest); README went over 800 lines, so the Python API reference
  moved to `docs/python-api.md`.

## Measured effect on 0.7.0

See "Measured on 0.7.0" in
[`../design/resolver-0-7-evidence.md`](../design/resolver-0-7-evidence.md):
242 of 462 sample values (84.1% of projects, 90.2% of downloads) carry an
expression; every refusal has a reason. The later pull requests moved one
sample value.

## Traps

- A widened rule needs the prose cases that share its words: refusing any
  second ID beside a grant broke `Intel` (round 3 of #149).
- A fix made in several readers needs the agreement table first: "or later"
  and the "+" each had three readers.
- A golden file must not hold what a release changes (the version).
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
