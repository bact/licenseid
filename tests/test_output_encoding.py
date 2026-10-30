# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What a result line is on a locale that cannot write every character.

A text line is written in the stream's encoding, a character it cannot
encode as ``\\xHH``, ``\\uHHHH`` or ``\\UHHHHHHHH`` (``output.echo``), which
``result.read_text_field`` reads back; a ``--json`` line is UTF-8 bytes on
every locale (``output.echo_json``, RFC 8785). Every line ends in ``\\n``,
on Windows too: the streams here translate a line feed to ``\\r\\n`` as
Windows' text streams do, on every OS (P123).
"""
# pylint: disable=missing-function-docstring

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import line_fields, make_ready_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import console, match, output
from licenseid.cli import cli
from licenseid.cli import main as cli_main
from licenseid.result import json_line, read_text_field, resolution_lines

# A list whose third part names nothing: its text comes back on a line.
VALUE = "MIT ; Apache 2 ; caf\u00e9 \U0001f600 \u201cx\u201d"
OPERAND = "caf\u00e9 \U0001f600 \u201cx\u201d"


def _stream(
    encoding: str, errors: str = "strict"
) -> tuple[io.BytesIO, io.TextIOWrapper]:
    """A text stream over bytes that writes a line feed as ``\\r\\n``, as
    a Windows console, pipe or file does."""
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, errors=errors, newline="\r\n")


@pytest.mark.parametrize(
    ("encoding", "errors", "written"),
    [
        ("cp1252", "strict", b"caf\xe9 \\U0001f600 \\u65e5\n"),
        ("latin-1", "strict", b"caf\xe9 \\U0001f600 \\u65e5\n"),
        ("ascii", "strict", b"caf\\xe9 \\U0001f600 \\u65e5\n"),
        ("utf-8", "strict", "caf\u00e9 \U0001f600 \u65e5\n".encode()),
        # The stream's own handler is not asked: one rule on every locale.
        ("latin-1", "replace", b"caf\xe9 \\U0001f600 \\u65e5\n"),
    ],
    ids=["cp1252", "latin-1", "ascii", "utf-8", "own-handler"],
)
def test_a_text_line_escapes_what_the_stream_cannot_encode(
    monkeypatch: pytest.MonkeyPatch, encoding: str, errors: str, written: bytes
) -> None:
    raw, stream = _stream(encoding, errors)
    monkeypatch.setattr(sys, "stdout", stream)
    output.echo("caf\u00e9 \U0001f600 \u65e5")
    stream.flush()
    assert raw.getvalue() == written
    assert read_text_field(written.decode(encoding)[:-1]) == (
        "caf\u00e9 \U0001f600 \u65e5"
    )


@pytest.mark.parametrize("encoding", ["latin-1", "ascii", "cp1252", "utf-8"])
def test_a_json_line_is_utf8_on_every_locale(
    monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    raw, stream = _stream(encoding)
    monkeypatch.setattr(sys, "stdout", stream)
    output.echo("first")  # what was written before stays in order
    output.echo_json('{"text":"caf\u00e9 \U0001f600"}')
    assert raw.getvalue().endswith('{"text":"caf\u00e9 \U0001f600"}\n'.encode())
    assert raw.getvalue().startswith(b"first\n")


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252", "ascii", "cp932"])
def test_every_line_ends_in_a_line_feed_on_windows(
    monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    """Text and JSON lines alike: one ending in one run (JSON Lines, and
    ``awk`` in Git Bash keeps a ``\\r`` in the last field)."""
    raw, stream = _stream(encoding)
    monkeypatch.setattr(sys, "stdout", stream)
    output.echo("A=1\tB=2")
    output.echo_json('{"a":1}')
    output.echo("")
    output.echo("C=3")
    assert raw.getvalue() == b'A=1\tB=2\n{"a":1}\n\nC=3\n'


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252", "ascii", "cp932"])
def test_every_diagnostic_line_ends_in_a_line_feed_on_windows(
    monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    """Standard error follows the same rule, and a character its encoding
    cannot hold is escaped, never raised."""
    raw, stream = _stream(encoding)
    monkeypatch.setattr(sys, "stderr", stream)
    console.status("Fetching", end="")
    console.status("...", end="")
    console.warn("input: not UTF-8, read as Latin-1: caf\u00e9 \U0001f600")
    console.status("done")
    console.write("help\n")
    text = {
        "utf-8": "caf\u00e9 \U0001f600",
        "cp1252": "caf\u00e9 \\U0001f600",
        "ascii": "caf\\xe9 \\U0001f600",
        "cp932": "caf\\xe9 \\U0001f600",
    }[encoding]
    expected = (
        f"Fetching...\nWARNING: input: not UTF-8, read as Latin-1: {text}\ndone\nhelp\n"
    )
    assert raw.getvalue() == expected.encode(encoding)


@pytest.mark.parametrize(
    "args",
    [["--version"], ["--help"], ["is-osi", "--help"], ["match", "--help"]],
    ids=["version", "help", "command-help", "match-help"],
)
def test_the_version_and_help_end_lines_in_a_line_feed_on_windows(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    raw, stream = _stream("utf-8")
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(SystemExit) as stopped:
        monkeypatch.setattr(sys, "argv", ["licenseid", *args])
        cli_main()
    assert stopped.value.code == 0
    assert b"\r" not in raw.getvalue()
    assert raw.getvalue().endswith(b"\n")


def test_a_json_line_on_a_text_only_stream_is_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    output.echo_json('{"a":"\u00e9"}')
    assert stream.getvalue() == '{"a":"\u00e9"}\n'


@pytest.mark.parametrize("write", [output.echo, output.echo_json], ids=["text", "json"])
def test_a_closed_stream_is_a_failed_write(
    monkeypatch: pytest.MonkeyPatch, write: object
) -> None:
    _, stream = _stream("utf-8")
    stream.close()
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(output.OutputError, match="^closed$"):
        write("x")  # type: ignore[operator]


def test_an_encoding_python_does_not_know_is_left_to_the_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Odd(io.StringIO):
        """A stream that names an encoding Python does not know."""

        encoding = "no-such-codec"

    stream = Odd()
    monkeypatch.setattr(sys, "stdout", stream)
    output.echo("caf\u00e9")
    assert stream.getvalue() == "caf\u00e9\n"


def test_an_unknown_encoding_over_bytes_is_left_to_the_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stream over bytes that names a codec Python does not know gets the
    text, which it encodes its own way."""

    class Odd(io.TextIOWrapper):
        """Names an encoding Python does not know; writes UTF-8."""

        @property
        def encoding(self) -> str:  # type: ignore[override]
            return "no-such-codec"

    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", Odd(raw, encoding="utf-8", newline="\n"))
    output.echo("caf\u00e9")
    assert raw.getvalue() == "caf\u00e9\n".encode()


