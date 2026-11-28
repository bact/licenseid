---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "The texts in a plain table (build 10)"
---

## The texts in a plain table (build 10)

Status: task T7 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`, decisions D5 and D6), built
2026-11-27 on layer 12, not merged. The FTS5 table is gone; the texts are in
a plain table. Measurements: Apple M-series, Python 3.10, SPDX License List
3.29.0, a machine shared with other runs (load average 4 to 7).

### 1. What is stored

- `license_texts (text_id INTEGER PRIMARY KEY, license_id TEXT, search_text
  TEXT)`: one row per text, in List order. `text_id` is the rowid, so it
  holds through `VACUUM` and every reader that kept a rowid
  (`TableCache.index_rows`, `candidate_rows`, the postings' text numbers,
  `textentries.read_rows`, the fingerprints) reads the same numbers as from
  the FTS5 table, whose rowids were also 1 to N in insertion order. No index
  on `license_id`: a lookup by ID goes through `index_rows` (read once per
  `last_update_datetime`), so it never scans.
- `dbschema.has_shape` checks the key: a `license_texts` whose `text_id` is
  not its one `INTEGER PRIMARY KEY` (`ROWID_KEYS`) is missing, so `empty`,
  as a view or a table without the rowid is.
- `records.BUILD_VERSION` 10. No reader of an older shape: a file of builds 7
  to 9 is `build vN outdated` and `update` builds it again from nothing.
- The FTS5 table `license_index` and its shadow tables
  (`dbschema.RETIRED_TABLES`, `RETIRED_SHADOWS`) are known for two things
  only: `dbverdict` counts them as licenseid's (a 0.9.x file is `outdated`,
  not `invalid`), and `replace_schema` drops them, then any table left whose
  name starts `license_index_` (a shadow table without its FTS5 table),
  quoted. A plain table named `license_index` was never licenseid's: still
  `invalid`.

### 2. Sizes

The List 3.29.0 built by `update`, by table (`dbstat`, MB):

| Object | Build 9 (layer 12) | Build 10 |
| --- | ---: | ---: |
| `license_index_data` (FTS5 trigram index) | 10.281 | - |
| `license_index_content` / `license_texts` | 4.772 | 4.772 |
| `licenses` | 4.104 | 4.104 |
| `text_postings` | 3.396 | 3.396 |
| `text_codes` | 3.363 | 3.363 |
| `license_fingerprints` and its two indexes | 1.974 | 1.974 |
| the rest | 0.327 | 0.270 |
| file | 28.217 | 17.879 |

The 0.9.4 file is 24.7 MB. `update` from the packaged tarball, three runs
each, alternated: build 9 4.30, 4.29, 4.37 s (user 4.10 to 4.15 s), build 10
4.09, 4.09, 4.10 s (user 3.95 to 3.96 s): the trigram index cost 0.2 s to
build.

### 3. Older and damaged files

- A file of 0.9.4 (build 7) and the FTS5 shapes of builds 8 and 9: every
  lookup exits 2, `database: build v7 outdated: current v10; run 'licenseid
  update'`, and writes nothing; `update` rebuilds it; `clear-cache` deletes
  it.
- A damaged FTS5 table is never read. `update` drops it: SQLite drops an
  FTS5 table without its `data`, `content`, `docsize` or `idx` shadow table.
  Without `config` the drop fails (`vtable constructor failed:
  license_index`), so `update` exits 1 with `database: update failed:
  ...`, one line, the file unchanged; `clear-cache` deletes the file. Not
  cured by `PRAGMA writable_schema`: that writes `sqlite_master` by hand.
