# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Streams and signals (roadmap item 10): a failure never passes for an
answer. Click exits 1, the code for "no", on a closed pipe and on Ctrl-C."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import errno
import io
import os
import shlex
import signal
import subprocess
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from conftest import invoke_match, make_ready_db_path, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db

from licenseid import console, output
from licenseid.cli import cli
from licenseid.cli import main as cli_main
from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def db() -> Generator[str, None, None]:
    db_path, keep_alive = make_ready_db_path("test_cli_streams")
    yield db_path
    keep_alive.close()


@pytest.mark.parametrize(
    ("code", "exit_code", "stderr"),
    [
        (errno.EFBIG, 2, "ERROR: output: write failed: File too large\n"),
        (errno.ENOSPC, 2, "ERROR: output: write failed: No space left on device\n"),
        (errno.EPIPE, 141, ""),  # the reader left: quiet, as cat and grep
    ],
    ids=["too-large", "disk-full", "closed-pipe"],
)
@pytest.mark.parametrize(
    "args", [["--bold", "MIT"], ["--json", "--id", "MIT"]], ids=["bold", "json"]
)
def test_an_output_failure_is_no_answer(
    db: str, code: int, exit_code: int, stderr: str, args: list[str]
) -> None:
    failing = mock.create_autospec(
        click.echo, side_effect=OSError(code, os.strerror(code))
    )
    with mock.patch.object(click, "echo", failing):
        result = invoke_match(db, *args)
    assert (result.exit_code, result.stderr) == (exit_code, stderr)


def test_an_unencodable_result_is_a_failed_write_not_a_traceback(db: str) -> None:
    """A code page without the character (Windows pipes) must not exit 1."""
    failing = mock.create_autospec(
        click.echo,
        side_effect=UnicodeEncodeError("charmap", "\u65e5", 0, 1, "no mapping"),
    )
    with mock.patch.object(click, "echo", failing):
        result = invoke_match(db, "--id", "MIT")
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: output: write failed: 'charmap' codec")


def test_unencodable_output_is_escaped_as_stderr_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="\n")
    monkeypatch.setattr(sys, "stdout", stream)
    output.escape_unencodable_output()
    click.echo("caf\u00e9 \u65e5")
    stream.flush()
    assert raw.getvalue() == b"caf\xe9 \\u65e5\n"


def test_an_error_handler_the_user_chose_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="surrogateescape")
    monkeypatch.setattr(sys, "stdout", stream)
    output.escape_unencodable_output()
    assert stream.errors == "surrogateescape"


def test_a_closed_stream_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    stream.close()
    monkeypatch.setattr(sys, "stdout", stream)
    output.escape_unencodable_output()  # reconfigure raises ValueError


@pytest.mark.parametrize("stream", [None, io.StringIO()], ids=["closed", "no_codec"])
def test_escaping_needs_a_text_stream(
    monkeypatch: pytest.MonkeyPatch, stream: object
) -> None:
    monkeypatch.setattr(sys, "stdout", stream)
    output.escape_unencodable_output()  # nothing to reconfigure, no exception


def test_main_escapes_unencodable_output_before_it_runs_a_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        "licenseid.cli.escape_unencodable_output", lambda: seen.append("escaped")
    )

    def run(**_: object) -> int:
        seen.append("ran")
        return 0

    monkeypatch.setattr(cli, "main", run)
    with pytest.raises(SystemExit):
        cli_main()
    assert seen == ["escaped", "ran"]


def test_an_update_whose_report_fails_is_not_a_failed_update(tmp_path: Path) -> None:
    """The update itself succeeded; only its line could not be written."""
    failing = mock.create_autospec(
        click.echo, side_effect=OSError(errno.EFBIG, "File too large")
    )
    with (
        mock.patch.object(
            LicenseDatabase, "update_from_remote", autospec=True, return_value=True
        ),
        mock.patch.object(click, "echo", failing),
    ):
        result = CliRunner().invoke(cli, ["--db", str(tmp_path / "l.db"), "update"])
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: output: write failed: File too large\n",
    )


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_an_interrupt_exits_130_without_a_message(db: str, command: str) -> None:
    """Exit 1 would read as "no license" or "not OSI"."""
    with mock.patch.object(
        AggregatedLicenseMatcher, "match", autospec=True, side_effect=KeyboardInterrupt
    ):
        result = CliRunner().invoke(cli, ["--db", db, command, "MIT"])
    assert (result.exit_code, result.stderr) == (130, "")


def test_an_interrupt_ends_an_open_progress_line(db: str) -> None:
    def interrupt(*_: object, **__: object) -> None:
        console.status("Downloading...", end="")
        raise KeyboardInterrupt

    with mock.patch.object(
        AggregatedLicenseMatcher, "match", autospec=True, side_effect=interrupt
    ):
        result = CliRunner().invoke(cli, ["--db", db, "match", "MIT"])
    assert (result.exit_code, result.stderr) == (130, "Downloading...\n")


