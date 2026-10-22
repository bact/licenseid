---
Created: 2026-09-18
Last-Modified: 2026-10-22
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Data fetching and caching (`spdx_source.py`)

What was built in PR #51, why, and the traps found on the way. Code:
`src/licenseid/spdx_source.py`; caller: `LicenseDatabase.update_from_remote`
in `database.py`.

Since PR #85 `update` reads the tarball into one `SpdxData`
(`spdxdata.py`, standard library only) and `records.py` builds the database
rows from it; see "Store path" below.

## What it does

`licenseid update` reads third-party sources and caches each in the database
directory (`~/.local/share/licenseid/` by default):

- version: the bundle pointer `latest.json` or spdx.org `licenses.json` →
  `licenses.json` (both have `licenseListVersion` and `releaseDate`), 45
  days, `get_version_info`
- data, one of: the published bundle → `spdx-bundle-v<ver>.json.gz`; the
  GitHub `license-list-data` tarball → `spdx-data-v<ver>.tar.gz`; the
  snapshot in the package (no cache). Neither cached file expires.
- GitHub Innovation Graph CSV → `popularity.csv`, 75 days,
  `fetch_popularity_data`

The functions return where their data came from: `cache`, `remote`,
`stale cache`, `unavailable` or `packaged`; `update_from_remote` prints them
under `Data sources:` (the data line reads `bundle (remote)`, `bundle
(cache)`, `tarball (remote)`, `tarball (cache)` or `packaged`).

## Rules to keep

- **Fallback order**: valid cache, then one download, then (only with
  caching allowed) a stale cache, then an explicit `--version` or an error.
  `--no-cache` never reads cached data, not even as a fallback. The
  snapshot in the package is shipped data, not cache: `--no-cache` may use it.
- **Non-silent**: every deviation prints one `WARNING:` line to standard
  error through `console.warn()` (unusable cache, unusable download, stale
  data, bad counts), in the `LEVEL: SUBJECT: CONDITION` grammar from
  `AGENTS.md`, with the cache file name as the subject (for example
  `WARNING: popularity.csv: download failed: <error>; using stale cache`,
  one line per event). Progress goes to standard
  error through `console.status()`. Do not add a silent fallback.
- **Gentle**: identifying `User-Agent` (`user_agent()`), explicit timeouts,
  one attempt per source per run, no retry or backoff loop. Not added, on
  purpose: ETag / `If-Modified-Since`, a rate limiter (the expiry already
  gives about one request per source per update).
- **Only usable data is cached**: a response is written to the cache only if
  it parses to something usable (non-empty popularity map, `licenses.json`
  with a valid `licenseListVersion`). A CSV parse error yields no data, never
  a partial map.
- **Atomic writes**: all three caches go through `_atomic_path` (unique temp
  file next to the target, `os.replace` on success, removed either way).
  `clear_cache` also removes orphaned `*.tmp` files.
- **Untrusted input**: a version (from `--version` or a downloaded
  `licenses.json`) must match `[A-Za-z0-9][A-Za-z0-9._-]*` before it reaches a
  file name or URL. `SpdxData.from_tarball` does not extract: it reads only
  `<root>/json/*.json` and `<root>/text/*.txt`, so a member with an absolute
  or `..` name is never read. The tarball and the bundle share one check of
  the version, the release date and every licence and exception ID
  (`[A-Za-z0-9][A-Za-z0-9.+-]{0,99}`, no duplicates).
- **Self-healing**: a cached bundle or tarball that cannot be read is
  removed (`ReleaseChain._read_tarball`; `TarError`, `EOFError`,
  `zlib.error`), warned about (`cache unusable: ...; downloading`) and
  downloaded again in the same run; if it cannot be removed (Windows, held
  open) the error says `remove it and run 'licenseid update' again`; a local
  popularity cache that parses to nothing is re-downloaded once.

## Store path (PR #85)

- One object feeds the store: `SpdxData` (version, release date, licence and
  exception entries, `texts` by licence ID). `ReleaseChain` builds it from
  the bundle, the tarball or the snapshot; `database._store` stores it.
