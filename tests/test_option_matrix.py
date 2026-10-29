# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Combination matrix for CLI options and API parameters.

Every combination of the axes below is one test case, so an option is never
only tested on its own. When you add a CLI option or an API parameter, add it
as an axis (or a value on an axis) here; see AGENTS.md "Testing".

| Surface              | Axes                                         |
|----------------------|----------------------------------------------|
| CLI ``detect``       | SOURCES x OUTPUTS x found / not found        |
| CLI ``is-*``         | PREDICATES x SOURCES x found / not found     |
| CLI blank input      | commands x blank arg / --text / --id / stdin |
| API ``detect()``     | every subset of text / license_id / file     |
| API ``is_*()``       | PREDICATES x text / license_id / file        |
| API ``match()``      | source x default database (STATES) x bundle  |

Current precedence when several inputs are given (pinned below; the losing
input is ignored without a warning):

- CLI: ``--id`` > ``--text`` > positional argument > stdin.
- API: ``license_id`` > ``file_path`` > ``text``.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import contextlib
import itertools
import re
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import RESULT_KEYS, json_lines, make_mit_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import MIT_TEXT, make_ready_file_db
from input_payloads import PAYLOADS, Payload
from release_fakes import release_bundle, ship
from resolve_states import MISSING as NO_DATABASE
from resolve_states import (
    NO_HOME,
    OUTDATED,
    OUTDATED_WARNING,
    STATES,
    VERSION,
    build,
    refusal,
)

from licenseid import LicenseDatabase, match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.resolvertypes import Source
from tools.cli_matrix.judge import PLAIN

OTHER_TEXT = "The quick brown fox jumps over the lazy dog near the river bank"
MISSING = "ERROR: input: missing; pass a file, an ID, --text, --id or stdin\n"
NO_MATCH = "ERROR: match: no license found\n"

SOURCES = ["arg_id", "arg_file", "text", "id", "stdin", "none"]
OUTPUTS = [
    (),
    ("--json",),
    ("--bold",),
    ("--diff",),
    ("--json", "--bold"),
    ("--json", "--diff"),
    ("--bold", "--diff"),
]
# Every found input is exact here (the ID, or MIT's text word for word), so
# --exact keeps the answer: this axis checks that --exact combines with the
# other options and inputs, not what it filters (test_public_result does).
OUTPUTS += [(*output, "--exact") for output in OUTPUTS]
PREDICATES = ["is-osi", "is-fsf", "is-open", "is-free", "is-spdx"]


@pytest.fixture
def mit_db() -> Generator[str, None, None]:
    # Fresh timestamp: no staleness warning, so stderr is exactly asserted.
    db_path, keep_alive = make_mit_db_path(
        "test_matrix", datetime.now(timezone.utc).isoformat()
    )
    yield db_path
    keep_alive.close()


def _source_args(source: str, found: bool, tmp_path: Path) -> tuple[list[str], str]:
    """CLI arguments and stdin for one input *source*."""
    text = MIT_TEXT if found else OTHER_TEXT
    license_id = "MIT" if found else "Nope-1.0"
    if source == "arg_id":
        return [license_id], ""
    if source == "arg_file":
        path = tmp_path / "LICENSE"
        path.write_text(text, encoding="utf-8")
        return [str(path)], ""
    if source == "text":
        return ["--text", text], ""
    if source == "id":
        return ["--id", license_id], ""
    if source == "stdin":
        return [], text
    return [], ""  # "none"


def _invoke(db: str, command: str, args: list[str], stdin: str) -> Result:
    return CliRunner().invoke(cli, ["--db", db, command, *args], input=stdin)


# --- CLI detect: SOURCES x OUTPUTS x found ---


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("output", OUTPUTS, ids=lambda o: "+".join(o) or "plain")
@pytest.mark.parametrize("source", SOURCES)
def test_match_matrix(
    mit_db: str, tmp_path: Path, source: str, output: tuple[str, ...], found: bool
) -> None:
    args, stdin = _source_args(source, found, tmp_path)
    result = _invoke(mit_db, "detect", [*args, *output], stdin)

    if source == "none":
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", MISSING)
    elif not found:
        assert (result.exit_code, result.stdout, result.stderr) == (1, "", NO_MATCH)
    else:
        assert (result.exit_code, result.stderr) == (0, "")
        _assert_match_stdout(result.stdout, output)


