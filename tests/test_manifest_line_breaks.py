# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

r"""Two readers of a manifest value that read it wrongly (0.9.0).

A TOML file ends a line at LF or CRLF; an old Mac file ends it at a lone CR,
which the input readers of the command line turn into an LF, so the API reads
it so too. ``str.splitlines()`` also splits at U+2028, U+2029, U+0085, U+000B,
U+000C and U+001C to U+001E, so a comment such as
``# note<U+2028>license = "GPL-3.0-only"`` held a field, and one such as
``# <U+2028>x = \"\"\"`` opened a string that hid the real field.

A JSON ``"\udcff"`` escape decodes to a lone surrogate, which SQLite cannot
bind: the name lookup of a package.json value raised ``UnicodeEncodeError``
(a traceback, exit 1). A TOML surrogate escape already gives no value, so
every channel now gives no answer.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import json_lines
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.manifest import (
    _toml_text_lines,
    license_value_groups,
    toml_license_values,
)

BREAKS = {
    "U+2028": " ",
    "U+2029": " ",
    "U+0085": "\u0085",
    "FF": "\x0c",
    "VT": "\x0b",
}

#: A manifest body, a real ``license = "MIT"`` field last. ``{br}`` is a break
#: TOML does not read as a line end, in a comment or in a multi-line string:
#: after it comes a field (``GPL-3.0-only``), a header or the start of a string,
#: none of which is TOML there.
TEMPLATES = {
    "comment-field": '{head}# note{br}license = "GPL-3.0-only"\nlicense = "MIT"\n',
    "comment-string": '{head}# note{br}x = """\nlicense = "MIT"\n',
    "string-field": (
        '{head}note = """\nline{br}license = "GPL-3.0-only"\n"""\nlicense = "MIT"\n'
    ),
    "string-header": (
        '{head}note = """\nline{br}[other]\nlicense = "GPL-3.0-only"\n"""\n'
        'license = "MIT"\n'
    ),
}
HEADS = {
    "pyproject": ("pyproject.toml", '[project]\nname = "x"\n'),
    "cargo": ("Cargo.toml", '[package]\nname = "x"\nedition = "2021"\n'),
}


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        Lic("MIT", "MIT License", True, True, True),
        Lic("GPL-3.0-only", "GNU General Public License v3.0 only", True, True, True),
        *GPL2_ROWS,
    ]
    yield from seeded_db("test_manifest_line_breaks", rows)


#: ``(file name, text)`` of each head, template and break, by id.
CASES = {
    f"{head}-{template}-{name}": (
        file_name,
        body.format(head=prefix, br=brk),
    )
    for head, (file_name, prefix) in HEADS.items()
    for template, body in TEMPLATES.items()
    for name, brk in BREAKS.items()
}


@pytest.mark.parametrize("case", CASES)
def test_a_line_break_that_is_no_toml_line_end_holds_no_field(case: str) -> None:
    assert toml_license_values(CASES[case][1]) == ["MIT"]


def cli_top(db: str, tmp_path: Path, via: str, name: str, text: str) -> dict[str, Any]:
    """The first result of ``detect --json`` for *text* given as a file called
    *name*, as ``--text`` or on standard input."""
    args = ["--db", db, "detect", "--json"]
    stdin = None
    if via == "file":
        path = tmp_path / name
        path.write_bytes(text.encode("utf-8"))
        args.append(str(path))
    elif via == "text":
        args += ["--text", text]
    else:
        stdin = text
    result = CliRunner().invoke(cli, args, input=stdin)
    assert result.exit_code == 0, result.output
    return json_lines(result.stdout)[0]


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("via", ["file", "text", "stdin"])
def test_the_field_after_such_a_break_is_the_answer(
    db: str, tmp_path: Path, via: str, case: str
) -> None:
    name, text = CASES[case]
    top = cli_top(db, tmp_path, via, name, text)
    assert (top["expression"], top["exact"]) == ("MIT", True)


@pytest.mark.parametrize("brk", BREAKS.values(), ids=BREAKS)
def test_a_comment_with_such_a_break_is_no_table_header(brk: str) -> None:
    """Text with no file name is TOML only if it starts with a table."""
    text = f'# note{brk}[project]\nlicense = "MIT"\n'
    assert license_value_groups(text, "") == []


