# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for spdx_source cache validity and popularity-data fetching.

No test touches the network: requests.get is replaced by an autospec'd fake.
"""
# pylint: disable=missing-function-docstring,protected-access

import os
import time
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
import requests
from conftest import fake_requests_get, leftover_tmp_files

from licenseid import __version__, spdx_source
from licenseid.database import LicenseDatabase
from licenseid.spdx_source import is_cache_valid


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


def _popularity_map(cache_dir: Path, local_path: Path | None = None) -> dict[str, int]:
    """Just the popularity map; source reporting is tested separately."""
    return spdx_source.fetch_popularity_data(cache_dir, local_path)[0]


def test_popularity_sums_duplicate_ids_and_skips_blank_and_noassertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_text = _CSV + "MIT,10\nMIT,5\nApache-2.0,7\nNOASSERTION,99\n,3\n"
    fake_requests_get(monkeypatch, csv_text)
    assert _popularity_map(tmp_path) == {"MIT": 15, "Apache-2.0": 7}


def test_popularity_non_numeric_count_is_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_requests_get(monkeypatch, _CSV + "MIT,abc\nMIT,\nISC,4\n")
    assert _popularity_map(tmp_path) == {"MIT": 0, "ISC": 4}


def test_popularity_header_only_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_requests_get(monkeypatch, _CSV)
    assert _popularity_map(tmp_path) == {}


def test_popularity_local_path_used_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "popularity.csv"
    local.write_text(_CSV + "MIT,2\n", encoding="utf-8")
    fake = fake_requests_get(monkeypatch, _CSV + "ISC,9\n")
    assert _popularity_map(tmp_path, local) == {"MIT": 2}
    fake.assert_not_called()


@pytest.mark.parametrize("content", [None, ""], ids=["missing", "empty"])
def test_popularity_unusable_local_path_falls_back_to_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str | None
) -> None:
    local = tmp_path / "local.csv"
    if content is not None:
        local.write_text(content, encoding="utf-8")
    fake = fake_requests_get(monkeypatch, _CSV + "ISC,9\n")
    assert _popularity_map(tmp_path, local) == {"ISC": 9}
    fake.assert_called_once()


def test_popularity_download_writes_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = _CSV + "MIT,1\n"
    fake_requests_get(monkeypatch, text)
    _popularity_map(tmp_path)
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
    fake_requests_get(monkeypatch, _CSV + "MIT,1\n", **kwargs)  # type: ignore[arg-type]
    assert _popularity_map(tmp_path) == {}
    assert not (tmp_path / spdx_source.CACHE_POPULARITY_CSV).exists()


# --- fetch_popularity_data: regressions for previously pinned bugs ---


def test_popularity_short_row_counts_as_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a row missing num_pushers gives None; int(None) used to
    raise an uncaught TypeError."""
    fake_requests_get(monkeypatch, _CSV + "MIT\nISC,3\n")
    assert _popularity_map(tmp_path) == {"MIT": 0, "ISC": 3}


def test_popularity_cache_write_failure_keeps_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression: an unwritable/missing cache_dir used to abort after a
    successful download; now it only warns."""
    fake_requests_get(monkeypatch, _CSV + "MIT,1\n")
    assert _popularity_map(tmp_path / "missing-dir") == {"MIT": 1}
    assert "Failed to cache popularity data" in capsys.readouterr().out


def test_popularity_unparseable_download_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: garbage used to be cached and then served as a valid
    cache for the full expiry period."""
    fake_requests_get(monkeypatch, "<html>Service unavailable</html>")
    assert _popularity_map(tmp_path) == {}
    assert not (tmp_path / spdx_source.CACHE_POPULARITY_CSV).exists()


def test_popularity_non_utf8_local_file_falls_back_to_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a corrupt cache file used to crash with
    UnicodeDecodeError instead of falling back to a download."""
    local = tmp_path / "popularity.csv"
    local.write_bytes(b"\xff\xfe\x00\x80")
    fake_requests_get(monkeypatch, _CSV + "ISC,9\n")
    assert _popularity_map(tmp_path, local) == {"ISC": 9}


def test_popularity_poisoned_local_cache_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local cache that parses to nothing (e.g. garbage cached by an older
    version) is re-downloaded once and overwritten."""
    local = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    local.write_text("<html>oops</html>")
    fake = fake_requests_get(monkeypatch, _CSV + "MIT,4\n")
    assert _popularity_map(tmp_path, local) == {"MIT": 4}
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
    fake = fake_requests_get(monkeypatch, **fake_kwargs)  # type: ignore[arg-type]
    assert _popularity_map(tmp_path) == {"MIT": 1}
    fake.assert_called_once()
    assert "stale cached popularity data" in capsys.readouterr().out


# --- gentle fetching ---


