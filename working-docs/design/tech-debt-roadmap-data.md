---
Created: 2026-11-28
Last-Modified: 2026-11-28
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Tech debt roadmap: data, environment, speed and docs

The open items on the database and its files, the environment (locale,
platform, concurrent calls), the cost of a call and the user docs. Split
from [`tech-debt-roadmap.md`](tech-debt-roadmap.md) on 2026-11-28 at the
size limit; that file explains the priority score and the item numbers
(shared by the three files, never reused) and links the resolved items.

## 2. `py-spdx-license` reads its data with the locale encoding — Priority 20

`py_spdx_license/ast.py` (v0.0.1) loads `data/licenses.json` and
`data/exceptions.json` at import time with `Path.open("r")` and no
`encoding`, so Python decodes the files with the locale's preferred
encoding. Both files are UTF-8 (JSON must be, RFC 8259), and
`licenses.json` holds non-ASCII text (`é` in `Licence Libre du Québec`,
the en dash `–` in `Data licence Germany – attribution – version 2.0`).

- **Symptom on a legacy locale**: `licenseid` cannot even start.
  `import licenseid.detector` imports `py_spdx_license`, and under
  `LC_ALL=ja_JP.eucJP` (macOS, checked on Python 3.10) every command dies
  with `UnicodeDecodeError: 'euc_jp' codec can't decode byte 0xe2 in
  position 103585` before any output. Other multibyte locales (cp932 on
  Windows, Big5, GBK) should fail the same way; not tested.
- **Silent variant**: a single-byte legacy encoding such as cp1252 (the
  Windows default in many Western locales) decodes without error and gives
  mojibake, for example `Data licence Germany â€“ attribution â€“ version
  2.0`. Seven license names are affected. `licenseid` uses only IDs and
  expressions from this package, so the visible effect there is none today,
  but the package's own `get_license()` data is wrong.
- **Not affected**: UTF-8 locales, `LC_ALL=C` (Python 3.7+ coerces it to
  UTF-8) and `PYTHONUTF8=1`. Python 3.15 makes UTF-8 the default
  (PEP 686), which hides the bug there.
- **Root cause**: missing `encoding="utf-8"` in two `open()` calls
  (`ast.py` lines 21 and 33). Pylint `unspecified-encoding` (W1514) and
  Python's `-X warn_default_encoding` flag exactly this.
- **Upstream fix** (report and send a pull request to
  `github.com/JPEWdev/py-spdx-license`): use
  `p.open("r", encoding="utf-8")`, or `json.loads(p.read_bytes())`, which
  lets the `json` module detect UTF-8 itself. Add a test that runs the
  import under `-X warn_default_encoding -W error`.
- **Workaround until a release**: `PYTHONUTF8=1`, documented in
  `README.md` (2026-09-28); vendoring the two JSON files was not chosen.
  Importing `py_spdx_license` lazily would only move the crash to marker
  detection, so it is not a cure.
- **Status (2026-09-28)**: upstream pull request
  <https://github.com/JPEWdev/py-spdx-license/pull/5> adds the encoding and
  a test (`tests/test_encoding.py`, import under `-X warn_default_encoding
  -W error::EncodingWarning`). With it, licenseid runs under `ja_JP.eucJP`.
  After a release, raise the minimum `py-spdx-license` version, drop the
  README section and close this item.
- **Status (2026-10-30)**: the pull request was still open and only 0.0.1 was
  on PyPI. 0.7.0 ships with the README workaround (the maintainer chose docs
  only over an import shim that would patch `Path.open` during the import,
  or a parser of our own); `licenseid detect` and `--version` fail the same
  way, at import.
- **Status (2026-11-18)**: the pull request was merged upstream on
  2026-11-10, and only 0.0.1 is on PyPI, so the floor stays and the README
  workaround stays (`docs/installation.md`).
- **Status (2026-11-28)**: 0.10.0 loads `py_spdx_license` where an
  expression is parsed (start-up time), so the crash moved, as the
  workaround note above said it would. Under `ja_JP.eucJP` (Python 3.10 and
  3.14) `--version`, a licence text, one ID, a name, a `WITH` expression, a
  tag with one ID and a predicate on one ID answer; `MIT OR Apache-2.0`,
  `MIT AND ISC` and a tag with `OR` die with the same traceback, exit 1.
  `docs/installation.md` says so.
- The CLI matrix flag of this item is `E2-109` (bash) in
  `tools/cli_matrix/baseline.txt`: `resolve 'MIT OR Apache-2.0'` under the
  eucJP locale, a cell added for 0.10.0. `E2-082` to `E2-090`, its flags up
  to 0.9.4, parse no `AND` or `OR` and pass now.
