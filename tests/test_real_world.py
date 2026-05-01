# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests using real-world file patterns and repository structures."""
# pylint: disable=redefined-outer-name,missing-function-docstring

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
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, True, True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "BSD-3-Clause",
                'BSD 3-Clause "New" or "Revised" License',
                True,
                True,
                True,
                False,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            (
                "GPL-2.0-only WITH Linux-syscall-note",
                "GPL-2.0-only WITH Linux Syscall Note",
                True,
                False,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-3.0-or-later", "GNU GPL v3.0 or later", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            (
                "GPL-2.0",
                "GNU General Public License v2.0 only",
                True,
                True,
                "GPL-2.0-only",
            ),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-2.0-only", "GNU General Public License v2.0 only", True, False, None),
        )
        conn.execute(
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) VALUES (?, ?, ?, ?)",
            ("Linux-syscall-note", "Linux Syscall Note", False, None),
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


@pytest.mark.parametrize("fixture_file, expected_id", get_fixtures())
def test_marker_detection_fixtures(
    test_db: str, fixture_file: Path, expected_id: str
) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    results = matcher.match(file_path=str(fixture_file))

    # Check if the expected ID is in the results
    # We use 'any' because some files might match multiple licenses
    # (though in our fixtures they should match exactly).
    found_ids = [r["license_id"] for r in results]
    assert expected_id in found_ids, (
        f"Expected {expected_id} in {found_ids} for {fixture_file.name}"
    )
