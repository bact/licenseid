# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Shared test configuration and fixtures for licenseid.
"""

import builtins
import json
import re
import sqlite3
import sys
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests
from click.testing import CliRunner, Result
from packaged_list import database_of, fixture_bundle
from resolver_corpus import corpus_db_path

from licenseid import console, keptdetector, listindex, listsource, spdxdata
from licenseid.cli import cli
from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase
from licenseid.dbconnection import Connections
from licenseid.detector import LicenseDetector
from licenseid.errors import LicenseIdError
from licenseid.records import BUILD_VERSION
from licenseid.result import read_text_field
from licenseid.types import Detection, Method

# tools/cli_matrix drives real shells and terminals (pwd, pty, termios): POSIX
# only, so its tests are not collected on Windows.
collect_ignore: list[str] = ["test_cli_matrix.py"] if sys.platform == "win32" else []

# Tests that need POSIX permission bits, symlinks, signals or /bin/sh. On
# Windows chmod only sets a read-only flag and symlinks need a privilege.
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX permissions, symlinks or signals"
)

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


_REAL_GET = requests.get
_REAL_PACKAGED_BUNDLE = spdxdata.packaged_bundle


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """No test reaches the network or sees the snapshot a wheel build ships.
    A test fakes ``requests.get`` itself (``fake_requests_get``,
    ``release_fakes.serve``) and ships a snapshot of its own
    (``release_fakes.ship``). The packaged index ``match()`` keeps, and
    the fallback warnings it said, are forgotten before and after: a test
    sees only its own snapshot (review gap G7)."""
    monkeypatch.setattr(
        requests,
        "get",
        mock.create_autospec(
            _REAL_GET, side_effect=requests.ConnectionError("offline: a test")
        ),
    )
    monkeypatch.setattr(
        spdxdata,
        "packaged_bundle",
        mock.create_autospec(_REAL_PACKAGED_BUNDLE, return_value=None),
    )
    _forget_packaged()
    yield
    _forget_packaged()


def _forget_packaged() -> None:
    listindex.reset_packaged_index()
    listsource.reset_warnings()
    listsource.reset_choice()
    keptdetector.reset()


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
                ("build_version", BUILD_VERSION),
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
    to hand to LicenseDetector/MarkerDetector. The caller must
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
def ordering_matcher() -> Generator[LicenseDetector, None, None]:
    """A matcher over a one-license database, for tests that call its ordering
    methods directly (tests/test_match_ordering*.py)."""
    db_path, keep_alive = make_mit_db_path(
        "test_match_ordering", datetime.now(timezone.utc).isoformat()
    )
    yield LicenseDetector(db_path)
    keep_alive.close()


def assert_cached_tarball_removed(
    db: LicenseDatabase, tar_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unusable cached tarball (corrupt, truncated or unsafe) beside *db*
    is reported in one grammar line and deleted, and update downloads it
    again: here the network is down (the autouse ``offline`` fixture), so
    that is the error."""
    capsys.readouterr()
    name = re.escape(tar_path.name)
    version = tar_path.name.removeprefix("spdx-data-v").removesuffix(".tar.gz")
    with pytest.raises(LicenseIdError, match=rf"^{name}: download failed: "):
        db.update_from_remote(version=version, source="upstream")
    warnings = [
        line for line in capsys.readouterr().err.splitlines() if "WARNING" in line
    ]
    assert [w for w in warnings if w.startswith(f"WARNING: {tar_path.name}")]
    assert re.fullmatch(
        rf"WARNING: {name}: cache unusable: .+; downloading", warnings[-1]
    )
    assert not tar_path.exists()


# The keys of every detect() result and --json line (types.Detection).
RESULT_KEYS = frozenset(
    {
        "expression",
        "method",
        "exact",
        "score",
        "similarity",
        "coverage",
        "is_spdx",
        "is_osi_approved",
        "is_fsf_libre",
    }
)


def public_match(  # pylint: disable=too-many-arguments
    license_id: str = "MIT",
    *,
    method: Method = "tag",
    exact: bool = True,
    score: float = 1.0,
    similarity: float | None = None,
    coverage: float | None = None,
) -> Detection:
    """A result as detect() returns it, for the code that prints one."""
    return Detection(
        expression=license_id,
        method=method,
        exact=exact,
        score=score,
        similarity=similarity,
        coverage=coverage,
        is_spdx=True,
        is_osi_approved=True,
        is_fsf_libre=False,
    )


