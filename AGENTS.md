# Agent instructions

## Project context

- License ID detection using hybrid search (`licenseid` package).
- Architecture: SQLite FTS5 trigram tokenization (Tier 1 recall) and RapidFuzz
  (Tier 2 precision ranking).
- Matching modules: `detector.py` (the pipeline), `retrieval.py` (Tier 1),
  `shorttext.py` (Tier 0 IDs and names), `looseid.py` (a loosely written
  ID: "Apache2", "GPLv3", "GPLv2 or any later version"), `ranking.py`
  (sort order and the `-only`/`-or-later` tie-breaker), `similarity.py`,
  `markers.py`, `plusoperator.py` (the "+" operator), `quotes.py` (quote
  marks around a whole declared value), `versionkey.py` (one key for each
  spelling of an ID), `trovenames.py` (the `License ::` trove names as
  data), `resolver.py` (a declared licence value to an SPDX expression and
  the steps taken; its types and vocabularies are in `resolvertypes.py`),
  `keptdetector.py` (`licenseid.detect()`: one `LicenseDetector` kept per
  default database file), `listlookup.py` (the list lookups the resolver
  reads through: a Protocol), `listrules.py` (which SPDX entries are kept and
  what a deprecated ID points to; `records.py` builds rows from it),
  `resolveleaf.py` (the reading of one value that names one licence, called
  by `resolver.py` per value), `resolvecompound.py` (a compound, each
  operand read by `resolveleaf`), `resolvetrove.py` (a trove classifier name
  or path, and a name with its short form; the table is `trovenames.py`),
  `resolveprose.py` (the prose form of one ID: `BSD 3-Clause License`),
  `resolvesemicolon.py` (licences joined by `;`: listed, no operator),
  `exprcanon.py` (its leaves and canonical
  order), `exprtokens.py` (the words of an expression), `resolverinfo.py`
  (the resolver, parser and list blocks of a result),
  `dropguard.py` (the characters and words a loose reading must not drop:
  `Apache 2.0?`, `REM MIT`), `listindex.py` (the shipped SPDX bundle in
  memory, a `ListLookup` for `match()` with no database),
  `listsource.py` (which list `match()` reads: database or packaged),
  `climatch.py` (the `licenseid match` command; what it shares with
  `cli.py` is in `clicommon.py`), `identifiers.py`, `classify.py`,
  `normalize.py`, `textinput.py` (bytes to text), `manifest.py` (the
  `license` field of package.json, pyproject.toml, Cargo.toml, setup.cfg),
  `datadir.py` (the default database path), `dbconnection.py` (SQLite
  connections), `dbcache.py` (whole-table reads kept per database),
  `fingerprint.py` (the maths), `fingerprintstore.py` (its table),
  `spdxdata.py` (an SPDX release as data: reads the upstream tarball and a
  bundle, standard library only), `records.py` (the database rows built from it),
  `releasesource.py` (where `update` gets a release: compact, upstream or
  packaged, and the order between them),
  `dbschema.py` (the tables and whether a file has them), `output.py` (the
  CLI's standard output and what a
  failed write means), `result.py` (the public result and its JSON and text
  lines), `types.py`, `usage.py` (click's usage errors in the grammar).
  Keep `detector.py` under the 800-line limit: put logic that needs no
  detector state in one of the others.
- Release sources of `update`, by where the data comes from: `compact`
  (our 1 MB bundle on the `data` branch), `upstream` (SPDX's own tarball),
  `packaged` (the bundle in the wheel). "Bundle" is only the file format
  (`spdxdata`, `spdx-bundle*.json.gz`); say `compact` or `packaged` for a
  source. Terms: `working-docs/implementation/data-fetching-and-caching.md`.
- Releasing: `working-docs/implementation/release-process.md` (order, checks
  before the tag, traps).
- Build system: `hatchling` via PEP 621 `pyproject.toml`.
- Design docs: `working-docs/design/` — future work, plans, roadmaps, sketches;
  may be discarded, not yet built.
- Implementation docs and progress reports: `working-docs/implementation/` —
  record of what WAS built: decisions made, why things are the way they are,
  paths considered and rejected. Not a user manual. Start at
  `working-docs/implementation/README.md` for current state.
- Paper notes: `working-docs/paper-notes/` — sourced raw material for an
  academic write-up (system, results, history, human–AI sessions). Add to
  it when a finding is worth publishing; start at its `README.md`.
- Test fixtures: `tests/fixtures/README.md`
- User docs: `README.md` (overview, CLI, Python API) and `docs/match.md`
  (every field of `match()`'s result, its categories and trust, the
  reasons for a refusal, quote marks). A change to any of those updates
  `docs/match.md`; `tests/test_resolver_shapes.py` checks its category
  table.
- Which licence values `match()` should read next: measure, do not guess.
  `tools/pypi_licence_sample/README.md` samples real PyPI values and counts
  what `match()` reads; findings in
  `working-docs/design/resolver-0-7-evidence.md`.
- Private alpha, one developer. No backward compat needed yet.
- `working-docs/` is internal notes only — content can change without notice.
  Any user-facing docs published outside this repo must not link into it;
  reference a PR or issue number instead.
- **Global file size**: soft limit ~400-500 lines, hard limit ~800 lines.
  Applies to all files — source, tests, docs. Split before crossing it; see
  `working-docs/design/complexity-and-file-size-roadmap.md` for the current
  backlog of files over the limit.
- **Doc file dating**: every `working-docs/` file's front matter carries
  `Created`/`Last-Modified` (`YYYY-MM-DD`), alongside the SPDX tags below. No
  date prefix on the filename — the front matter is authoritative.

## SPDX guidelines

- When doing normalization and matching, consult the
  SPDX License List matching guidelines and templates (Normative)
  <https://spdx.github.io/spdx-spec/v3.0/annexes/license-matching-guidelines-and-templates/>
- Be careful about the order of text transformation. The order is sensitive as
  text will be changed in each step.
- Document the text transformation steps in the code, explain the rationale,
  give references.

## CLI output

Unix philosophy. Consistent, predictable, parseable.

- One pattern for every result line of every command (`detect`, `match`,
  `update`, `is-*`), written through `output.echo`:
  - Default: line-delimited, one data point (one record) per line.
  - Fields: `KEY=VALUE`, uppercase KEY, no spaces around `=`, one tab
    between fields (`result.fields_line`). A key ends at the first `=`.
  - Escaping: a value is written as it is, except a tab, CR, LF and
    backslash (`\t`, `\r`, `\n`, `\\`), and a character the stream's
    encoding cannot hold (`\xHH`, `\uHHHH`, `\UHHHHHHHH`, by
    `output.echo`); `result.text_field` writes a value,
    `result.read_text_field` reads it back.
  - Nothing is an empty value (`SIMILARITY=`, `EXPRESSION=`); a flag is
    `true` or `false`.
  - `--json`: the same result, one object per line, its keys the text
    keys in lower case (`EXPRESSION` is `expression`), nothing `null`, a
    flag a boolean. `match --json` holds the whole resolution, of which
    the text lines show a part.
  - --json and any JSON output will always write with RFC 8785: JSON
    Canonicalization Scheme (JCS). Every JSON the CLI writes goes through
    the one writer, `result.json_line`, as UTF-8 bytes on every locale
    (`output.echo_json`, one object per line): never `json.dumps` on an
    output path.
  - Exit codes: 0 an answer, yes or done; 1 no answer, no, or an action
    that failed (`update`, a delete `--clear-cache` could not make); 2 a
    usage error, unusable input, a database not ready, or a result that
    could not be written. Exit 1 of `detect` and `match` prints nothing on
    standard error.
  - The only exceptions: `detect --bold` (the top ID alone, one line),
    `--version` (`licenseid <version>`) and `--help`.
  - `tests/test_output_pattern.py` runs every command, text and `--json`,
    and holds each line to this pattern.
- Standard output carries only a command's result. Progress, warnings and
  errors go to standard error through `licenseid.console` (`status`, `warn`,
  `error`); never `print` or `click.echo` them directly.
- Every line licenseid writes ends in `\n` on every platform, results and
  diagnostics alike: `console.emit` is the one writer of both streams. It
  writes bytes under the text stream, so Windows does not turn `\n` into
  `\r\n` (which `awk` in Git Bash keeps in the last field), in the
  stream's encoding with backslash escapes (UTF-8 for `--json`). Tests
  simulate Windows with a `TextIOWrapper(..., newline="\r\n")`
  (`tests/test_output_encoding.py`).
- Errors and warnings follow one grammar, one event per line:
  `LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION]`.
  - `LEVEL`: `ERROR` (the command fails, non-zero exit) or `WARNING` (a
    fallback lets it continue).
  - `SUBJECT`: the thing affected, a lowercase word or cache file name:
    `command`, `database`, `detect`, `input`, `option`, `output`, `usage`,
    `version`, `latest.json`, `licenses.json`, `popularity.csv`,
    `spdx-bundle-v<ver>.json.gz`, `spdx-bundle.json.gz` (the packaged bundle in
    the wheel), `spdx-data-v<ver>.tar.gz`.
  - `CONDITION`: short lowercase fragment, reused across subjects. The
    full current set (add new ones here): `not found`, `invalid`,
    `missing`, `empty`, `unreadable`, `binary file`,
    `not UTF-8, read as Latin-1`, `N days old`,
    `normalization vN outdated`, `build vN outdated`, `build vN newer`,
    `download failed`,
    `cache read failed`,
    `cache write failed`, `cache unusable`, `download unusable`,
    `stale cache unusable`, `parse failed`, `variant not stated`,
    `N rows with missing or non-numeric num_pushers`, `update failed`,
    `delete failed`, `write failed`, `compact failed`,
    `older than the database`.
  - `DETAIL`: the variable part (exception text, value, path), on one
    line: a path or file name through `errors.shown` (a control character
    escaped, `;` as `,`), a value through `errors.one_line` (folded, cut to
    60), an exception through `errors.typed`. Not the result escaping: a
    backslash stays, so a Windows path reads as typed.
  - `ACTION`: what happens next, after a semicolon: the fallback taken
    (`using stale cache`, `using stale <file>`, `downloading`,
    `downloading <file>`, `using cached <file>`, `using packaged data v<ver>`,
    `counted as 0`) or the command for the user to run
    (`run 'licenseid update'`). A fallback goes on the same line as its
    cause, e.g.
    `popularity.csv: download failed: <error>; using stale cache`.
  - No trailing period, no "Please", no full sentences.
  - A failure worded this way is raised as `licenseid.errors.LicenseIdError`
    (`SUBJECT: CONDITION…`, no prefix); the CLI prints it after `ERROR:` and
    exits 1, or 2 for its subclass `InvalidInputError` (a usage error). The
    CLI also exits 2 for `DatabaseNotReadyError` (a database that is missing,
    empty, invalid or unreadable) in `detect`, `match` and the `is-*`
    commands, where exit 1 already means "no". `update` and `--clear-cache`
    write or delete, so they refuse only an `invalid` database — one
    licenseid did not build — and accept every other condition, which is
    what they exist to fix.
  - Write a result line with `output.echo` (or `output.echo_json`), not
    `click.echo` or `print`: a result
    that cannot be written (standard output closed, a full disk) exits 2
    with `output: write failed: <reason>`, never 0 or 1. A reader that
    closes the pipe (`| head -1`) ends the run quietly with 141, and Ctrl-C
    with 130, both without a message (`DatabaseErrorGroup`). `--help` and
    `--version` go through `echo` too (`output.EchoHelpCommand`).
    `cli.main()` runs click outside its standalone mode, so Ctrl-C while
    options are parsed is 130 too. A closed
    standard input is no input; a failing standard error is skipped and
    pointed at the null device, or the flush at exit would turn every exit
    status into 120.
  - click's usage errors are worded in the grammar too
    (`ERROR: option: not found: --bogus; did you mean --bold`): `usage.py`
    re-raises them as `UsageLineError` in `parse_args` (option callbacks
    included) and in the group's `invoke` (an unknown command, and a
    command's own `BadParameter`), so click's standalone mode (every
    `CliRunner` test) and `cli.main()` print the same line. A command run
    outside the group would show click's format: wrap it too. With no
    subcommand, the help goes to standard error (exit 2), through
    `console.write`.
  - A step that prints partial progress (`status(..., end="")`) and can fail
    must call `console.end_line()` in a `finally`, so the caller's next
    stderr line starts at column 0.
    Any other exception, including RuntimeError subclasses such as
    RecursionError, is wrapped as `SUBJECT: update failed: <Type>: <text>`.
  - `tests/conftest.py::check_diagnostic_grammar` fails any test that
    prints a line breaking this grammar.
- Must work with `awk`, `wc`, `xargs`, similar Unix tools.
- `detect --json` prints JSON Lines, one
  RFC 8785 (JCS) object per result, through `licenseid.result.json_line`;
  the text line comes from `text_line` beside it. Both print the public form
  `result.public_result` builds at the one exit of `detect()`: tiers rank on
  their raw score (above 1 for a Tier 0 ID or name hit, look-alikes
  included, and for a close text with its bonuses), never on the public
  one, capped to 1. `exact`
  is what tells results at 1 apart; set it where a result is made.

## Python

- Min version: Python 3.10.
- Idiomatic Python. Prefer built-ins (`list`, `dict`, `set`, `tuple`) unless
  `collections`/`collections.abc` clearly better.
- Full type annotations on all functions, methods, classes, variables. Minimize
  `Any`. Use `if TYPE_CHECKING:` for heavy type-only imports.
- Verify types with mypy (strict=true). Use pyright/pytype for second opinions.
  Recheck `# noqa:` and `# type: ignore`. Reset mypy cache on unexpected errors.
- Type stubs: no official stubs → check <https://github.com/python/typeshed> for
  stubs; unavailable → derive from source on GitHub/GitLab.
- Fully qualified names in docstrings for non-stdlib types (e.g.,
  `numpy.ndarray`, not `ndarray`).
- No `assert` in production — tests only.
- No mutable default arguments.
- No wildcard imports (`from module import *`).
- No `pickle` (CWE-502).
- No `eval()` unless absolutely necessary and demonstrably safe.
- No hardcoded secrets/credentials/tokens.
- Defensive coding: check `None`/empty, handle exceptions for all external
  inputs.
- `time.monotonic()` for durations, not `time.time()`.
- All config in `pyproject.toml` where possible.
- `requires-python` must match actual min version.
- Make packages zip-safe when possible.
- Packaging metadata follows Core metadata spec: <https://packaging.python.org/en/latest/specifications/core-metadata/>
- Be careful of regex flags, lookahead, lookbehind, greediness, multi-line
  matching.

### Import order

Groups: stdlib → third-party → local, alphabetically within each. Don't reorder
imports with comments explaining required order (circular import/init
constraint).

### Type completeness

- All visible class vars, instance vars, methods annotated.
- All function/method params and return types annotated.
- Generic base classes have type args specified.
- Omit annotations only for:
  - Simple literal constants (e.g., `MAX = 50`, `RED = '#F00'`), preferably
    `Final`.
  - Enum member values inside `Enum`.
  - Module-level type aliases.
  - `self` and `cls` params.
  - `__init__` return type.
  - `__all__`, `__author__`, `__version__`, similar dunder module attrs.

## Code health and continuous refactoring

- **The Boy Scout Rule**: leave the codebase cleaner than you found it. Refactor
  proactively during small changes.
- **Prevent monoliths**: never let a single file (like `detector.py` or
  `database.py`) become a dumping ground. Extract cohesive pieces into dedicated
  modules early — see the file-size limit above.
- **Consolidate patterns**: extract duplicated logic into shared helpers
  immediately. Don't copy-paste code.
- **Enforce file size limits**: split files *before* they cross the soft limit,
  not after.

## Linting and formatting

Run and fix all errors before committing:

```shell
ruff check
mypy
pylint
flake8
ruff format
```

- Complexity targets (pylint's own built-in defaults, checked clean outside this
  repo's config): Args≤5, Locals≤15, Nesting≤5, Branches≤12, Returns≤6,
  Statements≤50, McCabe≤10, Cognitive≤15.
  Enforced ceilings in `pyproject.toml`/`.flake8` are currently interim
  ratchets set to the exact current repo max (`max-args=5`,
  `max-branches=13`, `max-locals=22`, McCabe=12, Cognitive=29, module
  lines=773) — see
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
- CI tests on Python 3.10 and 3.14 (Ubuntu) and 3.11 (Windows); it builds
  on 3.10-3.14 (Ubuntu). The local environment is the pyenv virtualenv
  named in `.python-version` (`license310`, Python 3.10, an editable
  install); there is no `.venv`. It can lag `pyproject.toml` (it lacked
  `rfc8785` and `hatchling`): then build a scratch one,
  `UV_PROJECT_ENVIRONMENT=<scratch> uv sync --python 3.10 --all-groups`.
  For anything stdlib-sensitive, also run
  `uv run --python 3.14 --group test pytest ...`. Always set
  `UV_PROJECT_ENVIRONMENT` to a scratch dir for `uv run` and `uv sync`:
  without it uv creates a `.venv` in the checkout. Simulate an older Python
  with a module flag, never by deleting stdlib attributes
  (`tarfile.data_filter` breaks `tarfile` itself on 3.12+).
- Mutation-check new tests by breaking a line and rerunning; clear
  `__pycache__` between mutants (a same-size mutant restored within the same
  second leaves a stale `.pyc`). To mutate a copy of the tree, run it with
  `PYTHONPATH=<copy>/src`: the environment is an editable install of this
  checkout, so without it the tests import the unmutated `src/` and every
  mutant seems to survive.
- A negative test ("answers no licence", "ranks X below Y") on a seeded
  database passes trivially when its rows have no `search_text`: Tiers 1
  and 2 retrieve nothing. Seed the near neighbours the real list has, with
  a text (`Lic(..., search_text=...)`, as `tests/test_qualified_plus.py`
  does), mutate the fix to see the test fail, and probe the input on a full
  database too. A four-row test hid a wrong answer that a reviewer found on
  3.29.0 (PR #101).
- Windows: before touching `dbcheck.py`, a database path or `file:` URI,
  `Path.home()`, or a test that needs POSIX features (chmod, symlinks,
  signals, `/bin/sh`), read `working-docs/implementation/cross-platform.md`.
  Mark such a test `posix_only` (`tests/conftest.py`); build a `file://` URI
  with `Path.as_posix()`, not `f"file://{path}"`. CI runs Windows on 3.11.
- Pytest cannot see the shell, locale, stdio, `HOME`, signal and input-size
  interactions between the OS and the CLI. Run the manual matrix,
  `python -m tools.cli_matrix --db <copy of a real database> --check`, before
  a PR that touches the CLI, exit codes, streams, input handling or the
  database path. It reports flags that are not in `baseline.txt`; read
  `tools/cli_matrix/README.md` first. Never run its cells by hand with
  `HOME` unset: Python then resolves the real cache (an early version
  deleted the developer's `licenses.db` that way).
- One reader for user input: `textinput.read_text_file` / `decode_input`
  (UTF-8 with BOM dropped, else Latin-1 with a warning, NUL means binary,
  checked by `reject_binary`, which `--text` also calls). The CLI and
  `detect(file_path=...)` both use it; do not `open()` a user file
  anywhere else (`tests/test_textinput.py` fails if `cli.py` or `detector.py`
  does). The SPDX data files stay strict UTF-8 on purpose: a fallback there
  would hide a corrupt download. A text with a lone surrogate (an API string,
  or a command-line argument of invalid UTF-8, which Python decodes to
  `\udcXX`) cannot be encoded for SQLite's parameter binding:
  `textinput.reject_lone_surrogate` raises `InvalidInputError` at the one
  place the detector takes a text, and `cli.reject_unencodable` exits 2 first
  for `--text` and the argument.
- `hatch_build.py` (Hatch custom hook, standard library only: the build
  environment has no `licenseid`) puts the packaged SPDX bundle in the wheel and
  the sdist (`src/licenseid/data/`, gitignored). `LICENSEID_BUNDLE=skip|<path>`
  and `LICENSEID_REQUIRE_BUNDLE=1` steer it; CI jobs that only install the
  package set `skip`. An editable install ships nothing, so a local run never
  sees a snapshot, and the `offline` fixture hides one from the tests;
  `listindex.packaged_index()` keeps one per process, which `offline` and
  `release_fakes.ship` forget. Only an
  unpacked sdist (it has `PKG-INFO`) uses a file in `src/licenseid/data/`; a
  checkout ignores one left there and downloads. The
  hook repeats the URL and file names of `spdx_source` and `spdxdata`;
  `tests/test_hatch_build.py` checks they agree.
- `database.py` imports `spdx_source` lazily (keeps `requests` off the match
  path and avoids an import cycle). Do not import `licenseid.__version__`
  at module level in `spdx_source.py`.
- Text extracted from `[`/`{`-starting input with no extension is tried as
  JSON first and falls through to TOML/INI. Every source of a license value
  (SPDX tag, JSON, TOML, INI and an explicit `license_id`) resolves through
  one function, `MarkerDetector.resolve_license_value`, and every expression
  through `_synthetic_candidate`: a candidate only for a valid SPDX expression
  or
  `LicenseRef-*` with at least one recognised ID, never for free text or an
  unknown ID. `is_*()` and the CLI's `is-*` commands answer from
  `LicenseDetector.resolve_record`, so they agree with `detect`; do not look
  a record up in the database on the side.
- An `SPDX-License-Identifier` tag value is the rest of its line, up to the
  next tag on it (`[ \t]`, never `\s`, so a tag cannot reach across a line
  break), and
  `identifiers.leading_expression` decides where the expression in it ends:
  only AND, OR and WITH join two parts, so a token none of them bridges ends
  it, and a dangling or unbalanced value is no expression at all. Do not
  write the SPDX grammar into a regex again; comment closers need no case of
  their own. Only white space joins the parts of an expression, and an
  "or later" grant qualifies the license beside it (`identifiers`
  `qualify_trailing_grant`, still through `classify.OR_LATER_PHRASE`), so
  `MIT OR GPL-2.0 or later` is `GPL-2.0-or-later OR MIT` and the grant of a
  WITH belongs to its license, not its exception. A version number between
  the ID and the phrase means another license stands in between, so the grant
  is that one's. A grant ends the expression, so a value that goes on after
  one (`MIT AND GPL-2.0 or later AND Apache-2.0`) is refused rather than
  answered without the operands that follow.
- A tag and a `license` field hold whatever their author wrote, but `--id`
  and `detect(license_id=...)` declare ONE license:
  `identifiers.is_simple_expression` is the one judge of that (an ID,
  optionally with `+` unless it ends in `-only` or `-or-later`, or a
  `LicenseRef-*`, which takes no `+`; either
  `WITH` an exception, in any brackets), and
  both entry points read it — `cli.reject_compound_id` exits 2 through
  `errors.invalid_id_error`, `LicenseDetector._try_explicit_id_match`
  raises. Text that is one simple expression and nothing else (`GPL-2.0+`)
  is read as `license_id` reads it, by
  `LicenseDetector._try_tier0_short_text`, whatever brings it (argument,
  `--text`, stdin, file, `detect(text=...)`); the rest, and a value that
  resolves to no license, is matched as text. The CLI
  makes no ID guess of its own. Ask the predicate BEFORE calling
  `detect(license_id=...)`, which raises rather than returning no match.
  Do not widen `--id` to expressions
  again: `MIT OR Apache-2.0` declares neither license, and the flags
  (`is-osi`, `is-fsf`) have no answer for it.
- The "+" operator has ONE reader, `plusoperator.PLUS_OPERATOR`
  (`strip_plus_operator`, `replace_plus_operator`, `plus_after_qualifier`;
  standard library only, so any module can import it): a "+" right after an
  ID, never after a space, a "+", an exception or a `LicenseRef-*`. The
  version key (`versionkey.version_key`) spells it out with it. The
  tokenizer (`is_simple_expression`) and the prose shorthand of `classify`
  ("GPLv2+", which also takes a comma or full stop after it) read the same
  grammar their own way: `tests/test_plus_readers.py` holds all four to one
  table. Change one, run it.
- "or any later version" has ONE reader, `classify.OR_LATER_PHRASE`; the
  tie-breaker (`ranking`), `identifiers.disambiguate_deprecated_id`,
  `markers` and `looseid` import it. `looseid.declared_grant_id_text` only
  finds where a declared value's grant starts and lets it judge, reading a
  bare "or later" as after a number unless `classify.is_negated`. Add a
  phrasing there and to `PHRASES` in `tests/ordering_helpers.py`, which
  `test_match_ordering` and `test_resolver_shapes` hold every reader to; do
  not write a regex of your own. The
  ranking and the tie-breaker sort with `ranking.ranking_key`; short-text
  results sort by `(-score, license_id)`.
- A change to the rows `records` builds bumps `records.BUILD_VERSION`, as a
  change to `normalize_text` bumps `database.NORMALIZATION_VERSION`: a
  database stamped older warns (`build vN outdated`) and `update` rebuilds
  it at the release it has. Without the bump, a user who upgrades keeps the
  old rows and is told nothing. Stamps compare as numbers (`"10"` is newer
  than `"2"`); a newer one warns `build vN newer` and is never rebuilt, and
  one that is no number is older. Only a database opened without `create`
  warns: `update`, which creates, is about to fix it.
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
  `pytest tests/` (no `-m 'not benchmark'`). CI's ruff is newer than a local
  one: also run `ruff check --select I` (import order failed CI once with a
  clean local run). pylint's duplicate-code check (R0801) sees two similar
  inline scripts in different test files: put a probe script in
  `tests/db_asserts.py` and import it.
- A flag in `tools/cli_matrix/baseline.txt` can stop flagging because the
  command now fails *earlier*, not because the defect is gone. Read the
  cell's recorded output in `.cli-matrix/results.json` before deleting the
  line, and record why it went.
- `--db` can name a thing that blocks or lies. Check the file type
  (`stat.S_ISREG`/`S_ISDIR`) before opening: a named pipe makes a read-only
  open hang for ever, with no exit code and no traceback, and a test for it
  hangs too: run `check_database_ready` on a FIFO in a child process with a
  timeout (`db_asserts.probe_check_does_not_hang`), so a broken guard fails
  the test after 30 s instead of hanging the run. `file::memory:NAME` is a
  file on disk (only `mode=memory` and
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
- `detect()` returns the public form: a score capped to 1 and rounded to 4
  places, so an exact hit and a look-alike both show 1. Code or a test that
  ranks, orders or asks "above 1" (Tier 0's early return, the tie-breaker)
  reads the raw records of `_match_raw`, not `detect()`. `exact` is set
  where a result is made, never derived from the score; an exact text is
  the whole non-empty normalised input equal to the licence's
  `search_text`. A deprecated name is not exact only when a row in use has
  the same normalised name: making every deprecated row inexact lost
  AGPL-3.0 and GFDL-1.x, which have names of their own.
- A `detect()` call shares one SQLite connection among its lookups, through
  `LicenseDatabase.reading()` (per thread, opened at the first query,
  closed at the end): query through `_connection()`, never
  `sqlite3.connect`, and wrap a new entry point that makes several lookups
  (`MarkerDetector` or `identifiers` called on their own still open one per
  query). Only the outermost query in a block ends its transaction, and
  each query starts with the default `row_factory`. Tests count connections
  with the `opened` fixture in `conftest.py`. Tier 0's RapidFuzz scorers
  take `score_cutoff=threshold`, which changes no result and stops early on
  a long word.
- A lookup by licence ID never scans a table: `dbcache.TableCache` reads
  each table's IDs once (ASCII case folded as SQLite's NOCASE folds it,
  `listlookup.fold_case`), and an unknown ID costs no query. It drops its
  reads when `last_update_datetime` changes, checked once per `reading()` block
  and at every lookup outside one, so a long-lived detector sees another
  process's `update`. A new write to `licenses` or `license_index` must
  call `self._tables.clear()`, as `_write_db_records` does. A read made
  while another thread cleared is not kept (`_generation`).
- Never build a `LIKE` or `GLOB` pattern from input: SQLite refuses one
  over 50,000 bytes, and `connection()` reports that as a broken database.
  Compare in memory from `TableCache`.
- Give a huge test parameter a short `id`: pytest puts the test ID in
  `PYTEST_CURRENT_TEST`, and Windows refuses an environment variable over
  32,767 characters (`conftest.MAX_TEST_ID` refuses IDs over 300). Keep a
  single long word in a test short too: Tier 1's full-text query costs time
  in its length, 312 s for 2 MB on Windows CI (roadmap item 42).
- A lookup never creates or writes the database. `Connections.connect` opens
  read-only (`dbcheck.open_uri`); the detector makes `LicenseDatabase(path,
  create=False)`, whose writes open `mode=rw` (a missing file fails, not
  created) and happen only for an older schema (`dbschema.schema_state`)
  of licenseid's own file. A missing norm column is filled in memory
  (`dbcache.TableCache.names_and_ids`), never written back. Any `sqlite3.Error`
  of a read becomes `DatabaseNotReadyError` in `Connections.connection`
  (`dbcheck.lookup_error`): do not wrap per method, and do not swallow a
  `sqlite3.Error` in a query (`search_candidates` quotes its words so its text
  cannot fail). The action `run 'licenseid update'` is only for a file update
  can rebuild (`dbcheck._can_rebuild`). A database must not be in WAL mode:
  `update` leaves it (`Connections.leave_wal`), since a read-only connection
  cannot remove `-wal` and `-shm`.
- A test that sends SIGINT to a child must restore the child's handler
  (`signal.default_int_handler`): a shell starts a background job, a CI step
  maybe too, with SIGINT ignored, and Python keeps it ignored. Signal at a
  point the child reports (`test_cli_streams._READY`), not after a sleep.
- Database tests must import the autouse `safe_home` fixture from
  `tests/db_asserts.py` (it patches `Path.home` as well as `HOME`) with
  `# noqa: F401  # pylint: disable=unused-import`.
- Do not run a mutation-testing agent while another agent edits `src/`: a
  snapshot taken then can capture a live mutant and produce phantom
  findings. Diff any snapshot against the working tree first.
- RapidFuzz costs time in the query's CHARACTERS, not its words, for the
  alignment scan and for the probe alike: a blob of few words and many
  characters used to take minutes. Guard by the probe
  (`similarity.build_probe`) and by `similarity.alignment_affordable`, never
  by characters per word: Japanese and Chinese have no spaces, so their words
  are long, and a per-word limit lost CC-BY-SA-2.1-JP. A limit that clears
  every fixture proves little: that one did, and the same licence sliced at
  other offsets crossed it. Before changing a limit, sweep real licence texts
  (Japanese included) at several offsets and lengths on the branch and on
  `main`, and compare the top answers. Details from PR #62: item 16 in
  `working-docs/implementation/tech-debt-resolved.md`.
- Details and the rest of the findings from PR #55:
  `working-docs/implementation/database-readiness-gate.md`.
- A fix to input reading can add the next quadratic path: a loop that
  re-slices or rescans its input once per item (`s = s[1:-1]` per bracket,
  a whole line per tag). Time a change against `main`, not against the
  branch, with distinct values (a dedupe hides the per-item cost) and
  balanced payloads (unbalanced ones fail early). Give a timing test 10x
  headroom for CI's Python 3.10, where a deep `py_spdx_license` parse
  that fails is slowest; keep deep nesting away from the parser rather
  than raising the limit. CI's 3.10 job runs under `coverage`, several
  times slower than a laptop: a timing test that needs a large input or a
  tight bound (a ratio of two sizes for linear time) is
  `@pytest.mark.benchmark`, run with `--run-benchmark` before a release, and
  keeps a small size in the every-commit run (PR #121). Details from PR #61:
  `working-docs/implementation/spdx-expression-reading.md`.
- Text-matching accuracy runs in layers: every commit checks the core set
  (`test_accuracy.py::test_core_accuracy`, about 15 s); `accuracy.yml` runs
  the must-have licences on a pull request that touches the matching code,
  and every benchmark weekly. A new module on the text-matching path goes
  into that workflow's `paths` list, or a change to it skips the check.

## Git and pull requests

- Commit messages: user impact, not implementation details.
- Follow: <https://chris.beams.io/posts/git-commit/>
- Every PR must address: **What changed?** / **Why?** / **Breaking changes?**
- Asked for a PR title and summary, give each in its own fenced code block
  (ready to copy): a title under 60 characters, and a summary under 280
  characters, as Markdown bullets (code spans for flags and keys).
- Update `CHANGELOG.md` for significant changes per Keep a Changelog
  (<https://keepachangelog.com/>).
  Mark breaking changes clearly with very concise migration instructions.
- A release not yet tagged keeps its section in `CHANGELOG.md` open: a PR
  merged before the tag goes into that section, not a new `[Unreleased]` one.
  Link the PR once it has a number (never guess one).
- **CHANGELOG entries**: concise, to the point. No background/rationale --
  link the PR for that. Target ~160 chars per bullet; exception for a genuinely
  complex PR. Merge related PRs into one entry (`[#1], [#2]`);
  sort entries per section by lowest PR number;
  skip docs/version-bump/CI-only noise.

## Project metadata consistency

Keep in sync: `pyproject.toml`, `codemeta.json`, other metadata files.

`CITATION.cff` is generated from `codemeta.json` by
`.github/workflows/codemeta2cff.yml`; do not edit it by hand. On a release,
update `version`, `dateModified` and `datePublished` in `codemeta.json`
(`dateModified` becomes `date-released` in `CITATION.cff`).

Consistent fields: project name, version, author/contributor names, license,
description, repository URL, keywords/tags (same order).

## Dependencies

- Sort in `pyproject.toml`. (Do not use `requirements.txt` or legacy setup
  files).
- Use most current compatible version.
- Verify package names — guard against typosquatting/slopsquatting.
- Remove unused imports and dependencies.
- Warn about abandoned packages; suggest maintained replacements.

## Security

- No deprecated/obsolete/insecure libraries/APIs.
- Validate/sanitize all user inputs (SQL injection, XSS, buffer overflows, path
  traversal CWE-22).
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
- Noun number: singular for single-entity classes, plural only for
  collections/utility modules/aggregates.

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

Verify version exists and is compatible before suggesting. Prefer Semantic
Versioning.

## Boundaries

**Ask before doing:**

- Large cross-package refactors.
- New dependencies with broad impact.
- Destructive data or migration changes.

**Never:**

- Commit secrets, credentials, or tokens.
- Edit generated files by hand when generation workflow exists.
- Use destructive git operations unless explicitly requested.
