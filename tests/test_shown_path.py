# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A file name in a diagnostic stays on its one line: a line break, a tab
or a control character in it is written as an escape, and a ";" as ",", as
the database's path already was (P125). A backslash stays as it is: a
diagnostic is read by a person, and a Windows path reads as typed."""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import DIAGNOSTIC_RE, make_ready_db_path, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid.cli import cli
from licenseid.errors import shown


@pytest.mark.parametrize(
    ("value", "written"),
    [
        ("LICENSE", "LICENSE"),
        ("C:\\Users\\me\\LICENSE", "C:\\Users\\me\\LICENSE"),
        ("a\nb", "a\\nb"),
        ("a\tb\rc", "a\\tb\\rc"),
        ("a;b", "a,b"),
        ("caf\u00e9 \u201cx\u201d", "caf\u00e9 \u201cx\u201d"),
        ("a\u2028b\x1b", "a\\u2028b\\x1b"),
    ],
    ids=["plain", "windows", "newline", "tab-cr", "semicolon", "unicode", "controls"],
)
def test_a_name_is_shown_on_one_line(value: str, written: str) -> None:
    assert shown(value) == written


@posix_only  # Windows refuses a line break in a file name
@pytest.mark.parametrize(
    ("content", "condition"),
    [
        (b"\x00\x01", "binary file"),
        (b"caf\xe9 MIT", "not UTF-8, read as Latin-1"),
        (b"   \n", "empty"),
    ],
    ids=["binary", "latin-1", "empty"],
)
def test_a_file_name_with_a_line_break_keeps_the_diagnostic_on_one_line(
    tmp_path: Path, content: bytes, condition: str
) -> None:
    path = tmp_path / "a\nb;c"
    path.write_bytes(content)
    db_path, keep = make_ready_db_path("test_shown_path")
    try:
        result = CliRunner().invoke(cli, ["--db", db_path, "detect", str(path)])
    finally:
        keep.close()
    lines = [line for line in result.stderr.splitlines() if line]
    assert len(lines) == 1, result.stderr
    assert DIAGNOSTIC_RE.fullmatch(lines[0]), lines[0]
    assert f"input: {condition}: {shown(str(path))}" in lines[0]
