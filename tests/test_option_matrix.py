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
| CLI ``match``        | SOURCES x OUTPUTS x found / not found        |
| CLI ``is-*``         | PREDICATES x SOURCES x found / not found     |
| CLI blank input      | commands x blank arg / --text / --id / stdin |
| API ``match()``      | every subset of text / license_id / file     |
| API ``is_*()``       | PREDICATES x text / license_id / file        |

Current precedence when several inputs are given (pinned below; the losing
input is ignored without a warning):

- CLI: ``--id`` > ``--text`` > positional argument > stdin.
- API: ``license_id`` > ``file_path`` > ``text``.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import itertools
import json
import re
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import make_mit_db_path

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher

MIT_TEXT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy"
)
OTHER_TEXT = "The quick brown fox jumps over the lazy dog near the river bank"
MISSING = "ERROR: input: missing; pass a file, an ID, --text, --id or stdin\n"
NO_MATCH = "ERROR: match: no license found\n"
PLAIN_LINE = re.compile(r"LICENSE_ID=\S+ SIMILARITY=\d\.\d{4} COVERAGE=\d\.\d{4}")

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


# --- CLI match: SOURCES x OUTPUTS x found ---


@pytest.mark.parametrize("found", [True, False], ids=["found", "not_found"])
@pytest.mark.parametrize("output", OUTPUTS, ids=lambda o: "+".join(o) or "plain")
@pytest.mark.parametrize("source", SOURCES)
def test_match_matrix(
    mit_db: str, tmp_path: Path, source: str, output: tuple[str, ...], found: bool
) -> None:
    args, stdin = _source_args(source, found, tmp_path)
    result = _invoke(mit_db, "match", [*args, *output], stdin)

    if source == "none":
        assert (result.exit_code, result.stdout, result.stderr) == (2, "", MISSING)
    elif not found:
        assert (result.exit_code, result.stdout, result.stderr) == (1, "", NO_MATCH)
    else:
        assert (result.exit_code, result.stderr) == (0, "")
        _assert_match_stdout(result.stdout, output)


def _assert_match_stdout(stdout: str, output: tuple[str, ...]) -> None:
    """--bold wins over --json and --diff; --json ignores --diff."""
    if "--bold" in output:
        assert stdout == "MIT\n"
    elif "--json" in output:
        assert [r["license_id"] for r in json.loads(stdout)] == ["MIT"]
    else:
        lines = stdout.splitlines()
        assert PLAIN_LINE.fullmatch(lines[0])
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
@pytest.mark.parametrize("command", ["match", *PREDICATES])
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
@pytest.mark.parametrize("command", ["match", *PREDICATES])
def test_cli_input_precedence(
    mit_db: str, command: str, args: list[str], stdin: str
) -> None:
    result = _invoke(
        mit_db, command, ["--bold", *args] if command == "match" else args, stdin
    )
    expected = "MIT\n" if command == "match" else "true\n"
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
    results = AggregatedLicenseMatcher(mit_db).match(**kwargs)
    if winner is None:
        assert results == []
    else:
        assert results[0]["license_id"] == "MIT"
        assert results[0]["score"] >= 0.85


_API_PREDICATES: dict[
    str, Callable[[AggregatedLicenseMatcher], Callable[..., bool]]
] = {
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
    check = _API_PREDICATES[predicate](AggregatedLicenseMatcher(mit_db))
    assert check(**kwargs) is found


def test_api_file_path_not_utf8(mit_db: str, tmp_path: Path) -> None:
    """The API reads file_path as strict UTF-8; the CLI reads the same file
    as Latin-1 with a warning and matches it."""
    # BUG: pinned, not fixed: the API should decode like the CLI.
    path = tmp_path / "LICENSE"
    path.write_bytes((MIT_TEXT + " (Jérôme)").encode("latin-1"))
    with pytest.raises(UnicodeDecodeError):
        AggregatedLicenseMatcher(mit_db).match(file_path=str(path))
