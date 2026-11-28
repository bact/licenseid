# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Assertions shared by the database readiness tests: what a refusal looks
like on the command line (exit 2, empty stdout, one grammar line)."""
# pylint: disable=missing-function-docstring

import os
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from db_variants import EMPTY, INVALID, NOT_FOUND, UNREADABLE, make_ready_file_db

from licenseid import keptdetector
from licenseid.cli import cli
from licenseid.dbconnection import Connections


def run_cli(db_arg: str, args: list[str], stdin: str = "") -> Result:
    """Invoke the CLI. ``--db=`` keeps a path starting with "-" a value."""
    return CliRunner().invoke(cli, [f"--db={db_arg}", *args], input=stdin)


def expected_refusal(kind: str, db_arg: str) -> str:
    if kind == NOT_FOUND:
        return f"ERROR: database: not found: {db_arg}; run 'licenseid update'\n"
    if kind == INVALID:
        return f"ERROR: database: invalid: {db_arg}\n"
    assert kind == EMPTY, f"{kind} has no fixed message"
    return f"ERROR: database: empty: {db_arg}; run 'licenseid update'\n"


def assert_one_diagnostic_line(stderr: str) -> None:
    assert stderr.endswith("\n"), f"not newline-terminated: {stderr!r}"
    assert stderr.count("\n") == 1, f"expected exactly one line: {stderr!r}"
    line = stderr[:-1]
    assert not line.startswith("Traceback"), stderr
    assert line == line.strip(), f"padded diagnostic line: {stderr!r}"


def assert_no_traceback(result: Result) -> None:
    exception = result.exception
    assert exception is None or isinstance(exception, SystemExit), (
        f"unhandled {type(exception).__name__}: {exception}"
    )


def assert_refused(result: Result, kind: str, db_arg: str) -> None:
    """Exit 2, empty stdout, exactly one contract-shaped stderr line."""
    assert_no_traceback(result)
    assert result.stdout == "", f"stdout not empty: {result.stdout!r}"
    assert result.exit_code == 2, f"exit {result.exit_code}, stderr {result.stderr!r}"
    assert_one_diagnostic_line(result.stderr)
    if kind in (NOT_FOUND, EMPTY, INVALID):
        assert result.stderr == expected_refusal(kind, db_arg)
    elif kind == UNREADABLE:
        # The SQLite error text varies by version, so only the head is pinned.
        assert result.stderr.startswith(f"ERROR: database: unreadable: {db_arg}: ")
    else:
        assert result.stderr.startswith(
            (
                f"ERROR: database: not found: {db_arg};",
                f"ERROR: database: empty: {db_arg};",
                f"ERROR: database: invalid: {db_arg}\n",
                f"ERROR: database: unreadable: {db_arg}: ",
            )
        ), result.stderr


def refuse_unlink(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Make deleting *target* fail with "Permission denied" on every OS
    (chmod does not stop a delete on Windows); any other file goes."""
    real_unlink = Path.unlink

    def refusing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refusing_unlink)


def run_args(*args: str, stdin: str = "") -> Result:
    """Invoke the CLI with the arguments exactly as given."""
    return CliRunner().invoke(cli, list(args), input=stdin)


@pytest.fixture(autouse=True)
def safe_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let anything resolve the developer's real cache."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() on Windows
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    keptdetector.reset()  # one kept for another home is not this one's


def db_in_an_unreadable_directory(tmp_path: Path) -> Path:
    """A ready database whose parent directory cannot be searched, or skip
    where the user can read through one anyway (root)."""
    if sys.platform == "win32":
        pytest.skip("chmod 000 does not hide a directory on Windows")
    inner = tmp_path / "inner"
    inner.mkdir()
    db_path = make_ready_file_db(inner / "licenses.db")
    inner.chmod(0o000)
    if os.access(str(db_path), os.R_OK):
        inner.chmod(0o755)
        pytest.skip("this user can read through a 000 directory (root?)")
    return db_path