- `records.build_records` is pure: no file or database access. A licence
  with no text is dropped, unless deprecated; then it keeps a row without an
  index entry (pinned by `tests/test_update_characterization.py`, with a
  `# BUG:` note for the silent drop).
- The XML (`license-list-XML/`) is no longer read or stored: nothing used
  it. `xml_template` stays in the schema, always NULL. `update` runs `VACUUM`
  at the end, so an existing database shrinks (24.6 MB to 17.3 MB for 3.29.0);
  a failure is a `database: compact failed` warning.
- `from_tarball` reads the archive in one forward pass (`_scan_tarball`). A
  lookup of each text by name seeks back in the gzip stream, which
  decompresses from the start each time: 93 s instead of 1.5 s for 3.29.0
  (`test_a_tarball_is_read_forward_once` pins it). Whole store path, cached
  3.29.0 tarball: 14 s on `main`, 7-10 s now.
- Text is read through `io.TextIOWrapper` (universal newlines), the same as
  `open(..., encoding="utf-8")`, so CRLF text gives the same fingerprint
  whichever way it was read.
- A tarball whose `licenses.json` has no valid `licenseListVersion` or a bad ID
  fails as `cache unusable`. Before, `update` stored a NULL version.
- Checked on the real 3.29.0 tarball (read-only): licences, search texts,
  exceptions and metadata equal those of a database built before the change.
  Fingerprints differed because of an older bug, not this change:
  `fingerprint.py` sorted ties by set order, so the top 20 n-grams of a
  licence changed from process to process. Ties now sort by n-gram; three
  builds under different `PYTHONHASHSEED` values store identical rows
  (14,117 fingerprints). A database built earlier keeps its old rows until
  `update --force`.

## Source chain (`releasesource.py`)

`update --source auto|bundle|tarball|packaged`, default `auto`. An explicit
source is the only one tried; `auto` falls back, one `WARNING:` per step whose
ACTION names the next source, e.g.
`spdx-bundle-v3.29.0.json.gz: download failed: HTTPError: 404 ...;
downloading spdx-data-v3.29.0.tar.gz`, then `spdx-data-v3.29.0.tar.gz:
download failed: ...; using packaged data v3.28.0`.

- **Version** (`auto`): the first valid cache of the two version files, then
  a download of `latest.json` and of spdx.org's `licenses.json` in turn, then
  (only with caching) the first stale cache, then the version of the
  packaged snapshot. Each file has its own cache: `latest.json` for one day
  (the pointer moves with the daily bundle job), `licenses.json` for 45 days.
  `--source bundle` reads only `latest.json`, `tarball` only spdx.org, so one
  never sees the other's answer. A version from the snapshot makes no
  network call, popularity included. A stale cache of the other file is
  reported as `using stale <file>`.
- **Data** (`auto`): a cached bundle or tarball of the target version first
  (cache before download across sources, so a forced re-run stays offline),
  then the bundle, the tarball, the snapshot. The snapshot is used only if it
  exists, equals `--version` when one is given, and is not older than the
  database: a failed download never downgrades it.
- **Skip**: the database is already at the target version without `--force`,
  or a fallback produced the version the database already has (the snapshot
  is never stored twice). Popularity data is fetched after both checks, so a
  skip makes no popularity request.
- **`--source packaged` and a newer database**: refused unless `--force`
  (`spdx-bundle.json.gz: older than the database: v3.28.0 < v3.29.0; run
  'licenseid update --source packaged --force'`). An explicit `--version`
  naming the snapshot's version passes, as it does for the other sources.
- **Timeouts** are (connect, read): (10, 30) for the version files and
  popularity, (10, 60) for the bundle and the tarball, so a black-holed host
  fails in seconds.
- **Bundle fetch**: one streamed request, `timeout=(10, 60)`; bytes are
  counted from `iter_content` and refused over 16 MiB; gzip's CRC is the
  integrity check (no hash on the client); cached atomically; a failed cache
  write is a warning. An unusable cache file is removed and the file fetched
  again in the same run.
- **One store path**: every source yields a `SpdxData`; `database._store`
  takes it; there is no other store entry point.
