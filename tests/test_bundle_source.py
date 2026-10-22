# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The fetches the bundle source adds to spdx_source: our bundle and its
cache, the version files in turn (latest.json, then spdx.org), and popularity
data read with no download. No test touches the network."""
# pylint: disable=missing-function-docstring

import gzip
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from conftest import fake_requests_get, leftover_tmp_files
from release_fakes import (
    RELEASE_DATE,
    bundle_url,
    release_bundle,
    release_data,
    serve,
    urls,
    version_json,
    warnings_of,
)

from licenseid import spdx_source
from licenseid.errors import InvalidInputError, LicenseIdError

NAME = "spdx-bundle-v9.99.json.gz"
NOT_FOUND = f"HTTPError: 404 Client Error: Not Found for url: {bundle_url()}"
BOTH = (spdx_source.LATEST_JSON_URL, spdx_source.LICENSES_JSON_URL)


# --- get_bundle ---


def test_a_bundle_is_downloaded_cached_then_read_from_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = serve(monkeypatch, {bundle_url(): release_bundle()})
    data, source = spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert (data, source) == (release_data(), "remote")
    assert (tmp_path / NAME).read_bytes() == release_bundle()
    assert not leftover_tmp_files(tmp_path)

    fake.reset_mock()
    assert spdx_source.get_bundle(tmp_path, "9.99", use_cache=True) == (
        release_data(),
        "cache",
    )
    fake.assert_not_called()


def test_no_cache_downloads_even_when_a_bundle_is_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / NAME).write_bytes(b"not read")
    fake = serve(monkeypatch, {bundle_url(): release_bundle()})
    assert spdx_source.get_bundle(tmp_path, "9.99", use_cache=False)[1] == "remote"
    assert urls(fake) == [bundle_url()]
    assert (tmp_path / NAME).read_bytes() == release_bundle()


def test_a_bundle_request_is_identified_streamed_and_quick_to_give_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = serve(monkeypatch, {bundle_url(): release_bundle()})
    spdx_source.get_bundle(tmp_path, "9.99", use_cache=False)
    kwargs = fake.call_args.kwargs
    assert kwargs["headers"]["User-Agent"] == spdx_source.user_agent()
    assert kwargs["timeout"] == (10, 60)
    assert kwargs["stream"] is True


def test_a_missing_bundle_is_a_download_failure_and_nothing_is_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {})
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert str(info.value) == f"{NAME}: download failed: {NOT_FOUND}"
    assert not list(tmp_path.iterdir())


def test_a_semicolon_in_the_error_cannot_start_an_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {bundle_url(): requests.ConnectionError("refused; retry")})
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert (
        str(info.value) == f"{NAME}: download failed: ConnectionError: refused, retry"
    )


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (b"<html>not gzip</html>", "BadGzipFile: Not a gzipped file (b'<h')"),
        (release_bundle()[:-8], "EOFError: Compressed file ended before the "),
        (release_bundle("9.98"), "version 9.98 is not the expected 9.99"),
    ],
    ids=["html", "truncated", "other_version"],
)
def test_an_unusable_download_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, detail: str
) -> None:
    serve(monkeypatch, {bundle_url(): body})
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert str(info.value).startswith(f"{NAME}: download unusable: {detail}")
    assert not list(tmp_path.iterdir())


def test_an_oversized_bundle_is_refused_as_it_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counted from the bytes that arrive, never from Content-Length, and
    given up at the first chunk past the cap."""
    sent: list[int] = []

    def chunks() -> Iterator[bytes]:
        for _ in range(5):
            sent.append(4)
            yield b"1234"

    fake = fake_requests_get(monkeypatch)
    fake.return_value.iter_content.return_value = chunks()
    monkeypatch.setattr(spdx_source, "MAX_BUNDLE_BYTES", 10)
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert str(info.value) == f"{NAME}: download unusable: larger than 10 bytes"
    assert len(sent) == 3
    fake.return_value.close.assert_called_once_with()
    assert not list(tmp_path.iterdir())


def test_a_bundle_exactly_at_the_cap_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = release_bundle()
    serve(monkeypatch, {bundle_url(): raw})
    monkeypatch.setattr(spdx_source, "MAX_BUNDLE_BYTES", len(raw))
    assert spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)[1] == "remote"


@pytest.mark.parametrize(
    "cached",
    [b"garbage", gzip.compress(b"{}"), release_bundle("9.98")],
    ids=["not_gzip", "not_a_bundle", "other_version"],
)
def test_an_unusable_cached_bundle_is_removed_and_downloaded_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cached: bytes,
) -> None:
    (tmp_path / NAME).write_bytes(cached)
    serve(monkeypatch, {bundle_url(): release_bundle()})
    assert spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)[1] == "remote"
    assert (tmp_path / NAME).read_bytes() == release_bundle()
    warnings = [
        line for line in capsys.readouterr().err.splitlines() if "WARNING" in line
    ]
    assert len(warnings) == 1
    assert warnings[0].startswith(f"WARNING: {NAME}: cache unusable: ")
    assert warnings[0].endswith("; downloading")


