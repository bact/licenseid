---
Created: 2026-11-27
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
status: built, released as 0.10.0
---

# Speed plan for 0.10.0

Status: plan of 2026-11-27, agreed by the maintainer that day (sections 4
and 5); built by 2026-11-28, not released. The body below stays the plan as
agreed: where the build differs, the Outcome and the notes it names decide.
Base: release 0.9.4 (`527df38`);
the measurements ran on `11b89de`, the same code under another version
string. The roadmap calls this work "the new detection engine of release
0.10.0" (decided 2026-11-27) and orders items 68, 69 and 70 after it;
section 10 says how each open item fits.

Outcome (2026-11-28), final gate run against 0.9.4 (not in the repository):

- Passed (gate names of section 6.2): Core CPU 340.5 s to 19.5 s, 17.5 times
  (need 12); Real file median 329 to 8.7 ms; One call, slowest of 8 files
  177 ms, MIT 93, BSD-3-Clause 110; No class slower (worst 1.06, A/A 0.994);
  Labels agree 182 to 193, other 19 to 14; Prose, TEXTS, Item 68, Damage,
  Threads, Versions; Memory 97 MB (107); Database 17.9 MB (24.7).
- Failed, three, each decided. Fixtures at 0.85, right 419 to 418: the
  plan's exception. Roadmap inputs: `real:f3b34c66:LICENSE` 211 ms against
  200 (2,059 in 0.9.4), one alignment of the Apache-2.0 text: accepted for
  0.10.0 on 2026-11-28, item 78.
  Standard headers (no gate of 6.2), right / wrong / none 56 / 11 / 12 to
  54 / 10 / 15 as given, 52 / 13 / 14 to 49 / 15 / 15 cut: accepted on
  2026-11-27 "for now, then cure later": item 71.
- Not measured in that run: Values (462 PyPI values, 1.39 to 0.84 s
  earlier), Accuracy test and Golden (pass in the suite), `--diff`,
  Storage alone, Platforms (Windows not run).
- Beyond the plan: the filter rule for `exclude`, `only_common` and
  `only_spdx`, with name hits under `exclude` (item 74); `update` never
  rewrites the database of a newer build.
- Taken out: a rule for texts that hold another List text (an independent
  review: 17 right answers wrong, 7 none to wrong, for 8 gained): item 77.
- Detail: the notes `gram-postings`, `gram-candidates`, `word-region`,
  `whole-text-first`, `texts-per-candidate` and `plain-text-table` in
  `../implementation/`; `speed-0-10-evidence.md`; roadmap items 71 to 78.

Every number is measured; the measurements, their method and their
corrections are in [`speed-0-10-evidence.md`](speed-0-10-evidence.md).
Reviewed on 2026-11-27 by two independent readers, one of the design against
the code and `AGENTS.md`, one of the numbers against the result files; their
findings are in this text (the evidence document lists them). Sections 4
and 5 hold what the maintainer decided.

## 1. Goal

0.10.0 makes detection clearly faster for a user, with answers no worse.
Speed-up of a licence text is the whole of it: a declared value already
takes under a millisecond.

| What a user does | 0.9.4 | Target | Prototype |
| - | - | - | - |
| `licenseid detect LICENSE`, one call | 0.17 to 1.3 s | about 0.1 s | 0.10 to 0.22 s |
| `detect()` of a real licence file, warm, median | 370 to 490 ms | under 15 ms | 9 ms |
| 868 benchmark inputs | 370 to 450 s CPU | 15 times less | 17 to 20 times less |
| `licenseid resolve MIT`, one call | 89 ms | 60 ms | 59 ms |
| Database file | 24.7 MB | under 20 MB | 17.7 MB |

Constraints, from the maintainer: no server; fit for use as a library; no
new dependency. The SPDX License List stays the default list, and a later
list (issue 15: ScanCode LicenseDB, Blue Oak, a custom list; under 10,000
texts) can be switched off by a user short of disk, memory or time, so the
cost with SPDX only must not rise when another list ships.

Not goals: a faster `update` (4.8 s of CPU, once), shipping a second list,
a gain from threads, a change of database engine (SQLite is 10 to 30 ms of
a 400 ms call).

## 2. What the measurements say

1. Over 90 % of a text's time is character alignment of about 50 Tier 1
   candidates. The lever is fewer and better candidates, and alignment on a
   region instead of a whole text.
2. Word 3-grams, looked up in a stored table, rank the true text better
   than the FTS5 trigram query and cost about a millisecond.
3. The word-level whole-text search that gives `TEXTS` is right more often
   than Tier 2 on a whole file. So it runs first, and Tier 2 scores only
   what it could not settle. This is roadmap item 68, built.