@pytest.mark.parametrize("function", [console.error, console.warn])
def test_a_failing_stderr_does_not_crash(
    monkeypatch: pytest.MonkeyPatch, function: Callable[[str], None]
) -> None:
    broken = mock.Mock(spec=sys.stderr)
    broken.write.side_effect = OSError(errno.EFBIG, "File too large")
    broken.fileno.side_effect = io.UnsupportedOperation  # no descriptor to discard
    monkeypatch.setattr(sys, "stderr", broken)
    function("database: not found")  # nowhere to report it; no exception


# The real streams, through a shell: click's test runner always has them.
# The shell, /dev/null, SIGINT and exit 141 are POSIX.


def _environ(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, "HOME": str(tmp_path / "home")}


@posix_only
@pytest.mark.parametrize(
    ("script", "exit_code", "stderr"),
    [
        ("$L match <&-", 2, "ERROR: input: missing; pass a file, an ID,"),
        ("$L match --bold MIT >&-", 2, "ERROR: output: write failed: closed"),
        ("$L is-osi MIT >&-", 2, "ERROR: output: write failed: closed"),
        # click writes help itself, before any command runs
        ("$L --help >&-", 2, "ERROR: output: write failed: closed"),
        ("$L match --help 1</dev/null", 2, "ERROR: output: write failed: Bad file"),
        # stderr read-only: its text cannot be flushed at exit either, which
        # turned every status into 120
        ("$L match --text 'zz qq' 2</dev/null", 1, ""),
        ("$L match --text MIT 1</dev/null 2</dev/null", 2, ""),
        # a usage error kept its status too; it once went round the console
        ("$L match --bogus 2</dev/null", 2, ""),
        ("$L match --bogus 2>&-", 2, ""),  # and stays off standard output
        # through cli.main(), the real entry point: one line in the grammar
        ("$L match --bogus", 2, "ERROR: option: not found: --bogus; did you mean"),
        ("$L", 2, "Usage: "),  # no subcommand: the help, on standard error
        ("$L match --bold MIT", 0, ""),
    ],
    ids=[
        "stdin-closed",
        "stdout-closed",
        "is-osi-stdout-closed",
        "help-stdout-closed",
        "help-stdout-read-only",
        "stderr-read-only-no-match",
        "both-read-only",
        "usage-stderr-read-only",
        "usage-stderr-closed",
        "usage-error",
        "no-subcommand",
        "control",
    ],
)
def test_a_broken_stream(
    tmp_path: Path, script: str, exit_code: int, stderr: str
) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    licenseid = shlex.join(
        [sys.executable, "-m", "licenseid.cli", "--db", str(db_path)]
    )
    result = subprocess.run(
        ["/bin/sh", "-c", script.replace("$L", licenseid)],
        capture_output=True,
        text=True,
        env=_environ(tmp_path),
        check=False,
    )
    assert result.returncode == exit_code
    assert result.stderr.startswith(stderr) and "Traceback" not in result.stderr
    assert "Usage" not in result.stdout


@posix_only
@pytest.mark.parametrize(
    "args", [["is-osi", "MIT"], ["--help"]], ids=["is-osi", "help"]
)
def test_a_reader_that_leaves_ends_the_run_quietly(
    tmp_path: Path, args: list[str]
) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-m", "licenseid.cli", "--db", str(db_path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_environ(tmp_path),
    ) as proc:
        assert proc.stdout is not None and proc.stderr is not None
        proc.stdout.close()  # long before the child writes its answer
        assert (proc.wait(timeout=30), proc.stderr.read()) == (141, b"")


# The child says "ready" from its read of standard input, so the signal comes
# while it waits there, never before main() handles it. A background job
# starts with SIGINT ignored, which Python keeps: the child restores it.
_READY = """
import signal, sys
import licenseid.cli as c

class Stdin:
    def __init__(self, real):
        self.real, self.buffer = real, self
    def isatty(self):
        return False
    def read(self, *args):
        sys.stderr.write("ready\\n")
        sys.stderr.flush()
        return self.real.read(*args)

signal.signal(signal.SIGINT, signal.default_int_handler)
sys.stdin = Stdin(sys.stdin.buffer)
sys.argv[1:] = ["--db", sys.argv[1], "match"]
c.main()
"""


@posix_only
def test_ctrl_c_exits_130(tmp_path: Path) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-c", _READY, str(db_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_environ(tmp_path),
    ) as proc:
        assert proc.stderr is not None
        assert proc.stderr.readline() == b"ready\n"
        proc.send_signal(signal.SIGINT)
        # Standard input stays open until the child exits: closed first, the
        # child could read end of input before the signal (`input: missing`).
        proc.wait(timeout=30)
        out, err = proc.communicate(timeout=30)
    assert (proc.returncode, out, err) == (130, b"", b"")


@posix_only
def test_ctrl_c_before_a_command_exits_130() -> None:
    """Click turns it into Abort while it parses the options."""
    with (
        mock.patch.object(
            cli, "main", autospec=True, side_effect=click.exceptions.Abort
        ),
        pytest.raises(SystemExit) as exit_info,
    ):
        cli_main()
    assert exit_info.value.code == 130
