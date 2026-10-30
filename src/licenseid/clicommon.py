# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What the CLI's commands share: their command class, the exit for a usage
error, and the checks of a value given on the command line.

``cli`` holds the group and the commands that read the database;
``climatch`` the ``match`` command. Both import from here, so neither
imports the other's module back.
"""

import sys
from typing import NoReturn

import click

from licenseid.console import error
from licenseid.errors import InvalidInputError
from licenseid.output import EchoHelpCommand
from licenseid.textinput import reject_binary, reject_lone_surrogate
from licenseid.usage import UsageLineCommand


class LicenseIdCommand(UsageLineCommand, EchoHelpCommand):
    """A command whose help and usage errors follow the stream and message
    rules (``output.EchoHelpCommand``, ``usage.UsageLineCommand``)."""


def exit_usage_error(ctx: click.Context, message: str) -> NoReturn:
    """Print *message* as an ERROR line and exit with a usage error (2)."""
    error(message)
    ctx.exit(2)


def exit_bad_input(ctx: click.Context, condition: str) -> NoReturn:
    """Exit with a usage error (2) for unusable input."""
    exit_usage_error(ctx, f"input: {condition}")


def reject_blank_options(ctx: click.Context, values: dict[str, str | None]) -> None:
    """Exit with a usage error (2) if an input given on the command line has
    no text, rather than skip it for the next input or match it as text."""
    for name, value in values.items():
        if value is not None and not value.strip():
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
