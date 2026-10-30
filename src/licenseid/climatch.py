# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid match VALUE``: one declared licence value, read by
:func:`licenseid.match`.

``detect`` answers "which licence is in this file or text"; ``match``
answers "which SPDX expression does this declared value stand for". So
``match`` takes one value on the command line and refuses what only
``detect`` answers, with exit 2 and ``; run 'licenseid detect'``: ``--text``,
standard input, a value with a line break and one longer than the resolver
reads, before any list is read; and, once read, a value that resolves to
nothing and names a file or directory here. Such a value would otherwise
come back ``unresolved``, exit 1, which says "no licence" where the user
meant "detect this".

It needs no database: with no ``--db`` it reads the list ``--source`` names,
as ``match()`` does (``auto`` falls back to the list shipped in the wheel).
Exit 0 when the value resolves to an expression, 1 when it does not (a list
joined by ``;`` included), 2 for a usage error, a list that cannot be read
(``DatabaseNotReadyError``, through the group) or a result that cannot be
written (``output.echo``).
"""

import os
import sys
from typing import get_args

import click

from licenseid.clicommon import (
    LicenseIdCommand,
    exit_bad_input,
    exit_usage_error,
    piped_input,
    reject_blank_options,
    reject_unencodable,
)
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import check_database_ready
from licenseid.errors import one_line
from licenseid.output import echo
from licenseid.resolver import MAX_EXPRESSION_CHARS, match, read_length
from licenseid.resolvertypes import Resolution, Source
from licenseid.result import json_line, resolution_lines

#: The ACTION of every refusal: the value is for ``detect``.
TO_DETECT = "; run 'licenseid detect'"


def _has_line_break(value: str) -> bool:
    """Whether *value* breaks a line where Python's ``str.splitlines`` does
    (``\\n``, ``\\r``, ``\\v``, ``\\f``, ``\\x1c`` to ``\\x1e``, ``\\x85``,
    U+2028, U+2029), at its end included."""
    return value.splitlines() != [value]


def _piped_something() -> bool:
    """Whether standard input brings anything: one byte is read to tell
    (``</dev/null`` and cron bring nothing: no value, not one for detect)."""
    if not piped_input():
        return False
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        return bool(stream.read(1))
    except (OSError, ValueError):  # unreadable or closed: nothing brought
        return False


def declared_value(ctx: click.Context, value: str | None, text: str | None) -> str:
    """The one value to match: the argument, checked. Exit 2 for no value,
    a blank one, one the command line could not encode (a lone surrogate),
    and for what only ``detect`` answers."""
    if text is not None:
        exit_usage_error(ctx, f"option: invalid: --text: a licence text{TO_DETECT}")
    if value is None:
        if _piped_something():
            exit_bad_input(ctx, f"invalid: standard input{TO_DETECT}")
        exit_bad_input(ctx, "missing; pass one declared licence value")
    reject_blank_options(ctx, {"argument": value})
    reject_unencodable(ctx, value)
    if _has_line_break(value):
        exit_bad_input(ctx, f"invalid: line break: {one_line(value)}{TO_DETECT}")
    # Counted as match() counts it (read_length), so it reads what this
    # passes; the first test is the fast one.
    if len(value) > MAX_EXPRESSION_CHARS and read_length(value) > MAX_EXPRESSION_CHARS:
        exit_bad_input(
            ctx, f"invalid: over {MAX_EXPRESSION_CHARS} characters{TO_DETECT}"
        )
    return value


def reject_a_path(ctx: click.Context, value: str, resolution: Resolution) -> None:
    """Exit 2 if *value* resolved to nothing and names a path that exists
    here (os.path.exists, the test detect makes before it reads a file): a
    file or a directory to detect, not a value. A value that resolves is
    answered whatever is here (``MIT``, ``mit`` beside a file ``MIT``)."""
    if resolution["expression"] is None and os.path.exists(value):
        exit_bad_input(ctx, f"invalid: path: {one_line(value)}{TO_DETECT}")


def given_database(ctx: click.Context, source: Source) -> LicenseDatabase | None:
    """The database ``--db`` names, opened as ``match(value, db)`` reads it,
    or None when it names none (the list ``--source`` names is read). An
    unready one raises ``DatabaseNotReadyError``, which the group words."""
    if ctx.obj["db_is_default"]:
        return None
    if source == "packaged":
        exit_usage_error(
            ctx,
            "option: invalid: --source: packaged with --db; pass --db or --source",
        )
    db_path = ctx.obj["db_path"]
    check_database_ready(db_path)
    return LicenseDatabase(db_path, create=False)


@click.command(name="match", cls=LicenseIdCommand)
@click.argument("value", required=False)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Print the whole resolution as one RFC 8785 JSON object.",
)
@click.option(
    "--source",
    type=click.Choice(get_args(Source)),
    default="auto",
    show_default=True,
    help="The SPDX License List to read when --db names no database: the "
    "database at the default path (database), the list shipped with "
    "licenseid (packaged), or the newer of the two (auto).",
)
@click.option(
    "--text",
    hidden=True,
    help="Refused: a licence text is for 'licenseid detect'.",
)
@click.pass_context
def match_command(
    ctx: click.Context,
    value: str | None,
    json_output: bool,
    source: Source,
    text: str | None,
) -> None:
    """Match one declared licence value to an SPDX expression.

    VALUE is what a package declares, such as a license field or a trove
    classifier. Exit 0 when it resolves, 1 when it does not.
    """
    declared = declared_value(ctx, value, text)
    resolution = match(declared, given_database(ctx, source), source=source)
    reject_a_path(ctx, declared, resolution)
    if json_output:
        echo(json_line(resolution))
    else:
        for line in resolution_lines(resolution):
            echo(line)
    ctx.exit(0 if resolution["expression"] is not None else 1)
