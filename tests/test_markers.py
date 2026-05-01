# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for license marker and heading detection."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring

import sqlite3
import uuid
from typing import Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_markers_{db_id}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "MIT",
                "permission is hereby granted free of charge to any person "
                "obtaining a copy",
            ),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "Apache-2.0",
                "apache license version 2.0 provides a grant of copyright license",
            ),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
    yield db_path
    keep_alive.close()


def test_spdx_identifier(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "Some source code\nSPDX-License-Identifier: MIT\nMore code"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"
    assert results[0]["score"] >= 0.95


def test_license_field(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "Metadata:\nLicense: Apache License 2.0\nVersion: 1.0"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "Apache-2.0"


def test_markdown_heading(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "# README\n\n## License\n\nMIT"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"


def test_ascii_heading_underline(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "LICENSE\n=======\n\nApache License 2.0"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "Apache-2.0"


def test_ascii_heading_box(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "#################\n#    LICENSE    #\n#################\n\nMIT"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"


def test_mixed_content_windowed_search(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    # A large README with license info buried
    text = (
        "Project Name\n"
        + "Junk text " * 100
        + "\nLicense\n"
        + "Permission is hereby granted free of charge to any person obtaining a copy"
        + "\n"
        + "More junk " * 100
    )
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"
