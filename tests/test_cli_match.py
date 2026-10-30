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
import sqlite3
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner, Result
from conftest import line_fields
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, match
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
        ("Foo", ["EXPRESSION=\tCATEGORY=unresolved\tTRUST=none"], 1),
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


def test_empty_piped_input_with_no_value() -> None:
    # BUG: nothing was piped (</dev/null, cron), so nothing is for detect:
    # the value is missing.
    result = run(stdin="")
    assert (result.exit_code, result.stderr) == (
        2,
        f"ERROR: input: invalid: standard input{DETECT}\n",
    )


def test_the_cap_counts_the_value_as_given() -> None:
    """Pinned: white space around the value counts towards the cap, which
    match() applies after trimming it."""
    assert run(" " + "M" * 2000).exit_code == 2


def test_the_longest_value_is_read() -> None:
    """2000 characters is the resolver's cap; the CLI refuses only longer."""
    result = run("M" * 2000)
    assert (result.exit_code, result.stderr) == (1, "")


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_a_value_that_names_a_file_here_is_for_detect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    """As detect would read it: what exists by that name (os.path.exists)."""
    monkeypatch.chdir(tmp_path)
    if kind == "file":
        (tmp_path / "MIT").write_text("MIT License", encoding="utf-8")
    else:
        (tmp_path / "MIT").mkdir()
    result = run("MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        f"ERROR: input: invalid: file: MIT{DETECT}\n",
    )
    assert run(str(tmp_path / "nope")).exit_code == 1  # no file: a value


def test_standard_input_with_no_value_is_for_detect() -> None:
    result = run(stdin="MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        f"ERROR: input: invalid: standard input{DETECT}\n",
    )


def test_standard_input_beside_a_value_is_not_read() -> None:
    """A script's standard input is seldom a terminal: the value decides."""
    assert run("MIT", stdin="GPL-3.0").stdout.startswith("EXPRESSION=MIT\t")


def test_no_value_and_no_piped_input_is_missing() -> None:
    """Standard input a terminal, or closed (``clicommon.piped_input``)."""
    with mock.patch("licenseid.climatch.piped_input", return_value=False):
        result = run()
    assert (result.exit_code, result.stdout, result.stderr) == (
        2,
        "",
        "ERROR: input: missing; pass one declared licence value\n",
    )


@pytest.mark.parametrize("value", ["LICENSE", "MIT\nX", "--text"], ids=str)
def test_a_refusal_comes_before_the_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    """Input first: a refused value is refused whether or not a list can be
    read (here none: no bundle and no database)."""
    ship(monkeypatch, None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "LICENSE").write_text("x", encoding="utf-8")
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
    failing = mock.create_autospec(click.echo, side_effect=OSError(28, "No space"))
    with mock.patch.object(click, "echo", failing):
        result = run(*(["--json"] if json_output else []), "MIT")
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: output: write failed: No space\n",
    )