def test_an_unusable_cached_bundle_and_a_failed_download_leave_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / NAME).write_bytes(b"garbage")
    serve(monkeypatch, {})
    with pytest.raises(LicenseIdError, match="download failed"):
        spdx_source.get_bundle(tmp_path, "9.99", use_cache=True)
    assert not (tmp_path / NAME).exists()


def test_a_bundle_that_cannot_be_cached_is_still_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    serve(monkeypatch, {bundle_url(): release_bundle()})

    def refuse(src: object, dst: object) -> None:
        raise PermissionError(13, "in use")

    monkeypatch.setattr(os, "replace", refuse)
    assert spdx_source.get_bundle(tmp_path, "9.99", use_cache=True) == (
        release_data(),
        "remote",
    )
    assert capsys.readouterr().err.endswith(
        f"WARNING: {NAME}: cache write failed: PermissionError: [Errno 13] in use\n"
    )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("version", ["../x", "", "a/b"])
def test_an_unsafe_version_never_reaches_a_file_name_or_url(
    tmp_path: Path, version: str
) -> None:
    with pytest.raises(InvalidInputError, match="^version: invalid: "):
        spdx_source.get_bundle(tmp_path, version, use_cache=True)
    assert not list(tmp_path.iterdir())


# --- get_version_info over several version files ---


def test_latest_json_answers_first_and_has_a_cache_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    latest = {**version_json(), "file": "v9.99.json.gz", "sha256": "0" * 64}
    fake = serve(monkeypatch, {spdx_source.LATEST_JSON_URL: latest})
    result = spdx_source.get_version_info(tmp_path, None, False, BOTH)
    assert result == ("9.99", RELEASE_DATE, "remote")
    assert urls(fake) == [spdx_source.LATEST_JSON_URL]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["latest.json"]
    fake.reset_mock()
    assert spdx_source.get_version_info(tmp_path, None, True, BOTH) == (
        "9.99",
        RELEASE_DATE,
        "cache",
    )
    fake.assert_not_called()


def _version_cache(tmp_path: Path, name: str, version: str, age_days: int) -> None:
    path = tmp_path / name
    path.write_text(json.dumps(version_json(version)), encoding="utf-8")
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))


def test_only_the_caches_of_the_urls_asked_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spdx.org's newer version in licenses.json never answers for latest.json."""
    _version_cache(tmp_path, "licenses.json", "9.99", 0)
    fake = serve(monkeypatch, {spdx_source.LATEST_JSON_URL: version_json("9.98")})
    latest_only = (spdx_source.LATEST_JSON_URL,)
    assert spdx_source.get_version_info(tmp_path, None, True, latest_only)[0] == "9.98"
    assert urls(fake) == [spdx_source.LATEST_JSON_URL]
    fake.reset_mock()  # both asked: a valid cache of either comes before a download
    assert spdx_source.get_version_info(tmp_path, None, True, BOTH)[0] == "9.98"
    (tmp_path / "latest.json").unlink()
    assert spdx_source.get_version_info(tmp_path, None, True, BOTH) == (
        "9.99",
        RELEASE_DATE,
        "cache",
    )
    fake.assert_not_called()


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        pytest.param(44, "9.98", id="valid"),
        pytest.param(46, "9.99", id="expired"),
    ],
)
def test_latest_json_is_cached_until_it_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, age: int, expected: str
) -> None:
    _version_cache(tmp_path, "latest.json", "9.98", age)
    fake = serve(monkeypatch, {spdx_source.LATEST_JSON_URL: version_json("9.99")})
    result = spdx_source.get_version_info(tmp_path, None, True, BOTH)
    assert result[0] == expected
    assert urls(fake) == ([] if expected == "9.98" else [spdx_source.LATEST_JSON_URL])


@pytest.mark.parametrize(
    ("name", "action"),
    [
        ("licenses.json", "using stale cache"),
        ("latest.json", "using stale latest.json"),
    ],
    ids=["own", "other"],
)
def test_a_stale_cache_names_its_file_when_it_is_another(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
    action: str,
) -> None:
    _version_cache(tmp_path, name, "9.97", 100)
    serve(monkeypatch, {})
    result = spdx_source.get_version_info(tmp_path, None, True, BOTH)
    assert result == ("9.97", RELEASE_DATE, "stale cache")
    last = warnings_of(capsys.readouterr().err)[-1]
    assert last.startswith("WARNING: licenses.json: download failed: HTTPError: 404")
    assert last.endswith(f"; {action}")


