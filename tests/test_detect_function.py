# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.detect()``: ``LicenseDetector().detect()`` on the database at
the default path, in one call."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

import licenseid
from licenseid import detector
from licenseid.datadir import get_default_db_path
from licenseid.errors import DatabaseNotReadyError, InvalidInputError

ROWS = (
    Lic(
        "MIT",
        "MIT License",
        True,
        True,
        True,
        search_text="permission is hereby granted free of charge to any person",
    ),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
)


@pytest.fixture(name="default_db")
def _default_db(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """A seeded database that ``get_default_db_path()`` returns."""
    for path in seeded_db("test_detect_function", ROWS):
        fake = mock.create_autospec(get_default_db_path, return_value=path)
        monkeypatch.setattr("licenseid.detector.get_default_db_path", fake)
        yield path


def test_the_package_exports_the_function() -> None:
    """``licenseid.detect`` is the function of ``licenseid.detector``."""
    assert licenseid.detect is detector.detect
    assert "detect" in licenseid.__all__


@pytest.mark.parametrize(
    "kwargs",
    [
        {"license_id": "MIT"},
        {"text": "Apache License 2.0"},
        {"text": "MIT", "enable_popularity": False},
    ],
    ids=["id", "text", "option"],
)
def test_detect_answers_as_the_detector_does(
    default_db: str, kwargs: dict[str, Any]
) -> None:
    """One call gives what a detector on the default database gives."""
    got = licenseid.detect(**kwargs)
    assert got
    expected = detector.LicenseDetector(default_db).detect(**kwargs)
    assert got == expected


def test_a_positional_text_is_text(default_db: str) -> None:
    """The first argument is text, as for the method."""
    assert default_db
    assert [r["license_id"] for r in licenseid.detect("MIT")] == ["MIT"]


def test_a_file_is_read(default_db: str, tmp_path: Path) -> None:
    """``file_path`` reaches the method."""
    assert default_db
    path = tmp_path / "LICENSE"
    path.write_text("MIT", encoding="utf-8")
    assert [r["license_id"] for r in licenseid.detect(file_path=str(path))] == ["MIT"]


def test_an_unknown_option_is_refused(default_db: str) -> None:
    """A keyword option the method does not know is refused."""
    assert default_db
    with pytest.raises(InvalidInputError):
        licenseid.detect("MIT", bogus=True)


def test_no_input_is_refused_as_the_method_does(default_db: str) -> None:
    """Called with nothing, it answers as the method does."""
    assert default_db
    assert licenseid.detect() == detector.LicenseDetector(default_db).detect()


def test_a_missing_default_database_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No database at the default path: not ready, raised at the call."""
    fake = mock.create_autospec(
        get_default_db_path, return_value=str(tmp_path / "none.db")
    )
    monkeypatch.setattr("licenseid.detector.get_default_db_path", fake)
    with pytest.raises(DatabaseNotReadyError):
        licenseid.detect("MIT")
    assert fake.call_count == 1
