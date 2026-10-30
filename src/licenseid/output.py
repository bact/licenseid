# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The CLI's results and help on standard output, and what a failed write
means: a result that was not delivered must not pass for an answer."""

import sys

import click

from licenseid.console import discard_stdout, emit, error


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
    """Write *message* and a line feed to standard output, in the stream's
    encoding (``console.emit``): a character it cannot encode is written as
    a backslash escape (``\\xHH``, ``\\uHHHH``, ``\\UHHHHHHHH``), as
    ``result.read_text_field`` reads it back, and the line ends in ``\\n``
    on Windows too. A result line escapes every backslash of its values, so
    the escape cannot be mistaken.

    Raises OutputError when it cannot be written: standard output closed
    (``>&-``), a full disk, a size limit or a closed pipe.
    """
    _write_line(message, None)


def echo_json(line: str) -> None:
    """Write one JSON line (``result.json_line``) and a line feed to standard
    output as UTF-8 bytes, whatever the stream's encoding: RFC 8785 is
    UTF-8, so the same result is the same bytes on every locale."""
    _write_line(line, "utf-8")


def _write_line(text: str, encoding: str | None) -> None:
    stream = sys.stdout
    if stream is None:
        raise OutputError(None)
    try:
        emit(stream, text + "\n", encoding)
    except (OSError, UnicodeError) as exc:
        raise OutputError(exc) from exc
    except ValueError as exc:  # a closed stream
        raise OutputError(None) from exc


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
