# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid update`` and ``licenseid clear-cache``: the commands that
write or delete the database.

``update --list ID[@VERSION]`` names a list by the ID ``match()`` gives it in
``lists[*].id``; with none, every list licenseid installs, at its latest
version. Each list prints one record, ``LIST``, ``VERSION``, ``STATUS`` and
``PATH``. ``clear-cache`` prints one, ``STATUS=cleared`` or ``nothing`` and
``PATH`` (C2 and C3 of the contract batch).
"""

import re
from pathlib import Path
from typing import NamedTuple, get_args

import click

from licenseid.clicommon import (
    LicenseIdCommand,
    echo_record,
    exit_usage_error,
    json_option,
)
from licenseid.console import error
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import delete_failed_error, reject_foreign_database
from licenseid.errors import InvalidInputError, LicenseIdError, one_line
from licenseid.resolvertypes import SPDX_LIST
from licenseid.types import UpdateSource

#: The lists ``update`` installs, by their ``lists[*].id`` in ``match()``.
UPDATED_LISTS = (SPDX_LIST,)
#: A release version of the SPDX License List (``3.29.0``, ``3.6``), stricter
#: than the file-name-safe check of ``spdx_source.is_valid_version``.
_RE_RELEASE = re.compile(r"[0-9]+(?:\.[0-9]+){1,2}")


class ListRequest(NamedTuple):
    """One ``--list`` value: the list, and the version asked for (None: the
    latest)."""

    list_id: str
    version: str | None


def parse_lists(ctx: click.Context, values: tuple[str, ...]) -> list[ListRequest]:
    """The ``--list`` values as requests, every list at its latest version
    when none is given. Exit 2 for an ID ``update`` does not install, a
    version that is no version, and one list named twice."""
    if not values:
        return [ListRequest(list_id, None) for list_id in UPDATED_LISTS]
    requests: list[ListRequest] = []
    for value in values:
        list_id, at, version = value.partition("@")
        if list_id not in UPDATED_LISTS or (at and not _RE_RELEASE.fullmatch(version)):
            exit_usage_error(
                ctx,
                f"option: invalid: --list: {one_line(value)}; "
                f"pass {SPDX_LIST} or {SPDX_LIST}@<version>",
            )
        if any(request.list_id == list_id for request in requests):
            exit_usage_error(
                ctx, f"option: invalid: --list: {list_id} given twice; pass it once"
            )
        requests.append(ListRequest(list_id, version if at else None))
    return requests


def make_default_db_dir(ctx: click.Context) -> None:
    """Create the directory of the default database path, if that is the one
    in use. Reading and clearing never create it; ``update`` does, because
    ``LicenseDatabase`` opens (and so creates) the file."""
    if ctx.obj["db_is_default"]:
        Path(ctx.obj["db_path"]).parent.mkdir(parents=True, exist_ok=True)


@click.command(name="update", cls=LicenseIdCommand)
@click.option(
    "--list",
    "lists",
    multiple=True,
    metavar="ID[@VERSION]",
    help=f"A list to install, as match() names it ({SPDX_LIST}), at a version "
    "(default: the latest). Repeatable; default: every list.",
)
@click.option("--force", is_flag=True, help="Force update even if version matches.")
@click.option(
    "--cache/--no-cache",
    "use_cache",
    default=True,
    help="Use local cache for downloads (default: true).",
)
@click.option(
    "--source",
    type=click.Choice(get_args(UpdateSource)),
    default="auto",
    show_default=True,
    help="Where to get the license list: compact (our 1 MB bundle), upstream "
    "(SPDX's tarball), packaged (the copy shipped with licenseid), or each in "
    "turn (auto).",
)
@json_option
@click.pass_context
def update_command(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: click.Context,
    lists: tuple[str, ...],
    force: bool,
    use_cache: bool,
    source: UpdateSource,
    json_output: bool,
) -> None:
    """Update the license database from remote sources.

    Prints one record per list: LIST, the VERSION the database now has,
    STATUS=updated or unchanged, and its PATH.
    """
    db_path = ctx.obj["db_path"]
    requests = parse_lists(ctx, lists)
    # It writes the schema on open, so never into somebody else's file. Kept
    # outside the try: an unready database is a setup error (exit 2), not an
    # update that failed (exit 1).
    reject_foreign_database(db_path)
    for request in requests:  # one list today: the SPDX License List
        try:
            make_default_db_dir(ctx)
            database = LicenseDatabase(db_path)
            updated = database.update_from_remote(
                version=request.version, force=force, use_cache=use_cache, source=source
            )
            outcome = "updated" if updated else "unchanged"
            installed = database.get_metadata().get("license_list_version")
        except InvalidInputError as e:
            exit_usage_error(ctx, str(e))
        except LicenseIdError as e:
            # Already worded "SUBJECT: CONDITION...".
            error(str(e))
            ctx.exit(1)
        except Exception as e:
            # Anything else (e.g. KeyError or RecursionError from malformed
            # release data) has no subject of its own; name the type.
            detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            error(f"database: update failed: {detail}")
            ctx.exit(1)
        # Outside the try: an output failure is not a failed update.
        echo_record(
            json_output,
            LIST=request.list_id,
            VERSION=installed,
            STATUS=outcome,
            PATH=db_path,
        )


@click.command(name="clear-cache", cls=LicenseIdCommand)
@json_option
@click.pass_context
def clear_cache_command(ctx: click.Context, json_output: bool) -> None:
    """Delete the database and the cache files beside it.

    Prints one record: STATUS=cleared, or nothing when there was nothing to
    delete, and the database PATH. A file licenseid did not build is refused
    (exit 2); a delete the system refuses exits 1.
    """
    db_path = ctx.obj["db_path"]
    # ``clear_cache`` refuses a file licenseid did not build (one mistyped
    # ``--db`` must not destroy another program's database); the group turns
    # that refusal into exit 2. A delete the system refuses is reported here,
    # naming the file that actually failed, with exit 1: the command was
    # understood and failed, as an update that fails does.
    try:
        cleared = LicenseDatabase.clear_cache(db_path)
    except OSError as exc:
        failed = exc.filename or db_path
        error(str(delete_failed_error(str(failed), exc)))
        ctx.exit(1)
    echo_record(json_output, STATUS="cleared" if cleared else "nothing", PATH=db_path)
