# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The real files of a benchmark, kept as a local folder with a manifest.

The files are other people's: they and the manifest stay outside the
repository. The manifest lists each file with its SHA-256, so a run reads the
same bytes on every day, not whatever is installed that day. ``build_corpus``
picks the files once, the way the prototype of 0.10.0 did (same seeds), and
``verify`` checks a folder against its manifest.
"""

import glob
import hashlib
import json
import os
import random
import shutil
from pathlib import Path
from typing import Any, Final

SITE: Final = "~/.pyenv/versions/*/lib/python*/site-packages"
LICENCE_PREFIXES: Final = ("LICEN", "COPYING", "NOTICE")
MAX_BYTES: Final = 400_000
REAL_LIMIT: Final = 300
README_LIMIT: Final = 300
REAL_SEED: Final = 7
README_SEED: Final = 5
#: Packages whose licence files the roadmap items name, by glob and label.
ROADMAP_PACKAGES: Final = (
    ("wcwidth-*", "68: wcwidth"),
    ("mypy_extensions-*", "68: mypy_extensions"),
    ("certifi-*", "69: certifi"),
    ("numpy-*", "70: numpy"),
    ("sympy-*", "64: sympy"),
    ("[Pp]illow-*", "64: pillow"),
)
MANIFEST: Final = "manifest.json"


def sha256(data: bytes) -> str:
    """The SHA-256 of *data* as hex."""
    return hashlib.sha256(data).hexdigest()


def sha1(data: bytes) -> str:
    """The SHA-1 of *data* as hex (the prototype's file keys)."""
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def pick_real(
    paths: list[str], limit: int = REAL_LIMIT
) -> list[tuple[str, str, bytes]]:
    """The licence files of *paths* (sorted) the benchmark uses: unique by
    SHA-1, none over 400 KB or with a NUL, shuffled with seed 7, the first
    *limit*. Each is ``(key, path, bytes)`` with the key ``real:<sha1[:8]>:
    <file name>``."""
    seen: dict[str, tuple[str, bytes]] = {}
    for path in paths:
        name = os.path.basename(path).upper()
        if not (name.startswith(LICENCE_PREFIXES) and os.path.isfile(path)):
            continue
        try:
            data = Path(path).read_bytes()
        except OSError:
            continue
        if b"\0" in data or len(data) > MAX_BYTES:
            continue
        seen.setdefault(sha1(data), (path, data))
    items = sorted(seen.items())
    random.Random(REAL_SEED).shuffle(items)
    return [
        (f"real:{h[:8]}:{os.path.basename(p)}", p, d) for h, (p, d) in items[:limit]
    ]


def pick_readmes(paths: list[str], limit: int = README_LIMIT) -> list[tuple[str, str]]:
    """The descriptions of the METADATA files of *paths* (sorted) that hold
    the word "licens", 200 to 100,000 characters, unique, shuffled with seed
    5, the first *limit*: ``(key, body)`` with the key ``<dist-info>:<sha1[:6]>``."""
    seen: dict[str, tuple[str, str]] = {}
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        body = text.partition("\n\n")[2]
        if "licens" not in body.lower() or not 200 <= len(body) <= 100_000:
            continue
        seen.setdefault(sha1(body.encode()), (path.split("/")[-2], body))
    items = sorted(seen.items())
    random.Random(README_SEED).shuffle(items)
    return [(f"{name}:{h[:6]}", body) for h, (name, body) in items[:limit]]


def roadmap_files(root: str = SITE) -> list[tuple[str, str, bytes]]:
    """The licence files of the packages roadmap items name: ``(key, path,
    bytes)``, one per distinct content, in the key form of the prototype."""
    out: list[tuple[str, str, bytes]] = []
    seen: set[tuple[str, str]] = set()
    for pattern, label in ROADMAP_PACKAGES:
        found = sorted(
            glob.glob(
                os.path.expanduser(f"{root}/{pattern}.dist-info/**/LICENSE*"),
                recursive=True,
            )
        )
        for path in found:
            if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
                continue
            data = Path(path).read_bytes()
            short = sha1(data)[:6]
            if (label, short) in seen:
                continue
            seen.add((label, short))
            where = path.split("site-packages/")[1].split(".dist-info")[0]
            key = f"{label} {where} {os.path.basename(path)} {short}"
            out.append((key, path, data))
    return out


def _put(dest: Path, rel: str, data: bytes) -> dict[str, Any]:
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "sha256": sha256(data), "bytes": len(data)}


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def build_corpus(
    dest: Path,
    labels: dict[str, Any],
    onecall: dict[str, str],
    item68: list[str],
) -> dict[str, Any]:
    """Copy the files into *dest* and write its manifest, which is returned.
    *labels* are the weak labels by key (``ids``, ``declared``, ``pkg``),
    *onecall* the texts of the one-call set, *item68* the keys of real files
    that roadmap item 68 asks about."""
    dest.mkdir(parents=True, exist_ok=True)
    pattern = os.path.expanduser(f"{SITE}/*.dist-info/**/*")
    licence_paths = sorted(glob.glob(pattern, recursive=True))
    metadata = sorted(glob.glob(os.path.expanduser(f"{SITE}/*.dist-info/METADATA")))
    files: list[dict[str, Any]] = []
    for key, path, data in pick_real(licence_paths):
        entry = _put(
            dest, f"real/{key.split(':')[1]}_{_safe(os.path.basename(path))}", data
        )
        entry.update(kind="real", key=key, source=path, **_label(labels, key))
        files.append(entry)
    for key, body in pick_readmes(metadata):
        entry = _put(dest, f"readme/{_safe(key)}.md", body.encode("utf-8"))
        files.append({**entry, "kind": "readme", "key": key})
    for key, path, data in roadmap_files():
        entry = _put(dest, f"roadmap/{_safe(key)}.txt", data)
        files.append({**entry, "kind": "roadmap", "key": key, "source": path})
    for key, text in sorted(onecall.items()):
        entry = _put(dest, f"onecall/{_safe(key)}.txt", text.encode("utf-8"))
        files.append({**entry, "kind": "onecall", "key": key})
    manifest = {"format": 1, "files": files, "item68": sorted(item68)}
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def _label(labels: dict[str, Any], key: str) -> dict[str, Any]:
    found = labels.get(key) or {}
    return {k: found.get(k) for k in ("ids", "declared", "pkg")}


