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
|                      | (OUTPUTS: --json, --id-only, --diff, --exact) |
| CLI ``is-*``         | PREDICATES x SOURCES x --json x found / not  |
| CLI blank input      | commands x blank arg / --text / --id / stdin |
| API ``detect()``     | method / function x text / license_id / file |
| API ``is_*()``       | PREDICATES x text / license_id / file        |
| API ``match()``      | source x default database (STATES) x bundle  |
| CLI ``match``        | --source x default database x --db x --json  |
| CLI ``update``       | ``test_update_matrix.py``: --source x --cache |
|                      | x --list x --force x --json                  |
| CLI ``clear-cache``  | ``test_clear_cache.py``: state x --json      |

Two inputs (``--id`` or ``--text`` with another input), and ``--json`` with
``--id-only`` or ``--diff``, are a usage error (C7 of the contract batch;
they were resolved without a word). A piped standard input beside one input
is not refused: a script's standard input is seldom a terminal.

- API: ``license_id`` > ``file_path`` > ``text``.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import contextlib
import itertools
import json
import re
import shutil
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import (
    NO_DETECTION,
    RESULT_KEYS,
    json_lines,
    make_mit_db_path,
    predicate_json,
    predicate_line,
)
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import MIT_TEXT, make_ready_file_db
from input_payloads import PAYLOADS, Payload
from matcher_db import Lic, seeded_db
from packaged_list import fixture_bundle
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

import licenseid
from licenseid import LicenseDatabase, match
from licenseid.cli import cli
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.resolvertypes import Source
from tools.cli_matrix.judge import PLAIN

OTHER_TEXT = "The quick brown fox jumps over the lazy dog near the river bank"
MISSING = "ERROR: input: missing; pass a file, an ID, --text, --id or stdin\n"
NO_MATCH = ""  # "no" is an answer: nothing on standard error

SOURCES = ["arg_id", "arg_file", "text", "id", "stdin", "dash", "none"]
OUTPUTS = [
    (),
    ("--json",),
    ("--id-only",),
    ("--diff",),
    ("--json", "--id-only"),
    ("--json", "--diff"),
    ("--id-only", "--diff"),
]
# Every found input is exact here (the ID, or MIT's text word for word), so
# --exact keeps the answer: this axis checks that --exact combines with the
# other options and inputs, not what it filters (test_public_result does).
OUTPUTS += [(*output, "--exact") for output in OUTPUTS]
PREDICATES = ["is-osi", "is-fsf", "is-spdx"]


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
    if source == "dash":  # C5: "-" names standard input
        return ["-"], text
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

    conflict = next((o for o in output if "--json" in output and o in _JSON_ONLY), "")
    if conflict:  # checked before the input is read, so for "none" too
        expected = f"ERROR: option: invalid: {conflict}: with --json; pass one of them\n"
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", expected)
    elif source == "none":
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", MISSING)
    elif not found:
        assert (result.exit_code, result.stdout, result.stderr) == (
            1,
            _no_record(output),
            NO_MATCH,
        )
    else:
        assert (result.exit_code, result.stderr) == (0, "")
        _assert_match_stdout(result.stdout, output)


#: The options --json refuses beside it.
_JSON_ONLY = ("--id-only", "--diff")


def _no_record(output: tuple[str, ...]) -> str:
    """What detect prints for no answer, by output option."""
    if "--id-only" in output:
        return "\n"
    if "--json" in output:
        return json.dumps(dict.fromkeys(sorted(RESULT_KEYS)), separators=(",", ":")) + "\n"
    return NO_DETECTION


def _assert_match_stdout(stdout: str, output: tuple[str, ...]) -> None:
    """--id-only prints the expression alone; --diff adds nothing to
    standard output (its diff is on standard error, and an exact answer has
    none)."""
    if "--id-only" in output:
        assert stdout == "MIT\n"
    elif "--json" in output:
        results = json_lines(stdout)
        assert [r["expression"] for r in results] == ["MIT"]
        assert all(set(r) == RESULT_KEYS for r in results)
    else:
        lines = stdout.splitlines()
        assert PLAIN.fullmatch(lines[0])
        assert lines[0].startswith("EXPRESSION=MIT\t")
        if "--diff" not in output:
            assert len(lines) == 1


