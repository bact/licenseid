# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The databases of the detector goldens: the long-text fixtures
(``long_text_db``, shared with ``test_accuracy.matcher``) and the resolver
corpus with their texts."""

import json
import sqlite3
from functools import lru_cache

from conftest import make_memory_db_path
from long_text_db import LONG_TEXTS, long_text_detector
from resolver_corpus import NEIGHBOURS, corpus_db_path
from seed_sql import INSERT_INDEX

from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.fingerprintstore import store_fingerprints
from licenseid.normalize import normalize_text

_KEEP_ALIVE: list[object] = []


def harness_detector() -> LicenseDetector:
    """A detector over a shared in-memory database of the long-text fixtures
    (read only: a test must not write to it)."""
    return long_text_detector()


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
