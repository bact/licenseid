# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `licenseid update` requests now send a `User-Agent` that identifies
  licenseid, make a single attempt per source, and reuse a stale cache file
  (with a warning) when a download fails ([#51])
- `licenseid update --no-cache` never falls back to cached data, even after a
  failed download ([#51])
- Fallbacks are reported: unusable caches or downloads, and popularity rows
  with a missing or non-numeric count, print a warning ([#51])

### Fixed

- Deeply nested JSON no longer crashes license detection with
  `RecursionError`, and extensionless INI/TOML text that starts with a section
  header is now read ([#50])
- Free text in a `license` field no longer becomes a phantom candidate marked
  as an SPDX license ([#50])
- `licenseid update` no longer crashes on a short popularity row, a corrupt
  cache file, or an unwritable cache directory, and no longer caches
  unparseable downloads ([#51])
- Cache files and the SPDX tarball are written atomically, so an interrupted
  download cannot leave a truncated file that is reused; a corrupt cached
  tarball is removed and downloaded again ([#51])
- A cache file dated in the future no longer counts as valid forever ([#51])
- Building a database from a single license no longer fails with
  `ZeroDivisionError` ([#51])
- `licenseid match --java` no longer prints a debug line to standard output,
  which corrupted JSON and other parseable output

### Security

- `--version` and the version in a downloaded `licenses.json` are validated
  before they are used in a file name or URL, and the downloaded SPDX tarball
  is extracted with path-traversal checks ([#51])

[#50]: https://github.com/bact/licenseid/pull/50
[#51]: https://github.com/bact/licenseid/pull/51

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