_FIFO_PROBE = """
import sys
from licenseid.dbconnection import Connections
try:
    Connections(sys.argv[1], sys.argv[1].startswith("file:"), create=False).connect()
except Exception as exc:
    print(type(exc).__name__, exc)
"""


_CHECK_PROBE = """
import sys
from licenseid.dbcheck import check_database_ready
try:
    check_database_ready(sys.argv[1])
except Exception as exc:
    print(type(exc).__name__, exc)
"""


def probe_does_not_hang(path: Path | str) -> str:
    """Open *path* in a child process: a guard that broke would hang it, and
    not the suite."""
    return _run_probe(_FIFO_PROBE, path)


_READ_PROBE = """
import sys
from licenseid.textinput import read_text_file
try:
    read_text_file(sys.argv[1])
except Exception as exc:
    print(type(exc).__name__, exc)
"""


def probe_read_does_not_hang(path: Path | str) -> str:
    """``read_text_file(path)`` in a child process: opening a named pipe would
    hang it, and not the suite."""
    return _run_probe(_READ_PROBE, path)


def probe_check_does_not_hang(path: Path | str) -> str:
    """``check_database_ready(path)`` in a child process, for the same reason;
    returns ``<exception type> <message>``, or nothing if it raised nothing."""
    return _run_probe(_CHECK_PROBE, path)


def _run_probe(script: str, path: Path | str) -> str:
    try:
        done = subprocess.run(
            [sys.executable, "-c", script, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"opening {path} hung")
    return done.stdout


# Probes for a file cut under an open connection. Each prints READY, waits for
# a line on standard input (the file is cut meanwhile), then queries again and
# prints "answered" or the error's type and message.
HOLD_PROBE = """
import sys
from licenseid import LicenseDetector
TEXT = "Permission is hereby granted, free of charge, to any person obtaining a copy"
matcher = LicenseDetector(db_path=sys.argv[1])
with matcher.db.reading():
    matcher.detect(TEXT)
    print("READY", flush=True)
    sys.stdin.readline()
    try:
        matcher.detect(TEXT)
        print("answered")
    except Exception as exc:
        print(type(exc).__name__, exc)
"""

# A half-read cursor, in a ``reading()`` block or not (IN_BLOCK is replaced).
SCAN_PROBE = """
import contextlib, sys
from licenseid.database import LicenseDatabase
db = LicenseDatabase(sys.argv[1], create=False)
block = db.reading() if IN_BLOCK else contextlib.nullcontext()
try:
    with block, db._connection() as conn:
        cur = conn.execute("SELECT value FROM db_metadata WHERE key LIKE 'pad%'")
        cur.fetchmany(5)
        print("READY", flush=True)
        sys.stdin.readline()
        print(len(cur.fetchall()))
except Exception as exc:
    print(type(exc).__name__, exc)
"""


def run_after_cut(
    script: str, path: Path, cut: Callable[[Path], None]
) -> tuple[int, str, str]:
    """Run *script* on *path* in a child, call *cut(path)* once it prints
    READY, let it go on; return ``(return code, stdout, stderr)``. A child that
    hangs is killed after 30 s (the return code then shows it)."""
    with subprocess.Popen(
        [sys.executable, "-c", script, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as child:
        assert child.stdout is not None and child.stdin is not None
        watchdog = threading.Timer(30, child.kill)
        watchdog.start()
        try:
            ready = child.stdout.readline().strip()
            if ready == "READY":
                cut(path)
                child.stdin.write("go\n")
                child.stdin.flush()
            out, err = child.communicate()
        finally:
            watchdog.cancel()
    assert ready == "READY", (ready, err)
    return child.returncode, out, err


def traced_statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every SQL statement licenseid runs from here on in the test: each
    connection it opens is traced. Never in a test that uses the ``opened``
    fixture: *monkeypatch* ends after it and would put its patch back."""
    statements: list[str] = []
    real = Connections.connect

    def traced(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(Connections, "connect", traced)
    return statements