- An FTS5 table left beside a build 10 file (a script's copy) does not stop
  a lookup; `update` rebuilds the file (`dbverdict.rebuild_refusal`) and
  drops it.
- The two damaged-FTS tests of `test_db_ready_adversarial.py`, which failed
  on macOS (SQLite 3.51.0 is defensive: a shadow table cannot be dropped or
  written), are gone with the table. `tests/test_text_table.py` damages each
  shadow table by renaming it in the file's bytes (same length), which works
  on every SQLite, and asserts what the lookup and `update` say.

### 4. One verdict per call; the norm columns where they are read

- The verdict of a file (`dbverdict.connection_refusal`, moved from
  `dbcheck`, which was past its line limit) was made twice per call: by
  `check_database_ready`, then by `LicenseDatabase(path, create=False)`. A
  caller that has just checked now opens `database.judged_database(path)`,
  which reads the metadata only (a file gone since is still `not found`, a
  hot journal still rolled back). `detect`, `is-*`, `resolve --db`,
  `LicenseDetector` and `resolve(db=...)` make one; `resolve` from the CLI
  with `--db` makes two (`listsource` checks a handle it is given), down
  from three. `tests/test_text_table.py` counts them.
- The verdict scanned every licence row for a norm column that is not text.
  That check is now made where the names are first read
  (`TableCache.names_and_ids`), same refusal (`database: empty: <path>; run
  'licenseid update'`), and `update` still rebuilds such a file
  (`rebuild_refusal`). A lookup that never reads the names (`resolve` by
  ID) answers on such a file.
- Measured on the real List: one verdict 0.265 ms on layer 12 (with the
  norm scan), 0.203 ms now; `LicenseDetector(path)` 1.34 ms, now 0.61 ms
  (CPU, mean of 50).

### 5. Gates

Two runs of layer 12 (`T7-base`, `T7-base2`) and two of this tree (`T7-1`,
`T7-2`), one after the other in the same hour, every set; load average 3 to 8
(other runs shared the machine).

- Database size: 17.9 MB, PASS (layer 12: 28.2 MB, FAIL).
- Versions: PASS on both runs. Each of `detect`, `detect --id`, `resolve`,
  `is-osi`, `is-fsf`, `is-spdx`, `LicenseDetector`, `resolve(db=)` on a copy
  of the 0.9.4 file: exit 2, `ERROR: database: build v7 outdated: current
  v10; run 'licenseid update'`, the file's bytes, time and folder unchanged.
  `update` then: exit 0, every table and row (but the timed stamps) and
  three answers equal to a fresh build's. `clear-cache`: deleted. 0.9.4 on
  a copy of the build 10 file: all eight commands, `update` and
  `clear-cache` too, exit 2 `ERROR: database: invalid: <path>`, nothing
  written. `resolve()` with the 0.9.4 file at the default path reads the
  shipped list with `database: build v7 outdated: current v10; using
  packaged data v3.29.0`, file unchanged, as layer 12 does (checked with
  the fixtures' bundle; the sides have no bundle, so the set records exit
  2 there).
- Storage alone: no field moved in any of 32 sets and damage kinds both
  have; the golden answers are those of layer 12. Core CPU: layer 12 25.9
  and 23.0 s (twin spread 1.128x), build 10 21.2 and 21.3 s: faster by
  1.22x, past the twin's spread, so the gate as written (CPU within the
  noise, either way) fails; it is not slower. The 200 first long fixtures
  in one process take 4.92 and 4.90 s on both sides, and the kana stress
  input 352 to 360 ms on both: no input class is slower.
- Against 0.9.4 (`compare` with its twin): core 16.7 and 16.6 times
  (layer 12: 13.6 and 15.4), real file median 9.9 and 9.3 ms, damage 29
  kinds equal their reference, memory peak 106 and 99 MB (0.9.4: 109).
  "No class slower" failed on `T7-1` (five stress inputs 1.21 to 1.36x,
  kana 1.32x, at a load of 8) and passed on `T7-2` (worst 1.05x). One call,
  Fixtures and Roadmap inputs fail as on layer 12.

### 6. Decisions beyond the plan

- The CLI builds its detector before it reads the input, so the database is
  still reported first, through the one verdict; a `WARNING: database:
  build vN newer` now comes before a usage error about the input.
- `clear-cache` moved to `dbclear` (`clear_database`), to keep
  `database.py` under its size.
- A `license_texts` with columns licenseid does not write is `invalid`; any
  other misshape of it (no key, a view, no rowid) is `empty`.
- The Storage alone gate allows at least 3 percent of core CPU
  (`speedgate/storage.py`, `NOISE_FLOOR`), as two runs of one side differ
  by that much on this machine.

### 7. Paths rejected

- A contentless or external-content FTS5 table: still a virtual table that
  needs FTS5 in the SQLite build, still shadow tables to damage, and nothing
  reads its index.
- A `WITHOUT ROWID` table keyed by ID: an ID can have several texts, and the
  rowid keeps List order, which ranking ties and the postings rely on.
- Reading the old table, or copying its rows into the new one in place:
  the one-shape rule (D6) has no reader of an older shape, and `update`
  builds the rest of the file from nothing anyway.
