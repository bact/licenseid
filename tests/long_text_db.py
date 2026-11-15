# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The database of the long-text fixtures: one build for the accuracy tests
(``test_accuracy.matcher``) and the detector goldens (``harness_db``)."""

import json
import sqlite3
from functools import lru_cache
from pathlib import Path

from conftest import seed_ready_metadata
from seed_sql import INSERT_INDEX

from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.fingerprintstore import store_fingerprints
from licenseid.normalize import normalize_text

LONG_TEXTS = Path(__file__).parent / "fixtures" / "license-text-long"
_DB_PATH = "file:long_text_detector?mode=memory&cache=shared"
_KEEP_ALIVE: list[object] = []

_LICENSE_SQL = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
    "is_fsf_libre, is_high_usage, is_deprecated, superseded_by, pop_score, "
    "word_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def long_text_rows() -> tuple[list[tuple[object, ...]], list[tuple[str, str]]]:
    """The ``licenses`` and ``license_index`` rows of every long-text fixture,
    in file-name order (the order does not change what a query returns)."""
    licenses: list[tuple[object, ...]] = []
    index: list[tuple[str, str]] = []
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
    return licenses, index


@lru_cache(maxsize=1)
def long_text_detector() -> LicenseDetector:
    """A detector over a shared in-memory database of the long-text fixtures
    (read only: a test must not write to it).

    The fingerprints are stored after the index, as a production build does
    (``LicenseDatabase._update_db_records``): without them near-duplicate
    texts (ISC and Python-2.0, the BSD variants) lose their only signal once
    copyright-notice text is normalised away."""
    manager = LicenseDatabase(_DB_PATH)  # opened first: it keeps the DB alive
    _KEEP_ALIVE.append(manager)
    licenses, index = long_text_rows()
    with sqlite3.connect(_DB_PATH, uri=True) as conn:
        conn.executemany(_LICENSE_SQL, licenses)
        conn.executemany(INSERT_INDEX, index)
    store_fingerprints(manager._connections)  # pylint: disable=protected-access
    seed_ready_metadata(_DB_PATH)
    return LicenseDetector(_DB_PATH)
