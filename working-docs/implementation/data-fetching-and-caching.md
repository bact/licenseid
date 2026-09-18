---
Created: 2026-09-18
Last-Modified: 2026-09-18
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Data fetching and caching (`spdx_source.py`)

What was built in PR #51, why, and the traps found on the way. Code:
`src/licenseid/spdx_source.py`; caller: `LicenseDatabase.update_from_remote`
in `database.py`.

## What it does

`licenseid update` reads three third-party sources and caches each in the
database directory (`~/.local/share/licenseid/` by default):

- spdx.org `licenses.json` → `licenses.json`, 45 days, `get_version_info`
- GitHub `license-list-data` tarball → `spdx-data-v<ver>.tar.gz`, never
  expires, `get_tarball_path`
- GitHub Innovation Graph CSV → `popularity.csv`, 75 days,
  `fetch_popularity_data`

Every function returns where its data came from: `cache`, `remote`,
`stale cache` or `unavailable`; `update_from_remote` prints them under
`Data sources:`.

## Rules to keep

- **Fallback order**: valid cache, then one download, then (only with
  caching allowed) a stale cache, then an explicit `--version` or an error.
  `--no-cache` never reads cached data, not even as a fallback.
- **Non-silent**: every deviation prints a `Warning:` line (unusable cache,
  unusable download, stale data, bad counts). Do not add a silent fallback.
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
  file name or URL. The tarball is extracted by `extract_tarball`: tarfile's
  `data` filter, or an equivalent manual check on Pythons without filters
  (leading slashes stripped, members and links must stay inside the
  destination). Both paths behave the same.
- **Self-healing**: a corrupt or truncated cached tarball is deleted by
  `_process_and_store` (`TarError`, `EOFError`, `zlib.error`) so the next run
  downloads it again; a local popularity cache that parses to nothing is
  re-downloaded once.

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
- Simulate an older Python by patching `spdx_source._HAS_EXTRACTION_FILTER`,
  not by deleting `tarfile.data_filter` (that breaks `tarfile` itself on
  3.12+ and failed CI on 3.14).
- Mutation check used to find weak tests: break a line, run the affected
  tests, restore. Clear `__pycache__` between mutants; a same-size mutant
  restored within the same second leaves a stale `.pyc` that looks like a
  failing baseline.

## Known gaps (deliberately not done)

- `licenseId` values in the tarball's JSON are used to build
  `text/<id>.txt` paths without validation.
- Timeouts are per read, not total, so a slow-drip download can run long.
- `Warning:` lines go to stdout, like the rest of `update`'s progress output.
- `DEFAULT_FALLBACK_VERSION` in `spdx_source.py` is unused.
