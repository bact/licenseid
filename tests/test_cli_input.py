# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for cli.decode_input(): how input bytes become match text."""
# pylint: disable=missing-function-docstring

import click
import pytest

from licenseid.cli import cli, decode_input, read_text_option, unescape_text
from licenseid.errors import InvalidInputError


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"MIT License\n", "MIT License\n"),
        (b"\xef\xbb\xbfMIT License\n", "MIT License\n"),  # UTF-8 BOM stripped
        (b"a\r\nb\rc\n", "a\nb\nc\n"),  # newlines as text-mode reading
        ("Copyright © Jérôme".encode(), "Copyright © Jérôme"),
    ],
    ids=["ascii", "utf8_bom", "newlines", "utf8_non_ascii"],
)
def test_utf8_input_decodes_without_warning(
    data: bytes, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert decode_input(data, "LICENSE") == expected
    assert capsys.readouterr().err == ""


def test_latin1_input_falls_back_with_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = "Copyright © Jérôme\r\n".encode("latin-1")
    assert decode_input(data, "LICENSE") == "Copyright © Jérôme\n"
    assert capsys.readouterr().err == (
        "WARNING: input: not UTF-8, read as Latin-1: LICENSE\n"
    )


def test_binary_input_raises() -> None:
    with pytest.raises(InvalidInputError, match=r"^input: binary file: logo\.png$"):
        decode_input(b"\x89PNG\r\n\x1a\n\x00\x00", "logo.png")


@pytest.mark.parametrize(
    "data",
    [
        b"MIT License\x00\x00",  # valid UTF-8, but contains NUL
        "MIT License".encode("utf-16-le"),  # no BOM: valid UTF-8 with NULs
        "MIT License".encode("utf-16"),  # with BOM: not UTF-8
    ],
    ids=["utf8_with_nul", "utf16le_no_bom", "utf16_bom"],
)
def test_any_nul_byte_is_binary(data: bytes) -> None:
    """The binary rule applies whether or not the bytes happen to be valid
    UTF-8, so the same text is not accepted or rejected by accident."""
    with pytest.raises(InvalidInputError, match=r"^input: binary file: f$"):
        decode_input(data, "f")


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
