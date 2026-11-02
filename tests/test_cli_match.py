# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid match VALUE``: one declared value, its lines and its exits.

The list is the 3.29.0 List of the fixtures, shipped as the packaged bundle
(``release_fakes.ship``); no database is at the default path unless a test
puts one there. The combinations of ``--source``, ``--db`` and ``--json``
are in ``test_option_matrix``; the field escape in ``test_text_field``.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner, Result
from conftest import line_fields, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, console, match, output
from licenseid.cli import cli
from licenseid.result import json_line, resolution_lines

DETECT = "; run 'licenseid detect'"


@pytest.fixture(autouse=True)
def packaged(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())


def run(*args: str, stdin: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["match", *args], input=stdin)


@pytest.mark.parametrize(
    ("value", "lines", "exit_code"),
    [
        ("MIT", ["EXPRESSION=MIT\tCATEGORY=exact\tTRUST=identity"], 0),
        (
            "Apache2",
            [
                "EXPRESSION=Apache-2.0\tCATEGORY=version_spelling\tTRUST=resolver_rule",
                "STEP=separator\tFROM=Apache2\tTO=Apache-2.0",
                "STEP=version_spelling\tFROM=Apache2\tTO=Apache-2.0",
            ],
            0,
        ),
        (  # a qualifier is an expansion, the only step here
            "GPL-2.0+",
            [
                (
                    "EXPRESSION=GPL-2.0-or-later\tCATEGORY=plus_to_or_later"
                    "\tTRUST=list_data"
                ),
                "STEP=plus_to_or_later\tFROM=GPL-2.0+\tTO=GPL-2.0-or-later",
            ],
            0,
        ),
        (  # a declined expansion is no step: the category says it
            "GPL-3.0",
            ["EXPRESSION=GPL-3.0\tCATEGORY=assumed_only\tTRUST=none"],
            0,
        ),
        (
            "GPLv2+ or MIT",
            [
                (
                    "EXPRESSION=GPL-2.0-or-later OR MIT"
                    "\tCATEGORY=version_spelling\tTRUST=resolver_rule"
                ),
                "STEP=separator\tFROM=GPLv2\tTO=GPL-2.0",
                "STEP=version_spelling\tFROM=GPLv2\tTO=GPL-2.0",
                (
                    "STEP=operator_case\tFROM=GPL-2.0-or-later or MIT"
                    "\tTO=GPL-2.0-or-later OR MIT"
                ),
                "STEP=plus_to_or_later\tFROM=GPLv2+\tTO=GPL-2.0-or-later",
            ],
            0,
        ),
        (  # the drop step was not applied: only the reason says it
            "Apache 2.0?",
            [
                "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none",
                "REASON=character dropped: U+003F",
            ],
            1,
        ),
        (
            "MIT OR Foo",
            [
                "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none",
                "REASON=operand not resolved: Foo",
            ],
            1,
        ),
        (
            "Foo",
            ["EXPRESSION=\tCATEGORY=unresolved\tTRUST=none", "REASON=not found: Foo"],
            1,
        ),
        (
            "MIT ; Apache 2",
            [
                "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none",
                "REASON=operator not stated: ;",
                "OPERAND=MIT\tEXPRESSION=MIT\tCATEGORY=exact",
                "OPERAND=Apache 2\tEXPRESSION=Apache-2.0\tCATEGORY=version_spelling",
            ],
            1,
        ),
    ],
    ids=[
        "exact",
        "steps",
        "expansion",
        "declined",
        "compound",
        "reason",
        "operand-reason",
        "unresolved",
        "semicolon",
    ],
)
def test_every_line_kind(value: str, lines: list[str], exit_code: int) -> None:
    result = run(value)
    assert (result.exit_code, result.stdout, result.stderr) == (
        exit_code,
        "".join(f"{line}\n" for line in lines),
        "",
    )


# Spaces, a tab, "=" and characters outside ASCII, in operands of a list.
AWKWARD = "MIT ; Apache License,\tVersion 2.0 ; é=1 “x”"


def test_a_line_splits_into_its_fields_and_reads_back() -> None:
    result = run(AWKWARD)
    assert result.exit_code == 1
    operands = [
        line_fields(line)
        for line in result.stdout.splitlines()
        if line.startswith("OPERAND=")
    ]
    assert [o["OPERAND"] for o in operands] == [
        "MIT",
        "Apache License,\tVersion 2.0",
        "\u00e9=1 \u201cx\u201d",
    ]
    assert [o["EXPRESSION"] for o in operands] == ["MIT", "Apache-2.0", ""]
    assert "OPERAND=Apache License,\\tVersion 2.0\t" in result.stdout
    widths = [len(line.split("\t")) for line in result.stdout.splitlines()]
    assert widths == [3, 1, 3, 3, 3]