- Impact 2, Risk 3, Effort 2.

## 10. Environment failures in the database and the API — Priority 12

Found by running the CLI under odd environments (manual matrix, 2026-09-19).
Each case is outside the message grammar or hides a failure. The stream
and signal cases (closed streams, a closed pipe, an output write error,
Ctrl-C) were fixed on 2026-10-02 (`tech-debt-resolved.md`); a replaced
database in 0.4.2 (`database-readiness-gate.md`); a data directory `update`
cannot make, a `file://localhost/` path and symlink loops in PR #209
(2026-11-15, `tech-debt-resolved-0-5.md`). Open: the three cases below.

- **A valid but read-only database** (a read-only mount, a root-owned
  install): every database licenseid writes is in WAL mode, and SQLite must
  create `-shm` beside it even to read. The readiness check gives no verdict
  for this (`_no_verdict`), so the failure now comes from the real open, as
  `database: unreadable: attempt to write a readonly database` (and no
  `run 'licenseid update'` hint, which could not help). Main crashed here
  too, in `LicenseDatabase`. Fix options: copy the file, or open it with
  `immutable=1` when the directory is not writable (safe then, since no
  `update` can be running there).
- **Lock contention** (`database is locked`, for example the first `update`
  that switches a database to WAL, during a `detect`): the readiness check
  cannot tell a busy database from a hot rollback journal it may not replay,
  so it returns the condition `unknown`. A reader goes on and whatever opens
  the file next reports the failure, still worded `database: unreadable`;
  `update` and `--clear-cache` refuse, because a file they could not inspect
  may be anybody's and deleting one needs no lock at all. The probe waits
  `_BUSY_WAIT` (1 s), not SQLite's default 5 s, since the command that
  follows waits again.
- **Ctrl-C during imports** (the first ~30 ms, before click runs): Python
  prints a `KeyboardInterrupt` traceback and dies by SIGINT, which the shell
  reports as 130. Found in review of PR #70; `main` is the same.
- **Open**: `immutable=1` for a read-only valid database. Safe only when
  all hold: a read (never `update`/`clear-cache`); the `mode=ro` open failed
  on an existing regular file; the directory and the file are both not
  writable by this user; no non-empty `-wal` or `-journal` beside it. Another
  user (root, a package manager) updating it still gives torn reads, which
  is why `database-readiness-gate.md` dropped it. Recommendation: keep it
  dropped; only a legacy WAL database on read-only media is affected (since
  0.4.2 `update` leaves WAL).
- Impact 2, Risk 2, Effort 3.

## 57. Keep the user docs true to the code — Priority 15

Found by five verifiers that ran every example and table row of the user
docs before 0.9.0 (2026-11-19). No example was wrong, but the text drifted: a
sample warning no code prints (`download failed: timed out`), `--no-cache`
for `--cache/--no-cache`, "fix waiting upstream" after the merge, two pages
missing from the README, a `—` count column in `docs/lists.md` for rows read
as `listed_name`, a reason in a generated table false for 7 of 13 rows,
promises the code did not keep (`InvalidInputError` for a `Path`, `MIT++`
warns), line numbers of an old commit. Why it slips: a PR that changes only
docs runs no test (`test.yml` skips `docs/**`, `README.md`, `CHANGELOG.md`
but `resolve.md` and `lists.md`; `lint.yml` skips `**.md`), and markdownlint
runs in no workflow.

Built 2026-11-26 (one PR, from a plan of 2026-11-26 that measured each check
on the docs first):

- `.github/workflows/docs.yml` runs on any Markdown change: markdownlint-cli2
  over `**/*.md` (`.markdownlint-cli2.jsonc` leaves out `tests/fixtures/`) and
  the doc tests below with `test_lists_page.py` and `test_resolver_shapes.py`.
- `tests/test_docs_vocabulary.py`: each click option and choice in its
  section of `docs/cli.md`; each step kind, step detail (one example per
  detail, run) and reason condition that `resolve()` gives on the 627 values
  of the resolver fixtures and the worked examples in `docs/resolve.md`, and
  each documented reason given by `resolve()` (`tests/docs_reasons.py` holds
  a value for each the corpus lacks); the keys of the result types and of the
  `detect` record; the category table of `resolve-flow.md`; README links each
  page; relative links and anchors resolve.
- `tests/test_docs_numbers.py`: a table of numbers the prose states
  (`NUMBERS`) against their constants.
