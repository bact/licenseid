# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The word-gram postings of the List texts: which texts hold each gram
(``licenseid.textgrams``), stored by ``update`` and read at a lookup.

``text_posting_ids`` numbers the texts (``k``, in row order, with the licence
ID and the text's count of distinct grams); ``text_postings`` holds one row
per gram: its hash ``h`` and the numbers of the texts that hold it, as one
blob of unsigned integers of a stored width, little-endian. One blob per
gram is a third of the size of one row per pair.

Postings are a second copy of the texts, so they are used only when they are
those of the rows: ``update`` writes a stamp in the transaction that writes
them (the gram spec, the width, the counts of texts and grams, and a copy of
``last_update_datetime``). A stamp that differs, a table whose count is not
the stamp's, or a blob that does not read (a wrong length, a number out of
range) makes the index be built in memory from the texts, which gives what
the stored one gives, and is never written back: a lookup never writes.
"""

import array
import json
import sqlite3
import sys
import threading
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from itertools import chain
from types import MappingProxyType
from typing import Final, NamedTuple, Protocol, TypeGuard

from licenseid.textgrams import (
    GRAM_SIZE,
    HASH_NAME,
    TOKEN_RULE,
    GramTable,
    gram_hash,
    gram_strings,
    input_grams,
    score_rows,
    split_words,
)

#: The ``db_metadata`` key of the stamp (a JSON object, :func:`stamp_value`)
#: and of the copy of ``last_update_datetime`` it was written with.
STAMP_KEY: Final = "text_postings"
STAMP_UPDATE_KEY: Final = "text_postings_update"
#: Gram hashes bound to one query: SQLite's old limit is 999 variables.
CHUNK: Final = 900
#: The widths a build chooses from, narrowest first (:func:`width_for`). Not
#: 1: a blob cut by one byte must not read as a shorter list.
WIDTHS: Final = (2, 4)
# The array type code of each width (``I``, not ``L``: 8 bytes on Linux).
_CODES: Final = MappingProxyType(
    {array.array(code).itemsize: code for code in reversed("BHILQ")}
)
_UPDATED: Final = "SELECT value FROM db_metadata WHERE key = 'last_update_datetime'"
# The texts each licence row is matched by: the index rows that have a
# licence row, in table order.
_TEXTS: Final = """
    SELECT li.license_id, li.search_text FROM license_index li
    JOIN licenses l ON l.license_id = li.license_id
    ORDER BY li.rowid
