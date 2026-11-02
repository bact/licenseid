# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Hatch build hook: ship the SPDX bundle that ``licenseid update`` falls
back to (source ``packaged``) when no network source answers.

It is the compact bundle (``licenseid.spdxdata``, format 1) of the SPDX
License List pinned below (``BUNDLE_VERSION``, ``BUNDLE_SHA256``), so a tag
builds the same wheel on any day. The hook adds it to the wheel as
``licenseid/data/spdx-bundle.json.gz`` and to the sdist as
``src/licenseid/data/spdx-bundle.json.gz``, so a wheel built from an
unpacked sdist finds it in the tree and needs no network. A checkout never
uses a file in the tree: it downloads, or takes ``LICENSEID_BUNDLE``. Every
source must be the pinned bytes, and ``finalize`` reads the bundle back from
the built wheel or sdist.

Standard library only: the build runs in an isolated environment that has
hatchling and nothing of ``licenseid``.

Environment:

``LICENSEID_BUNDLE=skip``
    Ship no snapshot (CI jobs that only install the package).
``LICENSEID_BUNDLE=<path>``
    Ship that bundle (the pinned one): a hermetic build, no network.
``LICENSEID_REQUIRE_BUNDLE=1``
    Fail the build, instead of a warning, when it would ship no snapshot: a
    download or a file that is missing or not the pin, or ``skip``.