def test_popularity_request_is_identified_with_timeout_and_single_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = fake_requests_get(monkeypatch, _CSV + "MIT,1\n")
    _popularity_map(tmp_path)
    fake.assert_called_once()
    kwargs = fake.call_args.kwargs
    assert kwargs["headers"]["User-Agent"] == spdx_source.user_agent()
    assert (
        spdx_source.user_agent()
        == f"licenseid/{__version__} (+https://github.com/bact/licenseid)"
    )
    assert kwargs["timeout"] == 30


def test_license_list_and_tarball_requests_are_identified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = fake_requests_get(monkeypatch)
    response = fake.return_value
    response.json.return_value = {"licenseListVersion": "3.28.0"}
    response.iter_content.return_value = [b"data"]

    spdx_source.get_version_info(tmp_path, None, use_cache=False)
    spdx_source.get_tarball_path(tmp_path, "3.28.0", use_cache=False)

    assert fake.call_count == 2
    for call in fake.call_args_list:
        assert call.kwargs["headers"]["User-Agent"] == spdx_source.user_agent()


# --- data source reporting, atomic cache write ---


def test_popularity_source_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "popularity.csv"
    local.write_text(_CSV + "MIT,2\n", encoding="utf-8")
    fake_requests_get(monkeypatch)
    assert spdx_source.fetch_popularity_data(tmp_path, local) == (
        {"MIT": 2},
        "cache",
    )


def test_popularity_source_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_requests_get(monkeypatch, _CSV + "MIT,2\n")
    assert spdx_source.fetch_popularity_data(tmp_path) == ({"MIT": 2}, "remote")


def test_popularity_source_is_remote_when_poisoned_cache_redownloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid-looking local cache that parses to nothing is replaced by a
    download, and the source says so."""
    local = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    local.write_text("<html>oops</html>")
    fake_requests_get(monkeypatch, _CSV + "MIT,4\n")
    assert spdx_source.fetch_popularity_data(tmp_path, local) == (
        {"MIT": 4},
        "remote",
    )


def test_popularity_source_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / spdx_source.CACHE_POPULARITY_CSV).write_text(_CSV + "MIT,1\n")
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.fetch_popularity_data(tmp_path) == (
        {"MIT": 1},
        "stale cache",
    )


def test_popularity_source_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.fetch_popularity_data(tmp_path) == ({}, "unavailable")


def test_popularity_stale_cache_that_parses_to_nothing_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / spdx_source.CACHE_POPULARITY_CSV).write_text("<html>oops</html>")
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.fetch_popularity_data(tmp_path) == ({}, "unavailable")


def test_popularity_cache_write_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache is written via a temp file + rename: on success no temp file
    remains, and if the rename fails the existing cache is left untouched."""
    cache = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    fake_requests_get(monkeypatch, _CSV + "MIT,1\n")
    _popularity_map(tmp_path)
    assert cache.read_text() == _CSV + "MIT,1\n"
    assert not leftover_tmp_files(tmp_path)

    cache.write_text("previous")
    monkeypatch.setattr(os, "replace", mock.Mock(side_effect=OSError("disk full")))
    assert _popularity_map(tmp_path) == {"MIT": 1}
    assert cache.read_text() == "previous"
    assert not leftover_tmp_files(tmp_path)


def test_popularity_cache_cleanup_failure_does_not_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression: a failing temp-file cleanup (e.g. PermissionError) inside
    the error handler must not escape and abort the update."""
    fake_requests_get(monkeypatch, _CSV + "MIT,1\n")
    monkeypatch.setattr(os, "replace", mock.Mock(side_effect=OSError("disk full")))
    monkeypatch.setattr(
        Path, "unlink", mock.Mock(side_effect=PermissionError("denied"))
    )
    assert _popularity_map(tmp_path) == {"MIT": 1}
    assert "Failed to cache popularity data" in capsys.readouterr().out


def test_atomic_path_uses_unique_temp_names(tmp_path: Path) -> None:
    """Regression: a fixed temp name let concurrent runs share and interleave
    writes to one temp file."""
    target = tmp_path / "data.csv"
    with (
        spdx_source._atomic_path(target) as first,
        spdx_source._atomic_path(target) as second,
    ):
        assert first != second
        assert first.parent == second.parent == tmp_path
        first.write_text("a")
        second.write_text("b")
    assert target.read_text() == "a"  # outer block renames last
    assert not leftover_tmp_files(tmp_path)


def _interrupted_chunks() -> Iterator[bytes]:
    yield b"partial"
    raise requests.exceptions.ChunkedEncodingError("connection dropped")


def test_tarball_interrupted_download_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a download that dies mid-stream used to leave a partial
    tarball at the cache path, which every later run then reused."""
    fake = fake_requests_get(monkeypatch)
    fake.return_value.iter_content.return_value = _interrupted_chunks()
    tar_path = tmp_path / spdx_source.CACHE_SPDX_TARBALL_TEMPLATE.format(
        version="3.28.0"
    )

    with pytest.raises(RuntimeError):
        spdx_source.get_tarball_path(tmp_path, "3.28.0", use_cache=True)
    assert not tar_path.exists()
    assert not leftover_tmp_files(tmp_path)

    fake.return_value.iter_content.return_value = [b"whole"]
    path, source = spdx_source.get_tarball_path(tmp_path, "3.28.0", use_cache=True)
    assert (path, source) == (tar_path, "remote")
    assert tar_path.read_bytes() == b"whole"
    assert fake.call_count == 2


