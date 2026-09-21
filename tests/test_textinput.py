# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for licenseid.textinput: how input bytes become match text."""
# pylint: disable=missing-function-docstring

import ast
from pathlib import Path

import pytest
from input_payloads import PAYLOADS, Payload

import licenseid
from licenseid.errors import InvalidInputError
from licenseid.textinput import decode_input, read_text_file

_TEXT = [p for p in PAYLOADS if p.text is not None]
_BINARY = [p for p in PAYLOADS if p.text is None]
_WARNING = "WARNING: input: not UTF-8, read as Latin-1: {}\n"


@pytest.mark.parametrize("payload", _TEXT, ids=lambda p: p.name)
def test_text_decodes_with_the_warning_only_for_latin1(
    payload: Payload, capsys: pytest.CaptureFixture[str]
) -> None:
    assert decode_input(payload.data, "LICENSE") == payload.text
    expected = _WARNING.format("LICENSE") if payload.latin1 else ""
    assert capsys.readouterr().err == expected


@pytest.mark.parametrize("payload", _BINARY, ids=lambda p: p.name)
def test_any_nul_byte_is_binary(payload: Payload) -> None:
    """The binary rule applies whether or not the bytes happen to be valid
    UTF-8, so the same text is not accepted or rejected by accident."""
    with pytest.raises(InvalidInputError, match=r"^input: binary file: f$"):
        decode_input(payload.data, "f")


@pytest.mark.parametrize("payload", PAYLOADS, ids=lambda p: p.name)
def test_a_file_is_read_as_its_bytes_are_decoded(
    payload: Payload, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """read_text_file is decode_input over the file's bytes, named by its path."""
    path = tmp_path / "LICENSE"
    path.write_bytes(payload.data)
    if payload.text is None:
        with pytest.raises(InvalidInputError, match=f"^input: binary file: {path}$"):
            read_text_file(str(path))
    else:
        assert read_text_file(str(path)) == payload.text
        expected = _WARNING.format(path) if payload.latin1 else ""
        assert capsys.readouterr().err == expected


def test_a_missing_file_raises_oserror(tmp_path: Path) -> None:
    """Not wrapped: callers word an unreadable file themselves."""
    with pytest.raises(FileNotFoundError):
        read_text_file(str(tmp_path / "nope"))


@pytest.mark.parametrize("module", ["cli", "matcher"])
def test_only_textinput_opens_a_users_file(module: str) -> None:
    """The CLI and the API read a file through read_text_file, so they cannot
    decode it differently: neither module calls `open`, `io.open`,
    `Path.open`, `read_bytes` or `read_text`. (database.py and spdx_source.py
    open SPDX data strictly on purpose.)"""
    path = Path(str(licenseid.__path__[0])) / f"{module}.py"
    called = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            func = node.func
            called.add(
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            )
    assert not called & {"open", "read_bytes", "read_text"}