def test_no_cache_reads_neither_version_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("latest.json", "licenses.json"):
        _version_cache(tmp_path, name, "9.97", 0)
    serve(monkeypatch, {})
    with pytest.raises(LicenseIdError, match="^licenses.json: download failed: "):
        spdx_source.get_version_info(tmp_path, None, False, BOTH)


def test_an_unusable_latest_json_cache_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "latest.json").write_text("not json", encoding="utf-8")
    serve(monkeypatch, {spdx_source.LATEST_JSON_URL: version_json()})
    assert spdx_source.get_version_info(tmp_path, None, True, BOTH)[2] == "remote"
    assert warnings_of(capsys.readouterr().err) == [
        "WARNING: latest.json: cache unusable; downloading"
    ]
    assert json.loads((tmp_path / "latest.json").read_text()) == version_json()


def test_a_latest_json_cache_write_failure_names_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, {spdx_source.LATEST_JSON_URL: version_json()})

    def refuse(src: object, dst: object) -> None:
        raise PermissionError(13, "in use")

    monkeypatch.setattr(os, "replace", refuse)
    assert spdx_source.get_version_info(tmp_path, None, True, BOTH)[0] == "9.99"
    assert warnings_of(capsys.readouterr().err) == [
        "WARNING: latest.json: cache write failed: PermissionError: [Errno 13] in use"
    ]


@pytest.mark.parametrize(
    ("latest", "condition"),
    [
        (None, "download failed: HTTPError: 404 Client Error: Not Found for url: "),
        ({"licenseListVersion": "../x"}, "download unusable: no valid license"),
    ],
    ids=["missing", "bad_version"],
)
def test_a_failed_latest_json_warns_and_asks_spdx_org(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    latest: dict[str, object] | None,
    condition: str,
) -> None:
    routes: dict[str, object] = {spdx_source.LICENSES_JSON_URL: version_json("9.98")}
    if latest is not None:
        routes[spdx_source.LATEST_JSON_URL] = latest
    fake = serve(monkeypatch, routes)  # type: ignore[arg-type]
    result = spdx_source.get_version_info(tmp_path, None, False, BOTH)
    assert result == ("9.98", RELEASE_DATE, "remote")
    assert urls(fake) == list(BOTH)
    warnings = [line for line in capsys.readouterr().err.splitlines() if "WARN" in line]
    assert len(warnings) == 1
    assert warnings[0].startswith(f"WARNING: latest.json: {condition}")
    assert warnings[0].endswith("; downloading licenses.json")


def test_when_every_version_file_fails_the_last_one_is_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {})
    with pytest.raises(LicenseIdError) as info:
        spdx_source.get_version_info(tmp_path, None, False, BOTH)
    assert str(info.value).startswith("licenses.json: download failed: HTTPError: ")
    assert ";" not in str(info.value)  # no ACTION: the caller adds its fallback


def test_a_release_date_that_is_not_a_string_is_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(
        monkeypatch,
        {
            spdx_source.LICENSES_JSON_URL: {
                "licenseListVersion": "9.99",
                "releaseDate": 1,
            }
        },
    )
    assert spdx_source.get_version_info(tmp_path, None, False) == (
        "9.99",
        None,
        "remote",
    )


# --- popularity data with no download ---


def _popularity_cache(tmp_path: Path, text: str, age_days: int = 0) -> None:
    path = tmp_path / spdx_source.CACHE_POPULARITY_CSV
    path.write_text(text, encoding="utf-8")
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))


def test_cached_popularity_reads_a_valid_cache_silently(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _popularity_cache(tmp_path, "spdx_license,num_pushers\nMIT,5\n")
    assert spdx_source.cached_popularity_data(tmp_path, True) == ({"MIT": 5}, "cache")
    assert "WARNING" not in capsys.readouterr().err


def test_cached_popularity_uses_an_expired_cache_with_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _popularity_cache(tmp_path, "spdx_license,num_pushers\nMIT,5\n", age_days=100)
    assert spdx_source.cached_popularity_data(tmp_path, True) == (
        {"MIT": 5},
        "stale cache",
    )
    assert capsys.readouterr().err.endswith(
        "WARNING: popularity.csv: 100 days old; using stale cache\n"
    )


@pytest.mark.parametrize(
    ("text", "use_cache", "condition"),
    [
        (None, True, "missing"),
        ("spdx_license,num_pushers\nMIT,5\n", False, "missing"),
        ("<html>oops</html>", True, "cache unusable"),
    ],
    ids=["absent", "no_cache", "unusable"],
)
def test_cached_popularity_without_usable_data_is_unavailable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    text: str | None,
    use_cache: bool,
    condition: str,
) -> None:
    """With no download: conftest's offline fake fails any request."""
    if text is not None:
        _popularity_cache(tmp_path, text)
    assert spdx_source.cached_popularity_data(tmp_path, use_cache) == (
        {},
        "unavailable",
    )
    assert capsys.readouterr().err.endswith(f"WARNING: popularity.csv: {condition}\n")
