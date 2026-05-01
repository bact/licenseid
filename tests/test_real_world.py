# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests using real-world file patterns and repository structures."""

import sqlite3
import uuid
from pathlib import Path
from typing import Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "license-markers"


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_real_{db_id}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            (
                "BSD-3-Clause",
                'BSD 3-Clause "New" or "Revised" License',
                True,
                True,
                True,
            ),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "MIT",
                "permission is hereby granted free of charge to any person obtaining a copy",
            ),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
    yield db_path
    keep_alive.close()


def test_pyproject_toml(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "pyproject.toml"
    results = matcher.match(file_path=str(f))
    assert any(r["license_id"] == "MIT" for r in results)


def test_package_json(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "package.json"
    results = matcher.match(file_path=str(f))
    assert any(r["license_id"] == "Apache-2.0" for r in results)


def test_readme_markdown(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "README.md"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "MIT"


def test_citation_cff(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "CITATION.cff"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "MIT"


def test_license_rst(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "LICENSE.rst"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "BSD-3-Clause"


def test_source_header(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "main.py"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "MIT"


def test_readme_txt(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "README.txt"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "Apache-2.0"


def test_copying(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "COPYING"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "BSD-3-Clause"


def test_setup_py(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "setup.py"
    results = matcher.match(file_path=str(f))
    assert any(r["license_id"] == "MIT" for r in results)


def test_contributing(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    f = FIXTURE_DIR / "CONTRIBUTING"
    results = matcher.match(file_path=str(f))
    assert results[0]["license_id"] == "MIT"
