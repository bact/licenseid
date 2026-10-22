# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Hatch build hook: ship the SPDX snapshot that ``licenseid update`` falls
back to when no network source answers.

The snapshot is the published bundle (``licenseid.spdxdata``, format 1). The
hook adds it to the wheel as ``licenseid/data/spdx-bundle.json.gz`` and to the
sdist as ``src/licenseid/data/spdx-bundle.json.gz``, so a wheel built from an
unpacked sdist finds it in the tree and needs no network.

Standard library only: the build runs in an isolated environment that has
hatchling and nothing of ``licenseid``.

Environment:

``LICENSEID_BUNDLE=skip``
    Ship no snapshot (CI jobs that only install the package, and the workflow
    that publishes the bundle).
``LICENSEID_BUNDLE=<path>``
    Ship that bundle: a hermetic build, no network.
``LICENSEID_REQUIRE_BUNDLE=1``
    A missing or unusable snapshot fails the build instead of a warning.
"""

import gzip
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Final

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Copies of constants in ``licenseid.spdx_source`` and ``licenseid.spdxdata``
# (BUNDLE_BASE_URL, PACKAGED_NAME, BUNDLE_FORMAT, MAX_UNZIPPED), which the
# build cannot import; tests/test_hatch_build.py checks they agree.
BASE_URL: Final = (
    "https://raw.githubusercontent.com/bact/licenseid/refs/heads/data/spdx/format-1/"
)
IN_TREE: Final = "src/licenseid/data/spdx-bundle.json.gz"
ARCHIVE_PATH: Final = {"wheel": "licenseid/data/spdx-bundle.json.gz", "sdist": IN_TREE}
BUNDLE_FORMAT: Final = 1
MAX_BUNDLE: Final = 16 * 1024 * 1024
MAX_UNZIPPED: Final = 32 * 1024 * 1024
MAX_POINTER: Final = 64 * 1024
CHUNK: Final = 1024 * 1024
TIMEOUT: Final = 30
# What ``tools.build_bundle`` writes: nothing that could leave the base URL.
FILE_RE: Final = re.compile(r"v[0-9]+(\.[0-9]+)*\.json\.gz")
SHA256_RE: Final = re.compile(r"[0-9a-f]{64}")


class SnapshotError(Exception):
    """The snapshot cannot be had; ``str()`` says why."""


def fetch(url: str, limit: int) -> bytes:
    """The body of *url*, refused over *limit* bytes."""
    if not url.startswith("https://"):
        raise SnapshotError(f"{url}: not https")
    chunks: list[bytes] = []
    size = 0
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:  # nosec B310
        while chunk := response.read(CHUNK):
            size += len(chunk)
            if size > limit:
                raise SnapshotError(f"{url}: larger than {limit} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def check_bundle(raw: bytes, version: str | None) -> None:
    """Refuse *raw* unless it is a format 1 bundle (of *version*, if given)."""
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            payload = stream.read(MAX_UNZIPPED + 1)
    except (OSError, EOFError) as exc:
        raise SnapshotError(f"not gzip: {type(exc).__name__}: {exc}") from exc
    if len(payload) > MAX_UNZIPPED:
        raise SnapshotError(f"larger than {MAX_UNZIPPED} bytes unzipped")
    try:
        doc: Any = json.loads(payload)
        found = (doc["format"], doc["licenseListVersion"])
    except (ValueError, KeyError, TypeError) as exc:
        raise SnapshotError(f"not a bundle: {type(exc).__name__}: {exc}") from exc
    if found[0] != BUNDLE_FORMAT:
        raise SnapshotError(f"format {found[0]!r}, not {BUNDLE_FORMAT}")
    if version is not None and found[1] != version:
        raise SnapshotError(f"version {found[1]!r}, not {version!r}")


def download(scratch: Path) -> Path:
    """Fetch and check the latest published bundle into *scratch*."""
    try:
        pointer: Any = json.loads(fetch(BASE_URL + "latest.json", MAX_POINTER))
        name, version = pointer["file"], pointer["licenseListVersion"]
        digest, size = pointer["sha256"], pointer["size"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SnapshotError(f"latest.json: {type(exc).__name__}: {exc}") from exc
    if not (isinstance(name, str) and FILE_RE.fullmatch(name)):
        raise SnapshotError(f"latest.json: file {name!r}")
    if not (isinstance(digest, str) and SHA256_RE.fullmatch(digest)):
        raise SnapshotError("latest.json: sha256 is not a digest")
    raw = fetch(BASE_URL + name, MAX_BUNDLE)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise SnapshotError(f"{name}: differs from latest.json")
    check_bundle(raw, version)
    path = scratch / "spdx-bundle.json.gz"
    path.write_bytes(raw)
    return path


class SpdxSnapshotHook(BuildHookInterface):  # type: ignore[type-arg]
    """Add the snapshot to the wheel and the sdist."""

    PLUGIN_NAME = "custom"
    _scratch: str | None = None

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        target = ARCHIVE_PATH.get(self.target_name)
        override = os.environ.get("LICENSEID_BUNDLE", "")
        # An editable install reads the checkout; a snapshot there would
        # change the results of a local test run.
        if version == "editable" or target is None or override == "skip":
            return
        try:
            source = self._source(override)
        except (OSError, SnapshotError) as exc:
            if os.environ.get("LICENSEID_REQUIRE_BUNDLE") == "1":
                raise
            self.app.display_warning(f"licenseid: no SPDX snapshot shipped: {exc}")
            return
        build_data["force_include"][str(source)] = target

    def _source(self, override: str) -> Path:
        """The bundle to ship: the override, else the file in the tree (a
        wheel built from an unpacked sdist), else a download."""
        in_tree = Path(self.root, IN_TREE)
        path = Path(override).resolve(strict=True) if override else in_tree
        if override or path.is_file():
            check_bundle(path.read_bytes(), None)
            return path
        self._scratch = tempfile.mkdtemp(prefix="licenseid-bundle-")
        return download(Path(self._scratch))

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None