#: ``(file name, text, license value, expression)``: a lone CR ends a line, as an
#: LF and a CRLF do, so a CR-only file gives its field (v0.8.4, the command line).
LINE_END_CASES = {
    "pyproject-first": (
        "pyproject.toml",
        '[project]\rlicense = "GPL-3.0-only"\r',
        "GPL-3.0-only",
        "GPL-3.0-only",
    ),
    "pyproject-after-name": (
        "pyproject.toml",
        '[project]\rname = "x"\r# note\rlicense = "MIT"\r',
        "MIT",
        "MIT",
    ),
    "cargo": (
        "Cargo.toml",
        '[package]\rname = "x"\redition = "2021"\rlicense = "MIT OR GPL-3.0-only"\r',
        "MIT OR GPL-3.0-only",
        "GPL-3.0-only OR MIT",
    ),
}


@pytest.mark.parametrize(
    ("text", "lines"),
    [
        ("a\nb", ["a", "b"]),
        ("a\r\nb\r\n", ["a", "b", ""]),  # CRLF is one line end
        ("a\rb\r", ["a", "b", ""]),
        ("a\r\rb", ["a", "", "b"]),
        ("a\u2028b\u0085c\x0cd\x0be", ["a\u2028b\u0085c\x0cd\x0be"]),
    ],
)
def test_toml_lines_end_at_lf_crlf_and_a_lone_cr_only(
    text: str, lines: list[str]
) -> None:
    assert list(_toml_text_lines(text)) == lines


@pytest.mark.parametrize("case", LINE_END_CASES)
def test_a_lone_cr_ends_a_toml_line(case: str) -> None:
    _, text, value, _ = LINE_END_CASES[case]
    assert toml_license_values(text) == [value]


@pytest.mark.parametrize("case", LINE_END_CASES)
@pytest.mark.parametrize("via", ["api", "file", "text", "stdin"])
def test_the_api_and_the_command_line_read_a_cr_only_file_alike(
    db: str, tmp_path: Path, via: str, case: str
) -> None:
    name, text, _, expression = LINE_END_CASES[case]
    if via == "api":
        top: Mapping[str, object] = LicenseDetector(db).detect(text=text)[0]
    else:
        top = cli_top(db, tmp_path, via, name, text)
    assert (top["expression"], top["exact"]) == (expression, True)


@pytest.mark.parametrize("head", ["# note\r", "\r"], ids=["comment", "blank"])
def test_a_table_header_after_a_cr_line_end_starts_a_toml_text(head: str) -> None:
    """Text with no file name is TOML if its first line that is not blank or
    a comment is a table header: a lone CR ends those lines."""
    text = f'{head}[project]\rlicense = "MIT"\r'
    assert ["MIT"] in license_value_groups(text, "")


def test_a_cr_line_end_ends_a_comment_before_a_multi_line_string() -> None:
    text = '[project]\rnote = """\rlicense = "GPL-3.0-only"\r"""\rlicense = "MIT"\r'
    assert toml_license_values(text) == ["MIT"]


@pytest.mark.parametrize("ending", ["\n", "\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("head", HEADS)
def test_a_crlf_toml_file_is_read_as_before(head: str, ending: str) -> None:
    text = (
        '[project]\nname = "x"\n# note\nlicense = "MIT"\n'
        if head == "pyproject"
        else '[package]\nname = "x"\nlicense = "MIT"\n'
    ).replace("\n", ending)
    assert toml_license_values(text) == ["MIT"]
    assert license_value_groups(text, ".toml") == [["MIT"]]
    assert ["MIT"] in license_value_groups(text, "")  # _starts_with_table


def test_a_crlf_multi_line_string_still_hides_its_lines() -> None:
    text = (
        '[project]\r\nnote = """\r\nlicense = "GPL-3.0-only"\r\n"""\r\n'
        'license = "MIT"\r\n'
    )
    assert toml_license_values(text) == ["MIT"]


@pytest.mark.parametrize("name", ["package.json", "other.json"])
def test_a_json_surrogate_escape_gives_no_answer(
    db: str, tmp_path: Path, name: str
) -> None:
    path = tmp_path / name
    path.write_text('{"license": "GPL-2.\\udcff0"}', encoding="utf-8")
    assert LicenseDetector(db).detect(file_path=str(path)) == []
    result = CliRunner().invoke(cli, ["--db", db, "detect", str(path)])
    assert result.exit_code == 1, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_a_json_surrogate_escape_in_a_text_gives_no_answer(db: str) -> None:
    text = '{"license": "GPL-2.\\udcff0"}'
    assert LicenseDetector(db).detect(text=text) == []
    result = CliRunner().invoke(cli, ["--db", db, "detect", "--text", text])
    assert result.exit_code == 1, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
