# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The word-gram postings of ``licenseid.gramstore`` on a plain connection:
blobs and their byte order, the width, the index built from texts (hash
collisions too), the stored index read back, the 900-value lookups and the
bound on the grams looked up. The database around them:
``test_gramstore_db``."""
# pylint: disable=missing-function-docstring

import contextlib
import random
import sqlite3
import struct
import sys
from collections.abc import Iterator, Sequence
from unittest import mock

import pytest

from licenseid import gramstore, textgrams
from licenseid.dbschema import create_schema
from licenseid.gramstore import (
    Damaged,
    GramCache,
    MemoryPostings,
    StoredPostings,
    build_index,
    checked_blob,
    from_blobs,
    load,
    read_texts,
    to_blob,
    width_for,
    write_postings,
)
from licenseid.textgrams import (
    GramScore,
    gram_strings,
    input_grams,
    score_rows,
    split_words,
)

TEXTS = {
    "A-1.0": "permission is hereby granted to any person to deal in the software",
    "B-1.0": "the software is provided as is without warranty of any kind",
    "C-1.0": "two words",  # no gram: no number
    "D-1.0": "permission is hereby granted free of charge to deal in the software",
    "J-1.0": "本 ソフトウェア は 無保証 で 提供 さ れ ま す",
}


@contextlib.contextmanager
def _connection(
    texts: dict[str, str], stored: bool = True
) -> Iterator[sqlite3.Connection]:
    """A memory database of *texts* with the postings ``update`` stores, or
    none (*stored* False)."""
    conn = sqlite3.connect(":memory:")
    try:
        create_schema(conn)
        conn.executemany(
            "INSERT INTO licenses (license_id, name) VALUES (?, ?)",
            [(key, key) for key in texts],
        )
        conn.executemany(
            "INSERT INTO license_texts (license_id, search_text) VALUES (?, ?)",
            texts.items(),
        )
        conn.execute("INSERT INTO db_metadata VALUES ('last_update_datetime', 't1')")
        if stored:
            write_postings(conn, "t1")
        conn.commit()
        yield conn
    finally:
        conn.close()


def _brute(texts: dict[str, str], text: str) -> list[tuple[str, int, int, float]]:
    """The score table by its definition, with sets of grams by hash."""
    query = set(input_grams(text))
    rows = []
    for license_id, body in texts.items():
        held = {textgrams.gram_hash(g) for g in gram_strings(split_words(body))}
        shared = len(query & held)
        if shared:
            rows.append(
                (license_id, shared, len(held), shared / min(len(query), len(held)))
            )
    return rows


def _table(
    index: gramstore.Postings, conn: sqlite3.Connection, text: str
) -> list[GramScore]:
    grams = input_grams(text)
    return list(
        score_rows(index.shared(conn, grams), len(grams), index.ids, index.sizes)
    )


INPUTS = [
    *TEXTS.values(),
    "deal in the software is provided as is",
    "nothing here matches at all",
    "",
]


@pytest.mark.parametrize("text", INPUTS, ids=[f"input-{n}" for n in range(len(INPUTS))])
def test_stored_and_built_index_give_the_table_of_the_definition(text: str) -> None:
    with _connection(TEXTS) as conn:
        stored = load(conn)
        assert isinstance(stored, StoredPostings)
        built = build_index(read_texts(conn))
        expected = _brute({k: v for k, v in TEXTS.items() if k != "C-1.0"}, text)
        assert _table(stored, conn, text) == expected
        assert _table(built, conn, text) == expected


def test_a_text_with_no_gram_holds_no_number() -> None:
    index = build_index(TEXTS.items())
    assert index.ids == ("A-1.0", "B-1.0", "D-1.0", "J-1.0")
    assert index.sizes == (10, 9, 10, 16)


def test_the_first_row_of_an_id_wins_and_rows_without_a_licence_are_left() -> None:
    with _connection({"A-1.0": TEXTS["A-1.0"]}) as conn:
        conn.execute(
            "INSERT INTO license_texts (license_id, search_text) VALUES ('A-1.0', ?)",
            (TEXTS["B-1.0"],),
        )
        conn.execute(
            "INSERT INTO license_texts (license_id, search_text) VALUES ('Z-1.0', ?)",
            (TEXTS["B-1.0"],),
        )
        conn.execute(
            "INSERT INTO license_texts (license_id, search_text)"
            " VALUES (NULL, 'a b c d')"
        )
        conn.execute(
            "INSERT INTO license_texts (license_id, search_text) VALUES ('A-1.0', '')"
        )
        assert read_texts(conn) == [("A-1.0", TEXTS["A-1.0"])]


def test_grams_of_one_hash_count_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A collision of the 64-bit hash (made here with a hash of 3 values):
    the index holds what distinct hashes give, stored and built alike."""
    monkeypatch.setattr(gramstore, "gram_hash", lambda gram: len(gram) % 3)
    monkeypatch.setattr("licenseid.textgrams.gram_hash", lambda gram: len(gram) % 3)
    index = build_index(TEXTS.items())
    assert len(index.postings) == 3
    assert all(numbers == sorted(set(numbers)) for numbers in index.postings.values())
    with _connection(TEXTS) as conn:
        for text in INPUTS:
            expected = _brute({k: v for k, v in TEXTS.items() if k != "C-1.0"}, text)
            assert _table(index, conn, text) == expected
            assert _table(load(conn), conn, text) == expected


