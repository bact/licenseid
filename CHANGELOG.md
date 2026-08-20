# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `LicenseDatabase` no longer leaks a SQLite connection per query

## [0.3.6] - 2026-08-19

### Fixed

- Free-text bare deprecated license IDs (e.g. `match(text="GPL-2.0")`) now
  redirect to their canonical successor (`GPL-2.0-only`), matching the
  behaviour already used by the explicit `license_id=` path.
- `ruff`/`flake8`/`pylint` cleanliness issues across `tests/`,
  `benchmarks/`, and `scripts/` (missing docstrings, line length,
  unbound loop variables, unnecessary `list()`/generator wrapping,
  missing executable bit on scripts with a shebang).

### Changed

- Linting: complexity and file-size ceilings
  (`max-args`, `max-branches`, `max-locals`, `max-statements`, McCabe,
  cognitive complexity, `max-module-lines`) tightened to interim
  ratchets at the exact current repository maximum, so any regression
  trips CI immediately. See
  [`working-docs/design/complexity-and-file-size-roadmap.md`](working-docs/design/complexity-and-file-size-roadmap.md)
  for the backlog that has to shrink before each ceiling can drop
  further, toward pylint's own built-in defaults.
- `requests` dependency floor bumped to `>=2.34.2`.
- Documentation restructured from `docs/` into `working-docs/{design,implementation}/`,
  following a design-vs-implementation-record split. Added a
  current-state index at
  [`working-docs/implementation/README.md`](working-docs/implementation/README.md)
  and prioritised roadmaps for remaining tech debt and complexity/file-size
  debt.

### Added

- `flake8-cognitive-complexity` added to the `lint` dependency group.

## [0.3.5] - 2026-08-18

### Added

- Pitloom embed-wheel support in the PyPI publish workflow ([#32]).

## [0.3.4] - 2026-08-11

### Fixed

- License expression operator casing normalisation ([#31]).

## [0.3.3] - 2026-07-28

### Added

- License expression support ([#28]).

## [0.3.2] - 2026-07-20

### Changed

- Matching pipeline performance optimisation ([#25]).

## [0.3.1] - 2026-07-09

### Added

- SBOM building support ([#24]).

## [0.3.0] - 2026-07-09

Faster license matching, and now comes with a software bill of
materials (SBOM) embedded in the wheel.

### Added

- SBOM generation, embedded in the built wheel ([#22]).

### Changed

- Query speed optimisation ([#19]).
- Text normalisation updated to follow SPDX matching guidelines ([#21]).

## [0.2.3] - 2026-05-13

### Added

- `is-spdx`, `is-open` CLI commands ([#11]).
- License marker detection ([#12]).

### Changed

- Predictable exit codes ([#10]).
- Matcher now uses the default database when none is specified ([#16]).

## [0.2.2] - 2026-04-29

### Changed

- Package marked as PEP 561 typed (`py.typed`) ([#8]).

## [0.2.1] - 2026-04-28

### Added

- `--bold` CLI output option ([#5]).

## [0.2.0] - 2026-04-28

### Changed

- Matching logic revised ([#4]).

## [0.1.1] - 2026-04-28

### Added

- Local caching of downloaded SPDX license data ([#3]).

## [0.1.0] - 2026-04-28

### Added

- First release.

### Known issues

- `Apache-2.0` vs `Pixar` matching confusion: `Pixar` is essentially
  `Apache-2.0` with a modified section 6, and license text for one is
  sometimes misidentified as the other. Tracked in
  [`working-docs/design/new-matcher.md`](working-docs/design/new-matcher.md).

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

[#3]: https://github.com/bact/licenseid/pull/3
[#4]: https://github.com/bact/licenseid/pull/4
[#5]: https://github.com/bact/licenseid/pull/5
[#8]: https://github.com/bact/licenseid/pull/8
[#10]: https://github.com/bact/licenseid/pull/10
[#11]: https://github.com/bact/licenseid/pull/11
[#12]: https://github.com/bact/licenseid/pull/12
[#16]: https://github.com/bact/licenseid/pull/16
[#19]: https://github.com/bact/licenseid/pull/19
[#21]: https://github.com/bact/licenseid/pull/21
[#22]: https://github.com/bact/licenseid/pull/22
[#24]: https://github.com/bact/licenseid/pull/24
[#25]: https://github.com/bact/licenseid/pull/25
[#28]: https://github.com/bact/licenseid/pull/28
[#31]: https://github.com/bact/licenseid/pull/31
[#32]: https://github.com/bact/licenseid/pull/32
