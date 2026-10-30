# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Every command's standard output follows one pattern (AGENTS.md, "CLI
output"): ``KEY=VALUE`` fields, an uppercase key, one tab between fields,
a value with no tab, line break or bare backslash; ``--json`` one RFC 8785
object per line, byte for byte, whose keys are the text keys in lower case.
The exceptions (``detect --id-only``, ``--version``, ``--help``) are not
run. A command with no answer prints its record too, every field empty
(``null`` in JSON).
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import re
from pathlib import Path

import click
import pytest
import rfc8785
from click.testing import CliRunner, Result
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import MIT_TEXT, release_bundle, ship

from licenseid.cli import cli
from licenseid.result import read_text_field

_VALUE = r"(?:[^\t\n\r\\]|\\[\\trn]|\\x[0-9a-f]{2}|\\u[0-9a-f]{4}|\\U[0-9a-f]{8})*"
_FIELD = rf"[A-Z][A-Z0-9_]*={_VALUE}"
TEXT_LINE = re.compile(rf"{_FIELD}(?:\t{_FIELD})*")
JSON_KEY = re.compile(r"[a-z][a-z0-9_]*")

PREDICATES = ["is-osi", "is-fsf", "is-spdx"]
# Each command, with the arguments it is run with (the database is added),
# and its exit status: a run that printed nothing would prove nothing.
RUNS: list[tuple[int, list[str]]] = [
    (0, ["detect", "MIT"]),
    (0, ["detect", "--text", MIT_TEXT]),
    (0, ["detect", "--top", "3", "--threshold", "0", "--text", "permission"]),
    (1, ["detect", "--id", "No-Such-1.0"]),
    (0, ["match", "MIT"]),
    (0, ["match", "GPLv2+ or MIT"]),
    (1, ["match", "MIT ; Apache 2"]),
    (1, ["match", "Apache 2.0?"]),
    (1, ["match", "\u201cMIT\u201d \\ caf\u00e9 \U0001f600"]),
    (0, ["match", "MIT\tOR ISC"]),
    (2, ["match", "line\nbreak"]),
    *[(0, [cmd, "MIT"]) for cmd in PREDICATES],
    *[(1, [cmd, "--id", "No-Such-1.0"]) for cmd in PREDICATES],
    (0, ["update", "--source", "packaged"]),
    (0, ["update", "--source", "packaged", "--force"]),
    (0, ["update", "--source", "packaged", "--list", "spdx-license-list"]),
    (0, ["clear-cache"]),  # the text run clears, the JSON run finds nothing
]
# Commands whose JSON is the text record, key for key (clear-cache too, but
# its two runs differ: test_clear_cache checks its JSON).
RECORDS = {"update", *PREDICATES}


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    """A database built by ``update`` from a list with MIT's text and flags."""
    ship(monkeypatch, release_bundle())
    path = str(tmp_path / "licenses.db")
    result = CliRunner().invoke(cli, ["--db", path, "update", "--source", "packaged"])
    assert result.exit_code == 0, result.output
    return path


def _run(db: str, args: list[str], as_json: bool) -> Result:
    command, *rest = args
    flags = ["--json"] if as_json else []
    where = [] if command == "match" else ["--db", db]  # match: the shipped list
    return CliRunner().invoke(cli, [*where, command, *flags, *rest])


def text_fields(line: str) -> dict[str, str]:
    """A text line's fields, each value read back; it must fit the pattern."""
    assert TEXT_LINE.fullmatch(line), line
    pairs = [field.partition("=") for field in line.split("\t")]
    keys = [key for key, _, _ in pairs]
    assert len(set(keys)) == len(keys), line
    return {key: read_text_field(value) for key, _, value in pairs}


def json_record(line: bytes) -> dict[str, object]:
    """A JSON line's object; its bytes must be its own JCS form."""
    record = json.loads(line)
    assert isinstance(record, dict), line
    assert rfc8785.dumps(record) == line, line
    assert all(JSON_KEY.fullmatch(key) for key in record), line
    return record


def _as_text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


@pytest.mark.parametrize(
    ("status", "args"), RUNS, ids=[" ".join(args)[:40] for _, args in RUNS]
)
def test_every_line_follows_the_pattern(
    monkeypatch: pytest.MonkeyPatch, db: str, status: int, args: list[str]
) -> None:
    if args[0] == "match":  # the fixtures' list: more IDs than the database
        ship(monkeypatch, fixture_bundle())
    text, as_json = _run(db, args, False), _run(db, args, True)
    assert (text.exit_code, as_json.exit_code) == (status, status), text.output
    if status == 2:  # a usage error: nothing printed
        assert (text.stdout, as_json.stdout) == ("", "")
        return
    assert text.stdout and as_json.stdout
    lines = [text_fields(line) for line in text.stdout.splitlines()]
    records = [json_record(line) for line in as_json.stdout_bytes.splitlines()]
    assert as_json.stdout_bytes.endswith(b"\n")
    if args[0] == "detect" and status == 1:  # no answer: one empty record
        assert len(lines) == len(records) == 1
        assert set(lines[0].values()) == {""}
        assert set(records[0].values()) == {None}
    if args[0] == "match":  # the whole resolution; the head line is part of it
        assert len(records) == 1
        pairs = list(zip(lines[:1], records))
    else:  # one object per line
        assert len(records) == len(lines)
        pairs = list(zip(lines, records))
    for fields, record in pairs:
        keys = {key.lower() for key in fields}
        assert keys <= set(record), (fields, record)
        if args[0] in RECORDS:
            assert keys == set(record)
            assert {k.lower(): v for k, v in fields.items()} == {
                key: _as_text(value) for key, value in record.items()
            }


def test_every_command_is_run() -> None:
    """A new command must be added to RUNS, or this fails."""
    commands = cli.list_commands(click.Context(cli))
    assert {args[0] for _, args in RUNS} == set(commands)


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("EXPRESSION=MIT\tMETHOD=id", True),
        ("EXPRESSION=", True),
        ("FROM=a\\tb\\\\c\\u201c\\xe9\\U0001f600", True),
        ("EXPRESSION=MIT METHOD=id", True),  # one field, its value has a space
        ("expression=MIT", False),
        ("EXPRESSION=MIT\t", False),
        ("EXPRESSION=a\\b", False),  # a bare backslash
        ("EXPRESSION=a\\", False),
        ("EXPRESSION", False),
        ("=MIT", False),
        ("EXPRESSION=a\rb", False),
    ],
)
def test_the_text_pattern(line: str, ok: bool) -> None:
    assert (TEXT_LINE.fullmatch(line) is not None) is ok


@pytest.mark.parametrize(
    "line",
    [b'{"b":1, "a":2}', b'{"b":1,"a":2}', b'{"a":1.0}', b'{"a":"\\u00e9"}', b"[1]"],
    ids=["space", "order", "number", "escape", "array"],
)
def test_a_json_line_that_is_not_jcs_fails(line: bytes) -> None:
    with pytest.raises(AssertionError):
        json_record(line)
