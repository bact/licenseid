# Agent instructions

## Project context

- License ID detection using hybrid search (`licenseid` package).
- Architecture: SQLite FTS5 trigram tokenization (Tier 1 recall) and RapidFuzz (Tier 2 precision ranking).
- Matching modules: `matcher.py` (the pipeline), `retrieval.py` (Tier 1),
  `shorttext.py` (Tier 0 IDs and names), `ranking.py` (sort order and the
  `-only`/`-or-later` tie-breaker), `similarity.py`, `markers.py`,
  `identifiers.py`, `classify.py`, `normalize.py`. Keep `matcher.py` under the 800-line limit:
  put logic that needs no matcher state in one of the others.
- Build system: `hatchling` via PEP 621 `pyproject.toml`.
- Design docs: `working-docs/design/` — future work, plans, roadmaps, sketches; may be discarded, not yet built.
- Implementation docs and progress reports: `working-docs/implementation/` — record of what WAS built: decisions made, why things are the way they are, paths considered and rejected. Not a user manual. Start at `working-docs/implementation/README.md` for current state.
- Test fixtures: `tests/fixtures/README.md`
- Private alpha, one developer. No backward compat needed yet.
- `working-docs/` is internal notes only — content can change without notice. Any user-facing docs published outside this repo must not link into it; reference a PR or issue number instead.
- **Global file size**: soft limit ~400-500 lines, hard limit ~800 lines. Applies to all files — source, tests, docs. Split before crossing it; see `working-docs/design/complexity-and-file-size-roadmap.md` for the current backlog of files over the limit.
- **Doc file dating**: every `working-docs/` file's front matter carries `Created`/`Last-Modified` (`YYYY-MM-DD`), alongside the SPDX tags below. No date prefix on the filename — the front matter is authoritative.

## SPDX guidelines

- When doing normalization and matching, consult the
  SPDX License List matching guidelines and templates (Normative)
  https://spdx.github.io/spdx-spec/v3.0/annexes/license-matching-guidelines-and-templates/
- Be careful about the order of text transformation. The order is sensitive as text will be changed in each step.
- Document the text transformation steps in the code, explain the rationale, give references.

## CLI output

Unix philosophy. Consistent, predictable, parseable.

- Default: line-delimited, one data point per line.
- Field separator: space or tab (consistent).
- Key-value: `KEY=VALUE` — uppercase KEY, no spaces around `=`.
- Standard output carries only a command's result. Progress, warnings and
  errors go to standard error through `licenseid.console` (`status`, `warn`,
  `error`); never `print` or `click.echo` them directly.
- Errors and warnings follow one grammar, one event per line:
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`.
  - `LEVEL`: `ERROR` (the command fails, non-zero exit) or `WARNING` (a
    fallback lets it continue).
  - `SUBJECT`: the thing affected, a lowercase word or cache file name:
    `database`, `input`, `match`, `option`, `version`, `licenses.json`,
    `popularity.csv`, `spdx-data-v<ver>.tar.gz`.
  - `CONDITION`: short lowercase fragment, reused across subjects. The
    full current set (add new ones here): `not found`, `invalid`,
    `missing`, `empty`, `unreadable`, `binary file`,
    `not UTF-8, read as Latin-1`, `no license found`, `N days old`,
    `normalization vN outdated`, `download failed`, `cache read failed`,
    `cache write failed`, `cache unusable`, `download unusable`,
    `stale cache unusable`, `parse failed`,
    `N rows with missing or non-numeric num_pushers`, `update failed`,
    `delete failed`.
  - `DETAIL`: the variable part (exception text, value, path).
  - `ACTION`: what happens next, after a semicolon: the fallback taken
    (`using stale cache`, `downloading`, `counted as 0`) or the command for
    the user to run (`run 'licenseid update'`). A fallback goes on the same
    line as its cause, e.g.
    `popularity.csv: download failed: <error>; using stale cache`.
  - No trailing period, no "Please", no full sentences.
  - A failure worded this way is raised as `licenseid.errors.LicenseIdError`
    (`SUBJECT: CONDITION…`, no prefix); the CLI prints it after `ERROR:` and
    exits 1, or 2 for its subclass `InvalidInputError` (a usage error). The
    CLI also exits 2 for `DatabaseNotReadyError` (a database that is missing,
    empty, invalid or unreadable) in `match` and the `is-*` commands, where
    exit 1 already means "no". `update` and `--clear-cache` write or delete,
    so they refuse only an `invalid` database — one licenseid did not build
    — and accept every other condition, which is what they exist to fix.
  - A step that prints partial progress (`status(..., end="")`) and can fail
    must call `console.end_line()` in a `finally`, so the caller's next
    stderr line starts at column 0.
    Any other exception, including RuntimeError subclasses such as
    RecursionError, is wrapped as `SUBJECT: update failed: <Type>: <text>`.
  - `tests/conftest.py::check_diagnostic_grammar` fails any test that
    prints a line breaking this grammar.
- Must work with `awk`, `wc`, `xargs`, similar Unix tools.
- JSON output supported as options.

## Python

- Min version: Python 3.10.
- Idiomatic Python. Prefer built-ins (`list`, `dict`, `set`, `tuple`) unless `collections`/`collections.abc` clearly better.
- Full type annotations on all functions, methods, classes, variables. Minimize `Any`. Use `if TYPE_CHECKING:` for heavy type-only imports.
- Verify types with mypy (strict=true). Use pyright/pytype for second opinions. Recheck `# noqa:` and `# type: ignore`. Reset mypy cache on unexpected errors.
- Type stubs: no official stubs → check <https://github.com/python/typeshed> for stubs; unavailable → derive from source on GitHub/GitLab.
- Fully qualified names in docstrings for non-stdlib types (e.g., `numpy.ndarray`, not `ndarray`).
- No `assert` in production — tests only.
- No mutable default arguments.
- No wildcard imports (`from module import *`).
- No `pickle` (CWE-502).
- No `eval()` unless absolutely necessary and demonstrably safe.
- No hardcoded secrets/credentials/tokens.
- Defensive coding: check `None`/empty, handle exceptions for all external inputs.
- `time.monotonic()` for durations, not `time.time()`.
- All config in `pyproject.toml` where possible.
- `requires-python` must match actual min version.
- Make packages zip-safe when possible.
- Packaging metadata follows Core metadata spec: <https://packaging.python.org/en/latest/specifications/core-metadata/>
- Be careful of regex flags, lookahead, lookbehind, greediness, multi-line matching.