@pytest.mark.parametrize(
    ("texts", "width"),
    [(0, 2), (1, 2), (65536, 2), (65537, 4), (1 << 32, 4)],
)
def test_the_width_is_the_narrowest_that_numbers_the_texts(
    texts: int, width: int
) -> None:
    assert width_for(texts) == width


def test_more_texts_than_four_bytes_number_are_refused() -> None:
    with pytest.raises(ValueError, match="too many texts"):
        width_for((1 << 32) + 1)


@pytest.mark.parametrize("width", [2, 4])
def test_a_blob_is_little_endian_on_any_host(width: int) -> None:
    numbers = [1, 258, 65535]
    code = "<3H" if width == 2 else "<3I"
    assert to_blob(numbers, width) == struct.pack(code, *numbers)
    assert list(from_blobs([to_blob(numbers, width)], width)) == numbers


@pytest.mark.parametrize("width", [2, 4])
def test_a_host_of_the_other_byte_order_swaps(width: int) -> None:
    """The host of the other order, simulated by the byte order the swap is
    told: its native items are the reverse of this host's."""
    other = "big" if sys.byteorder == "little" else "little"
    numbers = [1, 258]
    native = struct.pack(("=2H" if width == 2 else "=2I"), *numbers)
    reverse = struct.pack((">2H" if width == 2 else ">2I"), *numbers)
    if sys.byteorder == "big":
        native, reverse = reverse, native
    swapped = to_blob(numbers, width, "big")
    assert swapped == (reverse if sys.byteorder == "little" else native)
    assert list(from_blobs([swapped], width, "big")) == numbers
    assert to_blob(numbers, width, other) != to_blob(numbers, width)


@pytest.mark.parametrize(
    "blob",
    [b"", b"\x01", b"\x01\x00\x02", "text", None, 7],
    ids=["empty", "one-byte", "three-bytes", "text", "null", "integer"],
)
def test_a_blob_that_does_not_read_is_damage(blob: object) -> None:
    with pytest.raises(Damaged):
        checked_blob(blob, 2)


def test_a_blob_of_whole_items_reads() -> None:
    assert checked_blob(b"\x01\x00", 2) == b"\x01\x00"


def _statements(conn: sqlite3.Connection) -> list[str]:
    seen: list[str] = []
    conn.set_trace_callback(seen.append)
    return seen


@pytest.mark.parametrize(
    ("grams", "queries"), [(899, 1), (900, 1), (901, 2), (1800, 2), (1801, 3)]
)
def test_at_most_900_grams_are_bound_to_a_query(grams: int, queries: int) -> None:
    """A-1.0's 10 grams last: they cross the end of each query's 900 (the
    last of a chunk is no gram of a filler word)."""
    text = " ".join([*(f"w{n}" for n in range(grams - 10)), TEXTS["A-1.0"]])
    assert len(input_grams(text)) == grams
    with _connection(TEXTS) as conn:
        stored = load(conn)
        seen = _statements(conn)
        table = _table(stored, conn, text)
        assert sum("FROM text_postings WHERE" in s for s in seen) == queries
        assert table == _table(build_index(TEXTS.items()), conn, text)
        assert table[0][:2] == ("A-1.0", 10)