# --- CLI is-*: PREDICATES x SOURCES x found ---


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("output", [(), ("--json",)], ids=["plain", "json"])
@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("command", PREDICATES)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_predicate_matrix(
    mit_db: str,
    tmp_path: Path,
    command: str,
    source: str,
    output: tuple[str, ...],
    found: bool,
) -> None:
    args, stdin = _source_args(source, found, tmp_path)
    result = _invoke(mit_db, command, [*output, *args], stdin)

    def record(expression: str | None, answer: bool) -> str:
        if output:
            return predicate_json(command, expression, answer)
        return predicate_line(command, expression or "", answer)

    if source == "none":
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", MISSING)
    elif found:  # MIT is SPDX, OSI- and FSF-approved: every predicate is true
        yes = record("MIT", True)
        assert (result.exit_code, result.stdout, result.stderr) == (0, yes, "")
    else:
        no = record(None, False)
        assert (result.exit_code, result.stdout, result.stderr) == (1, no, "")


# Each flag on its own, so a predicate cannot pass by reading both as one.
_FLAGGED = [
    Lic("Osi-1.0", "Osi Only", is_osi_approved=True),
    Lic("Fsf-1.0", "Fsf Only", is_fsf_libre=True),
    Lic("Neither-1.0", "Neither"),
    Lic("Both-1.0", "Both", is_osi_approved=True, is_fsf_libre=True),
]
_HOLDS = {
    "is-osi": lambda lic: lic.is_osi_approved,
    "is-fsf": lambda lic: lic.is_fsf_libre,
    "is-spdx": lambda lic: lic.is_spdx,
}


@pytest.mark.parametrize("command", PREDICATES)
def test_each_predicate_reads_its_own_flag(command: str) -> None:
    for db in seeded_db("test_option_matrix_flags", _FLAGGED):
        for lic in _FLAGGED:
            answer = bool(_HOLDS[command](lic))
            result = _invoke(db, command, ["--id", lic.license_id], "")
            expected = (
                int(not answer),
                predicate_line(command, lic.license_id, answer),
            )
            assert (result.exit_code, result.stdout) == expected, lic


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
        (["-"], " \n\t", "stdin"),  # "-" reads standard input (C5)
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
        "dash_ws",
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


# --- CLI: two inputs are a usage error (C7) ---


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--id", "MIT", "--text", OTHER_TEXT], "--id: with --text"),
        (["--id", "MIT", "Nope-1.0"], "--id: with an argument"),
        (["--id", "MIT", "-"], "--id: with an argument"),
        (["--text", MIT_TEXT, "Nope-1.0"], "--text: with an argument"),
        (["--text", MIT_TEXT, "-"], "--text: with an argument"),
    ],
    ids=["id+text", "id+arg", "id+dash", "text+arg", "text+dash"],
)
@pytest.mark.parametrize("command", ["detect", *PREDICATES])
def test_two_inputs_are_refused(
    mit_db: str, command: str, args: list[str], message: str
) -> None:
    result = _invoke(mit_db, command, args, OTHER_TEXT)
    expected = f"ERROR: option: invalid: {message}; pass one input\n"
    assert (result.exit_code, result.stdout, result.stderr) == (2, "", expected)


@pytest.mark.parametrize(
    "args", [["MIT"], ["--text", MIT_TEXT], ["--id", "MIT"]], ids=["arg", "text", "id"]
)
@pytest.mark.parametrize("command", ["detect", *PREDICATES])
def test_a_pipe_beside_one_input_is_not_read(
    mit_db: str, command: str, args: list[str]
) -> None:
    """Standard input is read only when no other input is given."""
    result = _invoke(
        mit_db, command, ["--id-only", *args] if command == "detect" else args, OTHER_TEXT
    )
    expected = "MIT\n" if command == "detect" else predicate_line(command, "MIT", True)
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


