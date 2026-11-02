# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The build hook that ships the SPDX snapshot (``hatch_build.py``)."""
# pylint: disable=missing-function-docstring,protected-access

import gzip
import hashlib
import http.client
import http.server
import io
import json
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from http.client import HTTPMessage
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from release_fakes import FakeResponse, release_bundle

import hatch_build
from hatch_build import SnapshotError, SpdxSnapshotHook
from licenseid import spdx_source, spdxdata

# The real pin, read before the autouse fixture pins the fake release.
PIN = (hatch_build.BUNDLE_VERSION, hatch_build.BUNDLE_SHA256)
BUNDLE = release_bundle()
NAME = "v9.99.json.gz"


def serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]) -> list[str]:
    """Answer the URLs of *files* (by name under the base); anything else is an
    error. Return the URLs asked for."""
    calls: list[str] = []

    def open_url(url: str) -> FakeResponse:
        calls.append(url)
        name = url.removeprefix(hatch_build.BASE_URL)
        if url == name or name not in files:
            raise OSError(f"404: {url}")
        return FakeResponse(files[name])

    monkeypatch.setattr(hatch_build, "open_url", open_url)
    return calls


def online(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return serve(monkeypatch, {NAME: BUNDLE})


def gz(doc: object) -> bytes:
    return gzip.compress(json.dumps(doc).encode())


def names(calls: list[str]) -> list[str]:
    return [url.rsplit("/", 1)[1] for url in calls]


def unpacked_sdist(root: Path, content: bytes) -> Path:
    """Put *content* where an sdist keeps the snapshot; return the file. An
    sdist has a ``PKG-INFO``, a checkout does not."""
    (root / "PKG-INFO").write_text("Metadata-Version: 2.4\n", encoding="utf-8")
    in_tree = root / hatch_build.IN_TREE
    in_tree.parent.mkdir(parents=True)
    in_tree.write_bytes(content)
    return in_tree


def hook(root: Path, target: str = "wheel") -> tuple[SpdxSnapshotHook, mock.Mock]:
    app = mock.Mock(spec=["display_warning"])
    return SpdxSnapshotHook(
        str(root), {}, mock.Mock(), mock.Mock(), str(root / "dist"), target, app
    ), app


def build_artifact(root: Path, target: str, build_data: dict[str, Any]) -> str:
    """A wheel or sdist holding what ``force_include`` asks for, as hatchling
    builds it; ``""`` for another target."""
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    if target == "wheel":
        wheel = dist / "licenseid-0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("licenseid/__init__.py", "")
            for source, path in build_data["force_include"].items():
                archive.write(source, path)
        return str(wheel)
    if target == "sdist":
        sdist = dist / "licenseid-0.tar.gz"
        with tarfile.open(sdist, "w:gz") as archive:
            for source, path in build_data["force_include"].items():
                archive.add(source, f"licenseid-0/{path}")
        return str(sdist)
    return ""


def run(
    root: Path, target: str = "wheel", version: str = "standard"
) -> tuple[dict[str, Any], mock.Mock]:
    """Run ``initialize``, build and ``finalize``; return ``build_data`` and
    the app."""
    instance, app = hook(root, target)
    build_data: dict[str, Any] = {"force_include": {}}
    artifact = ""
    try:
        instance.initialize(version, build_data)
        artifact = build_artifact(root, target, build_data)
    finally:
        instance.finalize(version, build_data, artifact)
    return build_data, app


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No variable set, and the fake release is the pin."""
    for name in ("LICENSEID_BUNDLE", "LICENSEID_REQUIRE_BUNDLE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(hatch_build, "BUNDLE_VERSION", "9.99")
    monkeypatch.setattr(
        hatch_build, "BUNDLE_SHA256", hashlib.sha256(BUNDLE).hexdigest()
    )


def test_the_hook_and_the_package_agree_on_names() -> None:
    assert hatch_build.BASE_URL == spdx_source.BUNDLE_BASE_URL
    assert hatch_build.BASE_URL + NAME == spdx_source.BUNDLE_URL_TEMPLATE.format(
        version="9.99"
    )
    assert hatch_build.ARCHIVE_PATH == {
        "wheel": f"licenseid/data/{spdxdata.PACKAGED_NAME}",
        "sdist": f"src/licenseid/data/{spdxdata.PACKAGED_NAME}",
    }
    assert hatch_build.BUNDLE_FORMAT == spdxdata.BUNDLE_FORMAT
    assert hatch_build.MAX_UNZIPPED == spdxdata.MAX_UNZIPPED


@pytest.mark.parametrize("target", ["wheel", "sdist"])
def test_a_build_ships_the_downloaded_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    calls = online(monkeypatch)
    build_data, app = run(tmp_path, target)
    source, archive = next(iter(build_data["force_include"].items()))
    assert archive == hatch_build.ARCHIVE_PATH[target]
    assert names(calls) == [NAME]
    app.display_warning.assert_not_called()
    # The scratch directory is gone with the build.
    assert not Path(source).exists()


def test_the_bundle_is_read_before_the_scratch_directory_goes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    online(monkeypatch)
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    source = next(iter(build_data["force_include"]))
    assert Path(source).read_bytes() == BUNDLE
    instance.finalize(
        "standard", build_data, build_artifact(tmp_path, "wheel", build_data)
    )
    assert not Path(source).exists()


def test_the_file_in_the_tree_is_used_without_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    in_tree = unpacked_sdist(tmp_path, BUNDLE)
    build_data, _ = run(tmp_path, "wheel")
    assert build_data["force_include"] == {
        str(in_tree): "licenseid/data/spdx-bundle.json.gz"
    }
    assert not calls


def test_an_override_path_wins_over_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    unpacked_sdist(tmp_path, b"not a bundle")
    mine = tmp_path / "mine.json.gz"
    mine.write_bytes(BUNDLE)
    monkeypatch.setenv("LICENSEID_BUNDLE", str(mine))
    build_data, _ = run(tmp_path, "sdist")
    assert list(build_data["force_include"]) == [str(mine.resolve())]
    assert not calls


@pytest.mark.parametrize("version", ["editable", "standard"])
def test_skip_and_editable_ship_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    calls = serve(monkeypatch, {})
    if version == "standard":
        monkeypatch.setenv("LICENSEID_BUNDLE", "skip")
    build_data, app = run(tmp_path, "wheel", version)
    assert build_data == {"force_include": {}}
    assert not calls
    app.display_warning.assert_not_called()


def test_another_target_ships_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    build_data, _ = run(tmp_path, "custom")
    assert build_data == {"force_include": {}}
    assert not calls


OTHER_BUILD = gz({"format": 1, "licenseListVersion": "9.99", "other": "bytes"})
FAILURES = {
    "offline": {},
    "pinned version not published": {"v10.0.json.gz": BUNDLE},
    "not gzip": {NAME: b"<html>"},
    "another version": {NAME: gz({"format": 1, "licenseListVersion": "10.0"})},
    "other bytes of the version": {NAME: OTHER_BUILD},
}


@pytest.mark.parametrize("files", FAILURES.values(), ids=FAILURES.keys())
def test_a_failure_warns_and_ships_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]
) -> None:
    serve(monkeypatch, files)
    build_data, app = run(tmp_path)
    assert build_data == {"force_include": {}}
    (call,) = app.display_warning.call_args_list
    assert call.args[0].startswith("licenseid: no SPDX snapshot shipped: ")


@pytest.mark.parametrize("files", FAILURES.values(), ids=FAILURES.keys())
def test_a_failure_fails_the_build_when_a_snapshot_is_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, bytes],
) -> None:
    serve(monkeypatch, files)
    monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
    with pytest.raises((OSError, SnapshotError)):
        run(tmp_path)


class CutResponse(FakeResponse):
    """A response whose body is cut off."""

    def read(self, size: int) -> bytes:
        raise http.client.IncompleteRead(b"ab", 5)


def refused_status(url: str) -> FakeResponse:
    raise http.client.BadStatusLine(url)


def cut_body(url: str) -> FakeResponse:
    return CutResponse(url.encode())


@pytest.mark.parametrize("opener", [refused_status, cut_body], ids=["status", "body"])
@pytest.mark.parametrize("required", [False, True], ids=["warns", "fails"])
def test_a_broken_http_exchange_is_a_snapshot_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    required: bool,
    opener: Any,
) -> None:
    """``http.client`` errors are not ``OSError``: they must not crash a build
    that does not require the snapshot."""
    monkeypatch.setattr(hatch_build, "open_url", opener)
    if required:
        monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
        with pytest.raises(
            SnapshotError, match=r"v9\.99\.json\.gz: (BadStatusLine|Incomp)"
        ):
            run(tmp_path)
        return
    build_data, app = run(tmp_path)
    assert build_data == {"force_include": {}}
    (call,) = app.display_warning.call_args_list
    assert call.args[0].startswith("licenseid: no SPDX snapshot shipped: ")


@pytest.mark.parametrize("required", [False, True], ids=["warns", "fails"])
def test_a_failed_download_leaves_no_scratch_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    """Hatchling runs no finalize after an initialize that raised."""
    serve(monkeypatch, {})
    made: list[str] = []
    mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(*args: Any, **kwargs: Any) -> str:
        made.append(mkdtemp(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(tempfile, "mkdtemp", recording_mkdtemp)
    if required:
        monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    if required:
        with pytest.raises(OSError):
            instance.initialize("standard", build_data)
    else:
        instance.initialize("standard", build_data)
    assert len(made) == 1
    assert not Path(made[0]).exists()
    assert instance._scratch is None


def test_a_missing_override_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LICENSEID_BUNDLE", str(tmp_path / "absent.json.gz"))
    build_data, app = run(tmp_path)
    assert build_data == {"force_include": {}}
    app.display_warning.assert_called_once()


def test_an_unusable_file_in_the_tree_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    unpacked_sdist(tmp_path, b"not gzip")
    build_data, app = run(tmp_path)
    assert build_data == {"force_include": {}}
    app.display_warning.assert_called_once()
    assert not calls


@pytest.mark.parametrize(
    ("raw", "version", "reason"),
    [
        (b"plain", "1", "not gzip"),
        (gzip.compress(b"{"), "1", "not a bundle"),
        (gz([]), "1", "not a bundle"),
        (gz({"format": 1}), "1", "not a bundle"),
        (gz({"format": 2, "licenseListVersion": "1"}), "1", "format 2"),
        (gz({"format": 1, "licenseListVersion": "1"}), "2", "version '1'"),
    ],
    ids=["plain", "truncated", "list", "no version", "format", "version"],
)
def test_check_bundle_refuses(raw: bytes, version: str, reason: str) -> None:
    with pytest.raises(SnapshotError, match=reason):
        hatch_build.check_bundle(raw, version)


def test_check_bundle_accepts_a_bundle_of_the_named_version() -> None:
    hatch_build.check_bundle(BUNDLE, "9.99")
    hatch_build.check_bundle(BUNDLE, "9.99")


def test_check_bundle_refuses_a_bomb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hatch_build, "MAX_UNZIPPED", 10)
    with pytest.raises(SnapshotError, match="unzipped"):
        hatch_build.check_bundle(BUNDLE, "9.99")


def test_a_download_over_the_cap_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, {"x": b"0123456789"})
    monkeypatch.setattr(hatch_build, "CHUNK", 4)
    assert hatch_build.fetch(hatch_build.BASE_URL + "x", 10) == b"0123456789"
    with pytest.raises(SnapshotError, match="larger than 9 bytes"):
        hatch_build.fetch(hatch_build.BASE_URL + "x", 9)


def test_a_url_that_is_not_https_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = serve(monkeypatch, {})
    with pytest.raises(SnapshotError, match="not https"):
        hatch_build.fetch("file:///etc/passwd", 10)
    assert not calls


def test_a_checkout_ignores_a_file_left_in_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only an unpacked sdist (which has PKG-INFO) trusts the file in the tree."""
    calls = online(monkeypatch)
    stale = tmp_path / hatch_build.IN_TREE
    stale.parent.mkdir(parents=True)
    stale.write_bytes(gz({"format": 1, "licenseListVersion": "0.1"}))
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    source = next(iter(build_data["force_include"]))
    assert source != str(stale)
    assert Path(source).read_bytes() == BUNDLE
    assert names(calls) == [NAME]
    instance.finalize(
        "standard", build_data, build_artifact(tmp_path, "wheel", build_data)
    )


def test_an_sdist_without_a_snapshot_downloads_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An sdist built with no snapshot (the download failed) is not a source."""
    calls = online(monkeypatch)
    (tmp_path / "PKG-INFO").write_text("Metadata-Version: 2.4\n", encoding="utf-8")
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    assert len(build_data["force_include"]) == 1
    assert names(calls) == [NAME]
    instance.finalize(
        "standard", build_data, build_artifact(tmp_path, "wheel", build_data)
    )


def test_open_url_has_a_timeout_and_refuses_http_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class Opener:
        """An opener that records its call."""

        def open(self, url: str, timeout: float) -> str:
            seen.update(url=url, timeout=timeout)
            return "response"

    def build_opener(*handlers: Any) -> Opener:
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    assert hatch_build.open_url("https://example.org/a") == "response"
    assert seen == {
        "url": "https://example.org/a",
        "timeout": hatch_build.TIMEOUT,
        "handlers": (hatch_build._HttpsRedirects,),
    }


def test_a_redirect_to_https_is_followed_and_to_http_is_not() -> None:
    handler = hatch_build._HttpsRedirects()
    request = urllib.request.Request("https://example.org/a")
    followed, refused = io.BytesIO(), io.BytesIO()
    follow = handler.redirect_request(
        request, followed, 302, "Found", HTTPMessage(), "https://example.org/b"
    )
    assert follow is not None and follow.full_url == "https://example.org/b"
    assert not followed.closed  # urllib closes it
    with pytest.raises(SnapshotError, match="redirected to http://example.org/b"):
        handler.redirect_request(
            request, refused, 302, "Found", HTTPMessage(), "http://example.org/b"
        )
    assert refused.closed


def test_the_opener_stops_at_a_redirect_to_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler is wired into the opener, with a real redirect."""
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")

    class Redirect(http.server.BaseHTTPRequestHandler):
        """A server that sends every request to an http URL."""

        def do_GET(self) -> None:  # pylint: disable=invalid-name
            self.send_response(302)
            self.send_header("Location", "http://example.org/elsewhere")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            """Silent."""

    with http.server.HTTPServer(("127.0.0.1", 0), Redirect) as server:
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        try:
            with pytest.raises(SnapshotError, match="not https"):
                hatch_build.open_url(f"http://127.0.0.1:{server.server_port}/a")
        finally:
            thread.join(timeout=10)
