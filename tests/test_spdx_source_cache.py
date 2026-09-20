# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for the licenses.json cache in spdx_source.get_version_info() and
the cleanup of temporary cache files in LicenseDatabase.clear_cache().

No test touches the network: requests.get is replaced by an autospec'd fake.
"""
# pylint: disable=missing-function-docstring,protected-access

import json
import os
import time
from pathlib import Path
from unittest import mock

import pytest
import requests
from conftest import fake_requests_get, leftover_tmp_files

from licenseid import spdx_source
from licenseid.database import LicenseDatabase
from licenseid.errors import InvalidInputError, LicenseIdError

_LICENSES = {"licenseListVersion": "3.28.0", "releaseDate": "2026-01-01"}


def _write_cache(tmp_path: Path, content: str | bytes, age_days: int = 0) -> Path:
    path = tmp_path / spdx_source.CACHE_LICENSES_JSON
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    if age_days:
        old = time.time() - age_days * 86400
        os.utime(path, (old, old))
    return path


def _fake_json_get(
    monkeypatch: pytest.MonkeyPatch,
    payload: object = None,
    error: Exception | None = None,
) -> mock.MagicMock:
    fake = fake_requests_get(monkeypatch, error=error)
    fake.return_value.json.return_value = payload
    return fake


def test_valid_cache_used_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cache(tmp_path, json.dumps(_LICENSES))
    fake = _fake_json_get(monkeypatch, _LICENSES)
    result = spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert result == ("3.28.0", "2026-01-01", "cache")
    fake.assert_not_called()


def test_explicit_version_overrides_cached_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cache(tmp_path, json.dumps(_LICENSES))
    _fake_json_get(monkeypatch, _LICENSES)
    assert spdx_source.get_version_info(tmp_path, "3.20.0", use_cache=True) == (
        "3.20.0",
        "2026-01-01",
        "cache",
    )


@pytest.mark.parametrize(
    "content",
    [b"\xff\xfe\x00\x80", "[]", "not json", '{"releaseDate": "2026-01-01"}'],
    ids=["non_utf8", "not_an_object", "invalid_json", "no_version"],
)
def test_unusable_cache_is_refetched_and_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str | bytes
) -> None:
    """Regression: a corrupt cache used to raise (non-UTF-8, or a non-object
    JSON value) or return a None version; it is now refetched once."""
    path = _write_cache(tmp_path, content)
    fake = _fake_json_get(monkeypatch, _LICENSES)
    result = spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert result == ("3.28.0", "2026-01-01", "remote")
    fake.assert_called_once()
    assert json.loads(path.read_text()) == _LICENSES


def test_download_is_cached_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_json_get(monkeypatch, _LICENSES)
    spdx_source.get_version_info(tmp_path, None, use_cache=False)
    cache = tmp_path / spdx_source.CACHE_LICENSES_JSON
    assert json.loads(cache.read_text()) == _LICENSES
    assert not leftover_tmp_files(tmp_path)


def test_cache_write_failure_keeps_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression: an unwritable cache dir used to abort after a successful
    download; now it only warns."""
    _fake_json_get(monkeypatch, _LICENSES)
    result = spdx_source.get_version_info(
        tmp_path / "missing-dir", None, use_cache=False
    )
    assert result == ("3.28.0", "2026-01-01", "remote")
    assert "WARNING: licenses.json: cache write failed: " in capsys.readouterr().err


@pytest.mark.parametrize(
    "payload",
    [{"releaseDate": "2026-01-01"}, [], None],
    ids=["no_version", "list", "null"],
)
def test_response_without_version_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    """Regression: such a response used to be cached and could return a None
    version; it is now treated as a failed fetch."""
    _fake_json_get(monkeypatch, payload)
    with pytest.raises(
        LicenseIdError,
        match="^licenses.json: download unusable: no valid license list version$",
    ):
        spdx_source.get_version_info(tmp_path, None, use_cache=False)
    assert not (tmp_path / spdx_source.CACHE_LICENSES_JSON).exists()


@pytest.mark.parametrize(
    "fake_kwargs",
    [
        {"error": requests.ConnectionError("down")},
        {"payload": {"nothing": "useful"}},
    ],
    ids=["connection_error", "no_version"],
)
def test_stale_cache_used_when_fetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_kwargs: dict[str, object],
) -> None:
    """A failed or unusable fetch reuses an expired cache instead of raising,
    and is not retried."""
    _write_cache(tmp_path, json.dumps(_LICENSES), age_days=100)
    fake = _fake_json_get(monkeypatch, **fake_kwargs)  # type: ignore[arg-type]
    result = spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert result == ("3.28.0", "2026-01-01", "stale cache")
    fake.assert_called_once()
    err = capsys.readouterr().err
    assert "WARNING: licenses.json: download " in err
    assert err.rstrip().endswith("; using stale cache")
    assert err.count("WARNING:") == 1  # one event, one line


def test_fetch_failure_without_cache_or_version_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_json_get(monkeypatch, error=requests.ConnectionError("down"))
    with pytest.raises(LicenseIdError, match="down"):
        spdx_source.get_version_info(tmp_path, None, use_cache=True)


