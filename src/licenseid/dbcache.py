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
from typing import TypeVar, cast

from licenseid.dbconnection import Connections
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

    The tables change only when ``update`` rebuilds them, which calls
    ``clear()``; another process that rebuilds the file is not seen.
    """

    def __init__(self, connections: Connections) -> None:
        self._connections = connections
        self._license_ids: dict[str, str] | None = None
        self._index_rows: dict[str, int] | None = None
        self._names_and_ids: list[LicenseNameId] | None = None
        self._deprecated: dict[str, str] | None = None

    def clear(self) -> None:
        """Forget every read, after the tables were rewritten."""
        self._license_ids = self._index_rows = None
        self._names_and_ids = None
        self._deprecated = None

    def _first_rows(self, query: str, kind: type[_V]) -> dict[str, _V]:
        """Key to value for each row of *query*; the first row wins, as the
        scan it replaces returned the first match in rowid order."""
        with self._connections.connection() as conn:
            rows: list[tuple[str, _V]] = conn.execute(query).fetchall()
        found: dict[str, _V] = {}
        for key, value in rows:
            found.setdefault(key, kind(value))
        return found

    def license_id(self, license_id: str) -> str | None:
        """The ``licenses`` row's ID that *license_id* names, in any ASCII
        case, or None."""
        if self._license_ids is None:
            ids = self._first_rows(
                "SELECT license_id, license_id FROM licenses ORDER BY rowid", str
            )
            folded: dict[str, str] = {}
            for key, value in ids.items():
                folded.setdefault(fold_case(key), value)
            self._license_ids = folded  # whole, for another thread to see
        return self._license_ids.get(fold_case(license_id))

    def index_row(self, license_id: str) -> int | None:
        """The ``license_index`` rowid of *license_id* (exact case), or None."""
        if self._index_rows is None:
            self._index_rows = self._first_rows(
                "SELECT license_id, rowid FROM license_index ORDER BY rowid", int
            )
        return self._index_rows.get(license_id)

    def names_and_ids(self) -> list[LicenseNameId]:
        """Every licence's ID, name and flags, for short-text matching."""
        if self._names_and_ids is None:
            with self._connections.connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT license_id, name, is_deprecated, norm_license_id,"
                    " norm_name, is_spdx, is_osi_approved, is_fsf_libre"
                    " FROM licenses"
                ).fetchall()
            # The same columns as LicenseNameId, with its flags made bool.
            self._names_and_ids = [
                cast(LicenseNameId, cast_license_details(row)) for row in rows
            ]
        return self._names_and_ids

    def deprecated(self) -> dict[str, str]:
        """Each deprecated licence and exception ID to its successor."""
        if self._deprecated is None:
            deprecated = self._first_rows(
                "SELECT license_id, superseded_by FROM licenses"
                " WHERE is_deprecated = 1 AND superseded_by IS NOT NULL",
                str,
            )
            deprecated.update(
                self._first_rows(
                    "SELECT exception_id, superseded_by FROM exceptions"
                    " WHERE is_deprecated = 1 AND superseded_by IS NOT NULL",
                    str,
                )
            )
            self._deprecated = deprecated
        return self._deprecated
