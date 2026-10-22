# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The build hook that ships the SPDX snapshot (``hatch_build.py``)."""
# pylint: disable=missing-function-docstring,protected-access

import gzip
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from release_fakes import FakeResponse, release_bundle

import hatch_build
from hatch_build import SnapshotError, SpdxSnapshotHook
from licenseid import spdx_source, spdxdata

BUNDLE = release_bundle()
NAME = "v9.99.json.gz"


def pointer(raw: bytes = BUNDLE, **changes: Any) -> bytes:
    doc = {
        "file": NAME,
        "licenseListVersion": "9.99",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }
    return json.dumps({**doc, **changes}).encode()


def serve(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]
) -> list[tuple[str, float]]:
    """Answer the URLs of *files* (by name under the base); anything else is an
    error. Return the calls."""
    calls: list[tuple[str, float]] = []

    def urlopen(url: str, timeout: float) -> FakeResponse:
        calls.append((url, timeout))
        name = url.removeprefix(hatch_build.BASE_URL)
        if url == name or name not in files:
            raise OSError(f"404: {url}")
        return FakeResponse(files[name])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def online(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, float]]:
    return serve(monkeypatch, {"latest.json": pointer(), NAME: BUNDLE})


def hook(root: Path, target: str = "wheel") -> tuple[SpdxSnapshotHook, mock.Mock]:
    app = mock.Mock(spec=["display_warning"])
    return SpdxSnapshotHook(
        str(root), {}, mock.Mock(), mock.Mock(), str(root / "dist"), target, app
    ), app


def run(
    root: Path, target: str = "wheel", version: str = "standard"
) -> tuple[dict[str, Any], mock.Mock]:
    """Run ``initialize`` and ``finalize``; return ``build_data`` and the app."""
    instance, app = hook(root, target)
    build_data: dict[str, Any] = {"force_include": {}}
    try:
        instance.initialize(version, build_data)
    finally:
        instance.finalize(version, build_data, "")
    return build_data, app


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LICENSEID_BUNDLE", "LICENSEID_REQUIRE_BUNDLE"):
        monkeypatch.delenv(name, raising=False)


def test_the_hook_and_the_package_agree_on_names() -> None:
    assert hatch_build.BASE_URL == spdx_source.BUNDLE_BASE_URL
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
    assert [url.rsplit("/", 1)[1] for url, _ in calls] == ["latest.json", NAME]
    assert {timeout for _, timeout in calls} == {hatch_build.TIMEOUT}
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
    instance.finalize("standard", build_data, "")
    assert not Path(source).exists()


def test_the_file_in_the_tree_is_used_without_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    in_tree = tmp_path / hatch_build.IN_TREE
    in_tree.parent.mkdir(parents=True)
    in_tree.write_bytes(BUNDLE)
    build_data, _ = run(tmp_path, "wheel")
    assert build_data["force_include"] == {
        str(in_tree): "licenseid/data/spdx-bundle.json.gz"
    }
    assert not calls


def test_an_override_path_wins_over_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = serve(monkeypatch, {})
    in_tree = tmp_path / hatch_build.IN_TREE
    in_tree.parent.mkdir(parents=True)
    in_tree.write_bytes(b"not a bundle")
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


FAILURES = {
    "offline": {},
    "no pointer": {NAME: BUNDLE},
    "pointer not json": {"latest.json": b"<html>", NAME: BUNDLE},
    "pointer not an object": {"latest.json": b"[]", NAME: BUNDLE},
    "pointer without a key": {"latest.json": b"{}", NAME: BUNDLE},
    "file escapes": {
        "latest.json": pointer(file="../../x.json.gz"),
        NAME: BUNDLE,
    },
    "file not a name": {"latest.json": pointer(file=7), NAME: BUNDLE},
    "digest not a digest": {"latest.json": pointer(sha256="abc"), NAME: BUNDLE},
    "digest wrong": {"latest.json": pointer(sha256="0" * 64), NAME: BUNDLE},
    "size wrong": {"latest.json": pointer(size=1), NAME: BUNDLE},
    "bundle missing": {"latest.json": pointer()},
    "version differs": {"latest.json": pointer(licenseListVersion="1.0"), NAME: BUNDLE},
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


@pytest.mark.parametrize(
    "bad",
    [pointer(file="../../x.json.gz"), pointer(file=7), pointer(sha256="abc")],
    ids=["file escapes", "file not a name", "digest not a digest"],
)
def test_a_bad_pointer_fetches_no_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: bytes
) -> None:
    calls = serve(monkeypatch, {"latest.json": bad, "x.json.gz": BUNDLE, NAME: BUNDLE})
    run(tmp_path)
    assert [url.rsplit("/", 1)[1] for url, _ in calls] == ["latest.json"]


def test_a_failed_download_leaves_no_scratch_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {})
    instance, _ = hook(tmp_path)
    instance.initialize("standard", {"force_include": {}})
    scratch = instance._scratch
    assert scratch is not None and Path(scratch).is_dir()
    instance.finalize("standard", {}, "")
    assert not Path(scratch).exists()
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
    in_tree = tmp_path / hatch_build.IN_TREE
    in_tree.parent.mkdir(parents=True)
    in_tree.write_bytes(b"not gzip")
    build_data, app = run(tmp_path)
    assert build_data == {"force_include": {}}
    app.display_warning.assert_called_once()
    assert not calls


def gz(doc: object) -> bytes:
    return gzip.compress(json.dumps(doc).encode())


@pytest.mark.parametrize(
    ("raw", "version", "reason"),
    [
        (b"plain", None, "not gzip"),
        (gzip.compress(b"{"), None, "not a bundle"),
        (gz([]), None, "not a bundle"),
        (gz({"format": 1}), None, "not a bundle"),
        (gz({"format": 2, "licenseListVersion": "1"}), None, "format 2"),
        (gz({"format": 1, "licenseListVersion": "1"}), "2", "version '1'"),
    ],
    ids=["plain", "truncated", "list", "no version", "format", "version"],
)
def test_check_bundle_refuses(raw: bytes, version: str | None, reason: str) -> None:
    with pytest.raises(SnapshotError, match=reason):
        hatch_build.check_bundle(raw, version)


def test_check_bundle_accepts_a_bundle_of_any_or_the_named_version() -> None:
    hatch_build.check_bundle(BUNDLE, None)
    hatch_build.check_bundle(BUNDLE, "9.99")


def test_check_bundle_refuses_a_bomb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hatch_build, "MAX_UNZIPPED", 10)
    with pytest.raises(SnapshotError, match="unzipped"):
        hatch_build.check_bundle(BUNDLE, None)


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
