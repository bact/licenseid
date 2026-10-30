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
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner, Result
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import match
from licenseid.cli import cli
from licenseid.result import json_line, read_text_field, resolution_lines

DETECT = "; run 'licenseid detect'"


@pytest.fixture(autouse=True)
def packaged(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())


def run(*args: str, stdin: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["match", *args], input=stdin)


@pytest.mark.parametrize(
    ("value", "lines", "exit_code"),
    [
        ("MIT", ["EXPRESSION=MIT CATEGORY=exact TRUST=identity"], 0),
        (
            "Apache2",
            [
                "EXPRESSION=Apache-2.0 CATEGORY=version_spelling TRUST=resolver_rule",
                "STEP=separator FROM=Apache2 TO=Apache-2.0",
                "STEP=version_spelling FROM=Apache2 TO=Apache-2.0",
            ],
            0,
        ),
        (  # a qualifier is an expansion, the only step here
            "GPL-2.0+",
            [
                "EXPRESSION=GPL-2.0-or-later CATEGORY=plus_to_or_later TRUST=list_data",
                "STEP=plus_to_or_later FROM=GPL-2.0+ TO=GPL-2.0-or-later",
            ],
            0,
        ),
        (  # a declined expansion is no step: the category says it
            "GPL-3.0",
            ["EXPRESSION=GPL-3.0 CATEGORY=assumed_only TRUST=none"],
            0,
        ),
        (
            "GPLv2+ or MIT",
            [
                (
                    "EXPRESSION=GPL-2.0-or-later\\x20OR\\x20MIT"
                    " CATEGORY=version_spelling TRUST=resolver_rule"
                ),
                "STEP=separator FROM=GPLv2 TO=GPL-2.0",
                "STEP=version_spelling FROM=GPLv2 TO=GPL-2.0",
                (
                    "STEP=operator_case FROM=GPL-2.0-or-later\\x20or\\x20MIT"
                    " TO=GPL-2.0-or-later\\x20OR\\x20MIT"
                ),
                "STEP=plus_to_or_later FROM=GPLv2+ TO=GPL-2.0-or-later",
            ],
            0,
        ),
        (  # the drop step was not applied: only the reason says it
            "Apache 2.0?",
            [
                "EXPRESSION= CATEGORY=unresolved TRUST=none",
                "REASON=character\\x20dropped:\\x20U+003F",
            ],
            1,
        ),
        (
            "MIT OR Foo",
            [
                "EXPRESSION= CATEGORY=unresolved TRUST=none",
                "REASON=operand\\x20not\\x20resolved:\\x20Foo",
            ],
            1,
        ),
        ("Foo", ["EXPRESSION= CATEGORY=unresolved TRUST=none"], 1),
        (
            "MIT ; Apache 2",
            [
                "EXPRESSION= CATEGORY=unresolved TRUST=none",
                "REASON=operator\\x20not\\x20stated:\\x20;",
                "OPERAND=MIT EXPRESSION=MIT CATEGORY=exact",
                "OPERAND=Apache\\x202 EXPRESSION=Apache-2.0 CATEGORY=version_spelling",
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
    assert result.stdout.isascii()
    operands = [
        dict(field.split("=", 1) for field in line.split(" "))
        for line in result.stdout.splitlines()
        if line.startswith("OPERAND=")
    ]
    assert [read_text_field(o["OPERAND"]) for o in operands] == [
        "MIT",
        "Apache License,\tVersion 2.0",
        "é=1 “x”",
    ]
    assert [o["EXPRESSION"] for o in operands] == ["MIT", "Apache-2.0", ""]
    assert [len(line.split()) for line in result.stdout.splitlines()] == [3, 1, 3, 3, 3]


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
    assert run("MIT", stdin="GPL-3.0").stdout.startswith("EXPRESSION=MIT ")


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


@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_an_output_failure_is_exit_2(json_output: bool) -> None:
    failing = mock.create_autospec(click.echo, side_effect=OSError(28, "No space"))
    with mock.patch.object(click, "echo", failing):
        result = run(*(["--json"] if json_output else []), "MIT")
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: output: write failed: No space\n",
    )