- `tests/test_docs_status.py`: line numbers and releases only on the two
  pages pinned to 0.9.0; `TIME_BOUND` (a sentence and the version it was last
  read for); one version in `__init__`, codemeta, CHANGELOG and README; the
  licenseid version the docs show.
- `tests/test_lists_page.py`: each row of `ALIASES` and `TITLES` reads with
  the category and `EXACT` its section states; a key a sample value equals is
  counted. Counting by step stays: it is what a row reads (`New BSD License`
  reaches `new bsd` through P1). The named-rule check was dropped: T1 and T2
  read only tables, and the page computes `EXACT`.
- `tests/test_docs_examples.py` with `tests/docs_blocks.py`: each fenced
  block that shows a result runs (22 blocks: console, `# result` lines,
  Python, `resolve()` JSON, an output block under a `run:` marker), and the 33
  worked examples of `resolve-flow.md`; a block it cannot run carries a
  `skip:` marker; `COUNTS` pins the blocks of each page. In
  `tests/platform_files.py`: it drives the CLI and the default database path.
- Drift fixed: `cli.md` predicates named no input, "no licences yet";
  `resolve-flow.md` missed `assumed_only` on the GNU URL row; the step-detail
  table of `resolve.md` had no example for four details.
- The review habits are in `release-process.md` ("Checks before the tag").

Leftovers: numbers written inline and not in `NUMBERS` (Tier 1's 200 words,
Tier 0's 30) are not checked; the MPL-2.0 `SAME_TEXT` example of `output.md`
is skipped until a long-text fixture holds the MPL-2.0 text; the `bash`
instructions (install, update from the network) are checked by hand before a
tag.

- Impact 2, Risk 3, Effort 3.

## 62. 100,000 `License:` lines on the test database take 25 min — Priority 12

Found by `--run-benchmark` before 0.9.2 (2026-11-24); it fails on v0.9.0 and
v0.9.1 too. `test_100k_distinct_lines_detect_in_bounded_time` (bound 30 s)
takes about 14 ms a line on its seeded in-memory database: 2,000 lines run
about 60 SQL queries a line (119,000 in all), on v0.9.0 (22 s), v0.9.1 (28 s)
and 0.9.2 (35 s; the notice-free head normalises the text again, 1.3x). On a
database `update` built, 8,000 such lines take 1.4 s on 0.9.1 and 0.9.2
alike. Trace the queries per line first (the shared-cache memory database,
`dbcache` checks), then decide whether the test or the code is wrong.

Impact 2, Risk 2, Effort 3.

## 65. Concurrent first calls each load the text corpus — Priority 8

The text corpus is built or read once per database generation in
`dbcache.TableCache`, with no lock: threads that make their first `detect()`
call together each load it (0.016 s from `text_codes`, about 0.05 s since
build 7 stores the regions of item 64; 0.16 s coded). Wasted
work only; the result is the same and the corpus is immutable. Fix with a
lock around the first load if a measurement shows a cost.

Impact 1, Risk 1, Effort 2.

After the engine of 0.10.0 (2026-11-28): the store of loaded entries is
filled under a lock, a call reads its texts one by one (2 to 4 ms, not
the whole corpus), and the corpus a search reads stays immutable
(`../implementation/texts-per-candidate.md`). The final Threads gate: 4
threads, 150 items, 0 differing, errors 0. Open: no count of duplicate
loads under concurrent first calls was taken.

## 66. A misshaped optional table breaks `-v` and `update` — Priority 8

A `text_codes` (or `license_urls`) table that licenseid did not make, with
other columns or as a view, fails the read of `detect -v` and `--json` as
`database: unreadable: no such column` (terse `detect` and `is-*` still
answer), and `update` cannot repair it (`table text_codes has no column
named kind`). Found in review of PR #241; `license_urls` is the same on
0.9.2. Only a hand-edited file gets here. Fix: in `update`, drop an optional
table, or view, whose columns differ, before it is written again.

Since item 67 (2026-11-25) terse `detect`, `is-*` and `is_*()` also read
`text_codes` where a marker's floor binds above coverage 1.05 (the
`markerfloor` check), and since item 59 (2026-11-26) wherever the top result
is a text match of 40 tokens or more (`firsttext`), so a misshaped table fails
them on such an input as it fails `-v`.

Impact 1, Risk 1, Effort 2.

After the engine of 0.10.0 (2026-11-28): `text_codes` is a required
table of one shape. A misshaped table of the new ones, `text_codes`
included, reads as missing: the file is not ready and `update` drops it
and rebuilds (`dbschema.has_shape`; `../implementation/gram-postings.md`
section 3). Open: `license_urls` and the original `detect -v` case are
not shown in the notes of this work.