4. Better retrieval exposes a Tier 2 flaw (`JSON` over `MIT`) that the
   present code hides only because FTS5 never fetched the rival. Whole text
   first cures it; retrieval alone does not, so the two cannot ship apart.
5. The windowed search of mixed content costs most of a weak input's time
   and gives no answer on any probe; its rows are noise (section 5, Q3).

## 3. Design

### 3.1 Pipeline

Unchanged first: `resolve()` reads the whole input, then tags, fields and
the name tier. Then, for free text:

1. **Grams.** The normalised input, comment prefixes off, as word 3-grams;
   each Han or kana character is a word (`textcorpus.split_words`). Each
   gram is a 64-bit hash.
2. **Scores.** One lookup of the grams in a postings table gives, for every
   List text that shares a gram, `shared` and
   `score = shared / min(grams of input, grams of text)`.
3. **Filters.** `exclude`, `only_spdx` and `only_common` take their IDs out
   of the score table here, before any rule below reads it (section 3.5).
4. **None.** Best score under the bar: no gram candidate.
5. **Whole text first.** The word-level search (`wholetexts.found_texts`)
   runs on the texts of a candidate set only: the top 20 by score and every
   text the input holds at 0.5 or more (`shared / size`, the size of its
   core where that is smaller). It finds no text, one, or several.
6. **One text found, guard passed, not filtered out:** Tier 2 scores its
   same-text group and three runner-ups, which rank under it. Guard: no
   narrowing when another candidate shares more grams with the input than
   the found text, times 1.1 (a shorter text held whole inside a fragment
   of a longer one).
7. **Otherwise:** Tier 2 scores the top 3 by score and those within 0.05 of
   the best, at most 20.
8. **Markers and hints** merge after the gram candidates, as now
   (`add_free_text`), also when step 4 gave none.
9. **Tier 2 on a fragment.** Word codes of the input are aligned with the
   text's stored codes; the present character steps then run on that region
   padded by 4 words, not on the whole text. A weak word alignment (under
   60), or a candidate with no stored codes, takes the present scan.

Removed: the FTS5 query at the top level (`ftsquery`,
`database.search_candidates`, the notice-free query of `retrieval`) and the
windowed search (`detector._match_mixed_content`,
`candidates.license_sections`).

### 3.2 Numbers, and why each is not tuned

| Number | Value | Evidence |
| - | - | - |
| Gram size | 3 | 2 to 4 give the same answer quality; larger grams lose heavy distortion |
| None bar, also the runner-up floor | 0.1 | No answered input is under 0.4; 0.1 costs what 0.3 costs |
| Tier 2 selection | 3, within 0.05, at most 20 | Margin 0.05 holds the truth as often as 0.25 |
| Whole-text candidates | 20, and held at 0.5 | TEXTS equal to a search of all texts on 781 and 165 inputs |
| Guard margin | 1.1 | Any value from 1.02 to 1.25 gives the same result |
| Runner-up rows | 3 | Maintainer's decision; 5 costs twice the median |
| Word alignment accepted, pad | 60, 4 words | No short-fragment answer moved when it was added |

Net rules: one retrieval rule replaces two (the FTS5 query and its
notice-free twin), the windowed search and its section cut go, and the
size-key ordering tried in the prototype is not built. The guard and the
runner-up rule are new.

### 3.3 Storage and its validity

Built by `update`, in the database file, read through its one connection:

```text
text_postings     (h INTEGER PRIMARY KEY, ids BLOB)
text_posting_ids  (k INTEGER PRIMARY KEY, id TEXT, size INTEGER)
text_code_checks  (owner_id TEXT PRIMARY KEY, digest TEXT)
```

- `h` is a stable 64-bit hash (`hashlib`, never `hash()`), stored signed.
  `ids` is the texts that hold gram `h`, as numbers `k` of a width that is
  stored, not inferred; little-endian, swapped on a big-endian host. One
  blob per gram is a third of the size of one row per pair. 3.2 MB for List
  3.29.0, 0.25 to 0.5 s of `update`. Lookups bind at most 900 values a
  query.
- **Postings are used only when they are those of the rows.** A stamp
  written in the same transaction holds the build, the gram spec (size,
  hash, tokens) and a copy of `last_update_datetime`. A stamp that differs,
  a blob of a wrong length or a `k` out of range: the index is built in
  memory (245 to 510 ms a process), never written back. The stamp ties the
  postings to the texts they were built from; the per-entry check below
  cannot, because a text that is never a candidate is never read. A missing
  table is not damage: the file is not of this build (D6, below).
