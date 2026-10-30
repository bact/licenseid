# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Command-line interface for the licenseid tool.
"""

import sqlite3
import sys
from typing import Any

import click

from licenseid import __version__
from licenseid.clicommon import LicenseIdCommand, exit_usage_error
from licenseid.clidetect import PREDICATE_COMMANDS, detect_command
from licenseid.climatch import match_command
from licenseid.cliupdate import clear_cache_command, update_command
from licenseid.console import end_line, write
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import unreadable_error
from licenseid.errors import DatabaseNotReadyError
from licenseid.output import EchoHelpCommand, OutputError, echo, output_failed
from licenseid.usage import UsageLineError, UsageLineGroup


class DatabaseErrorGroup(UsageLineGroup, EchoHelpCommand):
    """A group that never lets a failure pass for an answer.

    ``detect`` and the ``is-*`` commands answer "no" with exit 1, so an unready
    database (``DatabaseNotReadyError``) must not share it. A file can also go
    bad after the readiness check (replaced or corrupted mid-run): a SQLite
    failure is then worded as an ``unreadable`` database, not a traceback.
    The detector words its own the same way (``DatabaseNotReadyError``), and
    that includes a ProgrammingError or InterfaceError: the original stays
    the ``__cause__`` for whoever debugs it.

    Click itself would exit 1 for both an interrupt (Ctrl-C) and a closed
    pipe. An interrupt exits 130 (128 + SIGINT), as the shell reports a
    killed command; a pipe whose reader has gone (``| head -1``) exits 141
    (128 + SIGPIPE) quietly, as ``cat`` and ``grep`` do; any other output
    that cannot be written exits 2 with an ``output`` error.
    """

    command_class = LicenseIdCommand

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except KeyboardInterrupt as exc:
            end_line()
            raise click.exceptions.Exit(130) from exc
        except OutputError as exc:
            raise click.exceptions.Exit(output_failed(exc)) from exc
        except DatabaseNotReadyError as exc:
            exit_usage_error(ctx, str(exc))
        except sqlite3.Error as exc:
            exit_usage_error(ctx, str(unreadable_error(ctx.obj["db_path"], exc)))


class _WithoutDatabase(dict[str, Any]):
    """The context of a run with no default database to name (no home
    directory): help and a bare run need none, so the error waits for the first
    command that reads ``db_path``."""

    def __init__(self, cause: DatabaseNotReadyError, items: dict[str, Any]) -> None:
        super().__init__(items)
        self.cause = cause

    def __missing__(self, key: str) -> Any:
        raise self.cause


def show_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """``--version``: ``licenseid <version>`` on standard output, before the
    group's own options are read, so no database path is looked up."""
    if value and not ctx.resilient_parsing:
        echo(f"licenseid {__version__}")
        ctx.exit()


@click.group(cls=DatabaseErrorGroup, invoke_without_command=True)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=show_version,
    help="Print the version and exit.",
)
@click.option("--db", help="Path to the license database.")
@click.pass_context
def cli(ctx: click.Context, db: str | None) -> None:
    """SPDX License ID matcher tool."""
    if db is not None and not db.strip():
        # Silently falling back to the default database would answer from a
        # file the user did not ask for. Every other blank option is a usage
        # error too (see reject_blank_options).
        exit_usage_error(ctx, "database: missing: --db; pass a path or drop --db")
    ctx.ensure_object(dict)
    ctx.obj["db_is_default"] = not db
    try:
        ctx.obj["db_path"] = db or get_default_db_path()
    except DatabaseNotReadyError as exc:
        ctx.obj = _WithoutDatabase(exc, ctx.obj)

    if ctx.invoked_subcommand is None:
        # A usage error, not a result: the help goes to standard error.
        write(ctx.get_help() + "\n")
        ctx.exit(2)


for _command in (detect_command, match_command, *PREDICATE_COMMANDS):
    cli.add_command(_command)
cli.add_command(update_command)
cli.add_command(clear_cache_command)


def main() -> None:
    """Main entry point for the CLI.

    Click's own handling (standalone mode) would exit 1 on Ctrl-C, the code
    for "no", and print a ClickException with no regard for a failing
    standard error, which then turned the exit status into 120 at the flush
    on exit.
    """
    try:
        status = cli.main(standalone_mode=False)
    except click.exceptions.Abort:  # Ctrl-C before a command runs
        end_line()
        status = 130
    except click.ClickException as exc:  # a usage error, through the console
        UsageLineError(exc).show()
        status = exc.exit_code
    except OutputError as exc:  # `licenseid --help`, before any command runs
        status = output_failed(exc)
    sys.exit(status if isinstance(status, int) else 0)


if __name__ == "__main__":
    main()
