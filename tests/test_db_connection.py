# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""One connection per match: ``LicenseDatabase.reading()`` (roadmap item 29)."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import contextlib
import sqlite3
import threading
from collections.abc import Callable, Generator
from typing import Any
from unittest import mock

import pytest
from conftest import is_closed
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.dbconnection import Connections
from licenseid.matcher import AggregatedLicenseMatcher

ROWS = (
    *GPL2_ROWS,
    Lic("MIT", "MIT License", True, True, True, search_text="permission is hereby"),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
    Lic("BSD-3-Clause", 'BSD 3-Clause "New" or "Revised" License', True, True),
)
# Each tag value is distinct, so no lookup can be reused: only sharing the
# connection saves the cost of opening one per lookup.
TAGS = "\n".join(f"// SPDX-License-Identifier: LicenseRef-x{i}" for i in range(200))


@pytest.fixture(scope="module")
def db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_db_connection", ROWS, exception_ids=["GCC-exception"])


def _lookups(db: LicenseDatabase) -> None:
    assert db.get_license_details("mit")
    assert db.get_license_by_name("apache license 2.0")
    assert db.get_exception_details("GCC-exception")
    assert db.search_candidates("permission is hereby", limit=5)


@pytest.mark.parametrize(
    ("nested", "raises"),
    [(False, False), (False, True), (True, False)],
    ids=["exits", "raises", "nested"],
)
def test_a_block_shares_one_connection_and_closes_it(
    db_path: str, opened: list[sqlite3.Connection], nested: bool, raises: bool
) -> None:
    db = LicenseDatabase(db_path)
    opened.clear()
    with contextlib.suppress(RuntimeError), db.reading():
        with db.reading() if nested else contextlib.nullcontext():
            _lookups(db)
        _lookups(db)
        assert len(opened) == 1 and not is_closed(opened[0])
        if raises:
            raise RuntimeError("boom")
    assert len(opened) == 1 and is_closed(opened[0])


def test_a_block_opens_lazily_and_a_query_outside_closes_its_own(
    db_path: str, opened: list[sqlite3.Connection]
) -> None:
    db = LicenseDatabase(db_path)
    _lookups(db)  # the first lookup by ID reads the table's IDs once
    opened.clear()
    with db.reading():
        pass
    assert not opened
    _lookups(db)
    assert len(opened) == 4 and all(is_closed(c) for c in opened)


_READ_KEY = "SELECT value FROM db_metadata WHERE key = ?"


@pytest.mark.parametrize("raises", [False, True], ids=["commits", "rolls-back"])
@pytest.mark.parametrize("lookup", [False, True], ids=["alone", "with-lookup"])
def test_a_write_in_a_block_ends_with_its_own_query(
    db_path: str, lookup: bool, raises: bool
) -> None:
    """A lookup nested in the write joins its transaction: committing there
    would keep a write whose query then fails."""
    db = LicenseDatabase(db_path)
    key = f"key-{lookup}-{raises}"
    expected = None if raises else ("kept",)
    with db.reading():
        assert db.get_license_details("MIT")  # the write is not the first query
        with contextlib.suppress(RuntimeError), db._connection() as conn:
            conn.execute("INSERT INTO db_metadata VALUES (?, 'kept')", (key,))
            if lookup:
                assert db.get_license_details("MIT")
            if raises:
                raise RuntimeError("boom")
        # The connection is still usable, and a lookup's sqlite3.Row rows do
        # not leak into the next query: it gets plain tuples.
        assert db.get_license_details("MIT")
        with db._connection() as conn:
            assert conn.execute(_READ_KEY, (key,)).fetchone() == expected
    with sqlite3.connect(db_path, uri=True) as other:
        assert other.execute(_READ_KEY, (key,)).fetchone() == expected


@pytest.mark.parametrize(
    "call",
    [
        lambda m: m.match(text=TAGS),
        lambda m: m.is_spdx(text=TAGS),  # match() and one more lookup
        lambda m: m.diff_pair("permission is hereby granted", "MIT"),
    ],
    ids=["match", "is_spdx", "diff_pair"],
)
def test_one_call_opens_one_connection(
    db_path: str,
    opened: list[sqlite3.Connection],
    call: Callable[[AggregatedLicenseMatcher], Any],
) -> None:
    """Each tag value cost about five connections before."""
    matcher = AggregatedLicenseMatcher(db_path)
    opened.clear()
    assert call(matcher)
    assert len(opened) == 1 and is_closed(opened[0])
    # The shared-cache database outlives the block: the keep-alive holds it.
    assert call(matcher)


def test_two_threads_match_on_one_matcher(db_path: str) -> None:
    """sqlite3 refuses a connection made in another thread, so each thread
    needs its own, one for its whole call. The barrier holds both threads in
    their block at once."""
    matcher = AggregatedLicenseMatcher(db_path)
    barrier = threading.Barrier(2, timeout=10)
    real = Connections.connect
    answers: dict[int, list[str]] = {}
    errors: list[BaseException] = []
    connects: list[int] = []

    def connect_together(self: Connections) -> sqlite3.Connection:
        connects.append(threading.get_ident())
        barrier.wait()
        return real(self)

    def run(index: int) -> None:
        try:
            answers[index] = [r["license_id"] for r in matcher.match(text=TAGS)]
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            errors.append(exc)

    with mock.patch.object(
        Connections, "connect", autospec=True, side_effect=connect_together
    ):
        threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert not errors
    assert answers[0] == answers[1] and answers[0]
    assert len(connects) == len(set(connects)) == 2