### Import order

Groups: stdlib → third-party → local, alphabetically within each. Don't reorder imports with comments explaining required order (circular import/init constraint).

### Type completeness

- All visible class vars, instance vars, methods annotated.
- All function/method params and return types annotated.
- Generic base classes have type args specified.
- Omit annotations only for:
  - Simple literal constants (e.g., `MAX = 50`, `RED = '#F00'`), preferably `Final`.
  - Enum member values inside `Enum`.
  - Module-level type aliases.
  - `self` and `cls` params.
  - `__init__` return type.
  - `__all__`, `__author__`, `__version__`, similar dunder module attrs.

## Code health and continuous refactoring

- **The Boy Scout Rule**: leave the codebase cleaner than you found it. Refactor proactively during small changes.
- **Prevent monoliths**: never let a single file (like `matcher.py` or `database.py`) become a dumping ground. Extract cohesive pieces into dedicated modules early — see the file-size limit above.
- **Consolidate patterns**: extract duplicated logic into shared helpers immediately. Don't copy-paste code.
- **Enforce file size limits**: split files *before* they cross the soft limit, not after.

## Linting and formatting

Run and fix all errors before committing:

```shell
ruff check
mypy
pylint
flake8
ruff format
```

- Complexity targets (pylint's own built-in defaults, checked clean outside this repo's config): Args≤5, Locals≤15, Nesting≤5, Branches≤12, Returns≤6, Statements≤50, McCabe≤10, Cognitive≤15.
  Enforced ceilings in `pyproject.toml`/`.flake8` are currently interim
  ratchets set to the exact current repo max (`max-args=5`,
  `max-branches=13`, `max-locals=23`, McCabe=12, Cognitive=29, module
  lines=926) — see
  `working-docs/design/complexity-and-file-size-roadmap.md` for the
  backlog that has to shrink before each ceiling can drop to its target.
  These are maximally tight — any regression trips CI immediately. Don't
  raise a ceiling to make a change pass; refactor instead, or lower the
  ceiling back down after shrinking the offender.
- Remove unused imports and trailing whitespace.
- Max line length = 88 (matches `.flake8`, `ruff`, and `[tool.pylint.format]`).

## File headers

All source files must have SPDX tags in this order (alphabetical):

```text
SPDX-FileCopyrightText: <year> <name>
SPDX-FileType: SOURCE                # or DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
```

`working-docs/` standalone docs also carry `Created` and `Last-Modified`
(`YYYY-MM-DD`) in the same front matter block, above the SPDX tags.

Sort SPDX metadata keys alphabetically.

## Testing

