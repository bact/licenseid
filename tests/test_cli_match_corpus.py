# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid match`` says what ``match()`` says, for every value of the
parity corpus and the PyPI sample, on the packaged 3.29.0 List of the
fixtures: ``--json`` prints ``json_line(match(value))``, the first text line
the result's expression, category and trust, and the exit is 0 for an
expression, 1 for none. A value the CLI refuses (exit 2) is one only
``detect`` reads (a line break, more than the resolver reads), a blank one,
or one with a lone surrogate, which no argument can hold and which RFC 8785
cannot write."""
# pylint: disable=missing-function-docstring

from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship
from resolver_corpus import parity_rows, sample_rows

from licenseid import match
from licenseid.cli import cli
from licenseid.resolver import MAX_EXPRESSION_CHARS
from licenseid.result import json_line, read_text_field
from licenseid.textinput import has_lone_surrogate
from tools.pypi_licence_sample.answer import unescape_field


def _values(rows: list[dict[str, str]]) -> list[str]:
    return list(dict.fromkeys(unescape_field(row["value"]) for row in rows))


def _refused_by_cli(value: str) -> bool:
    """What ``licenseid match`` refuses before reading (``climatch``)."""
    return (
        not value.strip()
        or value.splitlines() != [value]
        or len(value) > MAX_EXPRESSION_CHARS
        or has_lone_surrogate(value)
    )


def _check(runner: CliRunner, value: str) -> int:
    """The exit of ``licenseid match --json VALUE``, once its output agrees
    with match() (and the text output's first line with it)."""
    as_json = runner.invoke(cli, ["match", "--json", value])
    if _refused_by_cli(value):
        assert (as_json.exit_code, as_json.stdout) == (2, ""), value
        assert as_json.stderr.startswith("ERROR: input: "), value
        return 2
    expected = match(value)
    assert as_json.stdout == json_line(expected) + "\n", value
    assert as_json.exit_code == (0 if expected["expression"] else 1), value
    text = runner.invoke(cli, ["match", value])
    head = dict(f.split("=", 1) for f in text.stdout.splitlines()[0].split(" "))
    assert {key: read_text_field(field) for key, field in head.items()} == {
        "EXPRESSION": expected["expression"] or "",
        "CATEGORY": expected["category"],
        "TRUST": expected["trust"],
    }, value
    assert (text.exit_code, text.stderr) == (as_json.exit_code, ""), value
    return as_json.exit_code


@pytest.mark.parametrize(
    ("rows", "stride"),
    [
        (parity_rows, 1),
        (sample_rows, 7),  # every 7th value on every commit
        pytest.param(sample_rows, 1, marks=pytest.mark.benchmark),
    ],
    ids=["parity", "pypi-sample-part", "pypi-sample"],
)
def test_the_cli_says_what_match_says(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rows: Callable[[], list[dict[str, str]]],
    stride: int,
) -> None:
    ship(monkeypatch, fixture_bundle())
    monkeypatch.chdir(tmp_path)  # no file here shares a value's name
    values = _values(rows())[::stride]
    runner = CliRunner()
    exits = Counter(_check(runner, value) for value in values)
    assert len(values) > 50
    assert exits[0] and exits[1]
    print(f"{len(values)} values: exit {dict(sorted(exits.items()))}")
