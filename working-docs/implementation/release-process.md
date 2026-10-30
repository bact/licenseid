---
Created: 2026-10-22
Last-Modified: 2026-10-30
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Release process

How a licenseid release is cut, as done for 0.5.0 (2026-10-22, PRs #85
to #95) and 0.6.0 (2026-10-27, PRs #96 to #101), and what went wrong on
the way. The developer tags and publishes; an
agent prepares and checks.

## Order

1. Merge every PR meant for the release. Entries for them go into the
   release's own `CHANGELOG.md` section (opened by the preparation PR), not
   into `[Unreleased]`: the tag does not exist yet.
2. Preparation PR: bump `__version__` in `src/licenseid/__init__.py`;
   `version`, `dateModified` and `datePublished` in `codemeta.json`; the
   section heading and date in `CHANGELOG.md`. `CITATION.cff` follows from
   `codemeta.json` by workflow.
3. Wait for CI on the merge commit on `main` (unit tests, build wheels, lint,
   type checking). Tag `v<version>` on that commit and publish the GitHub
   release; publishing starts `pypi-publish.yml`, which builds with
   `LICENSEID_REQUIRE_BUNDLE=1`.
4. Watch the publish run. Then install from PyPI in a clean environment
   and run `licenseid update` (see below).
5. Check that the PyPI page and the release list the wheel and the sdist.

If the release is published on another day than the one in the files, change
the dates in `codemeta.json` and `CHANGELOG.md` before tagging.

## Checks before the tag

- Pitloom and licenseid depend on each other: licenseid's build runs
  Pitloom's hook, and Pitloom imports licenseid. A release that renames or
  removes a public name (0.7.0: `resolve`, `AggregatedLicenseMatcher`,
  `LicenseMatch`) breaks every Pitloom whose `licenseid` requirement has no
  upper bound, and with it licenseid's own isolated build once the release
  is on PyPI. Before the tag: a Pitloom release that caps `licenseid` below
  the new version (or reads the new names) is on PyPI, and
  `.github/requirements-release.txt` pins Pitloom and licenseid to a pair
  that imports, and `build-system.requires` floors Pitloom at that release,
  so a build from the sdist without the pins cannot pick an older Pitloom
  (0.7.0: Pitloom 0.21.2). The wheel's SBOM check runs in its own
  environment for the same reason (`build.yml`).
- A new `trove-classifiers` release can fail `tests/test_trovenames.py`
  (a new `License ::` classifier): decide each new entry in
  `src/licenseid/trovenames.py` and `tests/trove_golden.py`.
- `main` CI is green on the commit to tag. Scorecard
  (`Scorecard supply-chain security`) can fail on GitHub's GraphQL
  (`githubv4.Query: Something went wrong`) while the code is fine: re-run it.
- `data` branch: `latest.json` answers at
  `https://raw.githubusercontent.com/bact/licenseid/refs/heads/data/spdx/format-1/latest.json`.
  The release build downloads the packaged bundle from it and fails without it
  (`LICENSEID_REQUIRE_BUNDLE=1`). The branch must exist before the first
  build: `build.yml` also requires the bundle, and failed with a 404 until
  the branch was pushed.
- `update --source compact` from a clean throwaway `HOME` builds a database
  (about 17 MB; 24.6 MB before XML was dropped).
- Build the wheel and sdist as the release does, with a local bundle:
  `LICENSEID_BUNDLE=<bundle> LICENSEID_REQUIRE_BUNDLE=1 uv build`. Both must
  hold `spdx-bundle.json.gz` (980,375 bytes for 3.29.0). The sdist holds
  only its allowlist (`only-include` in `pyproject.toml`, pinned by
  `tests/test_sdist_contents.py`): list it with `tar -tzf` and look for
  anything new. Build with `--python 3.10`: a local 3.14 could not resolve
  Pitloom's build dependency `onnxruntime` (2026-10-29). Install the wheel in a
  fresh venv and run `env -i HOME=<scratch> licenseid update --source packaged`:
  it must build the database with no network.
- The ID snapshot `tests/fixtures/license-list/spdx-license-ids.json` has the
  `license_list_version` of the packaged bundle. If SPDX released since,
  refresh it from a database `update` built (query in
  `tests/fixtures/README.md`) and run `tests/test_looseid.py`: its drift
  guard is the only check on CI that no two IDs of the new list share a
  loose-ID key (PR #96). A failure there means `versionkey.version_key` needs
  a rule, not that the snapshot should stay old.
  Refresh `tests/fixtures/license-list/spdx-exception-ids.json` with it
  (`SELECT exception_id, name, is_deprecated, superseded_by FROM exceptions
  ORDER BY exception_id`, in the file's format) and set the new
  `license_list_version` and `release_date` in both files. The database must
  be a build v2 or later (`StandardML-NJ` names `SMLNJ`). Refreshing means
  re-pinning the resolver corpus and the PyPI sample
  (`tests/fixtures/resolver_parity.tsv`, `pypi_values_2026-10*.tsv`): run
  `tests/test_resolver_sample.py`, whose guard lists every answer that moved.
  The sample is regenerated (`tools/pypi_licence_sample/README.md`, `export`).
  The parity file has no generator: re-pin it by hand at the boundary. Take
  the new answer columns from the code, keep `expected_0_7_0` and `why`, then
  update the `# rows:` line (count and SHA-256 of the lines after the header
  row; `tests/test_resolver_parity.py` checks both). Do it once, when the
  release's fixtures are frozen, and list what moved in `EXPECTED_CHANGES`
  or retire the entry. Bump `Last-Modified` of the files you touch.
- `pytest tests/ --run-benchmark` on the release commit: the benchmarks
  (accuracy, long inputs, linear time) do not run on every commit (PR #121).
  Or run the `Accuracy` workflow by hand with `full` ticked: it runs every
  benchmark, and the full accuracy sweep takes about an hour.
- `python -m tools.cli_matrix --db <copy> --check` when the CLI, exit codes or
  input handling changed since the last run (see `AGENTS.md`).
- Claims in the notes and the README match the code: they were checked by
  running the command, not by reading the text. One claim was caught that
  way (the roadmap said the CLI could not send a lone surrogate; an
  argument of invalid UTF-8 can).

## Traps seen

- An outside review after the last planned merge of 0.6.0 found four bugs,
  one a wrong licence from `detect(text="GPL-2.0-only+")` that the seeded
  tests could not show (#101). Before the tag, probe each new input shape on
  a full database built by `update`, against the last release.
- The release planned as 0.5.1 became 0.6.0 after its preparation PR was
  open: a new public API (`resolve()`, now `match()`) is a minor release.
  Rename the version in docs and comments too, not only in the three
  version files.
- A fix PR after the preparation PR goes into the open release section;
  merge its entry with the related one (`[#99], [#101]`), and keep Keep a
  Changelog's section order (Removed before Fixed).
- A local tool older than CI: ruff did not report import order (I001) that CI
  did. Run `ruff check --select I`.
- The mocked test `offline` fixture hides the packaged bundle; only a built
  wheel shows what a user gets. An editable install ships none.
- Windows timing and mtime tests are flaky at the edges: a cache "99 days old"
  against 100 (mtime rounding) and tarball bytes that differ by gzip's mtime
  (`release_fakes.tarball` fixes it with `GzipFile(mtime=0)`).
- A fixed timing limit near the measured time fails on a busy machine: 10x
  headroom (`test_short_tag.py` was 0.5 s, now 5 s; the quadratic bug it
  guards took 7 s).
- A script that edits a file by `index()` must search from the position of
  its anchor, or it matches an earlier copy; flake8 `F811` (redefinition)
  showed the damage. Restore with `git checkout` and redo.
- Never type a PR number before the PR exists; add the `[#N]` link after.
- Names for sources were decided late, after the confusion showed in release
  notes ("bundle" meant both the download and the file in the wheel). Write the
  release notes before the tag, and rename while nothing is released: it was
  one PR (#95) because no old name was public yet.