def load_manifest(folder: Path) -> dict[str, Any]:
    """The manifest of a corpus folder."""
    loaded: dict[str, Any] = json.loads((folder / MANIFEST).read_text("utf-8"))
    return loaded


def verify(folder: Path) -> list[str]:
    """What differs between the folder and its manifest: a missing file, a
    changed one, a file the manifest does not list. Empty when they agree."""
    manifest = load_manifest(folder)
    problems: list[str] = []
    listed = {entry["path"] for entry in manifest["files"]}
    for entry in manifest["files"]:
        target = folder / entry["path"]
        if not target.is_file():
            problems.append(f"missing: {entry['path']}")
        elif sha256(target.read_bytes()) != entry["sha256"]:
            problems.append(f"changed: {entry['path']}")
    for sub in sorted({p.split("/")[0] for p in listed}):
        for path in sorted((folder / sub).rglob("*")):
            rel = path.relative_to(folder).as_posix()
            if path.is_file() and rel not in listed:
                problems.append(f"unlisted: {rel}")
    return problems


def read_entries(folder: Path, kind: str) -> list[tuple[dict[str, Any], str]]:
    """The manifest entries of one kind with their text (UTF-8, bad bytes
    replaced, as the prototype read them), in manifest order."""
    out = []
    for entry in load_manifest(folder)["files"]:
        if entry["kind"] == kind:
            data = (folder / entry["path"]).read_bytes()
            out.append((entry, data.decode("utf-8", "replace")))
    return out


def clear(folder: Path) -> None:
    """Remove a corpus folder (a rebuild starts from nothing)."""
    shutil.rmtree(folder, ignore_errors=True)
