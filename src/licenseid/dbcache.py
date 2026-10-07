# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whole-table reads a licence database keeps until it is rebuilt.

A tag value takes about five lookups by ID, and two of them could use no
index: ``license_index`` is an FTS5 table whose ``license_id`` is
``UNINDEXED``, and the primary key of ``licenses`` is binary, so
``license_id = ? COLLATE NOCASE`` cannot seek on it. Each scanned the whole
table, about 1.2 s for 4,000 distinct tags. Reading each table's IDs once
turns every later lookup into a seek, and an unknown ID into no query.
"""

import sqlite3
import string
import threading
from typing import TypeVar, cast

from licenseid.dbconnection import Connections
from licenseid.normalize import normalize_text
from licenseid.types import LicenseDetails, LicenseNameId

_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_V = TypeVar("_V", str, int)


def fold_case(value: str) -> str:
    """*value* with ASCII letters lowercased, as SQLite's NOCASE compares.

    ``str.lower`` folds more: the KELVIN SIGN would become ``k``.
    """
    return value.translate(_ASCII_LOWER)


def cast_license_details(row: sqlite3.Row) -> LicenseDetails:
    """A ``licenses`` row as LicenseDetails, its flags made bool."""
    details = dict(row)
    for key in (
        "is_spdx",
        "is_osi_approved",
        "is_fsf_libre",
        "is_high_usage",
        "is_deprecated",
    ):
        if key in details:
            details[key] = bool(details[key])
    return cast(LicenseDetails, details)


class TableCache:
    """Reads of whole tables, each made at its first use.

    ``update`` stamps every rebuild with ``last_update_datetime``. The
    stamp is read again once per ``reading()`` block, and at every lookup
    outside one: a new stamp, from this process or another, drops every read.
    """

    def __init__(self, connections: Connections) -> None:
        self._connections = connections
        self._stamp: str | None = None
        self._generation = 0  # clear() calls so far
        self._checked = threading.local()  # the block this thread checked in
        self._license_ids: dict[str, str] | None = None
        self._index_rows: dict[str, int] | None = None
        self._names_and_ids: list[LicenseNameId] | None = None
        self._deprecated: dict[str, str] | None = None

    def clear(self) -> None:
        """Forget every read, after the tables were rewritten."""
        self._generation += 1
        self._license_ids = self._index_rows = None
        self._names_and_ids = None
        self._deprecated = None

    def _check_stamp(self) -> None:
        """Drop every read if the tables were rebuilt since they were made."""
        block = self._connections.current_block()
        if block and getattr(self._checked, "block", 0) == block:
            return
        with self._connections.connection() as conn:
            row = conn.execute(
                "SELECT value FROM db_metadata WHERE key = 'last_update_datetime'"
            ).fetchone()
        stamp = row[0] if row else None
        if stamp != self._stamp:
            self.clear()
            self._stamp = stamp
        self._checked.block = block

    def _first_rows(self, query: str, kind: type[_V]) -> dict[str, _V]:
        """Key to value for each row of *query*; the first row wins, as the
        scan it replaces returned the first match in rowid order. A NULL key
        matches nothing, as in SQL."""
        with self._connections.connection() as conn:
            rows: list[tuple[str | None, _V]] = conn.execute(query).fetchall()
        found: dict[str, _V] = {}
        for key, value in rows:
            if key is not None:
                found.setdefault(key, kind(value))
        return found

    # Each read below is taken into a local name once: another thread's
    # clear() may set the attribute to None at any moment. A read made while
    # one ran may hold the old rows, so it serves its own call only.

    def license_id(self, license_id: str) -> str | None:
        """The ``licenses`` row's ID that *license_id* names, in any ASCII
        case, or None."""
        self._check_stamp()
        generation, ids = self._generation, self._license_ids
        if ids is None:
            ids = {}
            for key, value in self._first_rows(
                "SELECT license_id, license_id FROM licenses ORDER BY rowid", str
            ).items():
                ids.setdefault(fold_case(key), value)
            if generation == self._generation:
                self._license_ids = ids
        return ids.get(fold_case(license_id))

    def index_row(self, license_id: str) -> int | None:
        """The ``license_index`` rowid of *license_id* (exact case), or None."""
        self._check_stamp()
        generation, rows = self._generation, self._index_rows
        if rows is None:
            rows = self._first_rows(
                "SELECT license_id, rowid FROM license_index ORDER BY rowid", int
            )
            if generation == self._generation:
                self._index_rows = rows
        return rows.get(license_id)

    def names_and_ids(self) -> list[LicenseNameId]:
        """Every licence's ID, name and flags, for short-text matching."""
        self._check_stamp()
        generation, names = self._generation, self._names_and_ids
        if names is None:
            with self._connections.connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT license_id, name, is_deprecated, norm_license_id,"
                    " norm_name, is_spdx, is_osi_approved, is_fsf_libre"
                    " FROM licenses"
                ).fetchall()
            # The same columns as LicenseNameId, with its flags made bool.
            records = [dict(cast_license_details(row)) for row in rows]
            # A row without its normalised columns (a database of an earlier
            # version, or one a script filled directly) is normalised here
            # and not written back: a lookup never writes.
            for record in records:
                if record["norm_license_id"] is None:
                    record["norm_license_id"] = normalize_text(
                        str(record["license_id"])
                    )
                if record["norm_name"] is None:
                    record["norm_name"] = normalize_text(str(record["name"] or ""))
            names = cast(list[LicenseNameId], records)
            if generation == self._generation:
                self._names_and_ids = names
        return names

    def active_id_with_prefix(self, prefix: str) -> str | None:
        """The ID of the one active licence whose ID starts with *prefix*.

        Replaces a SQL ``LIKE``: no pattern built from input reaches SQLite,
        whose 50,000-byte pattern limit made a long input look like a broken
        database. Any length or character is a plain no match. ASCII case is
        folded as ``LIKE`` folds it. Deprecated IDs are left out; a NULL
        ``is_deprecated`` counts as active, as in Tier 0, and a NULL ID
        matches nothing, as in SQL. The answer is None unless the shortest
        match is alone or strictly shorter than the next.
        """
        folded = fold_case(prefix)
        # A hand-filled table can hold a NULL ID, whatever the type says.
        ids = (
            record["license_id"]
            for record in self.names_and_ids()
            if isinstance(record["license_id"], str) and not record["is_deprecated"]
        )
        found = sorted(
            (lic_id for lic_id in ids if fold_case(lic_id).startswith(folded)),
            key=len,
        )
        if len(found) == 1 or (found and len(found[0]) < len(found[1])):
            return found[0]
        return None

    def deprecated(self) -> dict[str, str]:
        """Each deprecated licence and exception ID to its successor."""
        self._check_stamp()
        generation, found = self._generation, self._deprecated
        if found is None:
            found = self._first_rows(
                "SELECT license_id, superseded_by FROM licenses"
                " WHERE is_deprecated = 1 AND superseded_by IS NOT NULL",
                str,
            )
            found.update(
                self._first_rows(
                    "SELECT exception_id, superseded_by FROM exceptions"
                    " WHERE is_deprecated = 1 AND superseded_by IS NOT NULL",
                    str,
                )
            )
            if generation == self._generation:
                self._deprecated = found
        return found
