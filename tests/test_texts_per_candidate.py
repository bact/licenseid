# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The coded texts read per candidate, through ``detect()``, ``texts()`` and
``--diff`` (``licenseid.textentries``): a call reads the entries of the texts
it searches and scores, markers and hints included, once each, in one
connection and one transaction, so an ``update`` cannot land between its
reads; threads that start at once load the head once and no entry twice; a
check that fails mid-call gives that call the corpus built in memory."""
# pylint: disable=missing-function-docstring,protected-access

import shutil
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from stored_texts import Counts, all_texts, counting
from template_texts import long_text, template_texts_db

from licenseid import textentries
from licenseid.database import snapshot, text_source
from licenseid.detector import LicenseDetector
from licenseid.gramselect import searched
from licenseid.retrieval import text_candidates
from licenseid.textstore import RawEntry

# The MIT text under a project's line and a copyright line.
MIT = "The widget project uses this licence.\n\n" + long_text("MIT")


@pytest.fixture(name="built", scope="module")
def _built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return template_texts_db(tmp_path_factory.mktemp("per-candidate"))


@pytest.fixture(name="path")
def _path(built: Path, tmp_path: Path) -> Path:
    """A copy of the built database a test may change."""
    path = tmp_path / "licenses.db"
    shutil.copy(built, path)
    return path


@pytest.fixture(name="counts")
def _counts(monkeypatch: pytest.MonkeyPatch) -> Counts:
    return counting(monkeypatch)


def _rows(results: Sequence[Any]) -> list[tuple[object, ...]]:
    return [(r["expression"], r["score"], r["exact"], r["texts"]) for r in results]


def _names(path: Path) -> list[str]:
    with writer(path) as conn:
        return [
            owner
            for (owner,) in conn.execute(
                "SELECT owner_id FROM text_code_checks WHERE owner_id != ''"
            )
        ]


def _searched(detector: LicenseDetector, text: str) -> list[str]:
    """The texts the whole-text search of *text* reads."""
    with snapshot(detector.db):
        texts = text_candidates(detector.db, text)
        return searched(texts.table.rows, text_source(detector.db).core_grams)


def test_a_call_reads_its_candidates_once_in_one_connection(
    path: Path, counts: Counts, opened: list[sqlite3.Connection]
) -> None:
    detector = LicenseDetector(db_path=str(path))
    opened.clear()
    results = detector.detect(MIT)
    assert len(opened) == 1  # every read of the call, the entries included
    assert results[0]["expression"] == "MIT" and results[0]["texts"] == ["MIT"]
    assert len(counts.read) == len(set(counts.read)) < len(_names(path))
    assert counts.builds == 0
    before = list(counts.read)
    assert _rows(detector.detect(MIT)) == _rows(results)
    assert counts.read == before  # kept: the second call reads no entry


def test_texts_alone_reads_the_texts_it_searches(path: Path, counts: Counts) -> None:
    detector = LicenseDetector(db_path=str(path))
    assert detector.texts(MIT) == ["MIT"]
    state = detector.db._tables._keyed.texts._state
    assert isinstance(state, textentries._Stored)
    assert sorted(counts.read) == sorted(state.entries)
    assert len(counts.read) < len(_names(path))


def test_the_entries_of_marker_and_hint_candidates_are_read(
    path: Path, counts: Counts
) -> None:
    """A hint whose text shares no gram with the input is no searched text:
    its entry is read for Tier 2 all the same (its word region)."""
    detector = LicenseDetector(db_path=str(path))
    unsearched = sorted(set(_names(path)) - set(_searched(detector, MIT)))
    assert unsearched
    hint = unsearched[0]
    counts.read.clear()
    results = detector.detect(MIT, hint=[hint])
    assert hint in counts.read
    assert hint in [r["expression"] for r in results] or results[0]["texts"]


def test_a_failed_check_mid_call_gives_that_call_the_built_corpus(
    path: Path, counts: Counts
) -> None:
    """The texts searched are read as stored, then a hint's entry fails its
    check: the call goes on with the corpus built in memory, and answers as
    on the intact file."""
    intact = _rows(LicenseDetector(db_path=str(path)).detect(MIT))
    detector = LicenseDetector(db_path=str(path))
    hint = min(set(_names(path)) - set(_searched(detector, MIT)))
    expected = _rows(LicenseDetector(db_path=str(path)).detect(MIT, hint=[hint]))
    with writer(path) as conn:
        conn.execute(
            "UPDATE text_code_checks SET digest = 'x' WHERE owner_id = ?", (hint,)
        )
    counts.builds = 0
    counts.read.clear()
    found = LicenseDetector(db_path=str(path)).detect(MIT, hint=[hint])
    assert counts.builds == 1 and hint in counts.read
    assert _rows(found) == expected
    assert _rows(found)[0] == intact[0]


def test_diff_reads_the_one_entry_it_aligns(path: Path, counts: Counts) -> None:
    detector = LicenseDetector(db_path=str(path))
    norm, window = detector._diff_pair(MIT[:400], "MIT")
    assert norm and window
    assert counts.read == ["MIT"]


# Another process that writes a new time, waiting for no lock.
WRITER = """
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1], timeout=0)
try:
    conn.execute(
        "UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"
    )
    conn.commit()
    print("committed")
