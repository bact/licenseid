# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - 2026-10-07

### Fixed

- An overlong licence ID ending in `+` (in an ID or a text) is no match, not
  `DatabaseNotReadyError` ([#82])

[#82]: https://github.com/bact/licenseid/pull/82

## [0.4.2] - 2026-10-07

### Added

- `get_default_db_path` is public; `LicenseDatabase(path, create=False)` opens a
  database that must exist, as the matcher now does ([#80])

### Changed

- A failing lookup raises `DatabaseNotReadyError`, not a raw `sqlite3.Error`
  (catch it instead); the CLI exits 2, also for `ProgrammingError` ([#80])
- `update` no longer uses WAL mode and takes an older database out of it; until
  then a lookup on that database still leaves `-wal` and `-shm` ([#80])

### Fixed

- A lookup no longer creates a missing database file or writes to it, no longer
  hides a locked or damaged database as "no candidates", and no longer hangs on
  a FIFO in place of the database, its `-journal` or `-wal` ([#80])
- A failed `update` is no longer skipped next time, and processes opening an
  older database at once no longer fail with `duplicate column name` ([#80])

[#80]: https://github.com/bact/licenseid/pull/80

## [0.4.1] - 2026-10-06

### Added

- The release SBOM has a Sigstore bundle and a build provenance attestation;
  `SECURITY.md` shows how to verify release files ([#76])

### Changed

- Pull request and release builds pin Pitloom and its checks through
  `.github/requirements-release.txt`; the SBOM check runs once per pull
  request ([#77])

### Fixed

- Windows: a plain database path opens read-only (no "invalid uri authority"),
  `file:` URIs (`file:///C:/...`, `file://localhost/...`) reach SQLite as
  given, and `update` writes its cache beside the database ([#77])
- No home directory exits 2 with an error line, not a traceback; a locked
  temporary file no longer fails a finished `update`; unencodable output is
  escaped, not a traceback ([#77])

[#76]: https://github.com/bact/licenseid/pull/76
[#77]: https://github.com/bact/licenseid/pull/77

## [0.4.0] - 2026-10-05

### Added

- Release files carry Sigstore signatures and build provenance attestations
  ([#39])
- `licenseid.LicenseIdError` and its subclass `InvalidInputError` for
  licenseid's own failures ([#53])
- `tools/cli_matrix`, a manual harness that runs the real CLI across shells,
  locales and streams ([#54])
- `licenseid.DatabaseNotReadyError` for a missing, empty, invalid or unreadable
  database ([#55])
- `match --exact` keeps only exact results, and `licenseid.Method` types a
  result's `method` ([#68])

### Changed

- Requires `click>=8.5.0` and `py-spdx-license<0.1`; building needs
  `hatchling>=1.32.3` and `pitloom[content-type]>=0.20.0` ([#46], [#56], [#74])
- `update` sends a licenseid `User-Agent`, tries each source once and warns on
  every fallback, such as a stale cache; `--no-cache` never falls back ([#51])
- `update` and `--clear-cache` write progress and warnings to standard error;
  standard output carries only the result ([#53])
- Errors and warnings use one format,
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`, one per line, usage errors
  included; an `update` failure is no traceback. Scripts matching old text
  need updating ([#53], [#73])
- `match` and `is-*` exit 2 with `ERROR: database: <condition>` when the
  database is not ready; the API raises `DatabaseNotReadyError` ([#55])
- `update` and `--clear-cache` refuse a database licenseid did not build
  (exit 2) instead of overwriting or deleting it ([#55])
- Read commands no longer create `~/.local/share/licenseid` or crash on an
  unwritable `HOME` ([#55])
- `--clear-cache` clears a database SQLite cannot read, with its `-wal`, `-shm`
  and `-journal` files. **Breaking (Python API):** call
  `LicenseDatabase.clear_cache(path)` ([#55])
- **Breaking (Python API):** `match()` rejects an unknown option with
  `InvalidInputError`; drop or correct it ([#57])
- Text quoting an "or any later version" notice resolves to `-or-later`, as the
  GPL family already did ([#58])
- A `WITH` expression matches even when the local database lacks its license or
  exception ([#61])
- **Breaking:** `--id` and `match(license_id=...)` take one license: an ID or
  `LicenseRef-*`, with `+` or `WITH`. Anything else exits 2 or raises; match it
  as text instead ([#61])
- **Breaking:** every match has the same keys, adding `method` and `exact`;
  `score` is 0 to 1, `similarity` and `coverage` may be `null`, and ranking-only
  keys are gone. Read `exact`, not a score above 1 ([#68])
- **Breaking:** `--json` prints JSON Lines in RFC 8785 form, not one array
  (`jq -s .` makes the array). Adds the `rfc8785` dependency ([#68])
- **Breaking:** the text line adds `METHOD=`, `EXACT=` and `SCORE=`;
  `SIMILARITY=` and `COVERAGE=` are empty where not measured. Read fields by key
  ([#68])
- **Breaking:** `--threshold` takes 0 to 1, else exits 2; use `--exact` to keep
  exact answers ([#68])
- `--diff` shows only for a top text match that is not exact, and leaves out the
  input's SPDX tags ([#68])
- With no subcommand, the help goes to standard error, as a usage error
  (exit 2) ([#73])
- The release attaches the SBOM the wheel carries, built by the Pitloom build
  hook with content types detected by magika, and no longer re-embeds it
  ([#74])

### Removed

- **Breaking:** the Java validation tier: `--java`, `licenseid[java]`,
  `SPDX_TOOLS_JAR`, `enable_java` and `java_verified`. Results are unchanged;
  drop them ([#54], [#57])
- **Breaking:** `AggregatedLicenseMatcher(enable_popularity=...)` is
  keyword-only ([#54])

### Fixed

- Deeply nested JSON no longer crashes detection; free text in a `license`
  field is no SPDX candidate; extensionless INI/TOML text is read ([#50])
- `update` no longer crashes on a short popularity row, a corrupt cache or an
  unwritable cache directory, nor caches a bad download ([#51])
- Cache files are written atomically; a corrupt cached tarball is downloaded
  again; a future-dated cache no longer stays valid ([#51])
- A database built from a single license no longer fails with
  `ZeroDivisionError` ([#51])
- Input that is not UTF-8 is read as Latin-1 with a warning,
  by the CLI and the API; binary, empty or unreadable input exits 2 or
  raises `InvalidInputError` ([#53], [#59])
- `--text` keeps non-ASCII text and decodes only backslash escapes;
  `update --version` with a bad value exits 2 ([#53])
- A blank `--db` is a usage error, not the default database ([#55])
- An "or any later version" grant in any wording reads as `-or-later` on every
  path; it qualifies the license beside it, after `WITH` or in brackets too
  ([#58], [#61])
- The `-only`/`-or-later` tie-breaker treats a 0.01 gap alike at every score
  and never ranks a deprecated ID above its replacement ([#58])
- A tag with no known license ID is no certain match; tags and `license`
  fields decide by one rule, and `is-*` answers as `match` does ([#60])
- An `SPDX-License-Identifier` tag is read as one whole expression,
  and may hold a license name or SPDX URL ([#61])
- `--id` accepts `LicenseRef-*`, `+` and `+ WITH` forms;
  a bare argument that is no ID is matched as text ([#61])
- Long tokens, embedded base64, overlong expressions or long runs of spaces no
  longer take seconds to minutes ([#61], [#62], [#65], [#66])
- A small `package.json`, `pyproject.toml` or `Cargo.toml` answers from its
  `license` field, never by name; `MIT/Apache-2.0` is no longer just MIT
  ([#65])
- PEP 639, Poetry, Cargo and written-out PEP 621 license forms are read,
  as are npm's old `license` object and `licenses` array ([#65])
- A TOML or INI `license` field is a certain match, as JSON is,
  and every result carries its SPDX, OSI and FSF flags ([#65])
- A short input answers from its `SPDX-License-Identifier` tag, not by license
  name; a tag that names no license is no match ([#66], [#67])
- `GPL-2.0-with-classpath-exception` and the deprecated `GFDL-1.x` IDs answer
  their current forms, with `+` and "or later" ([#66], [#67])
- A lone SPDX expression in any input is read as `--id` reads it:
  `--text GPL-2.0+` answers `GPL-2.0-or-later` ([#67])
- `LicenseRef-x+` is no expression; `--id LicenseRef-x+` exits 2 ([#67])
- A file of thousands of distinct tags matches over 20× faster, and a short
  input of one very long word about 9× faster ([#69], [#72])
- A failure no longer passes for an answer: Ctrl-C exits 130, not 1; a
  closed pipe exits 141 quietly; output or help that cannot be written exits
  2, not 0 or 120; a closed stdin is no input; a failing stderr no longer
  turns the exit status into 120 ([#70])
- A long-lived matcher sees a database that `licenseid update` rebuilt
  meanwhile ([#72])

### Security

- `--version` and the downloaded `licenses.json` version are validated before
  use in a path or URL; the SPDX tarball is extracted with path-traversal
  checks ([#51])

[#39]: https://github.com/bact/licenseid/pull/39
[#46]: https://github.com/bact/licenseid/pull/46
[#50]: https://github.com/bact/licenseid/pull/50
[#51]: https://github.com/bact/licenseid/pull/51
[#53]: https://github.com/bact/licenseid/pull/53
[#54]: https://github.com/bact/licenseid/pull/54
[#55]: https://github.com/bact/licenseid/pull/55
[#56]: https://github.com/bact/licenseid/pull/56
[#57]: https://github.com/bact/licenseid/pull/57
[#58]: https://github.com/bact/licenseid/pull/58
[#59]: https://github.com/bact/licenseid/pull/59
[#60]: https://github.com/bact/licenseid/pull/60
[#61]: https://github.com/bact/licenseid/pull/61
[#62]: https://github.com/bact/licenseid/pull/62
[#65]: https://github.com/bact/licenseid/pull/65
[#66]: https://github.com/bact/licenseid/pull/66
[#67]: https://github.com/bact/licenseid/pull/67
[#68]: https://github.com/bact/licenseid/pull/68
[#69]: https://github.com/bact/licenseid/pull/69
[#70]: https://github.com/bact/licenseid/pull/70
[#72]: https://github.com/bact/licenseid/pull/72
[#73]: https://github.com/bact/licenseid/pull/73
[#74]: https://github.com/bact/licenseid/pull/74

## [0.3.7] - 2026-08-20

### Added

- Releases attach the sdist and wheel, and the SBOM is validated in the
  built wheel ([#36])

### Fixed

- `LicenseDatabase` no longer leaks a SQLite connection per query ([#37])

[#36]: https://github.com/bact/licenseid/pull/36
[#37]: https://github.com/bact/licenseid/pull/37

## [0.3.6] - 2026-08-19

### Added

- Releases attach the SBOM ([#33])

### Fixed

- Free-text bare deprecated license IDs (`GPL-2.0` -> `GPL-2.0-only`) ([#34])

[#33]: https://github.com/bact/licenseid/pull/33
[#34]: https://github.com/bact/licenseid/pull/34

## [0.3.5] - 2026-08-18

### Added

- Pitloom embed-wheel support in the PyPI publish workflow ([#32]).

[#32]: https://github.com/bact/licenseid/pull/32

## [0.3.4] - 2026-08-11

### Fixed

- License expression operator casing normalisation ([#31]).

[#31]: https://github.com/bact/licenseid/pull/31

## [0.3.3] - 2026-07-28

### Added

- License expression support ([#28]).

[#28]: https://github.com/bact/licenseid/pull/28

## [0.3.2] - 2026-07-20

### Changed

- Matching pipeline performance optimisation ([#25]).

[#25]: https://github.com/bact/licenseid/pull/25

## [0.3.1] - 2026-07-09

### Added

- SBOM building support ([#24]).

[#24]: https://github.com/bact/licenseid/pull/24

## [0.3.0] - 2026-07-09

Faster license matching, and now comes with a software bill of
materials (SBOM) embedded in the wheel.

### Added

- SBOM generation, embedded in the built wheel ([#22]).

### Changed

- Query speed optimisation ([#19]).
- Text normalisation updated to follow SPDX matching guidelines ([#21]).

[#19]: https://github.com/bact/licenseid/pull/19
[#21]: https://github.com/bact/licenseid/pull/21
[#22]: https://github.com/bact/licenseid/pull/22

## [0.2.3] - 2026-05-13

### Added

- `is-spdx`, `is-open` CLI commands ([#11]).
- License marker detection ([#12]).

### Changed

- Predictable exit codes ([#10]).
- Matcher now uses the default database when none is specified ([#16]).

[#10]: https://github.com/bact/licenseid/pull/10
[#11]: https://github.com/bact/licenseid/pull/11
[#12]: https://github.com/bact/licenseid/pull/12
[#16]: https://github.com/bact/licenseid/pull/16

## [0.2.2] - 2026-04-29

### Changed

- Package marked as PEP 561 typed (`py.typed`) ([#8]).

[#8]: https://github.com/bact/licenseid/pull/8

## [0.2.1] - 2026-04-28

### Added

- `--bold` CLI output option ([#5]).

[#5]: https://github.com/bact/licenseid/pull/5

## [0.2.0] - 2026-04-28

### Changed

- Matching logic revised ([#4]).

[#4]: https://github.com/bact/licenseid/pull/4

## [0.1.1] - 2026-04-28

### Added

- Local caching of downloaded SPDX license data ([#3]).

## [0.1.0] - 2026-04-28

### Added

- First release.

### Known issues

- `Apache-2.0` vs `Pixar` matching confusion: `Pixar` is essentially
  `Apache-2.0` with a modified section 6, and license text for one is
  sometimes misidentified as the other.

[#3]: https://github.com/bact/licenseid/pull/3

[0.4.3]: https://github.com/bact/licenseid/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/bact/licenseid/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/bact/licenseid/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bact/licenseid/compare/v0.3.7...v0.4.0
[0.3.7]: https://github.com/bact/licenseid/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/bact/licenseid/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/bact/licenseid/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/bact/licenseid/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/bact/licenseid/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/bact/licenseid/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/bact/licenseid/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/bact/licenseid/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/bact/licenseid/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/bact/licenseid/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/bact/licenseid/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/bact/licenseid/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/bact/licenseid/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/bact/licenseid/releases/tag/v0.1.0