@pytest.mark.parametrize(
    "value",
    ["MIT", "Apache2", "GPL-2.0+", "MIT ; Apache 2", "Apache 2.0?", AWKWARD, "“MIT"],
    ids=["exact", "steps", "expansion", "semicolon", "reason", "awkward", "quote"],
)
def test_the_output_is_the_resolution(value: str) -> None:
    """Text: resolution_lines of match(); JSON: json_line of match(), the
    same bytes, one line."""
    expected = match(value)
    text, as_json = run(value), run("--json", value)
    assert text.stdout == "".join(f"{line}\n" for line in resolution_lines(expected))
    assert as_json.stdout == json_line(expected) + "\n"
    assert json.loads(as_json.stdout) == expected
    assert text.exit_code == as_json.exit_code == (expected["expression"] is None)


# --- what only detect answers, and other usage errors: exit 2 ---


@pytest.mark.parametrize(
    ("args", "stderr"),
    [
        (["--text", "MIT"], f"option: invalid: --text: a licence text{DETECT}"),
        (
            ["--json", "--text=MIT", "MIT"],
            f"option: invalid: --text: a licence text{DETECT}",
        ),
        (["MIT\nApache-2.0"], f"input: invalid: line break: MIT Apache-2.0{DETECT}"),
        (["MIT\n"], f"input: invalid: line break: MIT{DETECT}"),
        (["MIT\r"], f"input: invalid: line break: MIT{DETECT}"),
        (["MIT X"], f"input: invalid: line break: MIT X{DETECT}"),
        (["MIT\x1cX"], f"input: invalid: line break: MIT X{DETECT}"),
        (["M" * 2001], f"input: invalid: over 2000 characters{DETECT}"),
        ([""], "input: empty: argument"),
        (["  \t"], "input: empty: argument"),
        (["MIT\udcff"], "input: invalid: text: lone surrogate at character 3"),
        (["MIT", "ISC"], "input: invalid: extra argument: ISC; run 'cli match --help'"),
        (
            ["--source", "nope", "MIT"],
            "option: invalid: --source: 'nope' is not one of",
        ),
    ],
    ids=[
        "text",
        "text-and-arg",
        "newline",
        "trailing-newline",
        "cr",
        "u2028",
        "x1c",
        "too-long",
        "empty",
        "blank",
        "surrogate",
        "two-values",
        "bad-source",
    ],
)
def test_a_usage_error(args: list[str], stderr: str) -> None:
    result = run(*args)
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith(f"ERROR: {stderr}")
    assert result.stderr.count("\n") == 1


def test_an_empty_text_option_is_refused_too() -> None:
    """``--text ""`` is a text option given, not one left out."""
    result = run("--text", "", "MIT")
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr == f"ERROR: option: invalid: --text: a licence text{DETECT}\n"


@pytest.mark.parametrize("stdin", ["", None, "MIT"], ids=["empty", "none", "piped"])
def test_no_value_is_missing_whatever_is_piped(stdin: str | None) -> None:
    """C8 of the contract batch: ``match`` never reads standard input (it
    read a byte to tell a pipe from nothing, which waits for ever on a pipe
    that stays open)."""
    result = run(stdin=stdin)
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        "ERROR: input: missing; pass one declared licence value\n",
    )


_MAIN = "import sys; from licenseid.cli import main; sys.argv[0] = 'licenseid'; main()"


@posix_only
def test_no_value_does_not_wait_on_a_pipe_that_never_ends() -> None:
    """C8: standard input an open pipe that brings nothing and never closes
    (``sleep 1000 | licenseid match``, a CI step). It used to block in
    read(1); now it exits 2 at once. A child process, with a timeout, so a
    regression fails the test instead of hanging the run."""
    read_end, write_end = os.pipe()
    try:
        child = subprocess.run(
            [sys.executable, "-c", _MAIN, "match"],
            stdin=read_end,
            capture_output=True,
            timeout=30,
            check=False,
        )
    finally:
        os.close(read_end)
        os.close(write_end)
    assert child.returncode == 2
    assert child.stderr == b"ERROR: input: missing; pass one declared licence value\n"


@pytest.mark.parametrize(
    ("value", "refused"),
    [
        (" " + "M" * 2000 + "\t", False),
        ('"' + "M" * 2000 + '"', False),
        ("(" + "M" * 2000 + ")", False),
        ("M" * 2001, True),
        (" " + "M" * 2001, True),
        ('"' + "M" * 2001 + '"', True),
    ],
    ids=["padded", "quoted", "bracketed", "long", "long-padded", "long-quoted"],
)
def test_the_cap_counts_what_match_counts(value: str, refused: bool) -> None:
    """Trimmed, without the quotes and brackets around the whole: the value
    match() itself holds to its cap of 2000 characters."""
    result = run(value)
    assert result.exit_code == (2 if refused else 1)
    assert ("over 2000 characters" in result.stderr) is refused


def test_the_longest_value_is_read() -> None:
    """2000 characters is the resolver's cap; the CLI refuses only longer."""
    result = run("M" * 2000)
    assert (result.exit_code, result.stderr) == (1, "")


