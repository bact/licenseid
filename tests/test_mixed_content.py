# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests using real-world file patterns and repository structures."""
# pylint: disable=duplicate-code,redefined-outer-name,missing-function-docstring

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mixed-content"


@pytest.fixture(scope="session")
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_real_{db_id}?mode=memory&cache=shared"

    # pylint: disable=unused-variable
    db_manager = LicenseDatabase(db_path)  # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        # Populate from fixtures
        fixtures_root = Path(__file__).parent / "fixtures"
        long_text_dir = fixtures_root / "license-text-long"

        count = 0
        if long_text_dir.exists():
            for json_file in long_text_dir.glob("*.json"):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                conn.execute(
                    "INSERT INTO licenses (license_id, name, is_spdx, "
                    "is_osi_approved, is_fsf_libre, is_high_usage, "
                    "is_deprecated, superseded_by, pop_score) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        data["license_id"],
                        data.get("name", data["license_id"]),
                        data.get("is_spdx", False),
                        data.get("is_osi_approved", False),
                        data.get("is_fsf_libre", False),
                        data.get("is_high_usage", False),
                        data.get("is_deprecated", False),
                        data.get("superseded_by"),
                        data.get("pop_score", 1),
                    ),
                )
                conn.execute(
                    "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
                    (data["license_id"], normalize_text(data["license_text"])),
                )
                count += 1
        print(f"Populated test DB with {count} licenses from fixtures.")

        # Add exceptions used in tests
        conn.execute(
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?)",
            ("Linux-syscall-note", "Linux Syscall Note", False, None),
        )
        conn.execute(
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?)",
            ("Font-exception-2.0", "Font Exception 2.0", False, None),
        )

        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )

    yield db_path
    keep_alive.close()


def get_fixtures() -> list[tuple[Path, str]]:
    """Scan fixture directory and return (file_path, expected_license_id)."""
    fixtures = []
    if not FIXTURE_DIR.exists():
        return []
    for lic_dir in FIXTURE_DIR.iterdir():
        if not lic_dir.is_dir():
            continue
        expected_id = lic_dir.name.replace("_", " ")
        for f in lic_dir.iterdir():
            if f.is_file():
                fixtures.append((f, expected_id))
    return sorted(fixtures, key=lambda x: str(x[0]))


def test_marker_detection_fixtures(test_db: str) -> None:
    """Benchmark marker detection across multiple mixed-content fixtures.
    We aim for at least 60% accuracy on these real-world-style samples.
    """
    matcher = AggregatedLicenseMatcher(test_db)
    fixtures = get_fixtures()
    if not fixtures:
        pytest.skip("No mixed-content fixtures found.")

    passed = 0
    total = len(fixtures)
    failures = []

    for fixture_file, expected_id in fixtures:
        results = matcher.match(file_path=str(fixture_file))
        found_ids = [r["license_id"] for r in results]

        if expected_id in found_ids:
            passed += 1
        else:
            failures.append(
                f"Expected {expected_id} in {found_ids} for "
                f"{fixture_file.parent.name}/{fixture_file.name}"
            )

    accuracy = (passed / total) * 100
    print(f"\nMarker detection accuracy: {accuracy:.2f}% ({passed}/{total})")

    if failures:
        print("\nSome failures:")
        for fail in failures[:10]:  # Show first 10 failures
            print(f"  - {fail}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more.")

    # We expect at least 70% accuracy
    assert accuracy >= 70.0, (
        f"Marker detection accuracy too low: {accuracy:.2f}% "
        f"({passed}/{total}), expected >= 70.0%"
    )
