# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `licenseid.DatabaseNotReadyError`, a `LicenseIdError` for a missing, empty,
  invalid or unreadable database ([#55])
- `licenseid.LicenseIdError` (a `RuntimeError`) for failures reported in
  licenseid's own message format, and its subclass `licenseid.InvalidInputError`
  for invalid options or input ([#53])
- `tools/cli_matrix`, a manual test harness that runs the real CLI across
  shells, locales, standard streams and environments; not run in CI ([#54])

### Changed

- `match` and the `is-*` commands check that the database is ready before
  answering. A missing, empty (for example after a failed first `update`),
  invalid (another program's file) or unreadable database exits 2 with
  `ERROR: database: not found`, `empty`, `invalid` or `unreadable`, instead of
  "no license found", `false` (exit 1) or a traceback, and a file that is not
  ready is not written to. A SQLite failure while reading exits 2 the same
  way. A path the system will not look at (an unreadable parent directory, a
  symlink loop) is reported as `unreadable` rather than `not found`, which
  would have suggested an `update` that could not help, and so is anything
  that is not a file a database could be in, such as a named pipe (which the
  read-only open would have waited on for ever). Every spelling of one file
  gets the same answer, whether it differs by path (`licenses.db`,
  `licenses.db/`, `licenses.db/.`) or by URI (`file:`, `file://`,
  `file://localhost`). The
  Python API raises `DatabaseNotReadyError` from the
  `AggregatedLicenseMatcher` constructor ([#55])
- `update` and `--clear-cache` refuse a database licenseid did not build,
  with `ERROR: database: invalid: <path>` and exit 2, instead of writing
  licenseid's schema over it or deleting it: another program's SQLite file, a
  file that is not a database, anything that is not a regular file (a
  directory, a named pipe), a path naming no file (`.`, `/`), a `file:` URI
  only SQLite can resolve (one carrying `vfs=` or another host's name), a
  file they may not read, and one locked by another process. Every other
  state is still
  accepted, including a damaged database: they exist to build or clear one.
  The refusal comes before anything is removed, and the same check runs in
  `LicenseDatabase.clear_cache`, so the Python API and the CLI agree.
  A file the system will not remove is reported as
  `database: delete failed: <path>: <reason>` ([#55])
- **Breaking (Python API):** `AggregatedLicenseMatcher.match()` rejects an
  option it does not know (a typo such as `enable_popularty`, or a removed one)
  with `InvalidInputError`, `option: invalid: '<name>'; use one of ...`,
  instead of ignoring it. The known options are `enable_popularity`,
  `exclude`, `hint`, `only_common` and `only_spdx`. To migrate, drop or
  correct the option ([#57])
- Text that quotes an "or any later version" notice without being a whole
  license, such as a slice of the GNU Free Documentation License, now
  resolves to the `-or-later` license instead of `-only`. The two variants
  have identical bodies, so nothing can tell them apart; this is what the GPL
  family already did ([#58])
- Read commands no longer create `~/.local/share/licenseid`; only `update`
  does, so an unwritable `HOME` no longer crashes them ([#55])
- `--clear-cache` no longer opens the database to clear it, so it also clears
  one that SQLite cannot read, and does not create the default directory. It
  works through a `file:` URI, and removes SQLite's `-wal`, `-shm` and
  `-journal` files beside the database. It no longer crashes on an unwritable
  `HOME`. **Breaking (Python API):** `LicenseDatabase.clear_cache` is a static
  method taking the path, so `db.clear_cache()` becomes
  `LicenseDatabase.clear_cache(db.db_path)` ([#55])
- `licenseid update` sends a `User-Agent` that identifies licenseid, makes one
  attempt per source, and reuses a stale cache file (with a warning) when a
  download fails; `--no-cache` never falls back to cached data ([#51])
- Fallbacks are reported: unusable caches or downloads and popularity rows
  with a missing or non-numeric count print a warning ([#51])
- `licenseid update` and `--clear-cache` write progress, the data sources
  report and warnings to standard error; standard output carries only the
  result line ([#53])
- Errors and warnings use one format,
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`, for example
  `ERROR: database: not found: <path>; run 'licenseid update'`. Scripts that
  match the old text need updating ([#53])
- Each error or warning starts on its own line, and an unexpected failure in
  `licenseid update` is reported as
  `ERROR: database: update failed: <type>: <detail>`
  instead of a traceback ([#53])

### Removed

- **Breaking:** the optional Java validation tier: `match --java/--no-java`,
  the `licenseid[java]` extra, `SPDX_TOOLS_JAR`, `enable_java` and the
  `java_verified` result field. It was off by default and untested in CI, so
  match results are unchanged. To migrate, drop them.
  `AggregatedLicenseMatcher(db, enable_java=True)` raises `TypeError`, and
  `match(enable_java=True)` raises `InvalidInputError` as an unknown option
  ([#54], [#57])
- **Breaking:** `AggregatedLicenseMatcher(enable_popularity=...)` is now
  keyword-only; it took the positional slot of `enable_java`, so a positional
  `True` would have silently enabled popularity ranking ([#54])

### Fixed

- A header granting "or any later version" in other words (`or any later
  version`, `or a later version`, `or newer`, `or, at your option, any later
  version`, or wrapped over comment lines) is read as the `-or-later` license
  on every path. The marker detector, the `-only`/`-or-later` tie-breaker and
  the bare-ID prose check each read it differently, so the same header could
  give `-only` or `-or-later` depending on its length. "not any later version"
  no longer counts as a grant ([#58])
- The `-only`/`-or-later` tie-breaker treats a score gap of exactly 0.01 the
  same at every score, as no tie, instead of leaving it to floating-point
  rounding, and
  its re-sort no longer ranks a deprecated ID above its replacement ([#58])
- `--db` with a blank value is a usage error (`ERROR: database: missing:
  --db`) instead of silently using the default database ([#55])
- Deeply nested JSON no longer crashes license detection with
  `RecursionError`, and extensionless INI/TOML text that starts with a section
  header is read ([#50])
- Free text in a `license` field no longer becomes a phantom candidate marked
  as an SPDX license ([#50])
- `licenseid update` no longer crashes on a short popularity row, a corrupt
  cache file or an unwritable cache directory, and no longer caches
  unparseable downloads ([#51])
- Cache files and the SPDX tarball are written atomically, so an interrupted
  download cannot leave a truncated file that is reused; a corrupt cached
  tarball is removed and downloaded again ([#51])
- A cache file dated in the future no longer counts as valid forever, and
  building a database from a single license no longer fails with
  `ZeroDivisionError` ([#51])
- `match` and the `is-*` commands no longer crash on input that is not UTF-8:
  it is read as Latin-1 with a warning; binary data (any NUL byte, including
  UTF-16) exits 2 with `ERROR: input: binary file: <path>`; an empty or
  unreadable file (such as a directory) exits 2 with `input: empty` or
  `input: unreadable`. A UTF-8 byte order mark is dropped ([#53])
- An input with no text (`--text ""`, `--id " "`, a blank argument or blank
  piped input) exits 2 with `ERROR: input: empty: <input>` instead of being
  skipped or reported as no match ([#53])
- `--text` keeps non-ASCII characters and decodes only backslash escapes such
  as `\n`; an invalid escape is kept as typed. A NUL exits 2 as binary input
  ([#53])
- `update --version` with an invalid or empty version exits 2 (usage error)
  instead of 1 or meaning the latest version ([#53])

### Security

- `--version` and the version in a downloaded `licenses.json` are validated
  before use in a file name or URL, and the SPDX tarball is extracted with
  path-traversal checks ([#51])

[#50]: https://github.com/bact/licenseid/pull/50
[#51]: https://github.com/bact/licenseid/pull/51
[#53]: https://github.com/bact/licenseid/pull/53
[#54]: https://github.com/bact/licenseid/pull/54
[#55]: https://github.com/bact/licenseid/pull/55
[#57]: https://github.com/bact/licenseid/pull/57
[#58]: https://github.com/bact/licenseid/pull/58

## [0.3.7] - 2026-08-20

### Fixed

- `LicenseDatabase` no longer leaks a SQLite connection per query ([#37])

[#37]: https://github.com/bact/licenseid/pull/37

## [0.3.6] - 2026-08-19

### Fixed

- Free-text bare deprecated license IDs (`GPL-2.0` -> `GPL-2.0-only`) ([#34])

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
