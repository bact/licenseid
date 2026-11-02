# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Check that a built wheel and sdist ship the pinned SPDX bundle.

``build.yml`` and ``pypi-publish.yml`` run it on ``dist/`` after
``python -m build``, apart from the build hook (``hatch_build.py``), which
checks the same in its ``finalize``: a build that lost the hook would
otherwise ship no snapshot without a word.

The pin is ``BUNDLE_VERSION`` and ``BUNDLE_SHA256`` in ``hatch_build.py``,
read as data (the hook imports hatchling, which this job need not have).
``dist/`` must hold exactly one wheel and one sdist, and each must hold the
bundle as a regular file, of the pinned version and SHA-256.

Standard library only. Exit 0 when both match, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

# As in hatch_build.py (ARCHIVE_PATH, IN_TREE, MAX_BUNDLE, MAX_UNZIPPED);
# tests/test_releasebuild_dist.py checks they agree.
WHEEL_MEMBER = "licenseid/data/spdx-bundle.json.gz"
SDIST_MEMBER = "src/licenseid/data/spdx-bundle.json.gz"
MAX_BUNDLE = 16 * 1024 * 1024
MAX_UNZIPPED = 32 * 1024 * 1024
PIN_NAMES = ("BUNDLE_VERSION", "BUNDLE_SHA256")


class CheckError(Exception):
    """The dist does not ship the pinned bundle; ``str()`` says why."""


def read_pin(hook: Path) -> tuple[str, str]:
    """``BUNDLE_VERSION`` and ``BUNDLE_SHA256`` of the hook file *hook*."""
    found: dict[str, Any] = {}
    for node in ast.parse(hook.read_text(encoding="utf-8")).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in PIN_NAMES
            and node.value is not None
        ):
            found[node.target.id] = ast.literal_eval(node.value)
    version, digest = (found.get(name) for name in PIN_NAMES)
    if not (isinstance(version, str) and isinstance(digest, str)):
        raise CheckError(f"{hook.name}: no {' and '.join(PIN_NAMES)}")
    return version, digest


def only(dist: Path, pattern: str) -> Path:
    """The one file of *dist* that matches *pattern*."""
    matches = sorted(dist.glob(pattern))
    if len(matches) != 1:
        raise CheckError(f"{dist.name}: {len(matches)} files {pattern}, not 1")
    return matches[0]


def wheel_bundle(wheel: Path) -> bytes:
    """The bundle in *wheel*."""
    with zipfile.ZipFile(wheel) as archive, archive.open(WHEEL_MEMBER) as stream:
        return stream.read(MAX_BUNDLE + 1)


def sdist_bundle(sdist: Path) -> bytes:
    """The bundle in *sdist*: a regular file under its one top directory."""
    with tarfile.open(sdist, "r:gz") as archive:
        for member in archive:
            if member.isfile() and member.name.partition("/")[2] == SDIST_MEMBER:
                stream = archive.extractfile(member)
                if stream is not None:
                    return stream.read(MAX_BUNDLE + 1)
    raise CheckError(f"{sdist.name}: no {SDIST_MEMBER}")


def check_artifact(artifact: Path, raw: bytes, pin: tuple[str, str]) -> str:
    """The line that reports *raw*, the bundle of *artifact*, if it is *pin*."""
    if len(raw) > MAX_BUNDLE:
        raise CheckError(f"{artifact.name}: bundle larger than {MAX_BUNDLE} bytes")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            doc = json.loads(stream.read(MAX_UNZIPPED + 1))
        version = doc["licenseListVersion"]
    except (OSError, EOFError, ValueError, KeyError, TypeError) as exc:
        raise CheckError(f"{artifact.name}: not a bundle: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if version != pin[0]:
        raise CheckError(f"{artifact.name}: version {version!r}, not {pin[0]!r}")
    if digest != pin[1]:
        raise CheckError(f"{artifact.name}: SHA-256 {digest}, not {pin[1]}")
    return f"{artifact.name}: SPDX License List {version}, SHA-256 {digest}"


def check_dist(dist: Path, pin: tuple[str, str]) -> list[str]:
    """One line per artefact of *dist*; raise ``CheckError`` on a mismatch."""
    wheel, sdist = only(dist, "*.whl"), only(dist, "*.tar.gz")
    try:
        found = {wheel: wheel_bundle(wheel), sdist: sdist_bundle(sdist)}
    except (OSError, KeyError, EOFError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise CheckError(f"{dist.name}: {type(exc).__name__}: {exc}") from exc
    return [check_artifact(path, raw, pin) for path, raw in found.items()]


def main(argv: list[str] | None = None) -> int:
    """Check *dist* against the pin of *hook*; print one line per artefact."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dist", nargs="?", default="dist", type=Path)
    parser.add_argument("--hook", default="hatch_build.py", type=Path)
    args = parser.parse_args(argv)
    try:
        lines = check_dist(args.dist, read_pin(args.hook))
    except (CheckError, OSError, SyntaxError, ValueError) as exc:
        print(f"check_dist_bundle: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