@pytest.mark.parametrize("entry", ["method", "function"])
@pytest.mark.parametrize("names", _SUBSETS, ids=lambda n: "+".join(n) or "none")
def test_api_match_matrix(
    mit_db: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    names: tuple[str, ...],
    entry: str,
) -> None:
    """``LicenseDetector.detect`` and ``licenseid.detect`` (the database at
    the default path) take the same inputs and give the same answers."""
    winner = _winner(names)
    kwargs = _api_kwargs(names, winner, tmp_path)
    if entry == "method":
        results = LicenseDetector(mit_db).detect(**kwargs)
    else:
        monkeypatch.setattr(
            "licenseid.keptdetector.get_default_db_path", lambda: mit_db
        )
        results = licenseid.detect(**kwargs)
    if winner is None:
        assert results == []
    else:
        assert results[0]["expression"] == "MIT"
        assert results[0]["score"] >= 0.85


_API_PREDICATES: dict[str, Callable[[LicenseDetector], Callable[..., bool | None]]] = {
    "is_spdx": lambda m: m.is_spdx,
    "is_osi": lambda m: m.is_osi,
    "is_fsf": lambda m: m.is_fsf,
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
            matcher.is_osi(file_path=str(path))
        return

    warning = f"WARNING: input: not UTF-8, read as Latin-1: {path}\n"
    expected_stderr = warning if payload.latin1 else ""
    assert (cli_result.exit_code, cli_result.stderr) == (0, expected_stderr)
    assert cli_result.stdout.startswith("EXPRESSION=MIT\t")
    assert matcher.detect(file_path=str(path))[0]["expression"] == "MIT"
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


# --- CLI match: --source x the database at the default path x --db x --json ---

DEFAULT_DATABASES = ["usable", "missing"]


def _cli_match_outcome(source: str, default: str, given: bool) -> str | None:
    """Where ``licenseid match`` reads the list, or None for exit 2. The
    database and the bundle hold one List, built by this licenseid: a tie,
    which the database wins (Q10)."""
    if given:
        return None if source == "packaged" else "database"
    if source == "packaged":
        return "packaged"
    if default == "missing":
        return None if source == "database" else "packaged"
    return "database"


@pytest.mark.parametrize("output", [(), ("--json",)], ids=["plain", "json"])
@pytest.mark.parametrize("given", [False, True], ids=["no-db", "db"])
@pytest.mark.parametrize("default", DEFAULT_DATABASES)
@pytest.mark.parametrize("source", RESOLVE_SOURCES)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_cli_match_matrix(
    monkeypatch: pytest.MonkeyPatch,
    bundle_db: LicenseDatabase,
    source: str,
    default: str,
    given: bool,
    output: tuple[str, ...],
) -> None:
    """``--db`` is read as ``match(value, db)``; without it, the list
    ``--source`` names, as match() reads it. No database is needed."""
    ship(monkeypatch, fixture_bundle())
    if default == "usable":
        path = Path(get_default_db_path())
        path.parent.mkdir(parents=True)
        shutil.copyfile(bundle_db.db_path, path)
    db = ["--db", str(bundle_db.db_path)] if given else []
    result = CliRunner().invoke(
        cli, [*db, "match", "--source", source, *output, "Apache2"]
    )
    where = _cli_match_outcome(source, default, given)
    if where is None:
        refused = (
            "option: invalid: --source: packaged with --db; pass --db or --source"
            if given
            else f"database: not found: {get_default_db_path()}; run 'licenseid update'"
        )
        assert (result.exit_code, result.stdout, result.stderr) == (
            2,
            "",
            f"ERROR: {refused}\n",
        )
        return
    assert (result.exit_code, result.stderr) == (0, "")
    if output:
        got = json.loads(result.stdout)
        assert got["expression"] == "Apache-2.0"
        assert [entry["source"] for entry in got["lists"]] == [where]
    else:
        assert result.stdout.splitlines()[0] == (
            "EXPRESSION=Apache-2.0\tCATEGORY=version_spelling\tTRUST=resolver_rule"
        )