def _assert_match_stdout(stdout: str, output: tuple[str, ...]) -> None:
    """Current behaviour, not a documented contract (roadmap: conflicting
    options are resolved silently): --bold wins over --json and --diff, and
    --json ignores --diff."""
    if "--bold" in output:
        assert stdout == "MIT\n"
    elif "--json" in output:
        results = json_lines(stdout)
        assert [r["license_id"] for r in results] == ["MIT"]
        assert all(set(r) == RESULT_KEYS for r in results)
    else:
        lines = stdout.splitlines()
        assert PLAIN.fullmatch(lines[0])
        assert lines[0].startswith("LICENSE_ID=MIT ")
        if "--diff" not in output:
            assert len(lines) == 1


# --- CLI is-*: PREDICATES x SOURCES x found ---


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("command", PREDICATES)
def test_predicate_matrix(
    mit_db: str, tmp_path: Path, command: str, source: str, found: bool
) -> None:
    args, stdin = _source_args(source, found, tmp_path)
    result = _invoke(mit_db, command, args, stdin)

    if source == "none":
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", MISSING)
    elif found:  # MIT is SPDX, OSI- and FSF-approved: every predicate is true
        assert (result.exit_code, result.stdout, result.stderr) == (0, "true\n", "")
    else:
        assert (result.exit_code, result.stdout, result.stderr) == (1, "false\n", "")


# --- CLI blank input: an input given with no text is a usage error ---


@pytest.mark.parametrize(
    ("args", "stdin", "name"),
    [
        (["  "], "", "argument"),
        (["--text", ""], "", "--text"),
        (["--text", " \t "], "", "--text"),
        (["--id", ""], "", "--id"),
        (["--id", "  "], "", "--id"),
        ([], " \r\n\t\n", "stdin"),
        (["--text", "\\n\\t"], "", "--text"),  # blank once escapes are decoded
        ([], "\ufeff  \n", "stdin"),
        ([], "\ufeff", "stdin"),  # bytes were piped, so not "missing"
    ],
    ids=[
        "arg",
        "text",
        "text_ws",
        "id",
        "id_ws",
        "stdin_ws",
        "text_escaped_ws",
        "stdin_bom_ws",
        "stdin_bom",
    ],
)
@pytest.mark.parametrize("command", ["detect", *PREDICATES])
def test_blank_input(
    mit_db: str, command: str, args: list[str], stdin: str, name: str
) -> None:
    """Not skipped for the next input, not matched as text: exit 2."""
    result = _invoke(mit_db, command, args, stdin)
    expected = f"ERROR: input: empty: {name}\n"
    assert (result.exit_code, result.stdout, result.stderr) == (2, "", expected)


# --- CLI precedence when several inputs are given (pinned) ---


@pytest.mark.parametrize(
    ("args", "stdin"),
    [
        (["--id", "MIT", "--text", OTHER_TEXT], ""),  # --id beats --text
        (["--id", "MIT", "Nope-1.0"], ""),  # --id beats positional
        (["--text", MIT_TEXT, "Nope-1.0"], ""),  # --text beats positional
        (["MIT"], OTHER_TEXT),  # positional beats stdin
        (["--text", MIT_TEXT], OTHER_TEXT),  # --text beats stdin
    ],
    ids=["id>text", "id>arg", "text>arg", "arg>stdin", "text>stdin"],
)
@pytest.mark.parametrize("command", ["detect", *PREDICATES])
def test_cli_input_precedence(
    mit_db: str, command: str, args: list[str], stdin: str
) -> None:
    result = _invoke(
        mit_db, command, ["--bold", *args] if command == "detect" else args, stdin
    )
    expected = "MIT\n" if command == "detect" else "true\n"
    assert (result.exit_code, result.stdout, result.stderr) == (0, expected, "")


# --- API: every subset of text / license_id / file_path ---

_API_INPUTS = ("text", "license_id", "file_path")


