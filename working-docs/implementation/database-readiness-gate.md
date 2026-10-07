---
Created: 2026-09-20
Last-Modified: 2026-10-07
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Database readiness gate (PR #55)

What shipped is in `CHANGELOG.md`; the open items are in
[`../design/tech-debt-roadmap.md`](../design/tech-debt-roadmap.md) item 10.
This file records what was counter-intuitive, what took several rounds to
find, and the habits that produced or caught those findings.

## The shape of the answer

`src/licenseid/dbcheck.py` answers two different questions, and they are
not symmetric:

- **Read** (`match`, the `is-*` commands, the API constructor) is
  **fail-open**: `check_database_ready` refuses only a condition it is sure
  of. A wrong refusal costs the user an answer they could have had.
- **Write and delete** (`update`, `--clear-cache`,
  `LicenseDatabase.clear_cache`) are **fail-closed**:
  `reject_foreign_database` refuses anything it could not inspect. A wrong
  acceptance destroys or overwrites somebody else's file.

The bridge between them is the internal condition tag `unknown` (a locked
database, which cannot be told apart from a hot rollback journal the probe
may not replay). Read ignores it; write and delete refuse it. A `Refusal`
is `tuple[str, DatabaseNotReadyError]` — tag plus the exception — so the
two callers can apply different policy to the same finding. Without the
tag, every attempt to serve both callers from one boolean produced a bug in
one of them.

## SQLite and path traps

Each of these cost at least one review round.

- **A named pipe hangs the process.** `open(O_RDONLY)` on a FIFO blocks
  until a writer appears, so `--db` naming one produced no output, no exit
  code and no traceback. Check the file type with `stat.S_ISREG` /
  `S_ISDIR` **before** opening. This is the only failure mode in the PR
  that no test could have caught by assertion — the test would have hung
  too.
- **One file has many spellings.** `licenses.db`, `licenses.db/` and
  `licenses.db/.` are the same file to the OS; `file:`, `file://` and
  `file://localhost/` are the same file to SQLite. The first fix was an
  `endswith("/")` patch, which was wrong at the next depth (`/.`).
  Normalise once, in `_os_file` (`str(Path(...))`), and let every caller
  read that. An anti-pattern worth naming: patching the spelling at the
  call site instead of at the resolver.
- **`file::memory:NAME` is a file on disk**, not a memory database. Only
  `mode=memory` and the exact base `file::memory:` are memory. Treating the
  prefix as memory made `--clear-cache` silently do nothing and a read
  create a file.
- **Two notions of "the path" are needed**, and merging them broke a
  legitimate case. `_os_file` is what the OS would open (used for the
  blocking-file-type check, so a `vfs=` URI is still checked); `named_file`
  is what licenseid may act on, and is `None` for a URI with its own VFS,
  another host or in-memory. Deleting what `_os_file` returns would delete
  a file a `vfs=memdb` database never used.
- **`mode=ro` cannot create `-shm` or replay a hot journal.** Every
  database licenseid writes is in WAL mode, so a read-only mount fails at
  the real open with `attempt to write a readonly database`. The gate gives
  no verdict for that text (`_NEEDS_WRITING`), deliberately: refusing there
  would also block `--clear-cache` from removing a damaged WAL database.
  `immutable=1` was tried and dropped — it turns locking off, so a read
  during an `update` could see a torn file.
- **`database is locked` is not an error to report.** It means "ask again
  later", so it maps to `unknown`, not `unreadable`. The probe waits
  `_BUSY_WAIT = 1.0` s rather than SQLite's default 5 s, because the real
  command re-opens and waits again straight after.
- **Table names collide with other programs.** `licenses` and
  `db_metadata` are common enough to appear in a seat inventory or an asset
  register. Classifying such a file as `empty` printed
  `run 'licenseid update'`, and `update` then wrote licenseid's schema into
  somebody's database. A table of ours whose columns are not ours is
  `invalid`, with no hint (`_foreign_schema`). The check also verifies that
  `license_index` is FTS5, since a plain table of that name passes a naive
  existence test.

## Test traps

- **`Path.unlink(missing_ok=True)` swallows `FileNotFoundError` only.** A
  path whose parent is a file raises `NotADirectoryError` straight through
  it. Use `contextlib.suppress(OSError)` where any missing-path shape is
  acceptable.
- **`HOME` alone does not protect the real cache.** `Path.home()` is
  patched too, in the autouse `safe_home` fixture in `tests/db_asserts.py`.
  Any new database test file must import that fixture (and needs
  `# noqa: F401  # pylint: disable=unused-import`, since it looks unused).
- **Splitting a test file trips pylint R0801.** Shared fixtures and helpers
  move to `tests/db_asserts.py`; do not copy them into both halves.
- **Mutation-check every new guard.** Breaking one line of
  `_foreign_schema` and of the views variant in `tests/db_variants.py` both
  showed tests that passed for the wrong reason.

## Process notes

- **Do not run a mutation agent while another agent edits `src/`.** One
  round produced a snapshot of `src/` that had captured a live mutant of
  `database.py`; the finding was a phantom. Diff any snapshot against the
  working tree before trusting a result taken from it.
- **A `FIXED_FLAG` from `tools/cli_matrix` is not proof of a fix.** Cell
  `E4-028` (`ulimit -f 0`) stopped flagging because the command now fails
  *earlier*, at the database open, not because the unhandled standard
  output write was fixed. Read the recorded cell output before removing a
  baseline line, and say in the roadmap why the line went.
- **A ceiling is a ratchet.** `database.py` crossed `max-module-lines`
  three times during this work. The fix each time was to move a cohesive
  piece out (cache clearing went to `spdx_source.clear_cache_files`), never
  to raise the number; afterwards the ceiling was lowered to the new exact
  maximum (931 → 926).
- **Judging convergence.** Review rounds 4 to 7 each found something, which
  looks like a gate that will not stabilise. Reading where the findings
  came from told a different story: the readiness gate itself was clean for
  the last two rounds, and every new finding came from the write/delete
  guard added in round 4 — code being reviewed for the first time. Count
  findings per surface, not per round.

## After the gate: lookups (0.4.2)

The gate runs once, at construction. A database that failed later used to
raise a raw `sqlite3.Error`, and a lookup re-created a deleted file as an
empty one, so the next matcher said `empty` instead of `not found`.

- **Read-only by default.** `Connections.connect(write=False)` opens
  `dbcheck.open_uri(path)` (`mode=ro`). A write opens the file as given only
  when the database was made to `create` it (`update`, tests); the matcher's
  `create=False` opens `open_uri(path, "rw")`, which fails on a file that is
  gone. A user URI that says `mode=ro` or `immutable=1` is never upgraded. A
  write inside a `reading()` block gets its own connection, since the shared
  one is read-only.
- **One wording, at the one place every read passes.**
  `Connections.connection` words a `sqlite3.Error` of a read as
  `DatabaseNotReadyError` through `dbcheck.lookup_error`: `match`, the `is_*`
  calls, a direct `LicenseDatabase` read and a standalone `MarkerDetector`
  agree (a first version wrapped three matcher methods and left the rest raw).
  Every `sqlite3.Error` is wrapped, `ProgrammingError` and `InterfaceError`
  too, and the CLI does the same; the original is the `__cause__`. A write of
  a database made with `create` keeps its error: `update` words it
  (`database: update failed: <Type>: <text>`, exit 1, since `update` failures
  exit 1; a `DatabaseNotReadyError` without a cause passes unchanged).
- **The action** `run 'licenseid update'` is only for a file `update` can
  rebuild (`dbcheck._can_rebuild`: `no such table`, or `unable to open` a
  file that is gone). `update` refuses a file that is not a database, fails
  on a malformed one, and cannot open one that is there but unreadable.
- **The constructor** (`LicenseDatabase(path, create=True)`): `_init_db` asks
  `dbschema.schema_state` through a read-only connection and writes only for
  an older schema (`older`, migrated in place, only if
  `reject_foreign_database` finds the file licenseid's own) or, with
  `create`, for a missing file or tables (`none`). The matcher passes
  `create=False`, so a file deleted between the readiness check and the
  constructor raises `not found`, where it used to be re-created empty and
  answer `false`. A hot journal, or a WAL without its `-shm`, makes the
  read-only open fail with `readonly`; the constructor opens once for writing
  and reads (`Connections.recover`) to heal it. A journal that appears after
  the constructor is not healed: the lookup says so.
- **No WAL.** `update` wrote in WAL mode (`journal_mode=WAL`, `synchronous=
  NORMAL`) for no recorded reason: the same write took 430 ms in rollback
  mode and 473 ms in WAL on this machine. A read-only connection cannot
  remove the `-wal` and `-shm` files a WAL database gets, a read-only mount
  cannot create them, and switching a database to WAL needs a lock a reader
  holds. `update` now leaves WAL (`Connections.leave_wal`, never waiting for
  a lock) at its start, also when there is nothing to download.
- **Rows without norm columns** are normalised in memory
  (`TableCache.names_and_ids`), not written back, so a lookup works on a
  read-only install. The columns are only added to an older schema.
- **Searches forgive nothing.** `search_candidates` quotes each word, so an
  FTS5 operator in the text is a phrase and no query fails for its own text;
  every `sqlite3.Error` is the database's. `find_fingerprint_hits` forgives
  nothing either: opening a database creates its table.
- **The FIFO.** A read-only open of a named pipe, or of its `-journal` or
  `-wal`, waits for ever; `reject_blocking_file` stats the three before every
  connection, and the gate's own open (`_path_problem`) stats the sidecars
  too.
- **Version last.** `update` stamps `license_list_version` after the
  fingerprints. With the rollback journal a reader can fail the fingerprint
  commit with `database is locked`; stamped first, the version would make the
  next plain `update` skip the missing fingerprints for ever. `create_schema`
  is one `BEGIN IMMEDIATE` transaction, so two processes opening an older
  database do not both run `ALTER TABLE`.
- **One path, for reads and writes.** `Connections` makes a plain relative
  path absolute (and pins a relative `file:` URI) once, and
  `LicenseDatabase.db_path` is absolute, so the cache follows the database
  after a `chdir`. A `\\?\` prefix is dropped from the URI, and a NUL in a
  path is refused, as SQLite would read the name up to it.
- **Left open.** A lock is worded `unreadable` (a new condition would change
  the closed set in `AGENTS.md`); a hot journal that appears after the
  constructor is not healed; a read-only database that lacks `idx_licenses_name`
  or the fingerprint table is refused, as it was before; a lookup on a
  database an earlier version left in WAL mode creates `-shm` and `-wal`
  (the read-only connection cannot remove them) until `update` converts it.

## Input never builds a SQL pattern

An overlong licence ID ending in `+` (via `match(license_id=...)`, an
SPDX-License-Identifier tag, a `License:` line, or a JSON/TOML field)
made a healthy database look broken: `LicenseDatabase.get_license_by_id_prefix`
built a LIKE pattern from input, and SQLite refuses a pattern over 50,000 bytes
with `LIKE or GLOB pattern too complex`. `Connections.connection()` reports
every read `sqlite3.Error` as `DatabaseNotReadyError`, so the result was
an avoidable `DatabaseNotReadyError` on a working database.

The fix moves the prefix match into memory.
`dbcache.TableCache.active_id_with_prefix` scans the cached ID list (ASCII
case fold like LIKE, active IDs only, same shortest-unambiguous rule) and
finds the prefix. The exact row is then read from the database with `=` on
the ID. An unknown prefix costs no query, and input of any length is handled.

A length guard on the LIKE pattern was rejected: it would keep an input-built
pattern in SQL, require a magic constant or an extra MAX(LENGTH) query,
and still allow other characters through; no pattern from untrusted input
should reach SQLite.
