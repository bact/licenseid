# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The CLI's results and help on standard output, and what a failed write
means: a result that was not delivered must not pass for an answer."""

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
    """Write *message* and a newline to standard output, in the stream's
    encoding; a character it cannot encode is written as a backslash escape
    (``\\xHH``, ``\\uHHHH``, ``\\UHHHHHHHH``), as standard error writes it,
    and as ``result.read_text_field`` reads it back. A result line escapes
    every backslash of its values, so the escape cannot be mistaken.

    Raises OutputError when it cannot be written: click.echo drops output
    silently when standard output is closed (``>&-``), and raises a bare
    OSError for a full disk, a size limit or a closed pipe.
    """
    stream = sys.stdout
    if stream is None:
        raise OutputError(None)
    try:
        click.echo(_encodable(message, getattr(stream, "encoding", None)))
    except (OSError, UnicodeEncodeError) as exc:
        raise OutputError(exc) from exc
    except ValueError as exc:  # a closed stream
        raise OutputError(None) from exc


def echo_json(line: str) -> None:
    """Write one JSON line (``result.json_line``) and a newline to standard
    output as UTF-8 bytes, whatever the stream's encoding: RFC 8785 is
    UTF-8, so the same result is the same bytes on every locale. A stream
    with no bytes underneath (replaced by a text-only one) gets the text."""
    stream = sys.stdout
    if stream is None:
        raise OutputError(None)
    if getattr(stream, "buffer", None) is None:
        echo(line)
        return
    try:
        click.echo(line.encode("utf-8"))  # click writes bytes to the buffer
    except OSError as exc:
        raise OutputError(exc) from exc
    except ValueError as exc:  # a closed stream
        raise OutputError(None) from exc


def _encodable(message: str, encoding: str | None) -> str:
    """*message* with what *encoding* cannot encode as backslash escapes.
    The stream's own error handler is not asked: one rule on every locale
    (on Windows a pipe or file takes the ANSI code page, which has no room
    for most scripts, and Python raised after the result was written, with
    exit 1: the code for "no")."""
    try:
        return message.encode(encoding or "utf-8", "backslashreplace").decode(
            encoding or "utf-8"
        )
    except LookupError:  # an encoding Python does not know: leave it to it
        return message


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
