# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Which SPDX License List ``resolve()`` reads: the licence database, or the
bundle shipped in the wheel (:func:`licenseid.listindex.packaged_index`).

``source="auto"`` (the default), with no database given:

- a usable database at the default path and a bundle: the newer list
  version wins (:func:`licenseid.spdxdata.is_older`; a version that is not
  all numbers is never older). A tie goes to the database only if its rows
  were built by this licenseid's rules (``build vN outdated`` still warns
  when it opens), else to the bundle: the two then give the same answer;
- no database file (``not found``, an account with no home directory
  included): the bundle, silently;
- a database that is there but cannot answer: the bundle, after
  ``WARNING: database: <condition>: <detail>; using packaged data v<ver>``,
  said once per process (not once per value);
- no bundle either: the database's own error, as 0.6.0 raised it.

``source="database"`` reads the database at the default path, and raises
for one that is missing or that ``auto`` would call unusable (a file with
the tables and no rows is ``empty``, where 0.6.0 answered ``unresolved``
from it); ``source="packaged"`` reads the bundle, or raises when there is
none. A database given as ``db=`` is read as ``source="database"``, as the
caller built it.

Usable is what :func:`licenseid.dbcheck.check_database_ready` says, read
fail-open, as the matcher reads it: a lock held elsewhere is no verdict.
"""

import threading
from typing import get_args

from licenseid import listindex
from licenseid.console import warn
from licenseid.database import LicenseDatabase, is_current_build
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import check_database_ready
from licenseid.errors import DatabaseNotReadyError, InvalidInputError, one_line
from licenseid.listlookup import ListLookup
from licenseid.resolvertypes import ListSource, Source
from licenseid.spdxdata import PACKAGED_NAME, is_older

SOURCES: tuple[Source, ...] = get_args(Source)
# The fallback warnings this process printed: each is said once, not once per
# value resolved.
_LOCK = threading.Lock()
_warned: set[str] = set()


def choose_list(
    db: LicenseDatabase | None, source: Source
) -> tuple[ListLookup, ListSource]:
    """The list ``resolve(value, db, source=source)`` reads, and where it
    comes from. Raises :class:`licenseid.errors.InvalidInputError` for a
    *source* that is none of :data:`SOURCES`, or ``packaged`` with a *db*,
    and :class:`licenseid.errors.DatabaseNotReadyError` when the chosen
    list cannot be read."""
    if source not in SOURCES:
        raise InvalidInputError(
            f"option: invalid: source: {one_line(repr(source))};"
            " pass auto, database or packaged"
        )
    if db is not None:
        if source == "packaged":
            raise InvalidInputError(
                "option: invalid: source: 'packaged' with db; pass db or source"
            )
        return db, "database"
    if source == "database":
        path = get_default_db_path()
        check_database_ready(path)  # what auto calls unusable, this refuses
        return LicenseDatabase(path, create=False), "database"
    if source == "packaged":
        return _packaged(), "packaged"
    return _auto()


def _packaged() -> listindex.ListIndex:
    """The packaged index, or the error that there is none."""
    index = listindex.packaged_index()
    if index is None:
        problem = listindex.packaged_problem()
        condition, _, detail = problem.partition(": ")
        raise DatabaseNotReadyError(f"{PACKAGED_NAME}: {problem}", condition, detail)
    return index


def _auto() -> tuple[ListLookup, ListSource]:
    """The default database or the packaged index, as the module says."""
    try:
        path = get_default_db_path()
        check_database_ready(path)
        database = LicenseDatabase(path, create=False)
        metadata = database.get_metadata()
    except DatabaseNotReadyError as exc:
        index = listindex.packaged_index()
        if index is None:
            raise
        if exc.condition != "not found":
            _warn_once(
                f"database: {exc.condition}: {exc.detail};"
                f" using packaged data v{index.version}"
            )
        return index, "packaged"
    index = listindex.packaged_index()
    if index is None:
        return database, "database"
    version = metadata.get("license_list_version", "")
    if is_older(version, index.version):
        return index, "packaged"
    if is_older(index.version, version) or is_current_build(metadata):
        return database, "database"
    return index, "packaged"


def _warn_once(message: str) -> None:
    """Warn *message* unless this process did already."""
    with _LOCK:
        if message in _warned:
            return
        _warned.add(message)
    warn(message)


def reset_warnings() -> None:
    """Forget the warnings said, for a test that expects one."""
    with _LOCK:
        _warned.clear()
