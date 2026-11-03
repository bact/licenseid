---
Created: 2026-11-03
Last-Modified: 2026-11-03
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Reading the database while `update` rebuilds it

Status: design, for 0.8. Not built.

## The problem

`update` rebuilds the database in place, in three steps that commit apart
(`database.py`, `_update_db_records`):

1. one transaction deletes every row, `db_metadata` included, and inserts
   the new licences, index rows and exceptions;
2. `store_fingerprints` reads the committed full-text table and writes the
   fingerprints in a second transaction (seconds);
3. a third transaction writes `license_list_version`; then `VACUUM`.

Between the end of step 1 and step 3 the file has no
`license_list_version`, so `dbcheck` calls it `empty`. A reader in that
window (`detect`, `resolve`, `is-*`, or a long-lived `licenseid.detect()`)
fails with `database: empty: <path>; run 'licenseid update'`: it is told to
run the update that is already running. The 0.7.0 review measured 1,074
such errors against 634 answers from four reader threads during one 13 s
`update --force`. 0.6.0 behaves the same.

`VACUUM` also takes an exclusive lock for its whole run; a reader then
waits up to the connection's busy timeout (Python's default, 5 s) or fails
`database is locked`.

## Proposal A: an "update in progress" marker (the maintainer's sketch)

`update` writes a marker when it starts (a lock file beside the database,
or a flag row) and removes it at the end. A reader that finds the database
`empty` or unreadable checks the marker and says so:
`ERROR: database: update in progress: <path>`, and maybe waits.

It works for the message, but on its own it leaves four problems:

- **Stale marker.** A crash, a kill or a power cut leaves the file behind,
  and every later reader is told an update is running when none is. A
  plain file needs a process ID, a host name and a time to be judged stale,
  and a process ID cannot be checked on another host (a home directory on
  NFS). An operating-system lock (`fcntl.flock` on POSIX,
  `msvcrt.locking` on Windows) held by `update` for its run avoids this:
  the system drops it when the process ends, so "the lock is held" means
  "an update is running" with no stale state.
- **A flag inside the database** cannot be read while the writer holds its
  exclusive lock, and it is gone with the rest of `db_metadata` at step 1
  unless written again in the same transaction.
- **Readers still fail.** The marker improves the message; the reader
  still gets no answer for the length of the rebuild.
- **A race.** The reader judges `empty`, then looks for the marker after
  `update` has finished and removed it: the old, wrong message again. The
  reader has to look again at the database after it sees no marker.

## Proposal B: never show a half-built database (recommended)

Make the rebuild one transaction, so a reader sees the old database until
the new one is complete, and then the new one:

1. Steps 1-3 in one transaction on one connection, the version stamp
   last. FTS5 reads its own uncommitted rows on the same connection, so
   the fingerprints can be computed inside it; this removes the reason the
   steps were split. A failure rolls everything back: the old database
   stays, stamped and usable, which is better than today's "a failed run
   leaves a database it does not skip".
2. The database stays in rollback-journal mode (not WAL, see AGENTS.md).
   Readers keep reading the old pages while the writer holds its RESERVED
   lock; they wait only during the commit itself (PENDING then EXCLUSIVE,
   milliseconds for a 17 MB file). Reader connections set
   `PRAGMA busy_timeout` (for example 10 s) so that wait is not an error.
3. Drop the `VACUUM` after the write, or replace it: a rebuild that deletes
   every row and inserts them again leaves free pages the next rebuild
   reuses, so the file does not grow without bound. If the size matters,
   `VACUUM INTO` a temporary file and replace (option C).

Cost: the writer's journal holds the old pages, about the size of the
database, for the length of the run. That is the same disk space as
option C.

## Option C: build beside, then replace

Build the new database in a temporary file in the same directory and
`os.replace` it over the old one. On POSIX the replace is atomic and open
readers keep the old file until they close it. On Windows `os.replace`
fails while any reader has the file open (SQLite opens it without
`FILE_SHARE_DELETE`), so `update` would need a retry loop, and a
long-lived `licenseid.detect()` that keeps a connection open could block it
for ever. `dbcache.TableCache` would also need to notice a new file, not
only a new `last_update_datetime`. Simpler than B on POSIX, worse on
Windows; keep it in reserve for `VACUUM INTO`.

## Recommendation for 0.8

- B, the single transaction, as the fix: readers never see `empty` during
  an update, and they wait briefly at the commit instead of failing.
- Plus the operating-system lock of A, held by `update` for its run, used
  for two things only: a second `update` refuses at once
  (`ERROR: database: update in progress: <path>`) instead of rebuilding in
  parallel, and a reader whose wait times out reports
  `update in progress` instead of `locked` or `empty`. No marker file is
  ever judged by its contents, so none can be stale.
- New condition for the grammar list in AGENTS.md: `update in progress`.
- Tests: a reader thread running `detect()` in a loop during
  `update_from_remote` on a seeded database gives only answers, never
  `DatabaseNotReadyError`; a second `update` while the lock is held exits 1
  with the new line; a killed `update` (child process, SIGKILL) leaves no
  lock and the old database usable. Windows CI runs the first two.