"""


class Damaged(Exception):
    """Stored postings that are not those of the rows."""


def width_for(texts: int) -> int:
    """The narrowest width of :data:`WIDTHS` that numbers *texts* texts."""
    for width in WIDTHS:
        if texts <= 1 << (8 * width):
            return width
    raise ValueError(f"too many texts for postings: {texts}")


def to_blob(
    numbers: Sequence[int], width: int, byteorder: str = sys.byteorder
) -> bytes:
    """*numbers* as a blob of *width*-byte little-endian items, written on a
    host of *byteorder*."""
    items = array.array(_CODES[width], numbers)
    if byteorder == "big":
        items.byteswap()
    return items.tobytes()


def checked_blob(blob: object, width: int) -> bytes:
    """*blob* as read from ``text_postings``; :class:`Damaged` for a value
    that is not bytes, or is empty, or of a length that is no multiple of
    *width*."""
    if not isinstance(blob, bytes) or not blob or len(blob) % width:
        raise Damaged
    return blob


def from_blobs(
    blobs: Iterable[bytes], width: int, byteorder: str = sys.byteorder
) -> "array.array[int]":
    """The numbers in blobs :func:`to_blob` wrote (each checked by
    :func:`checked_blob`), in one array, read on a host of *byteorder*."""
    items = array.array(_CODES[width])
    items.frombytes(b"".join(blobs))
    if byteorder == "big":
        items.byteswap()
    return items


class Postings(Protocol):
    """An index of the List texts by gram: stored or built in memory."""

    @property
    def ids(self) -> Sequence[str]:
        """The licence ID of each text, by number."""

    @property
    def sizes(self) -> Sequence[int]:
        """The count of distinct grams of each text, by number."""

    def shared(self, conn: sqlite3.Connection, grams: Sequence[int]) -> Counter[int]:
        """Text number to the number of *grams* (distinct) the text holds,
        for the texts that hold one; read on *conn*."""


class MemoryPostings(NamedTuple):
    """An index built from the texts (:func:`build_index`): never changed
    after, so threads share it. The numbers of each gram's texts are an
    ascending list; *width* is the one the build stores them at."""

    ids: tuple[str, ...]
    sizes: tuple[int, ...]
    postings: Mapping[int, list[int]]
    width: int

    def shared(self, conn: sqlite3.Connection, grams: Sequence[int]) -> Counter[int]:
        """See :meth:`Postings.shared`; *conn* is not read."""
        del conn
        found = self.postings.get
        return Counter(chain.from_iterable(found(gram, ()) for gram in grams))


class StoredPostings(NamedTuple):
    """The stored index, its ids read and its stamp checked (:func:`load`):
    each blob is checked as it is read."""

    ids: tuple[str, ...]
    sizes: tuple[int, ...]
    width: int

    def shared(self, conn: sqlite3.Connection, grams: Sequence[int]) -> Counter[int]:
        """See :meth:`Postings.shared`. :class:`Damaged` for a blob that does
        not read, or counts that no postings of these texts give."""
        blobs: list[bytes] = []
        for start in range(0, len(grams), CHUNK):
            part = grams[start : start + CHUNK]
            marks = ", ".join("?" * len(part))
            query = f"SELECT ids FROM text_postings WHERE h IN ({marks})"
            blobs.extend(
                checked_blob(row[0], self.width) for row in conn.execute(query, part)
            )
        # One array and one count: a blob at a time costs twice as much.
        numbers = from_blobs(blobs, self.width)
        if numbers and max(numbers) >= len(self.ids):
            raise Damaged
        counts = Counter(numbers)
        # A number twice in one blob: more shared grams than the text has.
        if any(count > self.sizes[k] for k, count in counts.items()):
            raise Damaged
        return counts


def read_texts(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """The licence ID and text of each row a text is matched by, in table
    order; the first row of an ID wins, as a scan finds it first."""
    texts: dict[str, str] = {}
    for license_id, text in conn.execute(_TEXTS):
        if isinstance(license_id, str) and isinstance(text, str) and text:
            texts.setdefault(license_id, text)
    return list(texts.items())


def build_index(texts: Iterable[tuple[str, str]]) -> MemoryPostings:
    """The index of *texts* (licence ID and normalised text, in row order):
    a text with no gram holds no number."""
    ids: list[str] = []
    sizes: list[int] = []
    lists: defaultdict[str, list[int]] = defaultdict(list)
    for license_id, text in texts:
        grams = set(gram_strings(split_words(text)))
        if not grams:
            continue
        number = len(ids)
        ids.append(license_id)
        sizes.append(len(grams))
        for gram in grams:
            lists[gram].append(number)
    # Each distinct gram is hashed once, after the loop: the List texts
    # share most of their grams.
    postings: dict[int, list[int]] = {}
    for gram, held in lists.items():
        hashed = gram_hash(gram)
        other = postings.get(hashed)
        postings[hashed] = held if other is None else _merged(other, held, sizes)
    return MemoryPostings(
        tuple(ids), tuple(sizes), MappingProxyType(postings), width_for(len(ids))
    )


def _merged(first: list[int], second: list[int], sizes: list[int]) -> list[int]:
    """The texts of two grams of one hash (a collision), each once: a text
    that holds both has one distinct hash fewer than distinct grams."""
    for number in set(first).intersection(second):
        sizes[number] -= 1
    return sorted(set(first).union(second))


def stamp_value(width: int, texts: int, grams: int) -> str:
    """The stamp of postings of *texts* texts and *grams* grams stored at
    *width*, with the gram spec of this build."""
    return _json(
        {
            "gram": GRAM_SIZE,
            "grams": grams,
            "hash": HASH_NAME,
            "texts": texts,
            "tokens": TOKEN_RULE,
            "width": width,
        }
    )


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def write_postings(conn: sqlite3.Connection, updated: str) -> None:
    """Store the postings of the texts *conn* holds, and their stamp with
    *updated* (the ``last_update_datetime`` written beside them): inside
    ``update``'s transaction, after the texts and licence rows."""
    index = build_index(read_texts(conn))
    width = index.width
    conn.executemany(
        "INSERT INTO text_posting_ids (k, id, size) VALUES (?, ?, ?)",
        ((k, *row) for k, row in enumerate(zip(index.ids, index.sizes))),
    )
    conn.executemany(
        "INSERT INTO text_postings (h, ids) VALUES (?, ?)",
        (
            (gram, to_blob(index.postings[gram], width))
            for gram in sorted(index.postings)
        ),
    )
    conn.executemany(
        "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
        (
            (STAMP_KEY, stamp_value(width, len(index.ids), len(index.postings))),
            (STAMP_UPDATE_KEY, updated),
        ),
    )


