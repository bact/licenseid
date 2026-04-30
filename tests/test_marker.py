# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import pytest
from pathlib import Path
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.marker import MarkerDetector


@pytest.fixture
def detector() -> MarkerDetector:
    return MarkerDetector()


def test_marker_extraction(detector: MarkerDetector) -> None:
    text = """
    # Project Title
    
    SPDX-License-Identifier: MIT
    
    License: Apache License, Version 2.0
    
    ## License
    GPL-3.0-only
    
    =======
    License
    =======
    BSD-3-Clause
    """
    snippets = detector.extract_snippets(text)
    assert "MIT" in snippets
    assert "Apache License, Version 2.0" in snippets
    assert "GPL-3.0-only" in snippets
    assert "BSD-3-Clause" in snippets


def test_marker_first_line(detector: MarkerDetector) -> None:
    text = "Apache License, Version 2.0\n\nSome other text..."
    snippets = detector.extract_snippets(text)
    assert "Apache License, Version 2.0" in snippets


def test_keyword_windowing(detector: MarkerDetector) -> None:
    text = "This project is awesome. The license used here is the MIT license which is great."
    windows = detector.get_windows(text)
    # The word "license" appears twice.
    # First "license" -> "used here is the MIT license which is great."
    # Second "license" -> "which is great."
    assert any("MIT" in w for w in windows)


def test_integration(tmp_path: Path) -> None:
    db_path = str(tmp_path / "marker.db")
    from licenseid.database import LicenseDatabase
    from licenseid.normalize import normalize_text
    import sqlite3

    LicenseDatabase(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, norm_license_id, norm_name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Apache-2.0",
                "Apache License 2.0",
                normalize_text("Apache-2.0"),
                normalize_text("Apache License 2.0"),
                True,
                True,
            ),
        )

    matcher = AggregatedLicenseMatcher(db_path)

    # Text with a marker but low overall similarity to any full license
    text = """
    This is a large README file for a project.
    It contains many sections like Installation, Usage, etc.
    
    SPDX-License-Identifier: Apache-2.0
    
    And more text here...
    """
    results = matcher.match(text)
    assert len(results) > 0
    assert results[0]["license_id"] == "Apache-2.0"
    assert results[0]["method"] == "marker"


def test_integration_header(tmp_path: Path) -> None:
    db_path = str(tmp_path / "marker_header.db")
    from licenseid.database import LicenseDatabase
    from licenseid.normalize import normalize_text
    import sqlite3

    LicenseDatabase(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, norm_license_id, norm_name, is_spdx, is_osi_approved) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "MIT",
                "MIT License",
                normalize_text("MIT"),
                normalize_text("MIT License"),
                True,
                True,
            ),
        )

    matcher = AggregatedLicenseMatcher(db_path)

    text = """
    ## License
    MIT License
    
    Some other text.
    """
    results = matcher.match(text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"
    assert results[0]["method"] == "marker"