"""

import contextlib
import gzip
import hashlib
import http.client
import io
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import IO, Any, Final

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Copies of constants in ``licenseid.spdx_source`` and ``licenseid.spdxdata``
# (BUNDLE_BASE_URL, the file name of BUNDLE_URL_TEMPLATE, PACKAGED_NAME,
# BUNDLE_FORMAT, MAX_UNZIPPED), which the build cannot import;
# tests/test_hatch_build.py checks they agree.
BASE_URL: Final = (
    "https://raw.githubusercontent.com/bact/licenseid/refs/heads/data/spdx/format-1/"
)
IN_TREE: Final = "src/licenseid/data/spdx-bundle.json.gz"
ARCHIVE_PATH: Final = {"wheel": "licenseid/data/spdx-bundle.json.gz", "sdist": IN_TREE}
BUNDLE_FORMAT: Final = 1
MAX_BUNDLE: Final = 16 * 1024 * 1024
MAX_UNZIPPED: Final = 32 * 1024 * 1024
CHUNK: Final = 1024 * 1024
TIMEOUT: Final = 30

# The SPDX License List the package ships, and the SHA-256 of its compact
# bundle as published (``sha256`` in ``latest.json`` while that version is the
# latest). Raise both together, in a pull request before a release is tagged;
# tests/test_releasebuild_pin.py holds the version to the ID snapshots of the
# tests, which move with it.
BUNDLE_VERSION: Final = "3.29.0"
BUNDLE_SHA256: Final = (
    "c73987375509b961bf68aac1db8ec609db5bf548eaae8aa7ee3ef514012466e7"
)


class SnapshotError(Exception):
    """The snapshot cannot be had; ``str()`` says why."""


class _HttpsRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to https: urllib would follow one to http."""

    # The signature is urllib's.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.startswith("https://"):
            fp.close()  # urllib closes it only after this method returns
            raise SnapshotError(f"{req.full_url}: redirected to {newurl}, not https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url: str) -> Any:
    """An open response for *url* (a context manager with ``read``)."""
    opener = urllib.request.build_opener(_HttpsRedirects)
    return opener.open(url, timeout=TIMEOUT)  # nosec B310


def fetch(url: str, limit: int) -> bytes:
    """The body of *url*, refused over *limit* bytes. A broken HTTP exchange
    (``http.client.HTTPException``, which urllib does not wrap in an
    ``OSError``) is a ``SnapshotError``."""
    if not url.startswith("https://"):
        raise SnapshotError(f"{url}: not https")
    chunks: list[bytes] = []
    size = 0
    try:
        with open_url(url) as response:
            while chunk := response.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise SnapshotError(f"{url}: larger than {limit} bytes")
                chunks.append(chunk)
    except http.client.HTTPException as exc:
        raise SnapshotError(f"{url}: {type(exc).__name__}") from exc
    return b"".join(chunks)


def check_bundle(raw: bytes, version: str) -> None:
    """Refuse *raw* unless it is a format 1 bundle of *version*."""
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
    if found[1] != version:
        raise SnapshotError(f"version {found[1]!r}, not {version!r}")


def check_pinned(raw: bytes, origin: str) -> None:
    """Refuse *raw* (read from *origin*) unless it is the pinned bundle."""
    try:
        check_bundle(raw, BUNDLE_VERSION)
    except SnapshotError as exc:
        raise SnapshotError(f"{origin}: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256:
        raise SnapshotError(f"{origin}: SHA-256 differs from the pin")


def download(scratch: Path) -> Path:
    """Fetch the pinned bundle into *scratch*."""
    name = f"v{BUNDLE_VERSION}.json.gz"  # as tools.build_bundle names it
    raw = fetch(BASE_URL + name, MAX_BUNDLE)
    check_pinned(raw, name)
    path = scratch / "spdx-bundle.json.gz"
    path.write_bytes(raw)
    return path


def read_shipped(artifact: Path, target: str) -> bytes:
    """The snapshot inside a built wheel or sdist (*target*)."""
    try:
        if target == "wheel":
            with (
                zipfile.ZipFile(artifact) as wheel,
                wheel.open(ARCHIVE_PATH[target]) as stream,
            ):
                raw: bytes | None = stream.read(MAX_BUNDLE + 1)
        else:
            raw = _sdist_snapshot(artifact)
    except (OSError, KeyError, EOFError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise SnapshotError(f"{artifact.name}: {type(exc).__name__}: {exc}") from exc
    if raw is None:
        raise SnapshotError(f"{artifact.name}: no snapshot in it")
    if len(raw) > MAX_BUNDLE:
        raise SnapshotError(f"{artifact.name}: larger than {MAX_BUNDLE} bytes")
    return raw


def _sdist_snapshot(artifact: Path) -> bytes | None:
    """The snapshot in an sdist: ``IN_TREE`` under its one top directory."""
    with tarfile.open(artifact, "r:gz") as sdist:
        for member in sdist:
            if member.isfile() and member.name.partition("/")[2] == IN_TREE:
                stream = sdist.extractfile(member)
                return None if stream is None else stream.read(MAX_BUNDLE + 1)
    return None


class SpdxSnapshotHook(BuildHookInterface):  # type: ignore[type-arg]
    """Add the snapshot to the wheel and the sdist."""

    PLUGIN_NAME = "custom"
    _scratch: str | None = None
    _shipped: str | None = None

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        target = ARCHIVE_PATH.get(self.target_name)
        override = os.environ.get("LICENSEID_BUNDLE", "")
        # An editable install reads the checkout; a snapshot there would
        # change the results of a local test run.
        if version == "editable" or target is None:
            return
        required = os.environ.get("LICENSEID_REQUIRE_BUNDLE") == "1"
        if override == "skip":
            if required:
                raise SnapshotError(
                    "LICENSEID_BUNDLE=skip, but LICENSEID_REQUIRE_BUNDLE=1"
                )
            return
        try:
            source = self._source(override)
        except (OSError, SnapshotError) as exc:
            if required:
                raise
            self.app.display_warning(f"licenseid: no SPDX snapshot shipped: {exc}")
            return
        build_data["force_include"][str(source)] = target
        self._shipped = self.target_name

    def _local(self, override: str) -> Path | None:
        """The bundle to ship without a download: the override, else the file
        in the tree of an unpacked sdist (it has ``PKG-INFO``; a checkout does
        not, and a file left in one would ship stale)."""
        if override:
            return Path(override).resolve(strict=True)
        in_tree = Path(self.root, IN_TREE)
        if Path(self.root, "PKG-INFO").is_file() and in_tree.is_file():
            return in_tree
        return None

    def _source(self, override: str) -> Path:
        """The bundle to ship: a local one (see ``_local``), else a download."""
        path = self._local(override)
        if path is not None:
            check_pinned(path.read_bytes(), path.name)
            return path
        self._scratch = tempfile.mkdtemp(prefix="licenseid-bundle-")
        try:
            return download(Path(self._scratch))
        except BaseException:
            # Hatchling calls finalize only after every initialize returned.
            self._remove_scratch()
            raise

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        """Drop the scratch directory; check the bundle the artifact holds,
        and delete an artifact that fails, so no later upload can take it."""
        self._remove_scratch()
        shipped, self._shipped = self._shipped, None
        if shipped is None:
            return
        artifact = Path(artifact_path)
        try:
            check_pinned(read_shipped(artifact, shipped), artifact.name)
        except SnapshotError:
            with contextlib.suppress(OSError):
                artifact.unlink(missing_ok=True)
            raise

    def _remove_scratch(self) -> None:
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None
