# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.detect()``: ``LicenseDetector.detect()`` on the database at the
default path, in one call, with one detector kept while that file is the same."""

import importlib
import sqlite3
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db, writer
from matcher_db import Lic, seeded_db
from resolve_states import OUTDATED_WARNING

import licenseid
from licenseid import detector, keptdetector, listsource
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
        monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", fake)
        yield path


def test_the_package_exports_the_function() -> None:
    """``licenseid.detect`` is the function of ``licenseid.keptdetector``."""
    assert licenseid.detect is keptdetector.detect
    assert "detect" in licenseid.__all__


@pytest.mark.parametrize(
    "kwargs",
    [
        {"license_id": "MIT"},
        {"text": "Apache License 2.0"},
        {"text": "MIT"},
    ],
    ids=["id", "text", "plain"],
)
def test_detect_answers_as_the_detector_does(
    default_db: str, kwargs: dict[str, Any]
) -> None:
    """One call gives what a detector on the default database gives."""
    got = licenseid.detect(**kwargs)
    assert got
    assert got == detector.LicenseDetector(default_db).detect(**kwargs)


def test_every_argument_is_forwarded(default_db: str) -> None:
    """A spy on the method sees text, ``license_id``, ``file_path`` and a
    non-default option, as given."""
    assert default_db
    with mock.patch.object(
        detector.LicenseDetector, "detect", autospec=True, return_value=[]
    ) as spy:
        licenseid.detect(
            "t", license_id="MIT", file_path="f", exclude=["MIT"], hint=["x"]
        )
    spy.assert_called_once_with(
        mock.ANY, "t", license_id="MIT", file_path="f", exclude=["MIT"], hint=["x"]
    )


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


def test_no_input_gives_no_result(default_db: str) -> None:
    """Called with nothing, the method answers no result (it does not raise),
    and so does the function."""
    assert detector.LicenseDetector(default_db).detect() == []
    assert licenseid.detect() == []


def test_a_missing_default_database_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No database at the default path: not ready, raised at the call."""
    fake = mock.create_autospec(
        get_default_db_path, return_value=str(tmp_path / "none.db")
    )
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", fake)
    with pytest.raises(DatabaseNotReadyError):
        licenseid.detect("MIT")
    assert fake.call_count == 1


# --- one detector kept while the default file is the same ---


class _Built:
    """The detectors the function built, counted."""

    def __init__(self) -> None:
        self.made: list[detector.LicenseDetector] = []


@pytest.fixture(name="built")
def _built(monkeypatch: pytest.MonkeyPatch) -> _Built:
    """Count the detectors ``licenseid.detect()`` builds."""
    seen = _Built()
    real = detector.LicenseDetector

    def make(*args: Any, **kwargs: Any) -> detector.LicenseDetector:
        made = real(*args, **kwargs)
        seen.made.append(made)
        return made

    monkeypatch.setattr("licenseid.keptdetector.LicenseDetector", make)
    listsource.reset_warnings()
    return seen


@pytest.fixture(name="file_db")
def _file_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[str], Path]:
    """Make a ready database file by name, the default path being the last."""

    def make(name: str) -> Path:
        path = make_ready_file_db(tmp_path / name)
        monkeypatch.setattr(
            "licenseid.keptdetector.get_default_db_path", lambda: str(path)
        )
        return path

    return make


def test_repeated_calls_share_one_detector(
    built: _Built,
    file_db: Callable[[str], Path],
    opened: list[sqlite3.Connection],
) -> None:
    """The second call builds nothing and opens fewer connections."""
    file_db("a.db")
    assert licenseid.detect(license_id="MIT")
    first = len(opened)
    assert licenseid.detect(license_id="MIT")
    assert licenseid.detect(license_id="MIT")
    assert len(built.made) == 1
    assert len(opened) - first < 2 * first


def test_a_changed_file_builds_a_new_detector(
    built: _Built, file_db: Callable[[str], Path]
) -> None:
    """A write to the file changes its stamp."""
    path = file_db("a.db")
    licenseid.detect(license_id="MIT")
    with writer(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES ('k', 'v')"
        )
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2
    assert built.made[0] is not built.made[1]


def test_another_default_path_builds_a_new_detector(
    built: _Built, file_db: Callable[[str], Path]
) -> None:
    """Another HOME means another default path, so another detector."""
    file_db("a.db")
    licenseid.detect(license_id="MIT")
    file_db("b.db")
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2


def test_reset_forgets_the_detector(
    built: _Built, file_db: Callable[[str], Path]
) -> None:
    """The hook the fixtures call."""
    file_db("a.db")
    licenseid.detect(license_id="MIT")
    keptdetector.reset()
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2


def test_a_failed_build_is_never_kept(
    built: _Built, file_db: Callable[[str], Path]
) -> None:
    """A database that is not ready raises each time; once it is, it works."""
    path = file_db("a.db")
    path.write_bytes(b"")  # empty: not ready
    for _ in range(2):
        with pytest.raises(DatabaseNotReadyError):
            licenseid.detect(license_id="MIT")
    path.unlink()
    make_ready_file_db(path)
    assert licenseid.detect(license_id="MIT")
    assert len(built.made) == 1


def test_an_outdated_database_warns_once(
    built: _Built,
    file_db: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``build vN outdated`` is said once per process, as ``match()`` says it,
    also when the file changes and a detector is built again."""
    path = file_db("a.db")
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '1' WHERE key = 'build_version'")
    capsys.readouterr()
    licenseid.detect(license_id="MIT")
    licenseid.detect(license_id="MIT")
    with writer(path) as conn:
        conn.execute("INSERT OR REPLACE INTO db_metadata VALUES ('k', 'v')")
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2
    assert capsys.readouterr().err == OUTDATED_WARNING


@pytest.mark.parametrize(
    "name",
    ["resolve", "AggregatedLicenseMatcher", "LicenseMatch", "MatchRequest"],
)
def test_the_old_names_are_gone(name: str) -> None:
    """No alias is left for the names 0.6.0 had."""
    assert not hasattr(licenseid, name)
    assert name not in licenseid.__all__


def test_the_old_module_is_gone() -> None:
    """``licenseid.matcher`` is ``licenseid.detector``."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("licenseid.matcher")


def test_a_path_with_no_file_is_not_kept(built: _Built, default_db: str) -> None:
    """An in-memory database has no file to stamp, so each call builds."""
    assert default_db
    licenseid.detect(license_id="MIT")
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2


@posix_only
def test_the_same_file_by_another_path_builds_a_new_detector(
    built: _Built,
    file_db: Callable[[str], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stamp is the same (a link to one file), the default path is not."""
    path = file_db("a.db")
    licenseid.detect(license_id="MIT")
    twin = tmp_path / "twin.db"
    twin.symlink_to(path)
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: str(twin))
    licenseid.detect(license_id="MIT")
    assert len(built.made) == 2
