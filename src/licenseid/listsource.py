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
  the warning ``database: <condition>: <detail>; using packaged data
  v<ver>`` (a :class:`licenseid.LicenseIdWarning`), given once per process
  (not once per value);
- no bundle either: the database's own error, as 0.6.0 raised it.

``source="database"`` reads the database at the default path, and raises
for one that is missing or that ``auto`` would call unusable (a file with
the tables and no rows is ``empty``, where 0.6.0 answered ``unresolved``
from it); ``source="packaged"`` reads the bundle, or raises when there is
none. A database given as ``db=`` is read as ``source="database"``, as the
caller built it.

The choice is kept per process, for the default path, the file's stamp
(``os.stat``: modification, change and size, inode, device) and the packaged
index: a repeat on an unchanged file costs one ``stat`` and opens no
connection, and the database it returns keeps its warm table cache. A
changed stamp, a file that appeared or vanished, another path (the home
directory changed) or another packaged index chooses again, and so does a
``stat`` that fails for any reason but "not found". A choice that raised
is not kept, nor is a fallback to the packaged list for a condition that
can pass by itself (``unreadable``: a lock held elsewhere, an I/O error,
permissions); ``not found``, ``empty`` and ``invalid`` change only with the
file, so they are kept. The stamp is read before the choice is made, so a
file that changes meanwhile is chosen again.

The stamp is as fine as the file system's clock: on a coarse one (FAT, 2 s;
HFS+ and ext3, 1 s) an in-place update that keeps the size can pass for
unchanged within that tick, and the choice, and the build warning of the
database it opened, stay stale until the file changes again (the rows
still refresh through ``last_update_datetime``). ``reset_choice()`` forgets
them.

Usable is what :func:`licenseid.dbcheck.check_database_ready` says, read
fail-open, as the detector reads it: a lock held elsewhere is no verdict.
"""

import os
import threading
import weakref
from typing import NamedTuple, get_args

from licenseid import listindex
from licenseid.database import LicenseDatabase, is_current_build
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import check_database_ready, reject_blank_path
from licenseid.errors import DatabaseNotReadyError, InvalidInputError, one_line
from licenseid.listlookup import ListLookup
from licenseid.resolvertypes import ListSource, Source
from licenseid.spdxdata import PACKAGED_NAME, is_older
from licenseid.warning import once, parts, warn

SOURCES: tuple[Source, ...] = get_args(Source)


class _Kept(NamedTuple):
    """A list chosen, and what it was chosen for."""

    path: str
    stamp: tuple[int, ...] | None  # None: no file
    packaged: listindex.ListIndex | None
    lookup: ListLookup
    source: ListSource


# The last choice of each mode ("auto", "database"), under its own lock, held
# to look it up and to store it, never while choosing: a choice can wait on
# SQLite, and the choice itself warns (``licenseid.warning.once``: a
# fallback's warning or an opened database's, ``build vN outdated``, is
# given once per process, not once per value resolved), which takes a lock
# of its own.
_CHOICE_LOCK = threading.Lock()
_kept: dict[str, _Kept] = {}
# The databases given to resolve(db=...) found ready, by the stamp of their
# file then: a handle, and the last few paths with the database each opened.
_UNSEEN = object()
_checked: "weakref.WeakKeyDictionary[LicenseDatabase, tuple[int, ...] | None]" = (
    weakref.WeakKeyDictionary()
)
_KEPT_PATHS = 8
_paths: dict[str, tuple[tuple[int, ...] | None, LicenseDatabase]] = {}


#: What ``resolve(db=...)`` takes: a database, or the path of one.
GivenDatabase = str | os.PathLike[str] | LicenseDatabase


def choose_list(
    db: GivenDatabase | None, source: Source
) -> tuple[ListLookup, ListSource]:
    """The list ``resolve(value, db, source=source)`` reads, and where it
    comes from. Raises :class:`licenseid.errors.InvalidInputError` for a
    *source* that is none of :data:`SOURCES`, or ``packaged`` with a *db*,
    :class:`TypeError` for a *db* that is neither a database nor a path,
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
        return given_database(db), "database"
    if source == "packaged":
        return _packaged(), "packaged"
    return _kept_choice(source)


def given_database(db: GivenDatabase) -> LicenseDatabase:
    """The database *db* is or names, ready to read (P3 of the contract
    batch: a path raised ``AttributeError``, and a database was read
    unchecked). A path opens without ``create``, after the check, so a
    missing file is ``not found`` and none is made; every database, given
    or opened, passes :func:`licenseid.dbcheck.check_database_ready`.

    The check costs more than a lookup, so a verdict is kept while the file
    keeps its stamp (:func:`file_stamp`), per handle and per path, as the
    choice of ``auto`` is: a value resolved in a loop is checked once."""
    if isinstance(db, LicenseDatabase):
        stamp = file_stamp(str(db.db_path))
        with _CHOICE_LOCK:
            known = _checked.get(db, _UNSEEN) == stamp
        if not known:
            check_database_ready(db.location)
            if not isinstance(stamp, Exception):
                with _CHOICE_LOCK:
                    _checked[db] = stamp
        return db
    path: object = os.fspath(db) if isinstance(db, os.PathLike) else db
    if not isinstance(path, str):  # None is no db; bytes, a number: a mistake
        raise TypeError(
            "db must be a LicenseDatabase, str or os.PathLike[str],"
            f" not {type(db).__name__}"
        )
    reject_blank_path(path, "db")
    return _opened(path)


