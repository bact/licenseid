# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Streams and signals (roadmap item 10): a failure never passes for an
answer. Click exits 1, the code for "no", on a closed pipe and on Ctrl-C."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import errno
import os
import signal
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from conftest import invoke_match, make_ready_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db

from licenseid import console
from licenseid.cli import cli
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
    monkeypatch: pytest.MonkeyPatch, function: mock.Mock
) -> None:
    broken = mock.Mock(spec=sys.stderr)
    broken.write.side_effect = OSError(errno.EFBIG, "File too large")
    monkeypatch.setattr(sys, "stderr", broken)
    function("database: not found")  # nowhere to report it; no exception


# The real streams, through a shell: click's test runner always has them.


def _environ(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, "HOME": str(tmp_path / "home")}


@pytest.mark.parametrize(
    ("script", "exit_code", "stderr"),
    [
        ("$L match <&-", 2, "ERROR: input: missing; pass a file, an ID,"),
        ("$L match --bold MIT >&-", 2, "ERROR: output: write failed: closed"),
        ("$L is-osi MIT >&-", 2, "ERROR: output: write failed: closed"),
        ("$L match --bold MIT", 0, ""),
    ],
    ids=["stdin-closed", "stdout-closed", "is-osi-stdout-closed", "control"],
)
def test_a_closed_stream(
    tmp_path: Path, script: str, exit_code: int, stderr: str
) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    licenseid = f'"{sys.executable}" -m licenseid.cli --db "{db_path}"'
    result = subprocess.run(
        ["/bin/sh", "-c", script.replace("$L", licenseid)],
        capture_output=True,
        text=True,
        env=_environ(tmp_path),
        check=False,
    )
    assert result.returncode == exit_code
    assert result.stderr.startswith(stderr) and "Traceback" not in result.stderr


def test_a_reader_that_leaves_ends_the_run_quietly(tmp_path: Path) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-m", "licenseid.cli", "--db", str(db_path), "is-osi", "MIT"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_environ(tmp_path),
    ) as proc:
        assert proc.stdout is not None and proc.stderr is not None
        proc.stdout.close()  # long before the child writes its answer
        assert (proc.wait(timeout=30), proc.stderr.read()) == (141, b"")


def test_ctrl_c_exits_130(tmp_path: Path) -> None:
    """The run waits on standard input, which is never closed."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with subprocess.Popen(
        [sys.executable, "-m", "licenseid.cli", "--db", str(db_path), "match"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_environ(tmp_path),
    ) as proc:
        time.sleep(3)  # past the imports, into the read
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=30)
    assert (proc.returncode, out, err) == (130, b"", b"")
