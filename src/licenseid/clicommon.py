# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the CLI's commands share: their command class, the exit for a usage
error, the checks of a value given on the command line, the writer of a
one-record result, and the printer of the library's warnings.

``cli`` holds the group and the commands that read the database;
``climatch`` the ``match`` command. Both import from here, so neither
imports the other's module back.
"""

import contextlib
import sys
import warnings
from collections.abc import Iterator
from typing import NoReturn, TextIO

import click

from licenseid.console import error, warn
from licenseid.errors import InvalidInputError
from licenseid.exprtokens import WHITE_SPACE
from licenseid.output import EchoHelpCommand, echo, echo_json
from licenseid.result import FieldValue, fields_line, record_json
from licenseid.textinput import reject_binary, reject_lone_surrogate
from licenseid.usage import UsageLineCommand
from licenseid.warning import LicenseIdWarning


class LicenseIdCommand(UsageLineCommand, EchoHelpCommand):
    """A command whose help and usage errors follow the stream and message
    rules (``output.EchoHelpCommand``, ``usage.UsageLineCommand``)."""


# The --json flag of every command that prints a result.
json_option = click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Print the result as RFC 8785 JSON, one object per line.",
)


def echo_record(json_output: bool, **values: FieldValue) -> None:
    """Print one result record: ``KEY=VALUE`` fields (``result.fields_line``)
    or, with *json_output*, the same record as one JSON object with the keys
    in lower case (``result.record_json``)."""
    if json_output:
        echo_json(record_json(**values))
    else:
        echo(fields_line(**values))


def exit_usage_error(ctx: click.Context, message: str) -> NoReturn:
    """Print *message* as an ERROR line and exit with a usage error (2)."""
    error(message)
    ctx.exit(2)


def exit_bad_input(ctx: click.Context, condition: str) -> NoReturn:
    """Exit with a usage error (2) for unusable input."""
    exit_usage_error(ctx, f"input: {condition}")


def reject_blank_options(ctx: click.Context, values: dict[str, str | None]) -> None:
    """Exit with a usage error (2) if an input given on the command line has
    no text, rather than skip it for the next input or match it as text.
    White space is :data:`licenseid.exprtokens.WHITE_SPACE`, as ``match()``
    reads it: U+001C to U+001F, which ``str.strip`` takes, are control
    characters, a text the command reads (and refuses)."""
    for name, value in values.items():
        if value is not None and not value.strip(WHITE_SPACE):
            exit_bad_input(ctx, f"empty: {name}")


def reject_unencodable(
    ctx: click.Context, content: str, binary_source: str | None = None
) -> None:
    """Exit with a usage error (2) if text from the command line has a lone
    surrogate (an argument of invalid UTF-8 decodes to one) or, given
    *binary_source*, a NUL."""
    try:
        if binary_source is not None:
            reject_binary(content, binary_source)
        reject_lone_surrogate(content)
    except InvalidInputError as e:
        exit_usage_error(ctx, str(e))


def piped_input() -> bool:
    """Whether standard input brings something: not a terminal, and not
    closed (``<&-`` leaves it None)."""
    return sys.stdin is not None and not sys.stdin.isatty()


@contextlib.contextmanager
def printed_warnings() -> Iterator[None]:
    """Within the block, print each :class:`licenseid.LicenseIdWarning` as
    its ``WARNING:`` line (``console.warn``), when it is given, so it stands
    in order with the other lines on standard error. Every one is printed:
    the filter is "always", as each is an event of this run (two values, two
    lines), not a place in the code to warn about once. Any other warning
    is left to Python, as it was."""
    with warnings.catch_warnings():
        warnings.simplefilter("always", LicenseIdWarning)
        shown = warnings.showwarning

        def show(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            message: Warning | str,
            category: type[Warning],
            filename: str,
            lineno: int,
            file: TextIO | None = None,
            line: str | None = None,
        ) -> None:
            if isinstance(message, LicenseIdWarning):
                warn(str(message))
            else:
                shown(message, category, filename, lineno, file, line)

        warnings.showwarning = show
        yield