def _opened(path: str) -> LicenseDatabase:
    """The database at *path*, checked and opened, kept while its file keeps
    its stamp (the last few paths only)."""
    stamp = file_stamp(path)
    with _CHOICE_LOCK:
        kept = _paths.get(path)
    if kept is not None and kept[0] == stamp:
        return kept[1]
    check_database_ready(path)
    with once():
        database = LicenseDatabase(path, create=False)
    if not isinstance(stamp, Exception):
        with _CHOICE_LOCK:
            _paths[path] = (stamp, database)
            while len(_paths) > _KEPT_PATHS:
                del _paths[next(iter(_paths))]
    return database


def _packaged() -> listindex.ListIndex:
    """The packaged index, or the error that there is none."""
    index = listindex.packaged_index()
    if index is None:
        message = f"{PACKAGED_NAME}: {listindex.packaged_problem()}"
        _, condition, detail = parts(message)
        raise DatabaseNotReadyError(message, condition, detail)
    return index


def file_stamp(path: str) -> tuple[int, ...] | None | Exception:
    """The stamp of the file at *path*: None when there is none, the error
    when it cannot be told (that is no stamp to keep a choice by). The change
    time moves with ``chmod``, a write and ``os.utime`` on POSIX, so a file
    changed in place with its modification time restored is seen."""
    try:
        found = os.stat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return exc
    return (
        found.st_mtime_ns,
        found.st_ctime_ns,
        found.st_size,
        found.st_ino,
        found.st_dev,
    )


def _kept_choice(mode: Source) -> tuple[ListLookup, ListSource]:
    """The choice of *mode* (``auto`` or ``database``), kept while the
    default path, its file and the packaged index are the same."""
    try:
        path = get_default_db_path()
    except DatabaseNotReadyError:
        return _choose(mode, None)[:2]  # no home directory: nothing to key by
    stamp = file_stamp(path)  # before the choice: a change meanwhile is seen
    if isinstance(stamp, Exception):
        return _choose(mode, path)[:2]
    with _CHOICE_LOCK:
        kept = _kept.get(mode)
    if (
        kept is not None
        and (kept.path, kept.stamp) == (path, stamp)
        and kept.packaged is _packaged_for(mode)
    ):
        return kept.lookup, kept.source
    lookup, source, keep = _choose(mode, path)  # a raise keeps nothing
    if keep:
        # Read after the choice, so a warning about the bundle comes after the
        # ones of the database, as before the choice was kept.
        entry = _Kept(path, stamp, _packaged_for(mode), lookup, source)
        with _CHOICE_LOCK:
            _kept[mode] = entry
    return lookup, source


def _packaged_for(mode: Source) -> listindex.ListIndex | None:
    """The packaged index a choice of *mode* depends on (``database`` reads
    none)."""
    return listindex.packaged_index() if mode == "auto" else None


def _choose(mode: Source, path: str | None) -> tuple[ListLookup, ListSource, bool]:
    """Choose again, at *path* (None: ask for the default, which raises when
    there is no home): the list, where it comes from, and whether it may be
    kept."""
    if mode == "database":
        path = get_default_db_path() if path is None else path
        check_database_ready(path)  # what auto calls unusable, this refuses
        with once():
            database = LicenseDatabase(path, create=False)
        return database, "database", True
    return _auto(path)


def _auto(path: str | None) -> tuple[ListLookup, ListSource, bool]:
    """The database at *path* (None: the default) or the packaged index, as
    the module says; whether the choice may be kept is the third item."""
    try:
        path = get_default_db_path() if path is None else path
        check_database_ready(path)
        with once():
            database = LicenseDatabase(path, create=False)
        metadata = database.get_metadata()
    except DatabaseNotReadyError as exc:
        index = listindex.packaged_index()
        if index is None:
            raise
        # An error that kept no condition and detail is read from its message.
        condition, detail = (exc.condition, exc.detail)
        if condition is None:
            _, condition, detail = parts(str(exc))
        if condition != "not found":
            with once():
                warn(
                    "database",
                    condition,
                    detail,
                    f"using packaged data v{index.version}",
                )
        return index, "packaged", condition != "unreadable"
    index = listindex.packaged_index()
    if index is None:
        return database, "database", True
    version = metadata.get("license_list_version", "")
    # A version that is not all numbers is never older: then it is a tie.
    if is_older(version, index.version):
        return index, "packaged", True
    if is_older(index.version, version) or is_current_build(metadata):
        return database, "database", True
    return index, "packaged", True


def reset_choice() -> None:
    """Forget the list choices kept, for a test that swaps the home
    directory, the packaged index or the file behind the default path."""
    with _CHOICE_LOCK:
        _kept.clear()
        _checked.clear()
        _paths.clear()
