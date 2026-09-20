# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Assertions shared by the database readiness tests: what a refusal looks
like on the command line (exit 2, empty stdout, one grammar line)."""
# pylint: disable=missing-function-docstring

from click.testing import CliRunner, Result
from db_variants import EMPTY, INVALID, NOT_FOUND, UNREADABLE

from licenseid.cli import cli


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
                f"ERROR: database: unreadable: {db_arg}: ",
            )
        ), result.stderr
