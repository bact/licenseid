# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The input of ``detect`` and the ``is-*`` commands: one of a file, a
value, ``--text``, ``--id`` or standard input (``-``, or no argument and a
pipe).

Two inputs are a usage error (exit 2), not a choice of one: the input that
lost was ignored without a word before (C7 of the contract batch). ``--text``
is taken as written: a backslash is a backslash (C6).
"""

import os
import sys
from datetime import datetime, timezone
from typing import NoReturn

import click

from licenseid.clicommon import (
    exit_bad_input,
    exit_usage_error,
    piped_input,
    reject_blank_options,
    reject_unencodable,
)
from licenseid.console import warn
from licenseid.database import LicenseDatabase
from licenseid.errors import InvalidInputError, invalid_id_error, one_line, shown
from licenseid.exprtokens import is_license_ref
from licenseid.identifiers import is_simple_expression
from licenseid.textinput import (
    decode_input,
    looks_like_path,
    normalize_newlines,
    read_text_file,
)

#: The argument that names standard input, as ``cat -`` reads it (C5).
STDIN_ARGUMENT = "-"


def reject_two_inputs(
    ctx: click.Context, input_val: str | None, text: str | None, id_val: str | None
) -> None:
    """Exit 2 when more than one input is given: ``--text`` or ``--id`` with
    an argument (a file, a value or ``-``), or ``--id`` with ``--text``. A
    piped standard input beside one is not refused: a script's standard
    input is seldom a terminal."""
    given = [
        name
        for name, value in (("--id", id_val), ("--text", text))
        if value is not None
    ]
    if input_val is not None:
        given.append("an argument")
    if len(given) > 1:
        exit_usage_error(
            ctx, f"option: invalid: {given[0]}: with {given[1]}; pass one input"
        )


def check_db_staleness(database: LicenseDatabase) -> None:
    """Check if the database is older than 6 months and warn the user."""
    metadata = database.get_metadata()
    last_check = metadata.get("last_check_datetime")
    if last_check:
        try:
            last_check_dt = datetime.fromisoformat(last_check)
            if last_check_dt.tzinfo is None:
                # Databases written before this timestamp became
                # tz-aware stored a naive local-time value; treat it as
                # UTC rather than crashing on the subtraction below (this
                # is only a rough 6-month staleness check, not something
                # that needs to account for the original local offset).
                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - last_check_dt).days
            if days_old > 182:  # Approx 6 months
                warn(f"database: {days_old} days old; run 'licenseid update'")
        except (TypeError, ValueError):
            pass


def exit_no_input(ctx: click.Context) -> NoReturn:
    """Exit with a usage error (2) because no input was given."""
    exit_bad_input(ctx, "missing; pass a file, an ID, --text, --id or stdin")


def read_input(ctx: click.Context, path: str | None) -> str:
    """Read the file at *path*, or standard input if None, as text.
    Exit with a usage error (2) if it cannot be read, is binary, or is a file
    with no text (empty stdin is left to the caller's "input: missing")."""
    source = path if path is not None else "stdin"
    piped_nothing = False
    try:
        if path is not None:
            text = read_text_file(path)
        else:
            if (buffer := getattr(sys.stdin, "buffer", None)) is not None:
                data = buffer.read()
            else:  # stdin replaced by a text-only stream
                data = sys.stdin.read().encode("utf-8", "surrogatepass")
            piped_nothing = not data
            text = decode_input(data, source)
    except OSError as e:
        exit_bad_input(ctx, f"unreadable: {shown(source)}: {e.strerror or e}")
    except InvalidInputError as e:  # binary data; already "input: ..."
        exit_usage_error(ctx, str(e))
    # No bytes at all on stdin means nothing was piped: "input: missing".
    if not piped_nothing and not text.strip():
        exit_bad_input(ctx, f"empty: {shown(source)}")
    return text


def reject_compound_id(ctx: click.Context, id_val: str | None) -> None:
    """Exit with a usage error (2) if --id does not name one license.

    --id is a declaration: "MIT OR Apache-2.0" declares neither license, and
    a name or an SPDX URL is not an ID. A file's tag may still hold any of
    them, so the reading of a file is unaffected.
    """
    if id_val and not is_simple_expression(id_val):
        exit_usage_error(ctx, str(invalid_id_error("--id", id_val)))


def read_text_option(ctx: click.Context, text: str) -> str:
    """--text as written, treated as file or stdin text is treated: LF line
    ends; exit 2 if binary (a NUL), blank or not encodable. A backslash is a
    backslash: ``\\n`` is two characters, not a line break (C6)."""
    content = normalize_newlines(text)
    reject_unencodable(ctx, content, binary_source="--text")
    if not content.strip():
        exit_bad_input(ctx, "empty: --text")
    return content


def names_licences(db: LicenseDatabase, value: str) -> bool:
    """Whether every part of a "/"-joined *value* is a licence ID or a
    ``LicenseRef-*`` ("MIT/Apache-2.0", Cargo's old way to write OR): a
    declared value, not a path, whatever its shape."""
    return all(
        is_license_ref(part) or db.get_license_details(part)
        for part in value.split("/")
    )


def get_input_content(
    ctx: click.Context, input_val: str | None, text: str | None, db: LicenseDatabase
) -> str:
    """The input to match: --text, else the argument (``-`` for standard
    input; a file if one exists by that name; a usage error if it is shaped
    like a path and names no licence; else the value itself), else stdin;
    "" if there is none."""
    if text is not None:
        return read_text_option(ctx, text)
    if input_val == STDIN_ARGUMENT:
        return read_input(ctx, None)  # even from a terminal, as cat - does
    if input_val:
        if os.path.exists(input_val):
            return read_input(ctx, input_val)
        reject_unencodable(ctx, input_val)
        if looks_like_path(input_val) and not names_licences(db, input_val):
            # a mistyped path is no text to match
            exit_bad_input(ctx, f"not found: {one_line(input_val)}; pass --text")
        return input_val
    if piped_input():  # a closed one is no input, not a crash
        return read_input(ctx, None)
    return ""


def checked_inputs(
    ctx: click.Context, input_val: str | None, text: str | None, id_val: str | None
) -> None:
    """The checks of the inputs a command makes before it reads one: no
    blank option, one input at most, an ``--id`` that names one licence."""
    reject_blank_options(ctx, {"--id": id_val, "--text": text, "argument": input_val})
    reject_two_inputs(ctx, input_val, text, id_val)
    reject_compound_id(ctx, id_val)
