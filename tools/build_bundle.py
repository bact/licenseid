# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Build the published SPDX bundle of one license list release.

Run as ``python -m tools.build_bundle --out DIR (--tarball PATH | --version V)``.
It writes ``DIR/v<version>.json.gz`` and moves ``DIR/latest.json`` forward
only when the version is greater than the one it names. Standard library and
``licenseid`` only, so a CI job needs nothing else.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.request
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from licenseid.spdxdata import SpdxData, to_bundle

URL_TEMPLATE: Final = (
    "https://github.com/spdx/license-list-data/archive/refs/tags/v{version}.tar.gz"
)
MAX_DOWNLOAD: Final = 128 * 1024 * 1024
CHUNK: Final = 1024 * 1024
TIMEOUT: Final = 60
# Nothing that could carry a path separator or URL syntax into the URL.
VERSION_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
NUMERIC_RE: Final = re.compile(r"[0-9]+(\.[0-9]+)*")


class BuildError(Exception):
    """A failure whose message is the one line printed to standard error."""


def note(line: str) -> None:
    """One diagnostic line on standard error."""
    print(line, file=sys.stderr)


def version_key(version: str) -> tuple[int, ...]:
    """A dotted numeric version as a tuple, so 3.9 sorts below 3.29.0."""
    if not NUMERIC_RE.fullmatch(version):
        raise BuildError(f"latest.json: version {version!r} is not numeric")
    return tuple(int(part) for part in version.split("."))


def write_atomic(path: Path, content: bytes) -> None:
    """Write *content* to *path* through a temporary file and ``os.replace``."""
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def write_if_changed(path: Path, content: bytes) -> bool:
    """Write *content* unless *path* already holds exactly it."""
    try:
        if path.read_bytes() == content:
            return False
    except FileNotFoundError:
        pass
    write_atomic(path, content)
    return True


def verify(name: str, bundle: bytes, data: SpdxData) -> None:
    """Read *bundle* back and compare it with *data*."""
    try:
        back = SpdxData.from_bundle(bundle, data.version)
    except ValueError as exc:
        raise BuildError(f"{name}: verification failed: {exc}") from exc
    if back != data:
        raise BuildError(f"{name}: verification failed: data differs")


def existing_version(latest: Path) -> str | None:
    """The version ``latest.json`` names, or ``None`` when it is unusable."""
    try:
        doc: Any = json.loads(latest.read_text(encoding="utf-8"))
        version = doc["licenseListVersion"]
        version_key(version)
    except (OSError, ValueError, KeyError, TypeError, BuildError):
        return None
    return str(version)


def latest_document(data: SpdxData, name: str, bundle: bytes) -> bytes:
    """The bytes of ``latest.json`` for the bundle *bundle* called *name*."""
    doc = {
        "file": name,
        "licenseListVersion": data.version,
        "releaseDate": data.release_date,
        "sha256": hashlib.sha256(bundle).hexdigest(),
        "size": len(bundle),
    }
    return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build(tarball: Path, out: Path) -> list[Path]:
    """Build the bundle of *tarball* into *out*; return the files written."""
    data = SpdxData.from_tarball(tarball)
    newest = version_key(data.version)
    out.mkdir(parents=True, exist_ok=True)
    name = f"v{data.version}.json.gz"
    bundle = to_bundle(data)
    verify(name, bundle, data)
    written: list[Path] = []
    path = out / name
    if write_if_changed(path, bundle):
        written.append(path)
    latest = out / "latest.json"
    current = existing_version(latest)
    if current is not None and version_key(current) > newest:
        note(f"latest.json: keeping v{current}, newer than v{data.version}")
    elif write_if_changed(latest, latest_document(data, name, bundle)):
        written.append(latest)
    return written


def download(version: str, target: Path) -> None:
    """Stream the release tarball of *version* into *target* (size capped)."""
    if not VERSION_RE.fullmatch(version):
        raise BuildError(f"--version: invalid: {version!r}")
    url = URL_TEMPLATE.format(version=version)
    size = 0
    with (
        urllib.request.urlopen(url, timeout=TIMEOUT) as response,  # nosec B310
        target.open("wb") as stream,
    ):
        while chunk := response.read(CHUNK):
            size += len(chunk)
            if size > MAX_DOWNLOAD:
                raise BuildError(f"{url}: larger than {MAX_DOWNLOAD} bytes")
            stream.write(chunk)


def release_version(value: str) -> str:
    """An ``argparse`` type: a release name that is safe inside a URL."""
    if not VERSION_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"invalid release name {value!r}")
    return value


def parser() -> argparse.ArgumentParser:
    """The command line."""
    result = argparse.ArgumentParser(
        prog="python -m tools.build_bundle",
        description="Build the published SPDX bundle of one release.",
    )
    result.add_argument("--out", required=True, type=Path, help="output directory")
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--tarball", type=Path, help="local release tarball")
    source.add_argument(
        "--version", type=release_version, help="release to download, e.g. 3.29.0"
    )
    return result


def run(tarball: Path | None, version: str | None, out: Path) -> list[Path]:
    """Build from a local tarball, or from a download of *version*."""
    if tarball is not None:
        return build(tarball, out)
    if version is None:
        raise BuildError("--version: missing")
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "release.tar.gz"
        download(version, target)
        return build(target, out)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; the exit status is 0, 1 (failure) or 2 (usage)."""
    try:
        args = parser().parse_args(argv)
    except SystemExit as exc:  # argparse: 2 for a usage error, 0 for --help
        return exc.code if isinstance(exc.code, int) else 2
    try:
        written = run(args.tarball, args.version, args.out)
    except BuildError as exc:
        note(f"ERROR: {exc}")
        return 1
    except (tarfile.TarError, EOFError, zlib.error, OSError, ValueError) as exc:
        text = " ".join(f"{type(exc).__name__}: {exc}".split())
        note(f"ERROR: build failed: {text}")
        return 1
    for path in written:
        print(f"WROTE {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