- A database of a newer build is not rebuilt (`build vN newer`); its
  postings are not read unless the gram spec matches.
- **Texts are read per candidate**, not all at start (2 to 4 ms against 32
  to 42 ms). `text_code_checks` keeps the contract of `textstore.restore`:
  a head digest (coding, vocabulary, patterns) and one SHA-256 per entry.
  A mismatch or a missing row drops the stored codes for that database and
  builds in memory, as now. A file with no checks table is not of this
  build (D6): no second way to restore is kept for it.
- **A search still gets an immutable corpus.** `wholetexts` relies on it
  (threads share a corpus). Each call cuts its own small corpus from the
  entries of its candidates; the store of loaded entries behind it is one
  object owned by `dbcache.TableCache`, filled under a lock. A call that
  finds damage is given its corpus from the fallback instead; it does not
  restart. Postings, ids and entries of one call are read in one
  transaction, so an `update` cannot land between them.
- A misshaped table of these three (roadmap item 66) reads as a missing
  one: the file is not ready, and `update` rebuilds it.
- New tables join `dbschema.SCHEMA_OBJECTS`, all required; each new
  condition gets its read (fail-open) and write (fail-closed) policy in
  `dbcheck`.
- A second list gets its own postings and ids tables, read and merged only
  when the list is on: SPDX-only cost is then what it is in 0.10.0.