def _api_kwargs(
    names: tuple[str, ...], winner: str | None, tmp_path: Path
) -> dict[str, str]:
    """Only the *winner* input names MIT; every other given input names
    something that does not match, so the result shows which one was used."""
    kwargs: dict[str, str] = {}
    for name in names:
        good = name == winner
        if name == "text":
            kwargs[name] = MIT_TEXT if good else OTHER_TEXT
        elif name == "license_id":
            kwargs[name] = "MIT" if good else "Nope-1.0"
        else:
            path = tmp_path / "LICENSE"
            path.write_text(MIT_TEXT if good else OTHER_TEXT, encoding="utf-8")
            kwargs[name] = str(path)
    return kwargs


def _winner(names: tuple[str, ...]) -> str | None:
    for name in ("license_id", "file_path", "text"):  # current precedence
        if name in names:
            return name
    return None


_SUBSETS = [
    names
    for size in range(len(_API_INPUTS) + 1)
    for names in itertools.combinations(_API_INPUTS, size)
]


@pytest.mark.parametrize("names", _SUBSETS, ids=lambda n: "+".join(n) or "none")
def test_api_match_matrix(mit_db: str, tmp_path: Path, names: tuple[str, ...]) -> None:
    winner = _winner(names)
    kwargs = _api_kwargs(names, winner, tmp_path)
    results = LicenseDetector(mit_db).detect(**kwargs)
    if winner is None:
        assert results == []
    else:
        assert results[0]["license_id"] == "MIT"
        assert results[0]["score"] >= 0.85


_API_PREDICATES: dict[str, Callable[[LicenseDetector], Callable[..., bool]]] = {
    "is_spdx": lambda m: m.is_spdx,
    "is_osi": lambda m: m.is_osi,
    "is_fsf": lambda m: m.is_fsf,
    "is_open": lambda m: m.is_open,
}


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("name", _API_INPUTS)
@pytest.mark.parametrize("predicate", sorted(_API_PREDICATES))
def test_api_predicate_matrix(
    mit_db: str, tmp_path: Path, predicate: str, name: str, found: bool
) -> None:
    kwargs = _api_kwargs((name,), name if found else None, tmp_path)
    check = _API_PREDICATES[predicate](LicenseDetector(mit_db))
    assert check(**kwargs) is found