- Add tests for new behavior — cover success, failure, edge cases.
- Use pytest patterns, not `unittest.TestCase`.
- `spec`/`autospec` when mocking.
- `time_machine` for time-dependent tests.
- `@pytest.mark.parametrize` for multiple similar inputs.
- A new CLI option or API parameter goes into `tests/test_option_matrix.py`
  as an axis (or a value on one), so it is tested in combination with the
  others, not only on its own.

## Traps and test patterns

Things that cost time in earlier sessions; details in `working-docs/`.

- `CLAUDE.md` is a symlink to this file. Edit `AGENTS.md`. `.claude/` is
  gitignored.
- `flake8 src/ tests/` lints tests too: a test helper can set a complexity
  ceiling (the cognitive ceiling was `test_accuracy.py::run_accuracy_test`).
  Ceilings are exact ratchets: after a refactor re-measure across `src/` and
  `tests/`, and lower the ceiling if the last holder is gone.
- Refactor with **characterization tests first**: they found a real bug in
  every refactor so far. Pin the bug (`# BUG:`), refactor purely, then fix
  it as a separate step and flip the pin to a regression test.
- Tests have no `tests/__init__.py`: import shared helpers with
  `from conftest import ...` (not `tests.conftest`). Helpers there:
  `make_memory_db_path`, `fake_requests_get`, `leftover_tmp_files`.
- A shared-cache in-memory SQLite DB vanishes when its last connection
  closes, and CPython drops an unreferenced connection at once:
  `make_memory_db_path` opens its keep-alive connection *before* building
  `LicenseDatabase`. Keep that order.
- No test may touch the network: patch `requests.get` (autospec). Never
  modify or clear the real cache in `~/.local/share/licenseid/`; it is fine
  to read it to validate a parser against real data.
- CI tests on Python 3.10 and 3.14 only (it builds on 3.10-3.14); the local
  `.venv` is 3.10. For anything stdlib-sensitive, also run
  `uv run --python 3.14 --group test pytest ...`
  (set `UV_PROJECT_ENVIRONMENT` to a scratch dir). Simulate an older Python
  with a module flag, never by deleting stdlib attributes
  (`tarfile.data_filter` breaks `tarfile` itself on 3.12+).
- Mutation-check new tests by breaking a line and rerunning; clear
  `__pycache__` between mutants (a same-size mutant restored within the same
  second leaves a stale `.pyc`).
