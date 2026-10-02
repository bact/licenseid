# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""click's usage errors, worded as every other licenseid diagnostic.

click prints a usage error in three parts of its own (``Usage: …``,
``Try '… --help' for help.``, ``Error: …``); licenseid prints one line,
``ERROR: SUBJECT: CONDITION[: DETAIL][; ACTION]``. click raises these errors
while it parses (``Command.parse_args``) and while it finds the command
(``Group.resolve_command``), so ``UsageLineCommand`` and ``UsageLineGroup``
re-raise them there as ``UsageLineError``. Its ``show()`` writes through
``licenseid.console``, both in click's standalone mode (what the tests'
``CliRunner`` runs) and in ``cli.main()``.
"""

import re
from collections.abc import Sequence
from typing import IO, Any

import click

from licenseid.console import error
from licenseid.errors import one_line

# The one usage error click words only in English: Command.parse_args's
# ctx.fail for arguments left over.
_EXTRA_ARGUMENTS = re.compile(r"Got unexpected extra arguments? \((.*)\)", re.DOTALL)


def _sentence(message: str) -> str:
    """click's sentence as a DETAIL: no full stop, a lowercase start, and
    one line."""
    text = one_line(message.strip().removesuffix("."))
    return text[:1].lower() + text[1:]


def _action(ctx: click.Context | None, possibilities: Sequence[str] | None) -> str:
    """What to do next: click's suggestions if it has any, else the help."""
    if possibilities:
        return "did you mean " + " or ".join(one_line(p) for p in possibilities)
    path = ctx.command_path if ctx is not None else "licenseid"
    return f"run '{path} --help'"


def _option_name(param: click.Parameter) -> str:
    """The name a user would type: an option's longest spelling."""
    return max(param.opts, key=len) if param.opts else str(param.name)


def _bad_parameter(exc: click.BadParameter, ctx: click.Context | None) -> str:
    """A value click could not read, or a parameter given none."""
    param = exc.param
    missing = isinstance(exc, click.MissingParameter)
    if param is None or isinstance(param, click.Argument):
        if missing:
            return f"input: missing; {_action(ctx, None)}"
        return f"input: invalid: {_sentence(exc.message)}"
    name = one_line(_option_name(param))
    if missing:
        return f"option: missing: {name}; pass a value"
    return f"option: invalid: {name}: {_sentence(exc.message)}"


def _not_found(
    exc: click.NoSuchOption | click.NoSuchCommand, ctx: click.Context | None
) -> str:
    """An option or a command click does not know."""
    if isinstance(exc, click.NoSuchOption):
        thing, name = "option", exc.option_name
    else:
        thing, name = "command", exc.command_name
    return f"{thing}: not found: {one_line(name)}; {_action(ctx, exc.possibilities)}"


def _bad_option_usage(exc: click.BadOptionUsage) -> str:
    """An option given no value, or one it does not take."""
    name = one_line(exc.option_name)
    if "requires" in exc.message:  # "requires an argument", "… 2 arguments"
        return f"option: missing: {name}; pass a value"
    detail = exc.message.replace(f"Option {exc.option_name!r} ", "", 1)
    return f"option: invalid: {name}: {_sentence(detail)}"


def _other(exc: click.ClickException, ctx: click.Context | None) -> str:
    """Arguments left over, or an error with no attributes to read."""
    if extra := _EXTRA_ARGUMENTS.fullmatch(exc.message.strip()):
        return (
            f"input: invalid: extra argument: {one_line(extra.group(1))};"
            f" {_action(ctx, None)}"
        )
    return f"usage: invalid: {_sentence(exc.format_message())}; {_action(ctx, None)}"


def usage_line(exc: click.ClickException) -> str:
    """*exc*'s message in licenseid's grammar, without the ``ERROR: ``."""
    if isinstance(exc, UsageLineError):
        return exc.message
    ctx: click.Context | None = getattr(exc, "ctx", None)
    if isinstance(exc, (click.NoSuchOption, click.NoSuchCommand)):
        return _not_found(exc, ctx)
    if isinstance(exc, click.BadOptionUsage):
        return _bad_option_usage(exc)
    if isinstance(exc, click.BadParameter):
        return _bad_parameter(exc, ctx)
    return _other(exc, ctx)


class UsageLineError(click.UsageError):
    """A click error, its message in licenseid's grammar. Its exit code is a
    usage error's, 2; ``cli.main()`` keeps the code of the error it wraps."""

    def __init__(self, exc: click.ClickException) -> None:
        super().__init__(usage_line(exc), getattr(exc, "ctx", None))

    def show(self, file: IO[Any] | None = None) -> None:
        """Print ``ERROR: <message>`` on standard error, through the console
        (which survives a failing stream), wherever *file* points."""
        del file
        error(self.message)


class UsageLineCommand(click.Command):
    """A command whose usage errors are worded as licenseid's."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except UsageLineError:
            raise
        except click.UsageError as exc:
            raise UsageLineError(exc) from exc


class UsageLineGroup(UsageLineCommand, click.Group):
    """A group whose usage errors, an unknown command included, are worded
    as licenseid's."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except UsageLineError:
            raise
        except click.UsageError as exc:
            raise UsageLineError(exc) from exc
