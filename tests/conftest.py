# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Shared test configuration and fixtures for licenseid.
"""

import builtins
import re
import sqlite3
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests

from licenseid import console
from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase
from licenseid.errors import LicenseIdError
from licenseid.matcher import AggregatedLicenseMatcher

# LEVEL: SUBJECT: CONDITION[: DETAIL][; ACTION] -- see AGENTS.md "CLI output".
# The subject is a lowercase word or file name; the condition starts
# lowercase or with a digit. DETAIL may be third-party text, so the end of
# the line is not constrained here.
DIAGNOSTIC_RE = re.compile(r"(ERROR|WARNING): [a-z][a-z0-9._-]*: [a-z0-9].*")


@pytest.fixture(autouse=True)
def check_diagnostic_grammar(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Fail any test whose run prints an ERROR/WARNING line that breaks the
    message grammar. Violations are collected and reported at teardown, so
    a broad ``except Exception`` in the code under test cannot hide them."""
    violations: list[str] = []

    def checked_print(*args: Any, **kwargs: Any) -> None:
        text = " ".join(str(arg) for arg in args)
        if text.startswith(("ERROR:", "WARNING:")) and not DIAGNOSTIC_RE.fullmatch(
            text
        ):
            violations.append(text)
        builtins.print(*args, **kwargs)

    monkeypatch.setattr(console, "print", checked_print, raising=False)
    # A test that ends mid progress line must not shift the next test's output.
    # pylint: disable-next=protected-access
    monkeypatch.setitem(console._state, "line_open", False)
    yield
    assert not violations, f"diagnostics break the message grammar: {violations}"


def seed_ready_metadata(db_path: str) -> None:
    """Record what an update records: the license list version and the current
    normalisation version. With at least one license row the database is then
    ready (see licenseid.dbcheck) and prints no normalisation warning. Safe to
    call on a database that already has these keys."""
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            [
                ("license_list_version", "3.30"),
                ("normalization_version", NORMALIZATION_VERSION),
            ],
        )


def make_memory_db_path(name_prefix: str) -> tuple[str, sqlite3.Connection]:
    """Create a shared-cache in-memory SQLite DB with the licenseid schema
    initialised, for tests that seed their own rows directly via sqlite3.

    Returns (db_path, keep_alive_connection). A shared-cache in-memory DB
    is dropped the instant it has zero open connections, so the
    keep-alive connection is opened *before* constructing LicenseDatabase
    (whose own internal keep-alive connection is otherwise unreferenced
    and can be garbage-collected immediately after __init__ returns,
    which — since CPython deallocates it synchronously — can drop the
    shared-cache DB, including the schema __init__ just created, before
    the caller ever gets a chance to use it). Opening ours first ensures
    at least one connection is alive continuously across that handoff.
    Callers here only need the bare path (not a LicenseDatabase instance)
    to hand to AggregatedLicenseMatcher/MarkerDetector. The caller must
    close the returned connection (e.g. in a fixture's teardown) once the
    test is done with the DB.
    """
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:{name_prefix}_{db_id}?mode=memory&cache=shared"
    keep_alive = sqlite3.connect(db_path, uri=True)
    LicenseDatabase(db_path)
    seed_ready_metadata(db_path)
    return db_path, keep_alive


MIT_SEARCH_TEXT = (
    "permission is hereby granted free of charge to any person obtaining a copy"
)


def insert_mit_license(conn: sqlite3.Connection) -> None:
    """Add MIT (SPDX, OSI- and FSF-approved), indexed by MIT_SEARCH_TEXT."""
    conn.execute(
        "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
        "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
        ("MIT", "MIT License", True, True, True),
    )
    conn.execute(
        "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
        ("MIT", MIT_SEARCH_TEXT),
    )


def make_mit_db_path(
    name_prefix: str, last_check_datetime: str
) -> tuple[str, sqlite3.Connection]:
    """make_memory_db_path() seeded with one license, MIT (SPDX, OSI- and
    FSF-approved), indexed by MIT_SEARCH_TEXT. Same keep-alive contract."""
    db_path, keep_alive = make_memory_db_path(name_prefix)
    with sqlite3.connect(db_path, uri=True) as conn:
        insert_mit_license(conn)
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", last_check_datetime),
        )
    return db_path, keep_alive


def make_ready_db_path(name_prefix: str) -> tuple[str, sqlite3.Connection]:
    """A database that is ready and silent: MIT, the license list version,
    a fresh check time and the current normalisation version, so a command
    on it prints no warning. Same keep-alive contract as make_memory_db_path."""
    return make_mit_db_path(name_prefix, datetime.now(timezone.utc).isoformat())


@pytest.fixture
def ordering_matcher() -> Generator[AggregatedLicenseMatcher, None, None]:
    """A matcher over a one-license database, for tests that call its ordering
    methods directly (tests/test_match_ordering*.py)."""
    db_path, keep_alive = make_mit_db_path(
        "test_match_ordering", datetime.now(timezone.utc).isoformat()
    )
    yield AggregatedLicenseMatcher(db_path)
    keep_alive.close()


def assert_cached_tarball_removed(db: LicenseDatabase, tar_path: Path) -> None:
    """Building from an unusable cached tarball (corrupt, truncated or
    unsafe) fails with the grammar message and deletes the file."""
    with pytest.raises(
        LicenseIdError,
        match=rf"^{re.escape(tar_path.name)}: cache unusable: .*; removed, run",
    ):
        db._process_and_store(  # pylint: disable=protected-access
            tar_path, {}, None
        )
    assert not tar_path.exists()


def leftover_tmp_files(directory: Path) -> list[Path]:
    """Temporary files (*.tmp) left in *directory*."""
    return list(directory.glob("*.tmp"))


def fake_requests_get(
    monkeypatch: pytest.MonkeyPatch,
    text: str = "",
    error: Exception | None = None,
    status_error: bool = False,
) -> mock.MagicMock:
    """Replace requests.get with an autospec'd fake returning *text*, or
    raising *error* / an HTTP status error."""
    response = mock.create_autospec(requests.Response, instance=True)
    response.text = text
    if status_error:
        response.raise_for_status.side_effect = requests.HTTPError("503")
    fake: mock.MagicMock = mock.create_autospec(requests.get, return_value=response)
    if error is not None:
        fake.side_effect = error
    monkeypatch.setattr(requests, "get", fake)
    return fake


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options for pytest."""
    parser.addoption(
        "--run-benchmark",
        action="store_true",
        default=False,
        help="run benchmark tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "benchmark: mark test as a benchmark")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip benchmark tests by default."""
    if config.getoption("--run-benchmark"):
        # --run-benchmark given in cli: do not skip benchmark tests
        return
    skip_benchmark = pytest.mark.skip(reason="need --run-benchmark option to run")
    for item in items:
        if "benchmark" in item.keywords:
            item.add_marker(skip_benchmark)
