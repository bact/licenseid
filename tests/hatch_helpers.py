# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fakes for the tests of the build hook (``hatch_build.py``) and of
``scripts/check_dist_bundle.py``: a served release, a hook, built artefacts.

``clean_environment`` sets up each test of the hook."""

import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest
from release_fakes import FakeResponse, release_bundle

import hatch_build
from hatch_build import SpdxSnapshotHook

ROOT = Path(__file__).parent.parent


def gz(doc: object) -> bytes:
    """*doc* as gzipped JSON."""
    return gzip.compress(json.dumps(doc).encode())


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
    """Serve the fake release; return the URLs asked for."""
    return serve(monkeypatch, {NAME: BUNDLE})


def names(calls: list[str]) -> list[str]:
    """The file names of *calls*."""
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
    """A hook for *target* in *root*, and its app."""
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


def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No variable set, and the fake release is the pin: each test module of
    the hook calls it from an autouse fixture of its own."""
    for name in ("LICENSEID_BUNDLE", "LICENSEID_REQUIRE_BUNDLE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(hatch_build, "BUNDLE_VERSION", "9.99")
    monkeypatch.setattr(
        hatch_build, "BUNDLE_SHA256", hashlib.sha256(BUNDLE).hexdigest()
    )


OTHER_BUILD = gz({"format": 1, "licenseListVersion": "9.99", "other": "bytes"})


def wheel_with(path: Path, members: dict[str, bytes]) -> Path:
    """A zip at *path* holding *members*."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    return path


def sdist_with(path: Path, members: dict[str, bytes]) -> Path:
    """A gzipped tar at *path* holding *members* as regular files."""
    with tarfile.open(path, "w:gz") as archive:
        for name, raw in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return path


WHEEL_PATH = hatch_build.ARCHIVE_PATH["wheel"]
SDIST_PATH = f"licenseid-0/{hatch_build.IN_TREE}"


def load_script(name: str) -> ModuleType:
    """A module of ``scripts/`` (not a package), loaded by path."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sdist_with_link(path: Path) -> Path:
    """An sdist whose bundle is a symbolic link to another member."""
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("licenseid-0/other")
        info.size = len(BUNDLE)
        archive.addfile(info, io.BytesIO(BUNDLE))
        link = tarfile.TarInfo(SDIST_PATH)
        link.type = tarfile.SYMTYPE
        link.linkname = "../../../other"
        archive.addfile(link)
    return path
