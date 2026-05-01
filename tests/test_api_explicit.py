# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Explicit API tests for licenseid."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring

import sqlite3
from typing import Any, Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    import uuid

    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_api_{db_id}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
    # Keep a connection open to keep the in-memory DB alive
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
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
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )

    yield db_path
    keep_alive.close()
    # The database will be destroyed when the last connection is closed
    # which happens after the test ends and db_manager/matcher are GC'd


def test_match_explicit_id(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)

    # Normal ID
    res = matcher.match(license_id="MIT")
    assert len(res) == 1
    assert res[0]["license_id"] == "MIT"
    assert res[0]["score"] == 1.0

    # Case-insensitive and trimmed ID
    res = matcher.match(license_id=" mit ")
    assert len(res) == 1
    assert res[0]["license_id"] == "MIT"

    # Non-existent ID
    res = matcher.match(license_id="NonExistent")
    assert len(res) == 0


def test_match_explicit_file(test_db: str, tmp_path: Any) -> None:
    # We still need tmp_path for the actual file input test

    matcher = AggregatedLicenseMatcher(test_db)

    license_file = tmp_path / "LICENSE"
    license_file.write_text(
        "Permission is hereby granted, free of charge, to any person obtaining a copy"
    )

    res = matcher.match(file_path=str(license_file))
    assert len(res) == 1
    assert res[0]["license_id"] == "MIT"


def test_match_explicit_text(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)

    text = (
        "Permission is hereby granted, free of charge, to any person obtaining a copy"
    )
    res = matcher.match(text=text)
    assert len(res) == 1
    assert res[0]["license_id"] == "MIT"
