# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The CLI's results and help on standard output, and what a failed write
means: a result that was not delivered must not pass for an answer."""

import contextlib
import io
import sys

import click

from licenseid.console import discard_stdout, error


class OutputError(Exception):
    """Standard output could not take a result line."""

    def __init__(self, cause: OSError | UnicodeError | None) -> None:
        if cause is None:
            detail = "closed"
        else:
            detail = getattr(cause, "strerror", None) or str(cause)
            detail = detail or type(cause).__name__
        super().__init__(detail)
        self.broken_pipe = isinstance(cause, BrokenPipeError)


def echo(message: str = "") -> None:
    """Write *message* and a newline to standard output.

    Raises OutputError when it cannot be written: click.echo drops output
    silently when standard output is closed (``>&-``), and raises a bare
    OSError for a full disk, a size limit or a closed pipe.
    """
    if sys.stdout is None:
        raise OutputError(None)
    try:
        click.echo(message)
    except (OSError, UnicodeEncodeError) as exc:
        raise OutputError(exc) from exc


def escape_unencodable_output() -> None:
    """Write a character standard output cannot encode as a backslash escape,
    as standard error already does, instead of failing the command.

    On Windows a pipe or file takes the ANSI code page, which has no room for
    most scripts (a Japanese word of the input in ``--diff``, an accented
    user name in a path), and Python would raise after the result was
    written, with exit 1: the code for "no".
    """
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        with contextlib.suppress(OSError, ValueError):
            stream.reconfigure(errors="backslashreplace")


def output_failed(exc: OutputError) -> int:
    """Report *exc* and return the exit status: 141 (128 + SIGPIPE), quietly
    as ``cat`` and ``grep`` do, when the reader closed the pipe; else 2."""
    discard_stdout()
    if exc.broken_pipe:
        return 141
    error(f"output: write failed: {exc}")
    return 2


def _show_help(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Click's --help callback, writing through echo."""
    if value and not ctx.resilient_parsing:
        echo(ctx.get_help())
        ctx.exit()


class EchoHelpCommand(click.Command):
    """A command whose --help is written through echo, so a help text that
    cannot be written fails as a result does."""

    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        option = super().get_help_option(ctx)
        if option is not None:
            option.callback = _show_help
        return option