@pytest.mark.parametrize("payload", PAYLOADS, ids=lambda p: p.name)
def test_file_path_is_read_the_way_the_cli_reads_a_file(
    mit_db: str,
    tmp_path: Path,
    payload: Payload,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same bytes in a file give the same answer and the same warning
    through `licenseid detect FILE` and `detect(file_path=FILE)`: decoding is
    one function (licenseid.textinput), and this keeps it that way."""
    path = tmp_path / "LICENSE"
    path.write_bytes(payload.data)
    matcher = LicenseDetector(mit_db)

    cli_result = _invoke(mit_db, "detect", [str(path)], "")
    if payload.text is None:
        message = f"input: binary file: {path}"
        assert (cli_result.exit_code, cli_result.stderr) == (2, f"ERROR: {message}\n")
        with pytest.raises(InvalidInputError, match=f"^{re.escape(message)}$"):
            matcher.detect(file_path=str(path))
        with pytest.raises(InvalidInputError, match=f"^{re.escape(message)}$"):
            matcher.is_open(file_path=str(path))
        return

    warning = f"WARNING: input: not UTF-8, read as Latin-1: {path}\n"
    expected_stderr = warning if payload.latin1 else ""
    assert (cli_result.exit_code, cli_result.stderr) == (0, expected_stderr)
    assert cli_result.stdout.startswith("LICENSE_ID=MIT ")
    assert matcher.detect(file_path=str(path))[0]["license_id"] == "MIT"
    assert capsys.readouterr().err == expected_stderr


def test_a_missing_file_path_raises_oserror(mit_db: str, tmp_path: Path) -> None:
    """Not worded as a licenseid error: the API leaves I/O errors as they are."""
    with pytest.raises(FileNotFoundError):
        LicenseDetector(mit_db).detect(file_path=str(tmp_path / "nope"))


# --- API match(): source x the database at the default path x bundle ---

RESOLVE_SOURCES = ["auto", "database", "packaged"]
BUNDLES = ["shipped", "none", "invalid"]
_BUNDLE_BYTES = {"shipped": release_bundle(VERSION), "none": None, "invalid": b"bad"}
_BAD_BUNDLE = "spdx-bundle.json.gz: invalid: BadGzipFile: Not a gzipped file (b'ba')"
# What each bundle prints when match() loads it: an unusable one warns once.
_LOADED = {"shipped": "", "none": "", "invalid": f"WARNING: {_BAD_BUNDLE}\n"}
_NO_LIST = {"none": "spdx-bundle.json.gz: not found", "invalid": _BAD_BUNDLE}


def _resolve_outcome(source: str, state: str, bundle: str) -> tuple[str, str, str]:
    """What match("MIT", source=source) does, as ``(list source or
    "raise", what it raises, what it prints)``, the last two as regular
    expressions. The bundle holds the database's version, so a usable
    database wins the tie (Q4), an outdated one loses it (Q10). Only
    ``database`` leaves the bundle unread."""
    refused = refusal(state)
    loaded = "" if source == "database" else _LOADED[bundle]
    if source == "packaged":
        if bundle != "shipped":
            return "raise", re.escape(_NO_LIST[bundle]), re.escape(loaded)
        return "packaged", "", ""
    if source == "database" or bundle != "shipped":
        if refused:
            return "raise", refused[0] + re.escape(refused[1]), re.escape(loaded)
        opened = OUTDATED_WARNING if state == OUTDATED else ""
        return "database", "", re.escape(opened + loaded)
    return _auto_with_a_bundle(state, refused)


def _auto_with_a_bundle(
    state: str, refused: tuple[str, str] | None
) -> tuple[str, str, str]:
    """``auto`` with the bundle shipped: the database, the bundle silently,
    or the bundle after a warning."""
    if state == OUTDATED:
        return "packaged", "", re.escape(OUTDATED_WARNING)
    if refused is None:
        return "database", "", ""
    if state in (NO_DATABASE, NO_HOME):  # no database file: silent (Q11)
        return "packaged", "", ""
    fallback = re.escape(f"; using packaged data v{VERSION}\n")
    return "packaged", "", f"WARNING: {refused[0]}{fallback}"


@pytest.mark.parametrize("bundle", BUNDLES)
@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("source", RESOLVE_SOURCES)
def test_resolve_matrix(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: Source,
    state: str,
    bundle: str,
) -> None:
    """With no database given, match() reads the database at the default
    path or the bundle shipped in the wheel, as *source* says; a list it
    cannot read raises, a database's message unchanged from 0.6.0."""
    ship(monkeypatch, _BUNDLE_BYTES[bundle])
    build(state, monkeypatch)
    capsys.readouterr()
    where, raised, said = _resolve_outcome(source, state, bundle)
    if where == "raise":
        with pytest.raises(DatabaseNotReadyError) as error:
            match("MIT", source=source)
        assert re.fullmatch(raised, str(error.value)), str(error.value)
    else:
        got = match("MIT", source=source)
        assert (got["expression"], got["category"]) == ("MIT", "exact")
        assert [(e["source"], e["version"]) for e in got["lists"]] == [(where, VERSION)]
    err = capsys.readouterr().err
    assert re.fullmatch(said, err), err
    # Every warning, an opened database's and the bundle's included, is said
    # once per process.
    with contextlib.suppress(DatabaseNotReadyError):
        match("MIT", source=source)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("source", RESOLVE_SOURCES)
def test_resolve_matrix_with_a_database_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: Source
) -> None:
    """A database given is read as source="database"; packaged contradicts
    it, and is refused rather than one of the two ignored."""
    ship(monkeypatch, release_bundle(VERSION))
    db = LicenseDatabase(str(make_ready_file_db(tmp_path / "given.db")), create=False)
    if source == "packaged":
        message = "option: invalid: source: 'packaged' with db; pass db or source"
        with pytest.raises(InvalidInputError, match=f"^{re.escape(message)}$"):
            match("MIT", db, source=source)
        return
    got = match("MIT", db, source=source)
    assert [entry["source"] for entry in got["lists"]] == ["database"]
