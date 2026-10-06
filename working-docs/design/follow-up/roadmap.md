---
Created: 2026-10-06
Last-Modified: 2026-10-06
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Follow-up roadmap: Windows and cross-platform

Findings from the review rounds on PR #77 and the Windows review after it
that no PR has fixed yet. Each item says how sure we are: *confirmed* (shown
by a run or a simulation) or *plausible* (read from code or documentation,
not run on Windows). Nothing here is a decision; items may be dropped.

Order within a section is by value, highest first.

## Needs a decision

- **Default data directory.** `~/.local/share/licenseid` works on Windows
  (`C:\Users\<user>\.local\share\licenseid`) but is not the convention, and
  no document records why. `XDG_DATA_HOME` is honoured on no OS, yet a test
  clears it from the environment, as if it were.
  - A: honour an absolute `XDG_DATA_HOME` on every OS. No path change for
    existing users.
  - B: add an override variable (for example `LICENSEID_DB`) for CI,
    containers and services, checked with the same rules as `--db`.
  - C: `%LOCALAPPDATA%\licenseid` on Windows. Conventional, and an alpha has
    no compatibility cost, but docs need a path per OS, `safe_home` must
    patch `LOCALAPPDATA`, and Microsoft Store Python redirects that folder.
  - D: `platformdirs`. Rejected for now: a new dependency on the match path
    that also moves the macOS and Linux locations.
  - Record the outcome in
    `working-docs/implementation/data-fetching-and-caching.md`.
- **Argument expansion by click on Windows.** click expands `~`, `%VAR%`
  and wildcards in every argument when `os.name == "nt"`. `--text 'Copyright
  %USERNAME%'` changes, and `20[0-9][0-9]*` can become a file name, so the
  same command gives other input than on POSIX (confirmed from click's
  source). Turning it off (`windows_expand_args=False`) would also stop
  `licenseid match *.txt`, which Windows users may expect. Options: keep it,
  turn it off, or turn it off for `--text` and `--id` only (click cannot do
  that per option, so the values would need a different path).
- **UTF-16 input.** A file with a UTF-16 byte order mark (PowerShell 5.1's
  `>`, Notepad's "Unicode") is refused as `input: binary file`, because the
  NUL check comes first (confirmed). Decide whether `textinput` should
  decode a UTF-16 BOM, with a warning.

## Windows runtime behaviour to confirm on Windows

- **A closed pipe reader** (plausible). Windows reports a write to a pipe
  whose reader left as `OSError(EINVAL)` (or WinError 232), not
  `BrokenPipeError`, so `licenseid match … | more` would print
  `ERROR: output: write failed: Invalid argument` and exit 2 instead of
  ending quietly. Check on a real pipe before changing `output.py`.
- **Escape codes on the legacy console** (plausible, low). `--diff` colour
  prints `←[32m` in the old console host; Windows Terminal is fine. Enable
  escape processing on `win32`, or leave `--diff` plain there.
- **Windows device names** (plausible). `licenseid match CON` finds that
  `os.path.exists("CON")` is true and reads the console.
- **Ctrl-C while modules load** (plausible, low). It exits with
  `0xC000013A`, not 130, because it comes before `main()`'s `try`.
- **Drive-relative paths on Python 3.10 and 3.11** (plausible). `Path("C:x")
  .absolute()` stays `C:x` when the current directory is on another drive;
  3.12 and later resolve it. The URI becomes `file:///C:x`.
- **UNC and `\\?\` paths** (plausible). `\\server\share\db` gives
  `file:////server/share/db`, which SQLite parses; whether it opens the file
  is untested. A `\\?\C:\…` path becomes `file:////%3F/C:/…`; whether Win32
  takes the forward-slash form is also untested.

## Wording and small inconsistencies

- **Invalid UTF-8 in the text argument** (confirmed, found on POSIX, older
  than #77). `licenseid match $'…\xff…'` exits 1 with a traceback: a lone
  surrogate reaches `database.get_license_by_name`, and `sqlite3` raises
  `UnicodeEncodeError`. Exit 1 reads as "no". Decode or refuse the argument
  at the CLI input boundary.

- **`%FF` in a `file:` URI on Windows.** The write guard says
  `database: invalid` (a file licenseid did not build) and the read check
  says `unreadable`, for a name that cannot be decoded. Safe, but `not found`
  would be more exact.
- **`--clear-cache` with a held tarball.** The database, `licenses.json` and
  `popularity.csv` are deleted, then the tarball delete fails, reported as
  `database: delete failed: …` where the grammar wants the cache file name
  as the subject (`spdx-data-v<ver>.tar.gz`). Recoverable.
- **`file:` URI databases keep a connection open** (`_keep_alive`) with no
  `close()`, so in one process a later `clear_cache` of the same file fails
  on Windows until the object is collected. Keep it only for memory URIs,
  or add `close()` and context-manager support. The CLI is unaffected.
- **`update` for a URI that names no file** (a `vfs=` URI, another host, an
  undecodable name, `mode=memory`) still takes the cache directory from
  `Path(<URI>)`. The CLI's write guard refuses these; direct API callers do
  not get that.
- **Newlines.** The positional argument (`cli.py`) and `match(text=…)` skip
  `normalize_newlines`, which `--text` applies. CRLF changed no result over
  359 fixtures, but `normalize.strip_comment_prefixes` leaves ` */` on CRLF
  input.

## CI and tests

- **More Windows legs.** Only Python 3.11 runs on `windows-latest`. Python
  3.13 changed `ntpath.isabs`; consider 3.14 as well or instead.
- **Tarball member `C:\…`.** The absolute-name case checks the refusal on
  Windows; a `/evil.txt` member is tested on every OS.
- **`truncated_1` on Windows.** It expects `unreadable` there because SQLite's
  Unix file layer reads a 1-byte file as empty and the Windows layer does
  not; say so in the comment next to the variant.
- **Real tests of the Windows-only paths.** The `file:` URI cases build
  their text with `Path.as_posix()`; add a case with a UNC path when a
  Windows runner can open one without a network lookup.
