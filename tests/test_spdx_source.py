# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for spdx_source cache validity and popularity-data fetching.

No test touches the network: requests.get is replaced by an autospec'd fake.
"""
# pylint: disable=missing-function-docstring

import os
import time
from pathlib import Path
from unittest import mock

import pytest
import requests

from licenseid import spdx_source
from licenseid.spdx_source import fetch_popularity_data, is_cache_valid


def test_missing_file_is_invalid(tmp_path: Path) -> None:
    """A cache file that doesn't exist is never valid."""
    assert not is_cache_valid(tmp_path / "does-not-exist.json", days=45)


def test_fresh_file_is_valid(tmp_path: Path) -> None:
    """A cache file written just now is valid."""
    cache_file = tmp_path / "licenses.json"
    cache_file.write_text("{}")
    assert is_cache_valid(cache_file, days=45)


def test_old_file_is_invalid(tmp_path: Path) -> None:
    """A cache file older than the max age is invalid."""
    cache_file = tmp_path / "licenses.json"
    cache_file.write_text("{}")
    old_time = time.time() - 46 * 86400
    os.utime(cache_file, (old_time, old_time))
    assert not is_cache_valid(cache_file, days=45)


# --- fetch_popularity_data ---

_CSV = "spdx_license,num_pushers\n"


def _fake_get(
    monkeypatch: pytest.MonkeyPatch,
    text: str = "",
    error: Exception | None = None,
    status_error: bool = False,
) -> mock.MagicMock:
    """Replace requests.get with an autospec'd fake returning *text*, or
    raising *error* / an HTTP status error."""
    response = mock.create_autospec(requests.Response, instance=True)
    response.text = text
    if status_error:
        response.raise_for_status.side_effect = requests.HTTPError("503")
    fake: mock.MagicMock = mock.create_autospec(requests.get, return_value=response)
    if error is not None:
        fake.side_effect = error
    monkeypatch.setattr(requests, "get", fake)
    return fake


def test_popularity_sums_duplicate_ids_and_skips_blank_and_noassertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_text = _CSV + "MIT,10\nMIT,5\nApache-2.0,7\nNOASSERTION,99\n,3\n"
    _fake_get(monkeypatch, csv_text)
    assert fetch_popularity_data(tmp_path) == {"MIT": 15, "Apache-2.0": 7}


def test_popularity_non_numeric_count_is_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_get(monkeypatch, _CSV + "MIT,abc\nMIT,\nISC,4\n")
    assert fetch_popularity_data(tmp_path) == {"MIT": 0, "ISC": 4}


def test_popularity_header_only_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_get(monkeypatch, _CSV)
    assert fetch_popularity_data(tmp_path) == {}


def test_popularity_local_path_used_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "popularity.csv"
    local.write_text(_CSV + "MIT,2\n", encoding="utf-8")
    fake = _fake_get(monkeypatch, _CSV + "ISC,9\n")
    assert fetch_popularity_data(tmp_path, local) == {"MIT": 2}
    fake.assert_not_called()


@pytest.mark.parametrize("content", [None, ""], ids=["missing", "empty"])
def test_popularity_unusable_local_path_falls_back_to_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str | None
) -> None:
    local = tmp_path / "local.csv"
    if content is not None:
        local.write_text(content, encoding="utf-8")
    fake = _fake_get(monkeypatch, _CSV + "ISC,9\n")
    assert fetch_popularity_data(tmp_path, local) == {"ISC": 9}
    fake.assert_called_once()


def test_popularity_download_writes_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = _CSV + "MIT,1\n"
    _fake_get(monkeypatch, text)
    fetch_popularity_data(tmp_path)
    assert (tmp_path / spdx_source.CACHE_POPULARITY_CSV).read_text() == text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"error": requests.ConnectionError("down")},
        {"status_error": True},
    ],
    ids=["connection_error", "http_error"],
)
def test_popularity_download_failure_returns_empty_and_no_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object]
) -> None:
    _fake_get(monkeypatch, _CSV + "MIT,1\n", **kwargs)  # type: ignore[arg-type]
    assert fetch_popularity_data(tmp_path) == {}
    assert not (tmp_path / spdx_source.CACHE_POPULARITY_CSV).exists()