def _read_stamp(conn: sqlite3.Connection) -> dict[str, object] | None:
    """The stamp, when it was written with the rows: its copy of
    ``last_update_datetime`` is the rows' (a time, as ``update`` writes);
    else None."""
    found = dict(
        conn.execute(
            "SELECT key, value FROM db_metadata WHERE key IN (?, ?, ?)",
            (STAMP_KEY, STAMP_UPDATE_KEY, "last_update_datetime"),
        )
    )
    updated = found.get("last_update_datetime")
    if not isinstance(updated, str) or found.get(STAMP_UPDATE_KEY) != updated:
        return None
    try:
        stamp = json.loads(found.get(STAMP_KEY) or "null")
    except (TypeError, ValueError, RecursionError):  # not JSON; too deep
        return None
    return stamp if isinstance(stamp, dict) else None


def _stamped_width(conn: sqlite3.Connection) -> tuple[int, int] | None:
    """The width and count of texts the stamp gives, when it is the stamp
    of this build's spec written with the rows (:func:`_read_stamp`), and
    its count of grams is the table's; else None. The width read is the one
    a build chooses for that count of texts, or the stamp is not this
    build's."""
    stamp = _read_stamp(conn)
    if stamp is None:
        return None
    texts, grams = stamp.get("texts"), stamp.get("grams")
    if not (_is_count(texts) and _is_count(grams)):
        return None
    width = width_for(texts)
    # Compared as JSON: a JSON true equals 1 in Python, not in the text.
    if _json(stamp) != stamp_value(width, texts, grams):
        return None
    (rows,) = conn.execute("SELECT count(*) FROM text_postings").fetchone()
    return (width, texts) if rows == grams else None


def _is_count(value: object) -> TypeGuard[int]:
    """Whether *value* is a count a stamp can hold (not a JSON true)."""
    return type(value) is int and 0 <= value < 1 << 32  # pylint: disable=C0123


def load(conn: sqlite3.Connection) -> Postings:
    """The stored postings, when they are those of the rows; else the index
    built from the texts, in memory (never written back)."""
    stamped = _stamped_width(conn)
    if stamped is not None:
        width, texts = stamped
        rows = conn.execute(
            "SELECT k, id, size FROM text_posting_ids ORDER BY k"
        ).fetchall()
        if len(rows) == texts and all(map(_is_id_row, rows, range(texts))):
            return StoredPostings(
                tuple(row[1] for row in rows), tuple(row[2] for row in rows), width
            )
    return build_index(read_texts(conn))


def _is_id_row(row: tuple[object, object, object], number: int) -> bool:
    """Whether *row* of ``text_posting_ids`` is text *number*'s, with an ID
    and a positive count of grams."""
    k, license_id, size = row
    return (
        k == number
        and isinstance(license_id, str)
        and type(size) is int  # pylint: disable=C0123
        and size > 0
    )


class GramCache:
    """The postings of one database, loaded at the first call and kept for
    the ``last_update_datetime`` they were loaded at (owned by
    ``dbcache.TableCache``). Loaded under a lock, published whole."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: tuple[object, Postings] | None = None

    def scores(
        self, conn: sqlite3.Connection, norm_text: str, limit: int | None = None
    ) -> GramTable:
        """The texts that share a gram with *norm_text*, read in *conn*'s
        transaction; at most *limit* of its distinct grams (the first) are
        looked up. A stored blob that does not read switches this database to
        the index in memory, and the table is counted again from it."""
        grams = input_grams(norm_text)
        looked = grams if limit is None else grams[:limit]
        row = conn.execute(_UPDATED).fetchone()
        updated = None if row is None else row[0]
        index = self._index(conn, updated, None)
        try:
            shared = index.shared(conn, looked)
        except Damaged:
            index = self._index(conn, updated, index)
            shared = index.shared(conn, looked)
        return GramTable(
            score_rows(shared, len(looked), index.ids, index.sizes),
            len(looked),
            len(grams),
        )

    def _index(
        self, conn: sqlite3.Connection, updated: object, damaged: Postings | None
    ) -> Postings:
        """The postings of the rows *updated* stamps: kept, else loaded (built
        in memory when *damaged* is the kept index)."""
        state = self._state
        if state is not None and state[0] == updated and state[1] is not damaged:
            return state[1]
        with self._lock:
            state = self._state
            if state is not None and state[0] == updated and state[1] is not damaged:
                return state[1]
            index = load(conn) if damaged is None else build_index(read_texts(conn))
            self._state = (updated, index)
            return index
