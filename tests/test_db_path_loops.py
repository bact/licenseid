# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database path that loops through symlinks is refused as unreadable, by
read and write commands alike, before anything is downloaded."""

# pylint: disable=redefined-outer-name,missing-function-docstring

import errno
import os
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import is_absent, lookup_error, reject_foreign_database
from licenseid.errors import DatabaseNotReadyError
from licenseid.spdx_source import (
    CACHE_LATEST_JSON,
    CACHE_LICENSES_JSON,
    CACHE_POPULARITY_CSV,
    clear_cache_files,
)

pytestmark = posix_only
LOOP = os.strerror(errno.ELOOP)


def _self(root: Path) -> Path:
    (root / "self.db").symlink_to("self.db")
    return root / "self.db"


def _pair(root: Path) -> Path:
    (root / "a.db").symlink_to("b.db")
    (root / "b.db").symlink_to("a.db")
    return root / "a.db"


def _parent(root: Path) -> Path:
    (root / "loopdir").symlink_to("loopdir")
    return root / "loopdir" / "x.db"


def _under_file(root: Path) -> Path:
    (root / "f").write_text("x")
    return root / "f" / "g"


def _through_dir(root: Path) -> Path:
    (root / "d").mkdir()
    (root / "d" / "y").symlink_to("../d/y")
    return root / "d" / "y"


SHAPES = [_self, _pair, _parent, _through_dir]
SPELLINGS = {
    "plain": str,
    "slash": lambda p: f"{p}/",
    "dot": lambda p: f"{p}/.",
    "uri": lambda p: f"file:{p.as_posix()}",
    "localhost": lambda p: f"file://localhost{p.as_posix()}",
}


@pytest.fixture
def get() -> Iterator[mock.Mock]:
    with mock.patch("requests.get", autospec=True) as patched:
        yield patched


@pytest.mark.parametrize("command", ["update", "clear-cache", "is-osi"])
@pytest.mark.parametrize("spell", SPELLINGS.values(), ids=SPELLINGS)
@pytest.mark.parametrize("shape", SHAPES, ids=lambda f: f.__name__)
def test_a_loop_is_unreadable_and_nothing_is_downloaded(
    tmp_path: Path,
    get: mock.Mock,
    shape: Callable[[Path], Path],
    spell: Callable[[Path], str],
    command: str,
) -> None:
    arg = spell(shape(tmp_path))
    args = ["--db", arg, command] + (["MIT"] if command == "is-osi" else [])
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: database: unreadable: ")
    assert LOOP in result.stderr
    assert "run 'licenseid update'" not in result.stderr
    get.assert_not_called()


def test_a_loop_with_its_own_vfs_stays_invalid_for_a_write(
    tmp_path: Path, get: mock.Mock
) -> None:
    arg = f"file:{_self(tmp_path).as_posix()}?vfs=unix"
    result = CliRunner().invoke(cli, ["--db", arg, "update"])
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: database: invalid: ")
    get.assert_not_called()


def test_a_parent_loop_is_not_a_missing_database(tmp_path: Path) -> None:
    path = _parent(tmp_path)
    with pytest.raises(DatabaseNotReadyError) as info:
        LicenseDatabase(path, create=False)
    assert info.value.condition == "unreadable"
    assert "run 'licenseid update'" not in str(info.value)


def test_lookup_error_offers_no_update_for_a_parent_loop(tmp_path: Path) -> None:
    err = lookup_error(
        str(_parent(tmp_path)), sqlite3.OperationalError("unable to open database file")
    )
    assert "run 'licenseid update'" not in str(err)


@pytest.mark.parametrize(
    ("make", "absent"),
    [
        (lambda r: r / "nothing", True),
        (_self, False),
        (_parent, False),
        (lambda r: r, False),
        (_under_file, True),
    ],
    ids=["missing", "self-loop", "parent-loop", "directory", "under-a-file"],
)
def test_is_absent(
    tmp_path: Path, make: Callable[[Path], Path | None], absent: bool
) -> None:
    assert is_absent(str(make(tmp_path))) is absent


def test_a_dangling_link_into_a_missing_directory_is_refused_before_download(
    tmp_path: Path, get: mock.Mock
) -> None:
    link = tmp_path / "dang.db"
    link.symlink_to(tmp_path / "nowhere" / "z.db")
    result = CliRunner().invoke(cli, ["--db", str(link), "update"])
    assert result.exit_code == 1
    assert result.stderr.startswith("ERROR: database: update failed: ")
    get.assert_not_called()


def test_a_parent_that_is_a_file_is_no_loop(tmp_path: Path, get: mock.Mock) -> None:
    (tmp_path / "plain").write_text("x")
    result = CliRunner().invoke(
        cli, ["--db", str(tmp_path / "plain" / "x.db"), "update"]
    )
    assert result.exit_code == 1
    assert "update failed" in result.stderr
    get.assert_not_called()


def test_a_loop_in_the_default_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, get: mock.Mock
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".local").symlink_to(".local")
    result = CliRunner().invoke(cli, ["update"])
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: database: unreadable: ")
    get.assert_not_called()


def test_a_windows_loop_error_is_read_as_a_loop(tmp_path: Path) -> None:
    """WinError 1921 carries no ELOOP errno."""

    class WinLoop(OSError):
        """An OSError as Windows raises it."""

        winerror = 1921

    with (
        mock.patch("os.stat", side_effect=WinLoop(22, "cannot resolve")),
        pytest.raises(DatabaseNotReadyError) as info,
    ):
        reject_foreign_database(str(tmp_path / "x.db"))
    assert info.value.condition == "unreadable"


@pytest.mark.parametrize(
    "name", [CACHE_LATEST_JSON, CACHE_LICENSES_JSON, CACHE_POPULARITY_CSV]
)
@pytest.mark.parametrize("kind", ["self", "pair", "dangling"])
def test_clear_cache_removes_a_looped_cache_link(
    tmp_path: Path, name: str, kind: str
) -> None:
    link = tmp_path / name
    if kind == "self":
        link.symlink_to(name)
    elif kind == "pair":
        link.symlink_to("other")
        (tmp_path / "other").symlink_to(name)
    else:
        link.symlink_to("nowhere")
    assert clear_cache_files(tmp_path) is True
    assert not link.is_symlink()


def test_clear_cache_removes_the_link_not_its_target(tmp_path: Path) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("mine")
    (tmp_path / CACHE_LATEST_JSON).symlink_to(target)
    assert clear_cache_files(tmp_path) is True
    assert target.read_text() == "mine"
    assert not (tmp_path / CACHE_LATEST_JSON).is_symlink()
