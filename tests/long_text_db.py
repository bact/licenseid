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
from licenseid.records import core_of, same_text_of, uneven_cores

LONG_TEXTS = Path(__file__).parent / "fixtures" / "license-text-long"
# Real templates of a few licences, for the fixtures generated before
# scripts/generate_fixtures.py wrote ``license_template`` (tests/fixtures/README.md).
TEMPLATES = Path(__file__).parent / "fixtures" / "license-template"
DB_PATH = "file:long_text_detector?mode=memory&cache=shared"
_KEEP_ALIVE: list[object] = []

_LICENSE_SQL = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
    "is_fsf_libre, is_high_usage, is_deprecated, superseded_by, pop_score, "
    "word_count, core_text, core_word_count, same_text) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def fixture_template(data: dict[str, object]) -> str | None:
    """The template of a long-text fixture: its ``license_template``, else
    the file of its ID in TEMPLATES, else None (no core)."""
    template = data.get("license_template")
    if isinstance(template, str):
        return template
    path = TEMPLATES / f"{data['license_id']}.template.txt"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def long_text_rows() -> tuple[list[tuple[object, ...]], list[tuple[str, str]]]:
    """The ``licenses`` and ``license_index`` rows of every long-text fixture,
    in file-name order (the order does not change what a query returns),
    with the core of each that has a template (``records.core_of``) and the
    ``same_text`` of each, as a production build keeps them."""
    licenses: list[tuple[object, ...]] = []
    index: list[tuple[str, str]] = []
    cores: dict[str, str | None] = {}
    for path in sorted(LONG_TEXTS.glob("*.json"), key=lambda p: p.name):
        data = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_text(data["license_text"])
        word_count = len(normalized.split())
        core, core_words = core_of(fixture_template(data), word_count)
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
                word_count,
                core,
                core_words,
            )
        )
        index.append((data["license_id"], normalized))
        cores[data["license_id"]] = core
    return _with_same_text(licenses, index, cores), index


def _with_same_text(
    licenses: list[tuple[object, ...]],
    index: list[tuple[str, str]],
    cores: dict[str, str | None],
) -> list[tuple[object, ...]]:
    """*licenses* with the ``same_text`` of a production build and without
    the cores it drops (``records.same_text_of``, ``records.uneven_cores``)."""
    twins = same_text_of(index)
    dropped = uneven_cores(twins, cores)
    return [
        (
            *row[:10],
            *((None, None) if row[0] in dropped else row[10:]),
            twins.get(str(row[0])),
        )
        for row in licenses
    ]


@lru_cache(maxsize=1)
def long_text_detector() -> LicenseDetector:
    """A detector over a shared in-memory database of the long-text fixtures
    (read only: a test must not write to it).

    The fingerprints are stored after the index, as a production build does
    (``LicenseDatabase._update_db_records``): without them near-duplicate
    texts (ISC and Python-2.0, the BSD variants) lose their only signal once
    copyright-notice text is normalised away."""
    manager = LicenseDatabase(DB_PATH)  # opened first: it keeps the DB alive
    _KEEP_ALIVE.append(manager)
    licenses, index = long_text_rows()
    with sqlite3.connect(DB_PATH, uri=True) as conn:
        conn.executemany(_LICENSE_SQL, licenses)
        conn.executemany(INSERT_INDEX, index)
    store_fingerprints(manager._connections)  # pylint: disable=protected-access
    seed_ready_metadata(DB_PATH)
    return LicenseDetector(DB_PATH)