@pytest.mark.parametrize(
    ("value", "make"),
    [
        (".", None),
        ("/", None),
        ("docs", "directory"),
        ("Foo", "file"),
        ("LICENSE", "file"),
    ],
    ids=["dot", "root", "directory", "file", "license"],
)
def test_a_value_that_names_nothing_but_a_path_here_is_for_detect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str, make: str | None
) -> None:
    """Read first: a value that resolves to nothing and names what exists
    here (os.path.exists, as detect asks) is a file or a directory to
    detect. Nothing goes on standard output, --json or not."""
    monkeypatch.chdir(tmp_path)
    if make == "file":
        (tmp_path / value).write_text("MIT License", encoding="utf-8")
    elif make == "directory":
        (tmp_path / value).mkdir()
    expected = (2, "", f"ERROR: input: invalid: path: {value}{DETECT}\n")
    for args in ([value], ["--json", value]):
        result = run(*args)
        assert (result.exit_code, result.stdout, result.stderr) == expected
    if make is not None:  # without it here, the same value is a "no"
        os.chdir(tmp_path.parent)
        assert run(value).exit_code == 1


@pytest.mark.parametrize("value", ["MIT", "mit", "Apache2"])
def test_a_value_that_resolves_is_answered_beside_a_file_of_its_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    """Answer first. ``mit`` beside a file ``MIT`` names that file on a file
    system that folds case (macOS, Windows), and is answered all the same."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "MIT").write_text("MIT License", encoding="utf-8")
    (tmp_path / "Apache2").mkdir()
    result = run(value)
    assert (result.exit_code, result.stderr) == (0, "")
    assert result.stdout.startswith("EXPRESSION=")


def test_a_windows_device_name_that_resolves_to_nothing_is_for_detect() -> None:
    """``NUL`` exists everywhere on Windows (os.path.exists says so)."""
    exists = mock.create_autospec(os.path.exists, side_effect=lambda p: p == "NUL")
    with mock.patch("licenseid.climatch.os.path.exists", exists):
        refused, answered = run("NUL"), run("MIT")
    assert (refused.exit_code, refused.stderr) == (
        2,
        f"ERROR: input: invalid: path: NUL{DETECT}\n",
    )
    assert answered.exit_code == 0


def test_a_path_is_judged_after_the_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No list to read: the list's own error, though the value names a file."""
    ship(monkeypatch, None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "LICENSE").write_text("x", encoding="utf-8")
    result = run("LICENSE")
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: database: not found: ")


def test_a_dash_is_refused_for_detect() -> None:
    """C5: ``-`` names standard input for detect and is-*; match takes one
    declared value, so ``match -`` points there, and reads nothing."""
    result = run("-", stdin="MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        f"ERROR: input: invalid: standard input{DETECT}\n",
    )


def test_standard_input_beside_a_value_is_not_read() -> None:
    """A script's standard input is seldom a terminal: the value decides."""
    assert run("MIT", stdin="GPL-3.0").stdout.startswith("EXPRESSION=MIT\t")


@pytest.mark.parametrize(
    "value", ["MIT\nX", "--text", "M" * 2001], ids=["newline", "text", "too-long"]
)
def test_a_refusal_comes_before_the_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    """Input first: a refused value is refused whether or not a list can be
    read (here none: no bundle and no database)."""
    ship(monkeypatch, None)
    monkeypatch.chdir(tmp_path)
    args = ["--text", "MIT"] if value == "--text" else [value]
    result = run(*args)
    assert result.exit_code == 2
    assert result.stderr.rstrip("\n").endswith(DETECT)


def test_no_list_to_read_is_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """No bundle and no database: the database's error, as match() raises."""
    ship(monkeypatch, None)
    result = run("MIT")
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith("ERROR: database: not found: ")
    assert result.stderr.endswith("; run 'licenseid update'\n")


@pytest.mark.parametrize("state", ["missing", "empty", "invalid", "no-rows"])
def test_a_database_given_that_is_not_ready_is_exit_2(
    tmp_path: Path, state: str
) -> None:
    """--db is read as match(value, db): never in place of the packaged list."""
    path = tmp_path / "given.db"
    if state == "empty":
        path.write_bytes(b"")
    elif state == "no-rows":  # licenseid's tables, nothing in them
        LicenseDatabase(str(path))
    elif state == "invalid":
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE notes (body TEXT)")
        conn.close()
    result = CliRunner().invoke(cli, ["--db", str(path), "match", "MIT"])
    condition = {"missing": "not found", "no-rows": "empty"}.get(state, state)
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr.startswith(f"ERROR: database: {condition}: {path}")


@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_an_output_failure_is_exit_2(json_output: bool) -> None:
    failing = mock.create_autospec(console.emit, side_effect=OSError(28, "No space"))
    with mock.patch.object(output, "emit", failing):
        result = run(*(["--json"] if json_output else []), "MIT")
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: output: write failed: No space\n",
    )
