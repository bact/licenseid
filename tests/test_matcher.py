# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for AggregatedLicenseMatcher hybrid search flow."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring

import os
import sqlite3
import uuid
from typing import Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture(scope="module")
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_matcher_{db_id}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        mit_text = (
            "permission is hereby granted free of charge to any person obtaining a copy"
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("MIT", "MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("APSL-2.0", "Apple Public Source License 2.0", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("AML", "Apple MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            ("MIT", mit_text),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
        conn.commit()

    yield db_path
    keep_alive.close()


@pytest.mark.skipif(
    os.getenv("SPDX_TOOLS_JAR") is None, reason="SPDX_TOOLS_JAR not set"
)
def test_matcher_detects_bundled_jar(test_db: str) -> None:
    jar_path = os.getenv("SPDX_TOOLS_JAR")
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.jar_path == jar_path
    assert matcher.has_java is True


def test_hybrid_search_flow(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    input_text = (
        "Permission is hereby granted, free of charge, to any person"
        " obtaining a copy of this software"
    )

    results = matcher.match(text=input_text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"

    if matcher.has_java and matcher.jar_path:
        matcher_with_java = AggregatedLicenseMatcher(test_db, enable_java=True)
        results_with_java = matcher_with_java.match(text=input_text)
        assert len(results_with_java) > 0
        if results_with_java[0].get("java_verified"):
            assert results_with_java[0]["score"] == 1.0


def test_short_text_rejection(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)

    assert not matcher.match("")
    assert not matcher.match("   ")
    assert not matcher.match("\n\n")

    # Generic short string (should fail name matching because threshold is 90/85)
    assert not matcher.match("This")
    assert not matcher.match("Copyright 2024.")
    assert not matcher.match("One two three four")

    # Exact name matches (< 12 words)
    res_mit = matcher.match("MIT")
    assert res_mit and res_mit[0]["license_id"] == "MIT"
    res_aml = matcher.match("Apple MIT License")
    assert res_aml and res_aml[0]["license_id"] == "AML"

    # Partial name matches (< 12 words)
    res_apple = matcher.match("APPLE PUBLIC SOURCE LICENSE")
    assert len(res_apple) > 0 and res_apple[0]["license_id"] == "APSL-2.0"
