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
import threading
from collections.abc import Callable
from typing import TypeVar, cast

from licenseid.dbconnection import Connections
from licenseid.listlookup import ListedUrl, UrlRow, fold_case, index_urls
from licenseid.normalize import normalize_text
from licenseid.types import LicenseDetails, LicenseNameId, TextParts

__all__ = ["TableCache", "cast_license_details"]
_V = TypeVar("_V", str, int)


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


class _Keyed:
    """The reads a caller keys its own way, for one generation of the
    tables: names_and_ids() by a key of each ID, and the rows of
    ``license_urls`` with their index by a key of each URL. One key of each
    is kept; a call with another builds its index again. The words of the
    exceptions and the text parts are here too: they are read for one
    generation as well."""

    __slots__ = ("exception_words", "names", "text_parts", "url_rows", "urls")

    def __init__(self) -> None:
        self.names: tuple[Callable[[str], str], dict[str, list[LicenseNameId]]] | None
        self.names = None
        self.url_rows: list[UrlRow] | None = None
        self.exception_words: list[frozenset[str]] | None = None
        self.text_parts: dict[str, TextParts] | None = None
        self.urls: (
            tuple[Callable[[str], str | None], dict[str, list[ListedUrl]]] | None
        ) = None


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
        self._active_by_name: dict[str, list[str]] | None = None
        self._deprecated: dict[str, str] | None = None
        self._keyed = _Keyed()  # replaced, never emptied, by clear()

    def clear(self) -> None:
        """Forget every read, after the tables were rewritten."""
        self._generation += 1
        self._license_ids = self._index_rows = None
        self._names_and_ids = self._active_by_name = None
        self._deprecated = None
        self._keyed = _Keyed()

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
        """Key to value for each row of *query*; the first row wins, as a
        scan in rowid order would find it first. A NULL key matches nothing,
        as in SQL."""
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

    def text_parts(self) -> dict[str, TextParts]:
        """The core and the twins of each licence's text, by ID (exact
        case), read once per rebuild: only the licences with a core or a
        twin are in it, so a licence that is not has no entry. A database
        built before build 5 has none of the columns, or NULL in them, and
        gives an empty map: it is read as it is, never written (a lookup
        never writes; ``update`` fills them)."""
        self._check_stamp()
        generation, holder = self._generation, self._keyed
        parts = holder.text_parts
        if parts is None:
            parts = self._read_text_parts()
            if generation == self._generation:
                holder.text_parts = parts
        return parts

    def _read_text_parts(self) -> dict[str, TextParts]:
        """The rows of ``licenses`` that have a core or a twin."""
        with self._connections.connection() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
            if not {"core_text", "core_word_count", "same_text"} <= columns:
                return {}
            rows: list[tuple[str, str | None, int | None, str | None]] = conn.execute(
                "SELECT license_id, core_text, core_word_count, same_text"
                " FROM licenses ORDER BY rowid"
            ).fetchall()
        found: dict[str, TextParts] = {}
        for license_id, core, words, same in rows:
            if core is None and not same:
                continue
            found.setdefault(
                license_id,
                TextParts(
                    core if core is not None and words else None,
                    words if core is not None and words else None,
                    tuple(same.split()) if same else (),
                ),
            )
        return found

    def names_by_key(self, key: Callable[[str], str]) -> dict[str, list[LicenseNameId]]:
        """names_and_ids() by *key* of each ID, in table order: built once,
        so a lookup by key costs no pass over every row. One key is kept; a
        call with another rebuilds it."""
        generation, holder = self._generation, self._keyed
        names = self.names_and_ids()  # checks the stamp, which may clear
        keyed = holder.names
        if keyed is None or keyed[0] is not key or generation != self._generation:
            index: dict[str, list[LicenseNameId]] = {}
            for record in names:
                if isinstance(record["license_id"], str):
                    index.setdefault(key(record["license_id"]), []).append(record)
            keyed = (key, index)
            if generation == self._generation:
                holder.names = keyed
        return keyed[1]

    def ids_by_url(
        self, key: Callable[[str], str | None]
    ) -> dict[str, list[ListedUrl]]:
        """The owners of each page in ``license_urls`` by *key* of its URL
        (:func:`licenseid.listlookup.index_urls`), in table order: the
        licences, then the exceptions. The table is read once per rebuild;
        one key is kept, and a call with another keys the same rows again."""
        self._check_stamp()
        generation, holder = self._generation, self._keyed
        keyed = holder.urls
        if keyed is None or keyed[0] is not key:
            rows = holder.url_rows
            if rows is None:
                rows = self._url_rows()
            keyed = (key, index_urls(rows, key))
            if generation == self._generation:
                holder.url_rows, holder.urls = rows, keyed
        return keyed[1]

    def _url_rows(self) -> list[UrlRow]:
        """The rows of ``license_urls`` in table order, or none when the
        table is missing: a database built before it (build 3) is read as
        it is, as a missing norm column is filled in memory, never written
        (a lookup never writes; ``update`` makes the table)."""
        with self._connections.connection() as conn:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master"
                " WHERE type = 'table' AND name = 'license_urls'"
            ).fetchone():
                return []
            rows: list[UrlRow] = conn.execute(
                "SELECT owner_id, is_exception, url FROM license_urls ORDER BY rowid"
            ).fetchall()
        return rows

    def active_ids_by_name(self) -> dict[str, list[str]]:
        """The IDs in use by case-folded name, built once: a lookup by name
        costs no pass over every row."""
        self._check_stamp()
        generation, found = self._generation, self._active_by_name
        if found is None:
            found = {}
            # A hand-filled table can hold a NULL, whatever the type says.
            for record in self.names_and_ids():
                license_id, name = record["license_id"], record["name"]
                if (
                    isinstance(license_id, str)
                    and isinstance(name, str)
                    and not record["is_deprecated"]
                ):
                    found.setdefault(name.casefold(), []).append(license_id)
            if generation == self._generation:
                self._active_by_name = found
        return found

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

    def exception_words(self) -> list[frozenset[str]]:
        """The normalised words of each exception's name and of its ID, built
        once: ``licenseid.namehits`` asks whether the words after a "with"
        name an exception."""
        self._check_stamp()
        generation, holder = self._generation, self._keyed
        found = holder.exception_words
        if found is None:
            with self._connections.connection() as conn:
                rows: list[tuple[str | None, str | None]] = conn.execute(
                    "SELECT exception_id, name FROM exceptions"
                ).fetchall()
            found = [
                frozenset(normalize_text(text).split())
                for row in rows
                for text in row
                if isinstance(text, str)
            ]
            if generation == self._generation:
                holder.exception_words = found
        return found