- Pytest cannot see the shell, locale, stdio, `HOME`, signal and input-size
  interactions between the OS and the CLI. Run the manual matrix,
  `python -m tools.cli_matrix --db <copy of a real database> --check`, before
  a PR that touches the CLI, exit codes, streams, input handling or the
  database path. It reports flags that are not in `baseline.txt`; read
  `tools/cli_matrix/README.md` first. Never run its cells by hand with
  `HOME` unset: Python then resolves the real cache (an early version
  deleted the developer's `licenses.db` that way).
- `database.py` imports `spdx_source` lazily (keeps `requests` off the match
  path and avoids an import cycle). Do not import `licenseid.__version__`
  at module level in `spdx_source.py`.
- Text extracted from `[`/`{`-starting input with no extension is tried as
  JSON first and falls through to TOML/INI; a synthetic marker candidate is
  only built for a valid SPDX expression or `LicenseRef-*`, never for free
  text.
- "or any later version" has ONE reader, `classify.OR_LATER_PHRASE`; the
  tie-breaker (`ranking`), `identifiers.disambiguate_deprecated_id` and
  `markers` import it. Add a phrasing there and to `PHRASES` in
  `tests/test_match_ordering.py`; do not write a regex of your own. The
  ranking and the tie-breaker sort with `ranking.ranking_key`; short-text
  results sort by `(-score, license_id)`.
- A regex with `\s+` directly followed by a class that also matches
  whitespace (`\s+[\s/*#]*`) is quadratic on a long run of spaces (5 s at
  32,000): write `\s[\s/*#]*`. Time every new prose regex on `"x" + " " * N`
  payloads (see `test_the_phrase_regex_does_not_backtrack`).
- A fixture imported into a test module and then used as its argument trips
  ruff `F811`/flake8 (the argument redefines the import). Put a shared fixture
  in `tests/conftest.py`; keep plain helpers in a module (`ordering_helpers`,
  `db_asserts`).
- Judge `pylint` by its exit code (`pylint src/ tests/ >/dev/null; echo $?`),
  not the rating: one convention message still prints `10.00/10` and exits
  16, and CI fails on the exit code. Run CI's own commands, and plain
  `pytest tests/` (no `-m 'not benchmark'`).
- A flag in `tools/cli_matrix/baseline.txt` can stop flagging because the
  command now fails *earlier*, not because the defect is gone. Read the
  cell's recorded output in `.cli-matrix/results.json` before deleting the
  line, and record why it went.
- `--db` can name a thing that blocks or lies. Check the file type
  (`stat.S_ISREG`/`S_ISDIR`) before opening: a named pipe makes a read-only
  open hang for ever, with no exit code and no traceback, and a test for it
  hangs too. `file::memory:NAME` is a file on disk (only `mode=memory` and
  the exact base `file::memory:` are memory), and `file://localhost/p` and
  `?vfs=` are valid spellings SQLite resolves.
- Resolve a path spelling once, in `dbcheck._os_file`, not with an
  `endswith` patch at the call site: `x`, `x/` and `x/.` must reach the same
  verdict, on every command.
- `dbcheck` answers read and write differently on purpose: read is
  fail-open (`check_database_ready` ignores the `unknown` tag), write and
  delete are fail-closed (`reject_foreign_database` refuses it). Keep the
  `Refusal` tag when adding a condition, and decide both policies.
- `Path.unlink(missing_ok=True)` swallows `FileNotFoundError` only — a
  parent that is a file still raises `NotADirectoryError`.
- Database tests must import the autouse `safe_home` fixture from
  `tests/db_asserts.py` (it patches `Path.home` as well as `HOME`) with
  `# noqa: F401  # pylint: disable=unused-import`.
- Do not run a mutation-testing agent while another agent edits `src/`: a
  snapshot taken then can capture a live mutant and produce phantom
  findings. Diff any snapshot against the working tree first.
- Details and the rest of the findings from PR #55:
  `working-docs/implementation/database-readiness-gate.md`.

## Git and pull requests

- Commit messages: user impact, not implementation details.
- Follow: <https://chris.beams.io/posts/git-commit/>
- Every PR must address: **What changed?** / **Why?** / **Breaking changes?**
- Update `CHANGELOG.md` for significant changes per Keep a Changelog (<https://keepachangelog.com/>) and Semantic Versioning (<https://semver.org/>). Mark breaking changes clearly with migration instructions.

## Project metadata consistency

Keep in sync: `pyproject.toml`, `codemeta.json`, other metadata files.

`CITATION.cff` is generated from `codemeta.json` by
`.github/workflows/codemeta2cff.yml`; do not edit it by hand. On a release,
update `version`, `dateModified` and `datePublished` in `codemeta.json`
(`dateModified` becomes `date-released` in `CITATION.cff`).

Consistent fields: project name, version, author/contributor names, license, description, repository URL, keywords/tags (same order).

## Dependencies

- Sort in `pyproject.toml`. (Do not use `requirements.txt` or legacy setup files).
- Use most current compatible version.
- Verify package names — guard against typosquatting/slopsquatting.
- Remove unused imports and dependencies.
- Warn about abandoned packages; suggest maintained replacements.

## Security

- No deprecated/obsolete/insecure libraries/APIs.
- Validate/sanitize all user inputs (SQL injection, XSS, buffer overflows, path traversal CWE-22).
- No hardcoded secrets. Use env vars or secret managers.
- Strong, well-established crypto algorithms and key sizes.
- OAuth2/OpenID Connect for auth.
- Regularly update dependencies to latest secure versions.

## Shell scripts

- Account for GNU/BSD/macOS/Unix tool differences.
- Defensive variable expansion; quote paths and variables.
- Mind single-quote vs double-quote semantics.

## Naming

- ASCII letters, digits, hyphens (`-`), underscores (`_`) only.
- Standard naming conventions for the language/framework.
- Noun number: singular for single-entity classes, plural only for collections/utility modules/aggregates.

## Markdown

- Metadata as YAML front matter between triple-dashed lines (Hugo/Jekyll style).
- Standard Markdown; avoid GitHub-specific extensions.
- `sentence case` for headings/titles.
- Max line length = 80
- Run Markdownlint.

## Writing style

- British English for docs, comments, text. American English for code only.
- Active voice; concise sentences; no jargon/idioms.
- Short comments — don't restate the obvious.
- Consistent terminology throughout.
- Define acronyms on first use.
- Parallel structure in lists.
- Citations: Chicago style unless specified.

## Diagrams (ASCII/text)

Count characters, align carefully. Misaligned ASCII = bug.

## Versions

Verify version exists and is compatible before suggesting. Prefer Semantic Versioning.

## Boundaries

**Ask before doing:**

- Large cross-package refactors.
- New dependencies with broad impact.
- Destructive data or migration changes.

**Never:**

- Commit secrets, credentials, or tokens.
- Edit generated files by hand when generation workflow exists.
- Use destructive git operations unless explicitly requested.