# --- the commands, through click's runner on a latin-1 stream ---


def test_match_on_a_latin1_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())
    runner = CliRunner(charset="latin-1")
    text = runner.invoke(cli, ["match", VALUE])
    as_json = runner.invoke(cli, ["match", "--json", VALUE])
    assert (text.exit_code, as_json.exit_code) == (1, 1)
    last = text.stdout_bytes.splitlines()[-1]
    assert last == (
        b"OPERAND=caf\xe9 \\U0001f600 \\u201cx\\u201d\tEXPRESSION=\tCATEGORY=unresolved"
    )
    assert line_fields(last.decode("latin-1"))["OPERAND"] == OPERAND
    assert as_json.stdout_bytes == (json_line(match(VALUE)) + "\n").encode("utf-8")


def test_detect_json_on_a_latin1_stream_is_unchanged() -> None:
    """A detection is ASCII: the same bytes on any locale."""
    db_path, keep = make_ready_db_path("test_output_encoding")
    try:
        result = CliRunner(charset="latin-1").invoke(
            cli, ["--db", db_path, "detect", "--json", "--id", "MIT"]
        )
    finally:
        keep.close()
    assert result.exit_code == 0
    assert result.stdout_bytes.startswith(b'{"coverage":null,"exact":true,')


# --- the real entry point, with PYTHONIOENCODING ---


@pytest.mark.parametrize("encoding", ["latin-1", "ascii"])
def test_the_entry_point_on_a_narrow_locale(tmp_path: Path, encoding: str) -> None:
    """``cli.main()`` in a child, standard output a pipe in *encoding*. The
    packaged list is the fixtures' bundle, so no database is needed."""
    bundle = tmp_path / "bundle.json.gz"
    bundle.write_bytes(fixture_bundle())
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from unittest import mock\n"
        "import licenseid.cli as c\n"
        "from licenseid import spdxdata\n"
        "raw = Path(sys.argv[1]).read_bytes()\n"
        "with mock.patch.object(spdxdata, 'packaged_bundle', lambda: raw):\n"
        "    sys.argv[1:] = sys.argv[2:]\n"
        "    c.main()\n"
    )
    env = {**os.environ, "PYTHONIOENCODING": encoding, "HOME": str(tmp_path)}
    lines = {}
    for flag in ([], ["--json"]):
        proc = subprocess.run(
            [sys.executable, "-c", script, str(bundle), "match", *flag, VALUE],
            capture_output=True,
            env=env,
            check=False,
            timeout=60,
        )
        assert (proc.returncode, proc.stderr) == (1, b""), proc.stderr
        lines[bool(flag)] = proc.stdout
    text = lines[False].decode(encoding)
    assert text.isascii() or encoding == "latin-1"
    assert line_fields(text.splitlines()[-1])["OPERAND"] == OPERAND
    assert lines[True].decode("utf-8").rstrip("\n").endswith('"trust":"none"}')
    assert OPERAND.encode("utf-8") in lines[True]


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "cp932"])
def test_a_diagnostic_with_a_character_the_locale_lacks(
    tmp_path: Path, encoding: str
) -> None:
    """The real entry point: an ERROR line that echoes the value is written
    with an escape, never raises, and does not turn exit 2 into 120."""
    env = {**os.environ, "PYTHONIOENCODING": encoding, "HOME": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-m", "licenseid.cli", "match", "caf\u00e9 \u65e5\nMIT"],
        capture_output=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert (proc.returncode, proc.stdout) == (2, b""), proc.stderr
    line = proc.stderr.decode(encoding)
    assert line.startswith("ERROR: input: invalid: line break: caf")
    assert "caf\u00e9 \u65e5 MIT" in read_text_field(line)  # escapes read back
    assert line.isascii() or encoding != "ascii"
    assert line.endswith("\n") and "\r" not in line


def test_the_text_lines_are_those_of_the_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["match", VALUE])
    assert result.stdout.splitlines() == resolution_lines(match(VALUE))