- **One shape, and no reader of older files** (D6). 0.10.0 reads only a
  file of its own build. One with an older stamp (build or normalisation),
  or without one of the tables, is not ready: `ERROR: database: build v7
  outdated: current v10; run 'licenseid update'`, exit 2, where 0.9.4
  warned and went on. It joins `missing` and `empty`: every caller
  (`detect`, `resolve`, `is-*`, the API's `DatabaseNotReadyError`,
  `resolve()`'s choice of list) treats it as it treats an `empty` file
  now, so no caller gets a rule of its own. `update` rebuilds the file from
  scratch; it keeps the old object names only to see that the file is
  licenseid's own and to drop them. `clear-cache` deletes it. A user who
  upgrades runs `licenseid update` once, as after a first install.
- So a lookup never writes, with no exception, and this code goes:
  `dbschema.schema_state`'s `older` state, `_ADDED_COLUMNS` and
  `_BUILD_COLUMNS` with their `ALTER TABLE`; `OPTIONAL_OBJECTS`; in
  `dbcache`, the norm columns filled in memory, the "no core, no twin"
  reading of a build-4 file and the `license_urls` and `text_codes` tables
  read as missing. What stays is damage, not age: a stored value that fails
  its check is rebuilt in memory, never written back.
- **The FTS5 table goes** (D5): nothing in 0.10.0 reads its index. The
  texts are in a plain table under a new name (not `license_index`, so no
  file can hold a plain table of the FTS5 one's name): 17.7 MB in all
  against 24.7 MB, and `update` no longer builds a trigram index.
- Neither decision touches an answer or the speed of one: the texts stored
  are the same, and the code removed runs only on older files. Measured
  with the prototype on a copy whose text table is plain: answers and
  `TEXTS` of all 868 inputs equal, CPU 26.7 and 27.0 s against 26.0 and
  25.6 s with the FTS5 table (14.7 against 15.1 s on the fixtures alone):
  inside the noise of that machine. T7 holds the real build to it.
- The other direction (measured on such a file): every command of 0.9.4,
  `update` and `clear-cache` too, stops with `database: invalid`, exit 2,
  and leaves the file as it is. The way out is to upgrade (0.9 and 0.10
  ask the same Python) or to delete the file by hand; the CHANGELOG says
  both steps as breaking changes.

### 3.4 Modules

Names are proposals. `detector.py` is at 733 of 800 lines: the new logic
needs no detector state and goes elsewhere.

| Module | Change |
| - | - |
| `textgrams` (new) | Tokens, grams, hashes, scores; standard library only |
| `gramstore` (new) | Postings as rows to store, the stamp, reading and checking them, the index in memory |
| `gramselect` (new) | Pure rules over a score table: filters, none bar, Tier 2 selection, whole-text candidates, guard, runner-ups |
| `retrieval` | `get_candidates` from grams; FTS5 and notice-free paths removed |
| `wholetexts`, `firsttext`, `markerfloor`, `textnames` | Every `found_texts` caller searches one candidate set per input |
| `textcorpus`, `textstore`, `dbcache` | Entries read per candidate; per-entry check; a corpus cut per call |
| `similarity` | Word-level locate before the character steps, on the corpus's own codes |
| `ranking`, `variants` | The runner-up rule (Q1); `variants` sorts through `ranking.ranking_key` |
| `detector` | Calls the above; `_match_mixed_content` and the gate of five removed |
| `records`, `dbschema`, `dbcheck`, `database`, `dbcache`, `fingerprintstore` | New tables and stamp; `BUILD_VERSION` 8 (T2), 9 (T6), 10 (T7); an older file is not ready (T2); the code for older files removed (T7) |
| `ftsquery`, `candidates.license_sections` | Removed |
| `hiddenchars`, `plusoperator`, `shorttext`, `namehits` | Exact speed-ups of the value path |
| `__init__`, `cli`, `resolverinfo`, `spdxdata` | Imports at use (start-up) |

### 3.5 Options and other candidates

Today 50 or more candidates are fetched, then filtered. The prototype
selected first and filtered after: `exclude=["MIT"]` on the MIT text left
the three runner-ups, and `only_common` left two rows. The design filters
first:

- `exclude`, `only_spdx`, `only_common` act on the score table (step 3), so
  the bar, the selection and the narrowing see only what may answer. A
  found text that is filtered out does not narrow.
- A text that a text a filter took out beats on both counts (grams shared,
  score) is no candidate either (`gramselect.beyond_bar`; no tuned number:
  the score alone, `shared` alone and a margin were measured and rejected,
  `gram-candidates.md` section 8).
- `TEXTS` and `texts()` ignore every filter, as now ("a fact about the
  input"): the whole-text search runs on the unfiltered candidates, and the
  narrowing reads the filters afterwards.
- Marker and hint candidates are outside the gram set. They merge as now,
  and their entries are loaded so that step 9 has codes for them.
- `variant`, `--exact`, `--top`, `--threshold` act on results, unchanged.
- `--diff` shows the window Tier 2 aligned (`_diff_pair`): step 9 changes
  it, so T4 checks its output by hand and snaps it to word boundaries
  (roadmap item 11).
- Past a bound on the grams looked up (an input of very many distinct
  words), candidates come from the grams read, and `TEXTS` is None: never a
  partial list.

### 3.6 What a user sees change, beside speed

- **A database of 0.9.x.** No lookup answers until `licenseid update` has
  run once: exit 2 with `database: build vN outdated`, as after a first
  install without a database (D6).
- **Rows under the answer.** When a text is found whole, the rows under it
  are three runner-ups in gram order, not the old Tier 2 order: 628 of 938
  old rows return. `MIT` lists `FSL-1.1-MIT` third where it listed
  `X11-distribute-modifications-variant`.
- **Rows of a filtered call.** `exclude` of the answer gives the selection
  among the rest (at most 20 rows), not a ranking of 50.
- **Low rows of an input with no answer.** Fewer: of 125 inputs that list
  rows under 0.85 now, 99 still do. For the others the CLI's `REASON` reads
  `no match`, not `below threshold`. A misspelt licence name in prose is no
  longer listed as a low row.
- **Some answers.** Golden `short` moves 17 of 588, all other parts none:
  7 to the fixture's licence, 3 wrong answers to none, 3 from one other
  licence to another, and 4 new answers that are not the fixture's licence
  (two of them one candidate whose score crosses 0.85). Those 4 are examined
  one by one in T4 and T5: an answer that is not right is refused. Real
  files: 10 more agree with the declared licence, 4 fewer disagree.
- **A lower `--threshold`** gives more right and fewer wrong answers than
  now at 0.7 and 0.5.
- **Threads** no longer raise throughput (0.8 times with four; 1.3 times
  now). Four passes still take a tenth of the time.

## 4. Decisions taken

| # | Decision | By |
| - | - | - |
| D1 | No server; library use; nothing on `main` until the plan is agreed | Maintainer, 2026-11-26 |
| D2 | SPDX List is the default; other lists can be switched off | Maintainer, 2026-11-26 |
| D3 | Three runner-up rows under a text found whole, ranked under it | Maintainer, 2026-11-27 |
| D4 | 0.10.0 is the new detection engine; items 68, 69, 70 follow it | Maintainer, 2026-11-27 (roadmap) |
| D5 | The FTS5 table is dropped in 0.10.0 once no code reads it. No other install is expected to share the data directory, and 0.9 and 0.10 ask the same Python, so a user upgrades everything to 0.10 (was Q4) | Maintainer, 2026-11-27 |
| D6 | 0.10.0 moves to the new shape at once and keeps no code for an older database: the user rebuilds it with `update`. Answers and speed must not change by it | Maintainer, 2026-11-27 |

## 5. Questions put to the maintainer

None is open. The maintainer accepted each recommendation below on
2026-11-27; Q4 was decided the other way and became D5. A task that
measures something against one of these answers reports it, and does not
choose again on its own.

| # | Question | Decided |
| - | - | - |
| Q1 | A runner-up may score above the text it ranks under (11 of 868, all `JSON` over `MIT`). Every later step sorts or filters by score (`ranking.py:176`, `variants.py:526` and `:556`, `clidetect`'s threshold), so "ranked under" needs one of: a capped score; a rank field honoured in all four places; or leaving that runner-up out | Leave it out: no invented number, no second ordering. Costs 13 to 38 rows of 868 inputs. The scoring flaw itself stays its own item |
| Q2 | None bar 0.3, 0.1 or 0 | 0.1: free, and it is also the runner-up floor. 0 costs 10 % for rows that are noise on prose |
| Q3 | Remove the windowed search, name search on sections included | Yes. No answer lost on golden, 300 READMEs, 96 notices, 77 mixed inputs. Keeping only the name search costs 58 % more CPU on the core set for rows that reach 0.55 at most and name the declared licence in 50 of 186 READMEs. Lost: a misspelt name in prose as a low row (four tests pin it) |
| Q5 | Start-up edits (30 to 36 ms of a value command) in 0.10.0 | Yes, last: after the speed-up, import is over half of a one-file call |
| Q6 | The second guard clause, made for look-alikes of more lists (moves 1 answer with SPDX only) | Leave out of 0.10.0 unless T5 measures a loss; it returns with issue 15 |
| Q7 | Accept that four threads no longer help | Yes; say so in `docs/python-api.md` |
| Q8 | Where T2 to T7 land. Retrieval alone (T3) answers `JSON` for some MIT files until T5 cures it, and `main` may still give 0.9.x patches | An integration branch, one reviewed pull request a task into it, one merge to `main` after R1 |
| Q9 | `exclude` and `only_common` filter before the selection (section 3.5), so a filtered call lists fewer rows than now | Yes: the rows are those that may answer; the other order returns runner-ups of a text the caller excluded |

## 6. Benchmark plan

### 6.1 Harness, built first (T0)

The prototype's measurements become a tool in `benchmarks/` that compares
two source trees and records answers before time. It replaces
`bench_fts5_recall.py` and extends the speed gate of
[`release-process.md`](../implementation/release-process.md).

| Set | Inputs | Records |
| - | - | - |
| Core | 868: 300 real licence files, 408 long and 160 short fixtures | Rows, TEXTS, CPU per input |
| Labels | 225 real files with one declared ID | Agree, other, none, at 0.85, 0.7, 0.5 |
| Prose | 300 real READMEs, 96 notices, 77 mixed inputs | Top answer, rows |
| Many texts | 165: 2 to 40 texts joined, clean, 2 %, 5 %; some as cores only | TEXTS |
| Han and kana | 24: texts and fragments re-wrapped | Rows |
| Options | Whole texts under `exclude`, `only_spdx`, `only_common`, `hint` | Rows, TEXTS |
| Roadmap | The inputs items 11, 61, 62 and 68 name; item 68's 25 files; the HPND family fixtures of item 64 | Rows, TEXTS, seconds |
| Stress | 18 large or odd inputs, one process each, time limit | Seconds, rows |
| One call | 8 files and 3 value commands, fresh process, minimum of 11 | Milliseconds |
| Memory, threads | Peak RSS at 1, 300, 868 inputs; 4 threads on one detector | MB; answers against one thread |
| Damage | Damaged stored codes (9 kinds) and postings (stale against the texts, bad blob, bad width, other gram spec, no stamp) | Answers against an `update` build |
| Versions | A 0.9.4 file met, then updated, by 0.10.0; a 0.10.0 file met by 0.9.4 | Exit codes, error lines, no write before `update`; answers after it |

Rules of the harness, each learnt from a wrong number:

- Both sides are frozen copies (`git archive`), named by `PYTHONPATH`; the
  editable install follows the checkout and moved under a run once.
- Answers are compared first. A time is CPU seconds, taken with the other
  side in the same session, with an A/A twin for the noise floor. A run that
  shared the machine is rerun alone or reported as a ratio only.
- Tier 2 rows scored is the load-free proxy for a rule's cost.
- The real files are a manifest of hashes over a local folder, not a scan of
  whatever is installed that day.
- A figure is quoted with the prototype and settings that gave it: ten
  figures of the first draft were of an older prototype.

Before release, one set the rules were not chosen on: real licence files of
another ecosystem (npm or Cargo packages), labelled the same way. Every
number in section 3.2 was chosen on the core set; the accuracy test, the
READMEs and the many-text set were only checked afterwards.

### 6.2 Gates for the release

Against the last tag (0.9.4), as `release-process.md` asks.

| Gate | Pass when |
| - | - |
| Core, CPU | 12 times less or better (target 15; prototype 17 to 20, and 6 on the heaviest distortion) |
| Real file, median | 15 ms or under |
| One call, each of 8 files | 0.3 s or under; MIT and BSD-3-Clause 0.15 s or under |
| No class slower | No input kind and no stress input over 1.2 times the last tag, A/A read first |
| Values | `resolve()` and `detect()` of 462 PyPI values not slower |
| Labels | Agree not under 190, other not over 16 (now 182 and 19) |
| Fixtures | Right not lower and wrong not higher than the last tag at 0.85, 0.7, 0.5 |
| Accuracy test | Top 1, 3, 5 not lower at any distortion level |
| Golden | Every moved answer looked at and listed with its reason in `tests/harness_changes.py`; no right answer at 0.85 or more lost; no new answer that is not the fixture's licence, unless the fragment equals that other text |
| Item 68 | What it asks before any answer is made from TEXTS: real files, the several-texts cases, every fixture; no HPND-family fragment that names a neighbour becomes an answer |
| Roadmap inputs | The inputs of items 11, 61 and 68 answer as in the evidence, each under 0.2 s |
| TEXTS | Equal to the last tag where the answer is the same, on all many-text inputs, and under every option |
| Options | Each option case decided and pinned; `--threshold` between an answer's score and a rival's prints the answer |
| Prose | Top answer the same on READMEs, notices and mixed inputs |
| `--diff` | Output read by hand on fragments; window on word boundaries |
| Damage | Every case of codes and postings equals an `update` build, regions included |
| Versions | 0.10.0 on a 0.9.4 file: every lookup exits 2 with `build v7 outdated` and writes nothing; after `update` its tables, rows and answers equal a fresh build's; `clear-cache` deletes it. 0.9.4 on a 0.10.0 file exits 2 with `database: invalid` and writes nothing |
| Storage alone | T7 moves no golden answer, no row of the core set and no `TEXTS`; core CPU within the noise of two runs of T6 |
| Threads | Answers equal one thread; first calls from 8 threads on a fresh detector, a test in the suite, not a count of runs |
| Memory, size | Peak not over the last tag; database file under 20 MB |
| Platforms | Suite green on 3.10 and 3.14, and on Windows with `test-all-os`; `tools.cli_matrix` after T3 and T5 (`REASON` moves) |

"100,000 distinct words" is 1.25 times slower in the prototype (one lookup
per gram): T3 bounds the grams looked up for such an input (section 3.5),
or the gate fails.

## 7. Tasks, in order (one pull request each)

Each task ends with the harness run against its parent and the numbers in
its pull request. A task that moves an answer lists it in
`tests/harness_changes.py`, reruns the full golden, and gets one independent
adversarial review (heuristic code). Model and effort are suggestions.
T2 to T7 land on the integration branch of Q8.

| # | Pull request | Exit criteria | Author | Effort |
| - | - | - | - | - |
| T0 | Benchmark harness and baselines | Section 6.1 as a tool, item 61's and item 68's cases in it; baselines of 0.9.4 stored outside the repository; no source change | Sonnet | medium |
| T1 | Exact speed-ups of the value path | Four changes of the evidence; answers identical on the PyPI sample and the core set; 462 values 1.4 s to about 0.8 s; to `main`, could ship in 0.9.x | Sonnet | medium |
| T2 | Store word-gram postings at `update` | `textgrams`, `gramstore`, tables, stamp, `BUILD_VERSION` 8; from here an older build is not ready (exit 2, was a warning), so no task writes a reader for one; index in memory when the stored one fails its check, Han and kana per character; `dbschema` and `dbcheck` know the tables; a misshaped one is rebuilt; nothing reads them yet; damage and versions gates for postings | **Opus** | **high** |
| T3 | Candidates from grams | `gramselect`: filters first, none bar, selection; FTS5 query, notice-free query and windowed search no longer called; lookup bound; option cases decided; about 10 times on the core set; golden moves listed | **Opus** | **high** |
| T4 | Word-level locate in Tier 2 | Region from word codes, character steps on it; marker and hint candidates covered; `--diff` gate; the two score-crossing fragments examined; about 15 times | Sonnet | medium (Opus reviews) |
| T5 | Whole text first | One candidate set for every `found_texts` caller, cores counted; narrowing, guard, runner-ups as Q1 decided, with the floor; TEXTS unfiltered; item 68 gate; about 17 to 20 times | **Opus** | **high** |
| T6 | Read texts per candidate, with a per-entry check | `text_code_checks`, `BUILD_VERSION` 9; a corpus cut per call, store filled under a lock, one transaction a call; the whole-corpus restore goes where no caller needs it; contract tests of `test_text_codes_db` and `test_template_texts` rewritten for it and green; damage gate; first call 33 to 90 ms | **Opus** | **high** |
| T7 | One shape: drop the FTS5 table and the code for older files | Texts in a plain table under a new name, `BUILD_VERSION` 10; `ftsquery`, `search_candidates` removed; `schema_state`'s `older`, `_ADDED_COLUMNS`, `_BUILD_COLUMNS`, `OPTIONAL_OBJECTS` and the in-memory fills of `dbcache` removed, with their tests; `update` rebuilds a 0.9.x file from scratch, `clear-cache` deletes it; `dbcheck` policies for the one shape; versions and storage-alone gates; `tools.cli_matrix` run; file 17.7 MB | **Opus** | **high** |
| T8 | Faster start-up | Package `__init__` and commands loaded at use, with a name table for help and "did you mean"; `--version` 86 to about 50 ms; same output; to `main` | Sonnet | medium |
| R1 | Review and release gates | One independent review of T1 to T8 together; section 6.2 against 0.9.4; hold-out set; item 68's 25 files measured again; docs; then the merge to `main` | **Opus** | **high** |

Build note, 2026-11-27: the rule of D6 and the removal of the code for
older files are built before T2, as a layer of their own ("T2a"), so that
no later task carries dead code; T2 then adds its tables to one shape, and
T7 is the FTS5 table alone.

Order: T1 and T8 are independent. T3 needs T2. T4 and T5 need T3; T5 is
easier after T4. T6 needs T5. T7 comes last of the engine tasks: after T3
no code runs an FTS5 query, and after T6 every reader of the texts is one
it can move.

Every task that touches them updates `docs/how-it-works.md` (Tier 1 is no
longer FTS5), `docs/python-api.md` (the sections of mixed content, "the five
below which `detect()` searches", threads), `docs/output.md` (`REASON`),
`AGENTS.md` (module list, the Performance rules on trigrams and
`ftsquery`, the Database rules on an older schema, an older stamp and the
optional `text_codes`, a new `CONDITION` if one is added),
`docs/installation.md` and `docs/cli.md` (`update` after an upgrade, exit
2), `CHANGELOG.md`, the `paths` of
`accuracy.yml` for a new module on the matching path, and decides on
`tests/platform_files.py`.

## 8. Tests that will change

198 tests fail under the prototype (evidence, "Test suite under the
prototype"). What each class needs:

- **Option behaviour** (74, `test_detect_options_paths`: the option matrix
  32, "the options shape the text candidates" 20, TEXTS under filters 6,
  empty collections 8, others 8). Not row counts: these pin what each
  option does to the candidates. Filtering first (section 3.5) is expected
  to keep most; each one left is decided, not rewritten to pass. Its prose
  input `TIE` shares no gram with a List text and falls under the none bar:
  the matrix needs an input that reaches Tier 2.
- **Stored-codes contract** (39): stays, rewritten for the per-entry check
  (T6). These are the tests that keep "stored codes only when they are
  exactly those of the rows".
- **Removed code** (18): `test_get_candidates`, `test_ftsquery` go or move
  to `gramselect`; the four tests of the section name search go with Q3.
- **TEXTS call counts and low rows** (32): counts change with the candidate
  set; a test that reads row `[0]` of an input with no answer needs a row
  that still exists.
- **Not examined one by one** (35): 16 variant tests and 19 others, about
  ten of them on tiny seeded databases whose short texts may fall under the
  none bar. T3 examines each before it changes one; a seeded text that
  should answer and does not is a finding, not a test to rewrite.
- `tests/test_text_codes_db.py` pins `BUILD_VERSION` at 7: it moves with T2
  and T6. Its "0.9.2 case" (an older `update` on a newer file) cannot
  happen once 0.9.x refuses the file: T7 replaces it with the versions gate.
- **Older files** (D6): 14 test files read an older schema or an outdated
  stamp (`test_build4_database`, `test_license_urls_build3`, `db_variants`,
  `test_lookup_database_pins` among them). T2 flips the outdated ones to
  the not-ready error; T7 removes those of the code it removes. A seeded
  test database must come from the one builder, so that it has every
  table: a test that seeds by its own SQL is found by T2.

Characterisation first: T3 and T5 pin the present answers of the core set
and the golden before they change code, then flip each pin with its reason.

## 9. Risks

- **A real build is not the monkeypatch.** The gates leave room (12 times
  asked, 17 to 20 measured). The prototype capped scores, filtered options
  late, kept a mutable corpus, kept the FTS5 table and had three bugs of
  state kept too long or published half-built; none of that is the design,
  and each is a test of T3, T5, T6 or T7.
- **Rules chosen on the set they are judged on.** The hold-out set of
  section 6.1 is the answer; until it runs, the plateau evidence of section
  3.2 is the argument.
- **New answers on fragments.** Whole text first makes answers (item 68's
  warning). Four of 588 golden fragments already show it.
- **Stale stored data.** Postings are a second copy of the texts; the stamp
  and the damage gate are what keep them honest.
- **Two versions on one data directory.** Accepted (D5): a 0.9.x there
  stops with `database: invalid` until it is upgraded. The gate checks that
  it stops cleanly and writes nothing.
- **The first call after an upgrade fails** (D6) until `update` has run,
  in a program that uses the library too (Pitloom). It is what a first
  install does; the CHANGELOG and the release notes give the step, and the
  error line names the command.
- **Weak labels.** A declared licence is not the licence of every file in a
  package; nine known label errors.
- **Few real files hold several texts.** The many-text set is synthetic.
- **Look-alikes grow with more lists.** Three answers still name a short
  generic text on 2,375 texts. Not a 0.10.0 risk; issue 15 needs its own
  measured work on the guard.
- **Windows.** Nothing here ran on Windows; the blob byte order and path
  handling of new tables are the likely places.
- **A user of low rows.** The change is measured as better, but a script
  that reads row 2 or a row under 0.85 sees other rows.

## 10. Fit with the roadmap

Open items of [`tech-debt-roadmap.md`](tech-debt-roadmap.md) as of 0.9.4.
Their named inputs were run on the prototype (evidence, "Inputs the roadmap
names").

| Item | Fit |
| - | - |
| 68, `TEXTS` as ranking evidence | Built by T5: a text found whole ranks first. wcwidth answers `MIT`, not `JSON`; mypy_extensions answers. Of 12 real files with one text in TEXTS and no answer, 8 answer, none against its label. The measurement item 68 asks for first is T5's gate. What is left of the item after 0.10.0 is the files the guard holds back |
| 11, probe-anchored windowing | Superseded by T4. Its two inputs: 10.2 s to 0.10 s and 9.6 s to 0.014 s. Its caution stands and is T4's `--diff` gate |
| 61, core text and notice-free query | The cost part goes with the FTS5 query (MIT under two copyright lines: 0.52 s to 0.012 s). The notice-free query is removed by T3, so its recall cases (`RHeCos-1.1`, `BSD-ask-to-endorse`, a text under two copyright lines, HPND's core under a copyright line) join the harness in T0. Cores alike is untouched |
| 62, 100,000 `License:` lines | Not touched; the harness times it |
| 65, concurrent first calls | Changed by T6: the store of loaded entries is filled under a lock; the corpus a search reads stays immutable |
| 66, a misshaped optional table | Grows by three tables on the main path. T2: a misshaped one reads as missing, and `update` rebuilds it |
| 69, MPL header as a notice | Not touched: still no answer (top row becomes `MPL-2.0` 0.53) |
| 70, exception texts | Not touched: TEXTS the same |
| 7, 13, 28, 31 | Ranking and rule items: measure again on the new engine before any is taken up; the candidates they see change |

## 11. Not in 0.10.0

- A second list (issue 15); the second guard clause; another runner-up
  order.
- The `JSON` over `MIT` scoring of Tier 2, as its own roadmap item.
- A file that repeats one text many times gets no answer (present
  behaviour).
- A word-count cut before `resolve()` on a long text (possible, not shown
  exact).
- A batch API over processes.

## 12. Guide for the agent that does a task

- Read the evidence document first; the prototype scripts are in
  `.claude/speed-prototype-2026-11-27/` of the maintainer's checkout
  (`variants7.py` is prototype 6; its `README.txt` maps the rest). They show
  what was measured, not how to write it: section 9 lists where the design
  differs from them on purpose.
- A candidate list under five re-triggers the windowed search in
  `_run_tier1_and_tier2`: remove that gate with the search, not after.
- Sort candidates of equal score by row, or the order follows the hash seed.
- Keep per-database state on the database object, never by path (tests reuse
  paths), and give it one owner.
- A read that fails on stored data must end as a fallback or as
  `DatabaseNotReadyError`: a bad blob raises `ValueError` or `IndexError`,
  which `Connections.connection` does not catch.
- The first call of a process carries every lazy load: time warm and cold
  apart.
- In a worktree set `PYTHONPATH`; in zsh pass several settings through
  `bash -c` (an unsplit `$VAR` becomes one argument).
