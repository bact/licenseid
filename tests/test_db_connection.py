# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""One connection per match: ``LicenseDatabase.reading()`` (roadmap item 29),
and the Tier 0 scorers' early stop (item 27)."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import contextlib
import sqlite3
import threading
from collections.abc import Callable, Generator
from typing import Any
from unittest import mock

import pytest
from matcher_db import GPL2_ROWS, Lic, seeded_db
from rapidfuzz import fuzz

from licenseid import shorttext
from licenseid.database import LicenseDatabase
from licenseid.dbconnection import Connections
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text

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


@pytest.fixture
def opened() -> Generator[list[sqlite3.Connection], None, None]:
    """Every connection opened while the test runs."""
    conns: list[sqlite3.Connection] = []
    real = Connections.connect

    def track(self: Connections) -> sqlite3.Connection:
        conn = real(self)
        conns.append(conn)
        return conn

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=track):
        yield conns


def _is_closed(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


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
        assert len(opened) == 1 and not _is_closed(opened[0])
        if raises:
            raise RuntimeError("boom")
    assert len(opened) == 1 and _is_closed(opened[0])


def test_a_block_opens_lazily_and_a_query_outside_closes_its_own(
    db_path: str, opened: list[sqlite3.Connection]
) -> None:
    db = LicenseDatabase(db_path)
    opened.clear()
    with db.reading():
        pass
    assert not opened
    _lookups(db)
    assert len(opened) == 4 and all(_is_closed(c) for c in opened)


def test_a_write_in_a_block_is_committed(db_path: str) -> None:
    db = LicenseDatabase(db_path)
    with db.reading(), db._connection() as conn:
        conn.execute("INSERT INTO db_metadata VALUES ('block_key', 'kept')")
    with sqlite3.connect(db_path, uri=True) as other:
        row = other.execute(
            "SELECT value FROM db_metadata WHERE key = 'block_key'"
        ).fetchone()
    assert row == ("kept",)


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
    assert len(opened) == 1 and _is_closed(opened[0])
    # The shared-cache database outlives the block: the keep-alive holds it.
    assert call(matcher)


def test_two_threads_match_on_one_matcher(db_path: str) -> None:
    """sqlite3 refuses a connection made in another thread, so each thread
    needs its own. The barrier holds both threads in their block at once."""
    matcher = AggregatedLicenseMatcher(db_path)
    barrier = threading.Barrier(2, timeout=10)
    real = Connections.connect
    answers: dict[int, list[str]] = {}
    errors: list[BaseException] = []

    def connect_together(self: Connections) -> sqlite3.Connection:
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


# Tier 0: the cutoff stops RapidFuzz early and changes no result.

SHORT_INPUTS = [
    "MIT",
    "mit licence",
    "Apache License 2.0",
    "apache licence 2",
    "GNU General Public License v2.0",
    "gnu general public licence version 2",
    "GPL-2",
    "BSD",
    "BSD 3-Clause New or Revised",
    "the",
    "MIT License for everyone who wants it",
    "本ライセンスは",
    "a" * 2_000,
]


def _no_cutoff(scorer: Callable[..., float]) -> Callable[..., float]:
    def score(a: str, b: str, **_: Any) -> float:
        return scorer(a, b)

    return score


def test_the_cutoff_changes_no_short_text_result(db_path: str) -> None:
    db = LicenseDatabase(db_path)
    reference = mock.Mock(
        ratio=_no_cutoff(fuzz.ratio),
        partial_ratio=_no_cutoff(fuzz.partial_ratio),
        token_set_ratio=_no_cutoff(fuzz.token_set_ratio),
    )
    norms = [normalize_text(t) for t in SHORT_INPUTS]
    with mock.patch.object(shorttext, "fuzz", reference):
        expected = [shorttext.match_short_text(db, n) for n in norms]
    assert [shorttext.match_short_text(db, n) for n in norms] == expected
    # Most inputs reach a fuzzy match, or the comparison proves little.
    assert sum(map(bool, expected)) >= 6


@pytest.mark.parametrize(
    ("text", "threshold"), [("mit licence", 90.0), ("a b c", 85.0)]
)
def test_every_scorer_stops_at_the_threshold(
    db_path: str, text: str, threshold: float
) -> None:
    """A long word against every row took seconds without the cutoff."""
    db = LicenseDatabase(db_path)
    spy = mock.Mock(wraps=fuzz)
    with mock.patch.object(shorttext, "fuzz", spy):
        shorttext.match_short_text(db, text)
    calls = [
        *spy.ratio.call_args_list,
        *spy.partial_ratio.call_args_list,
        *spy.token_set_ratio.call_args_list,
    ]
    assert calls
    assert {c.kwargs.get("score_cutoff") for c in calls} == {threshold}