def test_a_bound_looks_up_only_the_first_grams() -> None:
    """100,000 distinct words: one query of 900, and the table says it is
    bounded. The first grams are the input's first."""
    text = TEXTS["A-1.0"] + " " + " ".join(f"w{n}" for n in range(100_000))
    with _connection(TEXTS) as conn:
        cache = GramCache()
        seen = _statements(conn)
        table = cache.scores(conn, text, limit=900)
        assert sum("FROM text_postings WHERE" in s for s in seen) == 1
        assert (table.grams, table.total, table.bounded) == (900, 901, True)
        assert [row[:3] for row in table.rows] == [("A-1.0", 10, 10), ("D-1.0", 5, 10)]
        assert cache.scores(conn, TEXTS["A-1.0"], limit=3).rows[0][:2] == ("A-1.0", 3)
        unbounded = cache.scores(conn, TEXTS["A-1.0"])
        assert (unbounded.grams, unbounded.bounded) == (10, False)


@pytest.mark.parametrize(
    ("grams", "total", "bounded"),
    [(49_999, 49_999, False), (50_000, 50_000, False), (50_001, 50_001, True)]
    + [(50_002, 50_001, True), (130_000, 50_001, True)],
)
def test_the_limit_of_50000_grams_reads_what_the_whole_input_gives(
    grams: int, total: int, bounded: bool
) -> None:
    """Just under, at and just over the limit of ``gramselect.GRAM_LIMIT``:
    the rows are those of the first 50,000 grams of the whole input, the
    count of grams read is the limit at most, and the table says it is
    bounded from 50,001 on. A-1.0's 10 grams last: they cross the limit."""
    text = " ".join([*(f"w{n}" for n in range(grams - 10)), TEXTS["A-1.0"]])
    first = input_grams(text)[:50_000]
    with _connection(TEXTS) as conn:
        index = load(conn)
        table = GramCache().scores(conn, text, limit=50_000)
        reference = score_rows(index.shared(conn, first), len(first), *_sizes(index))
    assert (table.grams, table.total, table.bounded) == (len(first), total, bounded)
    assert table.rows == reference
    held = 10 - max(0, grams - 50_000)  # the grams of A-1.0 inside the limit
    assert [row[:2] for row in table.rows if row[0] == "A-1.0"] == (
        [("A-1.0", held)] if held > 0 else []
    )


def _sizes(index: gramstore.Postings) -> tuple[Sequence[str], Sequence[int]]:
    return index.ids, index.sizes


def _han(count: int) -> str:
    """*count* Han characters, a gram of three of them each."""
    rnd = random.Random(1)
    return "".join(chr(rnd.randrange(0x4E00, 0x9FFF)) for _ in range(count))


@pytest.mark.parametrize(
    ("text", "hashed", "everything"),
    [
        (" ".join(f"w{n}" for n in range(400_000)), 60_000, 399_998),
        (_han(300_000), 70_000, 299_998),
    ],
    ids=["words", "han"],
)
def test_a_bounded_input_hashes_the_grams_of_its_first_pieces_only(
    text: str, hashed: int, everything: int
) -> None:
    """400,000 words (3 million characters), or 300,000 Han characters with
    no white space: the grams of the first pieces (65,536 characters each) are
    hashed, not those of the whole input, and they are the first the whole
    input gives."""
    with mock.patch.object(
        textgrams, "gram_hash", autospec=True, side_effect=textgrams.gram_hash
    ) as calls:
        grams = input_grams(text, 50_000)
        assert len(grams) == 50_001
        assert 50_001 <= calls.call_count < hashed
        calls.reset_mock()
        whole = input_grams(text)
        assert calls.call_count == everything
    assert grams == whole[:50_001]


def test_a_count_of_true_is_no_count_of_texts() -> None:
    """``"texts":true`` reads as 1 in Python: with one text it would pass
    every other check."""
    with _connection({"A-1.0": TEXTS["A-1.0"]}) as conn:
        assert isinstance(load(conn), StoredPostings)
        conn.execute(
            "UPDATE db_metadata SET value = replace(value, ?, ?)"
            " WHERE key = 'text_postings'",
            ('"texts":1', '"texts":true'),
        )
        assert isinstance(load(conn), MemoryPostings)


def test_a_database_with_no_stored_postings_is_built_in_memory() -> None:
    with _connection(TEXTS, stored=False) as conn:
        index = load(conn)
        assert isinstance(index, MemoryPostings)
        assert index == build_index(TEXTS.items())
        assert _table(index, conn, TEXTS["J-1.0"])[0][:2] == ("J-1.0", 16)
