# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The database of the detector goldens: every licence of the long-text
fixtures, built once per process like ``test_accuracy.matcher`` (its build,
kept here because a fixture of a test module cannot be shared)."""

import json
import sqlite3
from functools import lru_cache
from pathlib import Path

from conftest import make_memory_db_path, seed_ready_metadata
from resolver_corpus import NEIGHBOURS, corpus_db_path
from seed_sql import INSERT_INDEX

from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.fingerprintstore import store_fingerprints
from licenseid.normalize import normalize_text

LONG_TEXTS = Path(__file__).parent / "fixtures" / "license-text-long"
_DB_PATH = "file:harness_detector?mode=memory&cache=shared"
_KEEP_ALIVE: list[object] = []

_LICENSE_SQL = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
    "is_fsf_libre, is_high_usage, is_deprecated, superseded_by, pop_score, "
    "word_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


@lru_cache(maxsize=1)
def harness_detector() -> LicenseDetector:
    """A detector over a shared in-memory database of the long-text fixtures
    (read only: a test must not write to it)."""
    manager = LicenseDatabase(_DB_PATH)  # opened first: it keeps the DB alive
    _KEEP_ALIVE.append(manager)
    licenses, index = [], []
    for path in sorted(LONG_TEXTS.glob("*.json"), key=lambda p: p.name):
        data = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_text(data["license_text"])
        licenses.append(
            (
                data["license_id"],
                data.get("name", data["license_id"]),
                data.get("is_spdx", True),
                data.get("is_osi_approved", False),
                data.get("is_fsf_libre", False),
                data.get("is_high_usage", False),
                data.get("is_deprecated", False),
                data.get("superseded_by"),
                data.get("pop_score", 1),
                len(normalized.split()),
            )
        )
        index.append((data["license_id"], normalized))
    with sqlite3.connect(_DB_PATH, uri=True) as conn:
        conn.executemany(_LICENSE_SQL, licenses)
        conn.executemany(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)", index
        )
    store_fingerprints(manager._connections)  # pylint: disable=protected-access
    seed_ready_metadata(_DB_PATH)
    return LicenseDetector(_DB_PATH)


@lru_cache(maxsize=1)
def value_detector() -> LicenseDetector:
    """A detector over the database of the resolver corpus (every licence and
    exception of the List) with the text of every long-text fixture, so the
    text tiers have what the real List gives them (read only)."""
    paths = corpus_db_path("harness_value", make_memory_db_path)
    path = next(paths)
    _KEEP_ALIVE.append(paths)  # its keep-alive connection closes at the end
    manager = LicenseDatabase(path)
    _KEEP_ALIVE.append(manager)
    texts = []
    for text_file in sorted(LONG_TEXTS.glob("*.json"), key=lambda p: p.name):
        if text_file.stem not in NEIGHBOURS:
            data = json.loads(text_file.read_text(encoding="utf-8"))
            texts.append((data["license_id"], normalize_text(data["license_text"])))
    with sqlite3.connect(path, uri=True) as conn:
        conn.executemany(INSERT_INDEX, texts)
    store_fingerprints(manager._connections)  # pylint: disable=protected-access
    return LicenseDetector(path)


def detector_for(kind: str) -> LicenseDetector:
    """The detector a golden *kind* runs on."""
    return value_detector() if kind == "value" else harness_detector()
