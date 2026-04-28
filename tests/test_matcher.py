# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any

import pytest

from licenseid.matcher import AggregatedLicenseMatcher


@pytest.mark.skipif(
    os.getenv("SPDX_TOOLS_JAR") is None, reason="SPDX_TOOLS_JAR not set"
)
def test_matcher_detects_bundled_jar() -> None:
    """Verify that the matcher correctly identifies the jar in the tests directory."""
    jar_path = os.getenv("SPDX_TOOLS_JAR")
    assert jar_path is not None
    assert jar_path.endswith(".jar")
    assert os.path.exists(jar_path)

    matcher = AggregatedLicenseMatcher("dummy.db")
    assert matcher.jar_path == jar_path
    assert matcher.has_java is True


def test_hybrid_search_flow(tmp_path: Any) -> None:
    """Verify the 3-tier hybrid search flow."""
    db_path = str(tmp_path / "test.db")
    from licenseid.database import LicenseDatabase

    LicenseDatabase(db_path)  # Initialize schema

    # Manually populate DB for testing
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        # MIT text fingerprint
        mit_text = (
            "permission is hereby granted free of charge to any person obtaining a copy"
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?)",
            ("MIT", "MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            ("MIT", mit_text),
        )

        # Verify insertion
        row = conn.execute(
            "SELECT count(*) FROM license_index WHERE search_text MATCH 'permission'"
        ).fetchone()
        assert row[0] == 1, "FTS5 index verification failed: 'permission' not found."

    matcher = AggregatedLicenseMatcher(db_path)
    input_text = "Permission is hereby granted, free of charge, to any person obtaining a copy of this software"

    # Verify DB search directly
    candidates = matcher.db.search_candidates(input_text)
    assert len(candidates) > 0, f"DB search_candidates failed for '{input_text}'"
    assert candidates[0]["license_id"] == "MIT"

    # Tier 1 & 2: MIT match (Java off by default)
    results = matcher.match(input_text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"
    assert "java_verified" not in results[0]

    # Tier 3: Enable Java
    matcher_with_java = AggregatedLicenseMatcher(db_path, enable_java=True)
    results_with_java = matcher_with_java.match(input_text)
    assert len(results_with_java) > 0
    # If java verified it, it will have the flag
    if results_with_java[0].get("java_verified"):
        assert results_with_java[0]["score"] == 1.0


def test_short_text_rejection(tmp_path: Any) -> None:
    """Verify that inputs with fewer than 20 normalized words use fallback logic."""
    db_path = str(tmp_path / "test.db")
    from licenseid.database import LicenseDatabase
    import sqlite3

    LicenseDatabase(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?)",
            ("MIT", "MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?)",
            ("APSL-2.0", "Apple Public Source License 2.0", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?)",
            ("AML", "Apple MIT License", True, True),
        )

    matcher = AggregatedLicenseMatcher(db_path)

    # Empty strings
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
