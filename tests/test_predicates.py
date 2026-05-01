# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Predicate tests for licenseid."""
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
    db_path = f"file:test_pred_{db_id}?mode=memory&cache=shared"
    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
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
            ("GPL-3.0-only", "GNU GPL v3.0", True, False, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("Proprietary", "Proprietary License", False, False, False),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("0BSD", "BSD Zero Clause License", True, True, False),
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


def test_is_spdx(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.is_spdx(license_id="MIT") is True
    assert matcher.is_spdx(license_id="Proprietary") is False
    assert matcher.is_spdx(license_id=" MIT  ") is True
    assert matcher.is_spdx(license_id="mit") is True


def test_is_osi(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.is_osi(license_id="MIT") is True
    assert matcher.is_osi(license_id="GPL-3.0-only") is False
    assert matcher.is_osi(license_id="0BSD") is True


def test_is_fsf(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.is_fsf(license_id="MIT") is True
    assert matcher.is_fsf(license_id="GPL-3.0-only") is True
    assert matcher.is_fsf(license_id="0BSD") is False


def test_is_open(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.is_open(license_id="MIT") is True
    assert matcher.is_open(license_id="GPL-3.0-only") is True
    assert matcher.is_open(license_id="0BSD") is True
    assert matcher.is_open(license_id="Proprietary") is False


def test_predicate_with_text(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = (
        "Permission is hereby granted, free of charge, to any person obtaining a copy"
    )
    assert matcher.is_osi(text=text) is True
    assert matcher.is_spdx(text=text) is True
