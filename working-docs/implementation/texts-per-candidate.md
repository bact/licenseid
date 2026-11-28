---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Texts read per candidate, with a check per entry (build 9)"
---

## Texts read per candidate, with a check per entry (build 9)

Status: task T6 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`), built 2026-11-27 on layer 11,
not merged. A call reads the coded texts it searches and scores, not the
whole corpus. Measurements: Apple M-series, Python 3.10, SPDX License List
3.29.0.

### 1. What is stored

- `text_codes (kind, owner_id, body)`, as before: the head (owner `''`:
  `words`, the vocabulary in code order; `patterns`, the patterns of the
  regions; and, new, `coregrams`, the distinct word 3-gram count of each
  core by group name), then the codes and regions of each text and core.
  The whole-corpus `check` row is gone.
- `text_code_checks (owner_id TEXT PRIMARY KEY, digest TEXT) WITHOUT
  ROWID`: one SHA-256 for the head and one per entry, written by `update`
  in the transaction of the rows (`textentries.write_checks`), read back
  from those rows through the readers of a lookup.
- The head's check covers `textstore.CODING_VERSION`, the token rule,
  `last_update_datetime` and the head's bodies. An entry's check covers the
  head's check, the group name, the text and core as the rows hold them and
  the entry's bodies. Each value is length-prefixed; a missing body differs
  from an empty one.
- `dbschema.BUILD_VERSION` 9; the table is in `TABLES` and
  `WITHOUT_ROWID`, so a file without it, a view of its name or a table with
  a rowid is not ready (`empty`), as decision D6 asks.

### 2. Read per candidate

- `textentries.TextStore`, one per generation of `dbcache.TableCache`
  (`_Keyed.texts`), holds the state of one `last_update_datetime`: the head
  and the entries loaded so far (`_Stored`), or the corpus built in memory
  (`_Built`). A state is never changed: a load publishes a new one under a
  lock, and only when the database is still at the time it was read at.
- A call reads in one transaction (`TableCache.snapshot`: `BEGIN` on the
  shared connection of the `reading()` block, the stamp read again in it):
  the postings, the IDs, the head and the entries. An `update` cannot land
  between them (`test_an_update_cannot_land_between_the_reads_of_a_call`).
- `textcandidates.TextCandidates` asks `StoredTexts` (one a call) for the
  core gram counts of the texts it may search (from the head, no entry
  read), then for the corpus of the texts it searches; the detector asks it
  for the Tier 2 texts (markers and hints included) inside the same
  transaction (`prepare`), and scores outside it. `texts()` and `--diff`
  read the same way.
- Each corpus a reader gets is cut for the call (`TextCorpus.cut`) and
  immutable; threads share the store, never a call's corpus.
- Same-text groups come from the rows as a build makes them
  (`textcorpus.group_names`: the least ID of a group names it; its first
  licence in `license_index` order gives its text).
- Lookups bind at most 804 values a query (800 names and the 4 entry kinds:
  `textentries.CHUNK`).

### 3. Checked before use

An entry is used only when its rows are text, not empty, those of an entry
(a text, a core exactly when the row has one, regions only with their
codes), and its check equals the one computed from them. The check is
compared before a `CodedText` is made: a text edited under a stored region
used to raise `IndexError` (a region past the last token).

Anything else drops the stored codes of that database: the corpus is built
in memory from the rows (`TextCorpus.build`), never written back, and the
call that found the damage takes its corpus from it; it does not start
again. Later calls at the same time use that corpus.

| Damage | Found |
| - | - |
| Head check changed or missing, a head body changed, not JSON, not text, duplicate words, a negative count | at the first read of the call |
| A `last_update_datetime` written by hand (the head's check holds the time) | at the first read |
| An entry's check changed or missing, its codes or regions changed, a blob, a body cut short, a text edited | when that entry is read |
| `text_code_checks` missing, a view, with a rowid, a column missing | not ready (`empty`) |
| A row SQLite cannot decode as text | `DatabaseNotReadyError` (`unreadable`) |

Known limit: a text edited by hand without a new `last_update_datetime`
leaves the head and the postings valid. The entry's check catches it when
that entry is read; until then the postings, the core gram counts and the
vocabulary may be those of the old text, and nothing says so.

### 4. Measured

Harness of the speed plan, layer 11 copied as `T6-base` and run the same
hour as `T6-2` (load average 2 to 3.5: read times as ratios). Answers: 0
fields differ in every set (core, prose, many, cjk, options, roadmap,
stress); the texts read per candidate equal the whole corpus of layer 11
character for character (679 entries for 708 licences, one at a time and
all at once); `python -m tools.golden` as the golden.

| Item | Layer 11 | T6 |
| - | - | - |
| One call (CLI, min of 11): MIT file | 309 ms | 156 ms |
| BSD-3-Clause / Apache-2.0 file | 321 / 320 ms | 172 / 172 ms |
| GPL-3.0 long text / no answer | 417 / 306 ms | 257 / 160 ms |
| An ID value (the floor: start-up, imports) | 141 ms | 141 ms |
| Core CPU | 20.9 s | 20.8 s |
| Many set CPU | 85.2 s | 85.3 s |
| Peak memory, 868 inputs (1 input) | 99.1 MB (78.9) | 97.6 MB (66.5) |
| Threads, 4 x 150 items | differing 0 | differing 0, errors 0 |
| Damage kinds equal to their reference | 25 | 25 |
| `update`, three runs | 4.39 to 4.45 s | 4.45 to 4.52 s |
| Database file | 28,147,712 bytes | 28,217,344 bytes |

Where a call of the MIT file goes, in process: imports about 100 ms; the
head (one query, JSON of 11,000 words, the groups) about 4 ms; the entries
of the texts searched and scored (64 for BSD-3-Clause) about 5 ms; the rest
is the search and Tier 2 of earlier tasks. Loading all 679 entries costs
about as much as the whole-corpus restore did (110 to 140 ms): a process
that compares every text pays it once either way.

The harness warms each set with one call before it times: on layer 11 that
call restored the whole corpus, so per-input times of small sets read new
entries on T6 only (roadmap 61 and 68 1.4 to 1.6 times per input). Whole
processes, warm-up included, are faster on T6: roadmap 2.97 to 2.86 s, cjk
0.56 to 0.43 s, options 1.22 to 1.10 s of CPU. The one-call gate (150 ms for
MIT and BSD-3-Clause) is not met: the floor of a call that reads no text is
141 ms on this machine.

### 5. Decisions beyond the plan

- The head's check holds `last_update_datetime`, as the postings' stamp
  does: an edit made with a new time is found at the head, before any
  entry, and every stored code of the old time is dropped.
- Core gram counts are stored in the head: the whole-text search asks
  about 400 cores a call (`gramselect.searched`), and counting them from
  the texts costs about 70 ms.
- One failed entry drops the stored codes of the whole database, not that
  entry alone: a damaged file is rare, and one rule is easier to test.
- `TextCorpus.cut` moved from `textcandidates` to `textcorpus`;
  `read_text_parts` from `dbcache` to `textentries`; `textstore.restore` and
  the whole-corpus check removed (no caller needs them).