except sqlite3.OperationalError as exc:
    print(exc)
"""


def _try_write(path: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-c", WRITER, str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return done.stdout.strip()


def test_an_update_cannot_land_between_the_reads_of_a_call(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer that tries to commit while the call reads its entries is
    refused: the call holds one read transaction from its postings to its
    entries, the searched texts' and then a hint's for Tier 2. Outside a
    call, the same writer commits."""
    hint = min(set(_names(path)) - set(_searched(LicenseDetector(str(path)), MIT)))
    tried: list[str] = []
    real = textentries.read_raw_entries

    def read(conn: Any, names: Sequence[str], *rest: Any) -> list[RawEntry]:
        tried.append(_try_write(path))
        return real(conn, names, *rest)

    monkeypatch.setattr(textentries, "read_raw_entries", read)
    detector = LicenseDetector(db_path=str(path))
    assert detector.detect(MIT, hint=[hint])[0]["expression"] == "MIT"
    assert len(tried) == 2 and set(tried) == {"database is locked"}
    assert _try_write(path) == "committed"  # outside a call: nothing holds it


def _at_once(count: int, call: Callable[[], object]) -> list[object]:
    start = threading.Barrier(count)
    found: list[object] = []
    errors: list[BaseException] = []

    def run() -> None:
        start.wait()
        try:
            found.append(call())
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not errors
    return found


def test_threads_that_start_at_once_load_the_head_once_and_no_entry_twice(
    path: Path, counts: Counts, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _rows(LicenseDetector(db_path=str(path)).detect(MIT))
    heads: list[object] = []
    real = textentries.TextStore._first

    def first(conn: Any, reads: Any, updated: object) -> Any:
        heads.append(updated)
        return real(conn, reads, updated)

    monkeypatch.setattr(textentries.TextStore, "_first", staticmethod(first))
    counts.read.clear()
    detector = LicenseDetector(db_path=str(path))
    found = _at_once(8, lambda: _rows(detector.detect(MIT)))
    assert found == [expected] * 8
    assert len(heads) == 1
    assert len(counts.read) == len(set(counts.read))
    assert counts.builds == 0


def test_an_input_of_no_candidate_reads_no_entry(path: Path, counts: Counts) -> None:
    detector = LicenseDetector(db_path=str(path))
    text = " ".join(f"zq{i}x" for i in range(60))
    assert detector.detect(text) == []
    assert detector.texts(text) is None
    assert not counts.read


class _Bound:
    """A connection that records the count of values bound to each query."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.bound: list[int] = []

    def execute(self, sql: str, values: Sequence[object] = ()) -> sqlite3.Cursor:
        self.bound.append(len(values))
        return self.conn.execute(sql, values)


@pytest.mark.parametrize(
    ("names", "queries"), [(800, 3), (801, 6), (1600, 6), (1601, 9)]
)
def test_at_most_900_values_are_bound_to_a_query_of_entries(
    names: int, queries: int
) -> None:
    """800 names a query: the codes query binds the four entry kinds too."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE license_texts (search_text TEXT)")
    conn.execute("CREATE TABLE text_codes (kind TEXT, owner_id TEXT, body TEXT)")
    conn.execute("CREATE TABLE text_code_checks (owner_id TEXT, digest TEXT)")
    ids = {f"L{i}": i for i in range(1, names + 1)}
    conn.executemany(
        "INSERT INTO license_texts (rowid, search_text) VALUES (?, ?)",
        [(rowid, f"text {rowid}") for rowid in ids.values()],
    )
    conn.executemany(
        "INSERT INTO text_code_checks VALUES (?, ?)", [(i, "c" + i) for i in ids]
    )
    bound = _Bound(conn)
    groups = textentries.groups_of(ids, {})
    raws = textentries.read_raw_entries(
        cast(sqlite3.Connection, bound), list(groups.first), groups
    )
    assert len(bound.bound) == queries and max(bound.bound) <= 900
    assert [(r.name, r.text, r.check) for r in raws] == [
        (i, f"text {rowid}", "c" + i) for i, rowid in ids.items()
    ]


