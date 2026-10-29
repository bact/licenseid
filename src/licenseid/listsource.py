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
  when it opens, once per process), else to the bundle: the two then give
  the same answer;
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

The choice is kept per process, for the default path, the file's stamp
(``os.stat``: modification time, size, inode, device) and the packaged
index: a repeat on an unchanged file costs one ``stat`` and opens no
connection, and the database it returns keeps its warm table cache. A
changed stamp, a file that appeared or vanished, another path (the home
directory changed) or another packaged index chooses again, and so does a
``stat`` that fails for any reason but "not found". A choice that raised
is not kept.

Usable is what :func:`licenseid.dbcheck.check_database_ready` says, read
fail-open, as the matcher reads it: a lock held elsewhere is no verdict.
"""

import os
import threading
from typing import NamedTuple, get_args

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
# The warnings this process printed, a fallback's or an opened database's
# (``build vN outdated``): each is said once, not once per value resolved.
_LOCK = threading.Lock()
_warned: set[str] = set()


class _Kept(NamedTuple):
    """A list chosen, and what it was chosen for."""

    path: str
    stamp: tuple[int, ...] | None  # None: no file
    packaged: listindex.ListIndex | None
    lookup: ListLookup
    source: ListSource


# The last choice of each mode ("auto", "database"), under its own lock: the
# choice itself warns through ``_warn_once``, which takes ``_LOCK``.
_CHOICE_LOCK = threading.Lock()
_kept: dict[str, _Kept] = {}


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
    if source == "packaged":
        return _packaged(), "packaged"
    return _kept_choice(source)


def _packaged() -> listindex.ListIndex:
    """The packaged index, or the error that there is none."""
    index = listindex.packaged_index()
    if index is None:
        problem = listindex.packaged_problem()
        condition, _, detail = problem.partition(": ")
        raise DatabaseNotReadyError(f"{PACKAGED_NAME}: {problem}", condition, detail)
    return index


def _stamp(path: str) -> tuple[int, ...] | None | Exception:
    """The stamp of the file at *path*: None when there is none, the error
    when it cannot be told (that is no stamp to keep a choice by)."""
    try:
        found = os.stat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return exc
    return (found.st_mtime_ns, found.st_size, found.st_ino, found.st_dev)


def _kept_choice(mode: Source) -> tuple[ListLookup, ListSource]:
    """The choice of *mode* (``auto`` or ``database``), kept while the
    default path, its file and the packaged index are the same."""
    with _CHOICE_LOCK:
        try:
            path = get_default_db_path()
        except DatabaseNotReadyError:
            return _choose(mode)  # no home directory: nothing to key by
        stamp = _stamp(path)
        if isinstance(stamp, Exception):
            return _choose(mode)
        kept = _kept.get(mode)
        if (
            kept is not None
            and (kept.path, kept.stamp) == (path, stamp)
            and kept.packaged is _packaged_for(mode)
        ):
            return kept.lookup, kept.source
        lookup, source = _choose(mode)  # a raise keeps nothing
        # Read after the choice, so a warning about the bundle comes after the
        # ones of the database, as before the choice was kept.
        _kept[mode] = _Kept(path, stamp, _packaged_for(mode), lookup, source)
        return lookup, source


def _packaged_for(mode: Source) -> listindex.ListIndex | None:
    """The packaged index a choice of *mode* depends on (``database`` reads
    none)."""
    return listindex.packaged_index() if mode == "auto" else None


def _choose(mode: Source) -> tuple[ListLookup, ListSource]:
    """Choose again: what ``resolve()`` read before it kept its choice."""
    if mode == "database":
        path = get_default_db_path()
        check_database_ready(path)  # what auto calls unusable, this refuses
        return LicenseDatabase(path, create=False, report=_warn_once), "database"
    return _auto()


def _auto() -> tuple[ListLookup, ListSource]:
    """The default database or the packaged index, as the module says."""
    try:
        path = get_default_db_path()
        check_database_ready(path)
        database = LicenseDatabase(path, create=False, report=_warn_once)
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
    # A version that is not all numbers is never older: then it is a tie.
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


def reset_choice() -> None:
    """Forget the list choices kept, for a test that swaps the home
    directory, the packaged index or the file behind the default path."""
    with _CHOICE_LOCK:
        _kept.clear()
