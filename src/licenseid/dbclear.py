# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``clear-cache``: delete a database licenseid built, of any build, and the
download cache beside it where that is licenseid's
(``LicenseDatabase.clear_cache``)."""

import contextlib
import os
from pathlib import Path

from licenseid.console import status
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import (
    is_built,
    named_file,
    reject_foreign_database,
    require_path,
)
from licenseid.errors import DatabaseNotReadyError


def _holds_own_cache(db_path: Path) -> bool:
    """Whether the directory of *db_path* holds licenseid's download cache,
    so ``clear-cache`` may delete the cache files in it: the default data
    directory, or the directory of a database licenseid built, ready or of
    older rules (``update`` writes its cache beside the database it builds).
    Fail-closed, as a delete is (``reject_foreign_database``): a mistyped
    ``--db`` names a database that is not there, and the ``licenses.json``
    beside it is somebody else's."""
    if is_built(str(db_path)):
        return True
    try:
        default = Path(get_default_db_path()).parent
        return os.path.samefile(db_path.parent, default)
    except (DatabaseNotReadyError, OSError):
        return False  # no home, or no such directory: none of licenseid's


def clear_database(db_path: str | os.PathLike[str]) -> bool:
    """Delete the database (unopened) at *db_path* and, where they are
    licenseid's (:func:`_holds_own_cache`), the cache files beside it;
    True if there was any of them to delete. Raises
    :class:`licenseid.DatabaseNotReadyError` for a path licenseid did not
    build a database at."""
    # Local import: spdx_source pulls in `requests` (~60ms at import),
    # unused on the match path; update_from_remote() defers it too.
    from licenseid import spdx_source

    require_path(db_path, "db_path")
    db_path = os.fspath(db_path)
    reject_foreign_database(db_path)
    status("Clearing cache...")
    named = named_file(db_path)
    if named is None:
        return False  # in-memory: no directory to clear
    db_path = Path(named)
    # Asked before the database goes: then nothing would show it.
    own_cache = _holds_own_cache(db_path)
    deleted = False
    # The database goes first, so a refused delete leaves the cache
    # intact. Its sidecars follow, best effort: once it is gone a stale
    # -wal cannot be replayed, and reporting one would claim the delete
    # failed when it succeeded.
    if db_path.is_symlink() or db_path.exists():
        status(f"Deleting database at {db_path}...")
        db_path.unlink(missing_ok=True)
        deleted = True
    for suffix in ("-wal", "-shm", "-journal"):
        with contextlib.suppress(OSError):
            db_path.with_name(db_path.name + suffix).unlink()
            deleted = True
    if own_cache and spdx_source.clear_cache_files(db_path.parent):
        return True
    return deleted