def test_fetch_failure_with_explicit_version_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fake_json_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.get_version_info(tmp_path, "3.20.0", use_cache=True) == (
        "3.20.0",
        None,
        "unavailable",
    )
    assert capsys.readouterr().err == (
        "Fetching latest license list info from "
        f"{spdx_source.LICENSES_JSON_URL}...\n"
        "WARNING: licenses.json: download failed: down; using version 3.20.0\n"
    )


def test_clear_cache_removes_orphaned_temp_files(tmp_path: Path) -> None:
    """A run killed between writing and renaming leaves a *.tmp file; clear
    the ones this package creates, and leave unrelated files alone."""
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    ours = [
        tmp_path / f"{spdx_source.CACHE_LICENSES_JSON}.1a2b3c4d.tmp",
        tmp_path / f"{spdx_source.CACHE_POPULARITY_CSV}.1a2b3c4d.tmp",
        tmp_path / "spdx-data-v3.28.0.tar.gz.1a2b3c4d.tmp",
        tmp_path / "spdx-data-v3.28.0.tar.gz",
        tmp_path / spdx_source.CACHE_LICENSES_JSON,
    ]
    unrelated = tmp_path / "notes.tmp"
    for path in [*ours, unrelated]:
        path.write_text("x")
    LicenseDatabase.clear_cache(db.db_path)
    assert not any(path.exists() for path in ours)
    assert unrelated.exists()


@pytest.mark.parametrize(
    "bad_version",
    ["../../evil", "3.28/../x", "a/b", "3.28.0?x=1", "3 .28", "-3.28", ".hidden"],
)
def test_invalid_explicit_version_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_version: str
) -> None:
    """A --version value becomes a cache file name and a URL, so path
    separators and URL syntax must not get through."""
    fake = _fake_json_get(monkeypatch, _LICENSES)
    with pytest.raises(InvalidInputError, match="^version: invalid: "):
        spdx_source.get_version_info(tmp_path, bad_version, use_cache=True)
    with pytest.raises(InvalidInputError, match="^version: invalid: "):
        spdx_source.get_tarball_path(tmp_path, bad_version, use_cache=True)
    fake.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("version", ["3.28.0", "3.21", "3.0rc1", "3.20-rc1", "v3"])
def test_reasonable_versions_are_accepted(version: str) -> None:
    assert spdx_source._is_valid_version(version)


@pytest.mark.parametrize("version", ["", None, 3.28, ["3.28"], "../x"])
def test_non_string_or_unsafe_versions_are_rejected(version: object) -> None:
    assert not spdx_source._is_valid_version(version)


def test_unsafe_version_in_remote_licenses_json_is_not_used_or_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A compromised or broken licenses.json must not be able to steer the
    tarball file name or URL."""
    _fake_json_get(monkeypatch, {"licenseListVersion": "../../evil"})
    with pytest.raises(
        LicenseIdError,
        match="^licenses.json: download unusable: no valid license list version$",
    ):
        spdx_source.get_version_info(tmp_path, None, use_cache=False)
    assert not (tmp_path / spdx_source.CACHE_LICENSES_JSON).exists()


def test_unsafe_version_in_cached_licenses_json_is_refetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cache(tmp_path, json.dumps({"licenseListVersion": "a/b"}))
    _fake_json_get(monkeypatch, _LICENSES)
    result = spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert result == ("3.28.0", "2026-01-01", "remote")


def test_future_dated_cache_is_not_valid(tmp_path: Path) -> None:
    """Regression: a file dated in the future made `now - mtime` negative,
    which is < any expiry, so the cache never expired."""
    path = _write_cache(tmp_path, json.dumps(_LICENSES))
    future = time.time() + 10 * 86400
    os.utime(path, (future, future))
    assert not spdx_source.is_cache_valid(path, days=45)


def test_slightly_future_dated_cache_is_still_valid(tmp_path: Path) -> None:
    """A few seconds of clock difference (network filesystem) must not
    invalidate a cache file we just wrote."""
    path = _write_cache(tmp_path, json.dumps(_LICENSES))
    soon = time.time() + 30
    os.utime(path, (soon, soon))
    assert spdx_source.is_cache_valid(path, days=45)


def test_unusable_valid_cache_is_reported_not_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_cache(tmp_path, "not json")
    _fake_json_get(monkeypatch, _LICENSES)
    spdx_source.get_version_info(tmp_path, None, use_cache=True)
    assert (
        "WARNING: licenses.json: cache unusable; downloading\n"
        in capsys.readouterr().err
    )


def test_no_cache_flag_never_falls_back_to_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """use_cache=False means never use cached data, even after a failure:
    fail loudly (or use the explicit version) instead."""
    _write_cache(tmp_path, json.dumps(_LICENSES), age_days=100)
    _fake_json_get(monkeypatch, error=requests.ConnectionError("down"))
    with pytest.raises(LicenseIdError, match="down"):
        spdx_source.get_version_info(tmp_path, None, use_cache=False)
    assert spdx_source.get_version_info(tmp_path, "3.20.0", use_cache=False) == (
        "3.20.0",
        None,
        "unavailable",
    )