- **A valid `licenses.json` can answer `auto` before `latest.json` is
  fetched** (valid caches come before downloads, so a forced re-run stays
  offline). If the bundle of that version is not published yet, `auto` falls
  back to the tarball.
- **New diagnostics**: SUBJECTs `latest.json`, `spdx-bundle-v<ver>.json.gz`,
  `spdx-bundle.json.gz` (the snapshot); ACTIONs `downloading <file>`,
  `using cached <file>`, `using packaged data v<ver>`, `using stale <file>`,
  `run 'licenseid update --source packaged --force'`; CONDITION `older than
  the database`.
- **Timings** (cached 3.29.0, best of three, read-only): tarball 49,400,135
  bytes, read 1.2 s, store 3.8 s; bundle 980,375 bytes (4,954,511 unzipped),
  read 0.04 s, store 2.7 s. The two databases match row for row.
- **Tests**: `tests/release_fakes.py` serves a synthetic release (404 for any
  other URL); an autouse `offline` fixture makes `requests.get` fail and
  `packaged_bundle()` return `None`, so a test opts in. A tarball is valid
  gzip: a server fake that answers every URL with it hides a bundle failure.
- `tools/cli_matrix/launcher.py` answers `latest.json` and `.json.gz` with a
  404 and its `Resp` has `close()`.

## Traps and surprises

- A truncated `.tar.gz` raises a bare `EOFError`, not `tarfile.TarError`.
- A corrupted gzip CRC trailer is never noticed: tarfile stops reading at the
  end-of-archive marker. `gzip.BadGzipFile` is therefore not handled.
- The `data` filter makes absolute member names relative instead of
  raising, so the manual fallback does the same.
- `int(None)` (short CSV row) is a `TypeError`, not `ValueError`.
- A future-dated cache file makes `now - mtime` negative, which is less than
  any expiry, so it never expires; `is_cache_valid` allows 5 minutes of skew.
- `compute_idf_fingerprints` divided by zero for a one-license corpus
  (`log(1) = 0`); found only by the end-to-end update test.
- `licenseid.__version__` cannot be imported at module level in
  `spdx_source.py`: the package `__init__` imports `database`, which imports
  this module (pylint R0401). `user_agent()` resolves it at call time.
  `database.py` also imports `spdx_source` lazily to keep `requests` (about
  60 ms) off the match path.
- Never reach `licenseid.__version__` through package metadata: it lags in
  editable installs.
- `update_from_remote` with popularity `unavailable` still rebuilds the
  database, with baseline popularity scores. The `Data sources:` line and the
  warnings are the only signal.

## Validation against real data

The cached real files were used read-only to check the new code: SPDX 3.28.0
tarball = 13,018 files and 19 directories, no links, identical extraction
under the `data` filter and the manual path; `licenses.json` and the
29-license `popularity.csv` parse with no warnings. Repeat this kind of check
when changing a parser; never modify or clear the real cache for it.

## Tests

- `tests/test_spdx_source.py`, `tests/test_spdx_source_cache.py`: fake
  `requests.get` via `conftest.fake_requests_get` (autospec), `tmp_path`
  caches, `capsys` for the warnings. No test may touch the network.
- `tests/test_database_update.py`: `update_from_remote` and the CLI `update`
  end to end on a small synthetic release built in memory (a tarball,
  `licenses.json`, one CSV); extraction attacks tested one member kind at a
  time (a combined archive let one check mask another).
- `tests/test_spdxdata.py`, `tests/test_update_characterization.py`: the
  `SpdxData` readers and what a small release becomes in the database.
- Simulate an older Python with a module flag, not by deleting
  `tarfile.data_filter` (that breaks `tarfile` itself on 3.12+ and failed CI on
  3.14).
- Mutation check used to find weak tests: break a line, run the affected
  tests, restore. Clear `__pycache__` between mutants; a same-size mutant
  restored within the same second leaves a stale `.pyc` that looks like a
  failing baseline.

## Known gaps (deliberately not done)

- Timeouts are per read, not total, so a slow-drip download can run long.