## 75. Database leftovers of the 0.10.0 review — Priority 10

Found 2026-11-28 in the review of the 0.10.0 database. None changes an answer
of a normal call; "old" means 0.9.4 does the same.

- During `update`, for 0.5 to 1 s between the commit of the rows and the
  commit of the fingerprints and list version, a fresh open is refused as
  `empty; run 'licenseid update'`. An interrupted update leaves the file so
  until the next update (old layout of transactions). A kept detector is not
  affected.
- `database: update failed: database is locked` lacks the `<Type>:` the
  grammar asks for (two updates at once, a read-only file). Old wording.
- A non-numeric `idf_norm` in `license_fingerprints` gives a traceback on
  `detect`. Old.
- A flag stored as the text `'false'` reads as true (`bool('false')`):
  `is-osi` answers true. Old.
- "One transaction a call" covers Tier 1 and the loading of entries only: the
  fingerprint hits and the `lists` metadata are read after the snapshot ends,
  so a rebuild to another release in that gap could mix them into one call
  (not observed to change an answer).
- A kept detector whose file is replaced in place by a 0.9.x file still
  answers names from it; texts fail with `unreadable: no such table:
  license_texts`.
- An outdated file in an install without the packaged bundle (editable,
  `LICENSEID_BUNDLE=skip`) makes `resolve` exit 2; 0.9.4 warned and answered.
  With the wheel it falls back to the packaged list.
- A text edited by hand without a new `last_update_datetime` is caught only
  when read; the answer can show `COVERAGE` above 1 (stale core text, word
  count and fingerprints beside the new text).
- The postings blobs carry no content check: swapped blobs keep the answer
  but `TEXTS` becomes none and the runner-ups change (the limit stated in
  the gram postings note).
- A refused `update` on a newer build's file still runs `leave_wal` first: a
  newer file in WAL mode is switched out of it.
- `errors.one_line` folds white space but leaves other control characters as
  they are: an ESC in a stamp or a value reaches the terminal
  (`errors.shown` escapes them).
- `tools/cli_matrix/baseline.txt` was recorded without a packaged bundle:
  against a wheel, cells D4-001, D4-002 and D8-003 flag (`update` falls back
  to `packaged` and exits 0); 0.9.4 flags the same.
- Environments that share the default database (Pitloom, 2026-11-28):
  the first one moved to 0.10.0 builds the file as build 10, which
  0.9.x can neither read nor remove, so the others break. The changelog
  and `docs/installation.md` say so; the README's quick start does not.
  Add a sentence there (move every environment at once, or give each
  its own file with `--db`).

Done when: each is fixed or decided not to be, with a test.

Impact 2, Risk 3, Effort 4.

## 76. Repeated inputs: measure them, then keep their answers — Priority 15

Asked 2026-11-28, for after 0.10.0. A process that keeps licenseid loaded and
calls it on many packages meets the same input again and again: a declared
value (`MIT`, `Apache-2.0`), or a licence file that is the same byte for byte
(the Apache-2.0 or a GNU text). Each call pays in full. The speed gates of
0.10.0 measure distinct inputs only (`benchmarks/speedgate`), so they show
nothing of this.

First measure, do not guess: how often an input repeats, among the declared
values of `tools/pypi_licence_sample` (`fetch` keeps each package's value,
`analyze` the counts) and among the licence files of real manifests, and
what one repeated call costs now (`resolve()`, `detect(license_id=...)`,
`detect()` on a text).

Then, only if the share is high, keep answers by input. What a kept answer
must not change:

- Warnings. A call gives its `LicenseIdWarning`s each time (`variant not
  stated`, `deprecated ID`): a kept answer gives them again.
- The result. It is a mutable dict: a caller gets its own copy.
- The key: the input (its hash for a text), every option, `variant`, and
  the database's stamp, so `update` ends what was kept
  (`listsource.file_stamp` keys the choice of list so already).
- A bound by count and by size, and one behaviour under threads.

Not a `functools.cache` on the scorers: the memo of Tier 2
(`similarity._scored_once`) lives for one call on purpose. A cache of the
process keyed by the input and a licence text keeps every input it saw, and
two files that differ by a copyright line never meet in it. One CLI call
starts with nothing kept: this item is for the library.

Done when: the share of repeated inputs is in
`working-docs/paper-notes/`, and a cache is built with those four points
tested, or the item is closed with the numbers that say it does not pay.

Impact 3, Risk 2, Effort 3.