def invoke_match(db: str, *args: str, color: bool = False) -> Result:
    """``licenseid --db <db> detect <args>`` through click's runner."""
    return CliRunner().invoke(cli, ["--db", db, "detect", *args], color=color)


# The flag each is-* command prints after EXPRESSION.
PREDICATE_KEYS = {
    "is-osi": "IS_OSI_APPROVED",
    "is-fsf": "IS_FSF_LIBRE",
    "is-open": "IS_OPEN",
    "is-free": "IS_FREE",
    "is-spdx": "IS_SPDX",
}


def predicate_line(command: str, expression: str, answer: bool) -> str:
    """The line ``licenseid <command>`` prints: the ID judged (empty for
    none) and its flag."""
    flag = "true" if answer else "false"
    return f"EXPRESSION={expression}\t{PREDICATE_KEYS[command]}={flag}\n"


def update_line(status: str, version: str, path: object) -> str:
    """The line ``licenseid update`` prints."""
    return f"STATUS={status}\tVERSION={version}\tPATH={path}\n"


def line_fields(line: str) -> dict[str, str]:
    """The ``KEY=VALUE`` fields of one result line, each value read back
    (``result.read_text_field``)."""
    pairs = (field.partition("=") for field in line.split("\t"))
    return {key: read_text_field(value) for key, _, value in pairs}


def json_lines(stdout: str) -> list[dict[str, Any]]:
    """The results `detect --json` printed: one JSON object per line."""
    return [json.loads(line) for line in stdout.splitlines()]


@pytest.fixture
def opened() -> Generator[list[sqlite3.Connection], None, None]:
    """Every database connection licenseid opens while the test runs."""
    conns: list[sqlite3.Connection] = []
    real = Connections.connect

    def track(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conns.append(conn)
        return conn

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=track):
        yield conns


@pytest.fixture
def connects() -> Generator[list[bool], None, None]:
    """The ``write`` flag of every connection licenseid opens in the test."""
    flags: list[bool] = []
    real = Connections.connect

    def record(self: Connections, write: bool = False) -> sqlite3.Connection:
        flags.append(write)
        return real(self, write)

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=record):
        yield flags


def is_closed(conn: sqlite3.Connection) -> bool:
    """Whether *conn* was closed."""
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


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
    fake: mock.MagicMock = mock.create_autospec(_REAL_GET, return_value=response)
    if error is not None:
        fake.side_effect = error
    monkeypatch.setattr(requests, "get", fake)
    return fake


@pytest.fixture(scope="session")
def corpus_db() -> Generator[LicenseDatabase, None, None]:
    """A database of the whole SPDX 3.29.0 List (every licence and exception,
    the text of the near neighbours of the resolver corpus), built once per
    session. Read only: a test must not write to it."""
    for path in corpus_db_path("corpus", make_memory_db_path):
        yield LicenseDatabase(path, create=False)


@pytest.fixture(scope="session")
def bundle_db(tmp_path_factory: pytest.TempPathFactory) -> LicenseDatabase:
    """The database ``update --source packaged`` builds from
    ``packaged_list.fixture_bundle()`` (the 3.29.0 List of the fixtures),
    built once per session. Read only: a test must not write to it."""
    path = tmp_path_factory.mktemp("bundle_db") / "licenses.db"
    return database_of(fixture_bundle(), path)


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


# pytest puts the running test's ID in PYTEST_CURRENT_TEST, and Windows
# refuses an environment variable over 32,767 characters: a huge parameter
# used as its own ID errors there only. Give such a parameter a short id.
MAX_TEST_ID = 300


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Refuse an overlong test ID; skip benchmark tests by default."""
    long_ids = [item.nodeid[:80] for item in items if len(item.nodeid) > MAX_TEST_ID]
    if long_ids:
        raise pytest.UsageError(
            f"test IDs over {MAX_TEST_ID} characters; give the parameter an id: "
            + ", ".join(long_ids)
        )
    if config.getoption("--run-benchmark"):
        # --run-benchmark given in cli: do not skip benchmark tests
        return
    skip_benchmark = pytest.mark.skip(reason="need --run-benchmark option to run")
    for item in items:
        if "benchmark" in item.keywords:
            item.add_marker(skip_benchmark)
