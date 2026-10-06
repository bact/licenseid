---
Created: 2026-10-06
Last-Modified: 2026-10-06
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Cross-platform support (Windows) — what was built

A record of the Windows work in PR #77 (after the 0.4.0 release): the bug,
the rules that came out of it, how the tests deal with Windows, and what we
know from a real Windows run versus what we only simulated. Open items are
in [`../design/cross-platform-roadmap.md`](../design/cross-platform-roadmap.md).

## The bug in 0.4.0

On Windows every `match` failed with `database: unreadable`. The readiness
check (`dbcheck.open_uri` (then `_read_only_uri`)) built `file://C%3A%5CUsers%5C…?mode=ro`.
SQLite reads the text after `file://` up to the first `/` as the authority,
and refused it (`invalid uri authority`). `licenseid update` passed on
Windows because it never goes through the readiness check. Linux and macOS
were fine. Found in Pitloom's Windows CI.

## Rules that came out of it

- **A plain path becomes `file:///C:/…`.** `_plain_path_uri` uses
  `as_posix()` (forward slashes), puts a `/` before a drive letter, and
  quotes with `safe='/:'`. The authority stays empty, so a POSIX path that
  starts with `//` is not read as a host. A UNC path gives
  `file:////server/share/…`; SQLite parses it, but nobody has opened one.
- **A `file:` URI keeps its drive in the OS path.** `_uri_file_path` drops
  the `/` before a drive letter on Windows only (`_IS_WINDOWS`, ASCII letters
  only, as SQLite does). On POSIX `/C:/x` is a real path. Without this,
  `Path("/C:/x")` on Windows has no drive and the stat, write and delete
  guards would act on another file than SQLite opens.
- **A name Windows cannot decode names no file.** `os.fsdecode` uses UTF-8 on
  Windows, so a `%FF` byte raised `UnicodeDecodeError`; `_uri_file_path` now
  returns `None` ("cannot say which file"). Read reports `unreadable` and
  write refuses as `invalid`; both are safe, and `not found` would be more
  exact (see the roadmap).
- **`LicenseDatabase` hands a `file:` URI to SQLite as given.** `Path()`
  turned `file:///C:/x` into `file:\C:\x` on Windows (and collapsed `//` on
  POSIX, which broke `file://localhost/x`). `db_path` itself is the file the
  URI names (`dbcheck.named_file`), so `update` writes its cache beside the
  database and not in a made-up `file:/…` directory.
- **The default path needs a home directory.** `datadir.get_default_db_path`
  raises `DatabaseNotReadyError` (exit 2) when there is none, or when the
  home is empty or relative; the CLI defers that error until a command reads
  `db_path`, so `--help` and a bare run still work.
- **Windows file handles.** `update` never replaces or deletes the `.db`
  file; cache files are written to a unique `.tmp` and `os.replace`d after
  the handle is closed; the extraction directory is removed with
  `ignore_cleanup_errors=True`, so antivirus holding an extracted file cannot
  fail a finished update. A refused tarball write is `cache write failed`.
- **Output.** `cli.main` writes characters stdout cannot encode as
  backslash escapes (a cp1252 pipe), unless the user chose another handler,
  and `echo` turns a leftover `UnicodeEncodeError` into `output: write
  failed` (exit 2).

## Tests on Windows

CI runs Python 3.11 on `windows-latest` (Git Bash) in `test.yml`, next to the
Ubuntu legs. Rules for a test that cannot run there:

- Use `conftest.posix_only` (a `skipif` on `sys.platform == "win32"`) for a
  test that needs permission bits, symlinks, signals, `/bin/sh` or a named
  pipe. Give a reason in a comment when it is not obvious.
- Inside a fixture or builder, call `pytest.skip` (see
  `db_variants._skip_on_windows`) so every parametrised variant skips alone.
- `tests/test_cli_matrix.py` is not collected on Windows (it imports `pwd`,
  `pty`, `termios`); `tools/cli_matrix` refuses Windows before it imports
  them. The refusal test is in `test_cli_matrix_judge.py`, which Windows does
  collect.
- Build a `file://` URI from `Path.as_posix()` with a leading `/`, never
  `f"file://{path}"` (gives `file://C:\…` on Windows).
- Isolate the home with `safe_home` (patches `HOME`, `USERPROFILE` and
  `Path.home`); `Path.home()` ignores `HOME` on Windows.
- Windows paths in a regex need `re.escape`.
- A `TextIOWrapper` made in a test needs `newline="\n"` if the test compares
  bytes: Windows adds `\r`.

What is skipped, and why:

| Group | Why it cannot run on Windows |
|---|---|
| chmod 000 files and directories | chmod only sets a read-only flag |
| symlinks and links | creating one needs a privilege |
| `?`, `:` and newline in a file name | not allowed in Windows file names |
| non-UTF-8 file names | `fsencode` uses UTF-8 with `surrogatepass` |
| `/bin/sh`, SIGINT, exit 141, named pipes | POSIX only |
| `truncated_1` variant | expects `empty` on Unix, `unreadable` on Windows: SQLite's Unix layer reads a 1-byte file as empty, its Windows layer does not |

## Known versus simulated

Seen on a real Windows run (CI on PR #77): the URI fix, `file:///C:/…`,
`file://localhost/…` and `file:C:\…` all open; the new
`test_dbcheck_windows` tests; the tests above skip as intended; pytest's
temporary directories clean up with SQLite connections open.

Only simulated on macOS (patched `os.name`, `PureWindowsPath`, injected
`PermissionError`, `cp1252` wrappers): the `%FF` URI, a held temporary file,
a refused tarball rename, output with an unencodable character, and the
no-home behaviour. Treat them as likely, not proven, until a Windows run
shows them.

## Lookups and the database file (0.4.2)

- A lookup opens the file read-only (`open_uri`), so no handle can create it
  and tests delete, truncate or zero a file between queries. Each query still
  opens and closes its own connection; only a `reading()` block shares one.
- `update` no longer uses WAL, so no `-wal` or `-shm` remains after a lookup,
  which on Windows would make deletes and `tmp_path` clean-up noisier. A
  database built earlier is converted by the next `update`.
- A plain relative path is made absolute (`os.path.abspath`) when
  `Connections` is built, and so is a relative `file:` URI; a `\\?\` prefix is
  dropped. Still simulated, not run on Windows: a UNC path
  (`file:////server/share/x.db`).
- `reject_blocking_file` also looks at `-journal` and `-wal`: a named pipe
  there hangs the open.
- Tests that need `chmod` skip as root (`IS_ROOT`) and on Windows
  (`posix_only`).
