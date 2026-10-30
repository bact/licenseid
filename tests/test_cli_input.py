# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the CLI's --text handling: taken as written (C6 of the
contract batch: escapes were decoded), with file and stdin line ends."""
# pylint: disable=missing-function-docstring

import click
import pytest

from licenseid.cli import cli
from licenseid.cliinput import read_text_option


@pytest.mark.parametrize(
    "text",
    [
        "a\\nb\\tc",
        "\\u00e9 \\x41",
        "back\\\\nslash",
        "\\N{BULLET}",
        "C:\\temp\\new",  # a Windows path reads as typed
        "Copyright \u00a9 Zo\u00eb \u20ac\\n",
    ],
    ids=["newline_tab", "hex_unicode", "backslashes", "named", "windows_path", "non_ascii"],
)
def test_text_is_taken_as_written(text: str) -> None:
    """A backslash is a backslash: no escape is decoded."""
    assert read_text_option(click.Context(cli), text) == text


@pytest.mark.parametrize("text", ["a\r\nb", "a\rb"])
def test_text_option_line_ends_match_file_input(text: str) -> None:
    """--text gets the same LF line ends as file or stdin input."""
    assert read_text_option(click.Context(cli), text) == "a\nb"