# --- fetch_popularity_data: regressions for previously pinned bugs ---


def test_popularity_short_row_counts_as_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a row missing num_pushers gives None; int(None) used to
    raise an uncaught TypeError."""
    _fake_get(monkeypatch, _CSV + "MIT\nISC,3\n")
    assert fetch_popularity_data(tmp_path) == {"MIT": 0, "ISC": 3}


def test_popularity_cache_write_failure_keeps_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression: an unwritable/missing cache_dir used to abort after a
    successful download; now it only warns."""
    _fake_get(monkeypatch, _CSV + "MIT,1\n")
    assert fetch_popularity_data(tmp_path / "missing-dir") == {"MIT": 1}
    assert "Failed to cache popularity data" in capsys.readouterr().out


def test_popularity_unparseable_download_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: garbage used to be cached and then served as a valid
    cache for the full expiry period."""
    _fake_get(monkeypatch, "<html>Service unavailable</html>")
    assert fetch_popularity_data(tmp_path) == {}
    assert not (tmp_path / spdx_source.CACHE_POPULARITY_CSV).exists()


def test_popularity_non_utf8_local_file_falls_back_to_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a corrupt cache file used to crash with
    UnicodeDecodeError instead of falling back to a download."""
    local = tmp_path / "popularity.csv"
    local.write_bytes(b"\xff\xfe\x00\x80")
    _fake_get(monkeypatch, _CSV + "ISC,9\n")
    assert fetch_popularity_data(tmp_path, local) == {"ISC": 9}


def test_popularity_poisoned_local_cache_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local cache that parses to nothing (e.g. garbage cached by an older
    version) is re-downloaded once and overwritten."""
    local = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    local.write_text("<html>oops</html>")
    fake = _fake_get(monkeypatch, _CSV + "MIT,4\n")
    assert fetch_popularity_data(tmp_path, local) == {"MIT": 4}
    fake.assert_called_once()
    assert local.read_text() == _CSV + "MIT,4\n"


@pytest.mark.parametrize(
    "fake_kwargs",
    [
        {"error": requests.ConnectionError("down")},
        {"status_error": True},
        {"text": "<html>Service unavailable</html>"},
    ],
    ids=["connection_error", "http_error", "garbage_body"],
)
def test_popularity_stale_cache_used_when_download_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_kwargs: dict[str, object],
) -> None:
    """A failed or unusable download reuses an expired cache file instead of
    returning nothing (and the failure is not retried)."""
    (tmp_path / spdx_source.CACHE_POPULARITY_CSV).write_text(_CSV + "MIT,1\n")
    fake = _fake_get(monkeypatch, **fake_kwargs)  # type: ignore[arg-type]
    assert fetch_popularity_data(tmp_path) == {"MIT": 1}
    fake.assert_called_once()
    assert "stale cached popularity data" in capsys.readouterr().out


# --- gentle fetching ---


def test_popularity_request_is_identified_with_timeout_and_single_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _fake_get(monkeypatch, _CSV + "MIT,1\n")
    fetch_popularity_data(tmp_path)
    fake.assert_called_once()
    kwargs = fake.call_args.kwargs
    assert kwargs["headers"]["User-Agent"] == spdx_source.USER_AGENT
    assert spdx_source.USER_AGENT.startswith("licenseid/")
    assert kwargs["timeout"] == 30


def test_license_list_and_tarball_requests_are_identified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _fake_get(monkeypatch)
    response = fake.return_value
    response.json.return_value = {"licenseListVersion": "3.28.0"}
    response.iter_content.return_value = [b"data"]

    spdx_source.get_version_info(tmp_path, None, use_cache=False)
    spdx_source.get_tarball_path(tmp_path, "3.28.0", use_cache=False)

    assert fake.call_count == 2
    for call in fake.call_args_list:
        assert call.kwargs["headers"]["User-Agent"] == spdx_source.USER_AGENT