def test_the_store_follows_the_time_read_in_the_call(
    path: Path, counts: Counts
) -> None:
    """A new ``last_update_datetime`` is seen by the next call, whatever the
    reading block saw first: the head is read again (here it fails, the time
    being written by hand) and the corpus built."""
    detector = LicenseDetector(db_path=str(path))
    with detector.db.reading():
        detector.db.get_license_details("MIT")  # the block's check
        with writer(path) as conn:
            conn.execute(
                "UPDATE db_metadata SET value = 'later'"
                " WHERE key = 'last_update_datetime'"
            )
        counts.builds = 0
        corpus = all_texts(detector.db, ["MIT"])
    assert counts.builds == 1
    assert corpus.entries[0].text.row_id == "MIT"


def test_a_store_reads_the_head_again_at_another_time(path: Path) -> None:
    """The store keeps a state for the time it was read at only: a new time
    (here written by hand, so the head fails and the corpus is built) gives
    another state, whatever the cache above it holds."""
    reads = LicenseDetector(db_path=str(path)).db._tables.texts()
    store = textentries.TextStore()
    first = store.state(reads)
    assert isinstance(first, textentries._Stored)
    assert store.state(reads) is first
    with writer(path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = 'later' WHERE key = 'last_update_datetime'"
        )
    later = store.state(reads)
    assert isinstance(later, textentries._Built) and later.updated == "later"


def test_a_load_for_a_time_the_store_left_is_not_published(path: Path) -> None:
    """A thread that loads entries for a time while another has moved the
    store to a newer one gets its corpus, and leaves the newer state alone."""
    reads = LicenseDetector(db_path=str(path)).db._tables.texts()
    store = textentries.TextStore()
    state = store.state(reads)
    assert isinstance(state, textentries._Stored)
    newer = state._replace(updated="newer")
    store._state = newer
    corpus, loaded = store.cut(reads, state, ["MIT"])
    assert [e.text.row_id for e in corpus.entries] == ["MIT"]
    assert isinstance(loaded, textentries._Stored) and "MIT" in loaded.entries
    assert store._state is newer


def test_a_load_after_another_thread_built_the_corpus_takes_it(path: Path) -> None:
    """A thread that waited for the lock while another found damage and
    built the corpus for the same time cuts from that corpus."""
    reads = LicenseDetector(db_path=str(path)).db._tables.texts()
    store = textentries.TextStore()
    state = store.state(reads)
    assert isinstance(state, textentries._Stored)
    with reads.connection() as conn:
        built = textentries._built(conn, reads.text_parts(), state.updated)
    store._state = built
    corpus, loaded = store.cut(reads, state, ["MIT"])
    assert loaded is built and [e.text.row_id for e in corpus.entries] == ["MIT"]
