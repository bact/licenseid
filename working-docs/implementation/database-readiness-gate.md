---
Created: 2026-09-20
Last-Modified: 2026-09-20
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
