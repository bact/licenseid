# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the CLI's --text handling: escapes and line ends."""
# pylint: disable=missing-function-docstring

import click
import pytest

from licenseid.cli import cli, read_text_option, unescape_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a\\nb\\tc", "a\nb\tc"),
        ("\\u00e9 \\x41", "\u00e9 A"),
        ("back\\\\nslash", "back\\nslash"),  # escaped backslash, then "n"
        ("\\q \\x4 \\U00110000", "\\q \\x4 \\U00110000"),  # invalid: unchanged
        ("\\377 \\400 \\777 \\8", "\u00ff \\400 \\777 \\8"),  # octal ends at \377
        ("\\N{BULLET} \\N{NO SUCH NAME}", "\u2022 \\N{NO SUCH NAME}"),
        ("C:\\temp\\\\new", "C:\temp\\new"),  # a literal backslash is \\\\
        ("Copyright \u00a9 Zo\u00eb \u20ac\\n", "Copyright \u00a9 Zo\u00eb \u20ac\n"),
    ],
    ids=[
        "newline_tab",
        "hex_unicode",
        "escaped_backslash",
        "invalid",
        "octal_range",
        "named",
        "windows_path",
        "non_ascii",
    ],
)
def test_unescape_text(text: str, expected: str) -> None:
    """--text decodes escapes only; other non-ASCII text is kept as is, as it
    would be from a file or stdin."""
    assert unescape_text(text) == expected


@pytest.mark.parametrize("text", ["a\\r\\nb", "a\\rb", "a\r\nb"])
def test_text_option_line_ends_match_file_input(text: str) -> None:
    """--text gets the same LF line ends as file or stdin input."""
    assert read_text_option(click.Context(cli), text) == "a\nb"