@pytest.mark.parametrize(
    ("cache_valid", "use_cache"),
    [(True, True), (True, False), (False, True)],
    ids=["valid_cache", "no_cache_flag", "expired_cache"],
)
def test_update_from_remote_reports_actual_popularity_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cache_valid: bool,
    use_cache: bool,
) -> None:
    """update_from_remote() passes the cache path only when it is valid and allowed, and
    prints the source fetch_popularity_data reports (not a guess)."""
    db = LicenseDatabase(str(tmp_path / "licenses.db"))
    pop_cache = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    pop_cache.write_text(_CSV + "MIT,1\n")
    if not cache_valid:
        old = time.time() - 100 * 86400
        os.utime(pop_cache, (old, old))

    fetch = mock.create_autospec(
        spdx_source.fetch_popularity_data,
        return_value=({"MIT": 1}, "stale cache"),
    )
    monkeypatch.setattr(spdx_source, "fetch_popularity_data", fetch)
    monkeypatch.setattr(
        spdx_source, "get_version_info", lambda *_: ("9.99", None, "cache")
    )
    monkeypatch.setattr(
        spdx_source, "get_tarball_path", lambda *_: (tmp_path / "x.tgz", "cache")
    )
    monkeypatch.setattr(db, "_process_and_store", mock.Mock())

    assert db.update_from_remote(force=True, use_cache=use_cache)

    passed_local = fetch.call_args.args[1]
    assert passed_local == (pop_cache if cache_valid and use_cache else None)
    out = capsys.readouterr().out
    assert "GitHub license ranking data  : stale cache" in out


# --- non-silent deviations ---


def test_popularity_bad_counts_are_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Rows with a missing or non-numeric count still list the license (with
    0), and the deviation is reported once with the number of rows."""
    fake_requests_get(
        monkeypatch, _CSV + "MIT,abc\nISC\nGPL-2.0-only,\nBSD-2-Clause,5\n"
    )
    assert _popularity_map(tmp_path) == {
        "MIT": 0,
        "ISC": 0,
        "GPL-2.0-only": 0,
        "BSD-2-Clause": 5,
    }
    assert "3 popularity rows have a missing or non-numeric" in capsys.readouterr().out


def test_popularity_clean_data_prints_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_requests_get(monkeypatch, _CSV + "MIT,1\n")
    _popularity_map(tmp_path)
    assert "Warning" not in capsys.readouterr().out


def test_popularity_csv_parse_error_uses_no_partial_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A parse error mid-file must not leave a partial map that then gets
    cached for the full expiry period."""
    oversized = "MIT," + "9" * 200_000  # beyond csv's default field size limit
    fake_requests_get(monkeypatch, _CSV + "ISC,1\n" + oversized + "\n")
    assert _popularity_map(tmp_path) == {}
    assert not (tmp_path / spdx_source.CACHE_POPULARITY_CSV).exists()
    assert "Failed to parse popularity data" in capsys.readouterr().out


def test_popularity_unusable_data_is_reported_not_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    local = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    local.write_text("<html>oops</html>")
    fake_requests_get(monkeypatch, "<html>still broken</html>")
    assert _popularity_map(tmp_path, local) == {}
    out = capsys.readouterr().out
    assert "Cached popularity data has no usable rows; downloading" in out
    assert "Downloaded popularity data has no usable rows; not cached" in out


def test_popularity_stale_cache_with_no_rows_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / spdx_source.CACHE_POPULARITY_CSV).write_text("<html>oops</html>")
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.fetch_popularity_data(tmp_path) == ({}, "unavailable")
    assert "Stale cached popularity data has no usable rows" in capsys.readouterr().out


def test_popularity_stale_cache_not_used_when_disallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-cache means never fall back to cached data, even a stale copy."""
    (tmp_path / spdx_source.CACHE_POPULARITY_CSV).write_text(_CSV + "MIT,1\n")
    fake_requests_get(monkeypatch, error=requests.ConnectionError("down"))
    assert spdx_source.fetch_popularity_data(tmp_path, allow_stale=False) == (
        {},
        "unavailable",
    )
