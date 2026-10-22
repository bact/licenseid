# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
The SPDX License List as data, whatever its source: a bundle (gzipped JSON,
``format`` 1) or a release tarball.

Standard library only (no ``requests``, ``click`` or ``rapidfuzz``), so the
match path stays light. It reads bytes and files; it never touches the network
or the database.
"""

import gzip
import io
import json
import re
import tarfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Final

from licenseid.errors import typed
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry

BUNDLE_FORMAT: Final = 1
# Decompressed size cap: the bundle of 3.29.0 is about 5 MiB, so this leaves
# room and stops a gzip bomb.
MAX_UNZIPPED: Final = 32 * 2**20
PACKAGED_NAME: Final = "spdx-bundle.json.gz"

# Same idea as spdx_source's version rule (not imported: it needs requests):
# nothing that could carry a path separator or URL syntax.
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# All 826 IDs of list 3.29.0 pass.
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,99}")


class BundleError(ValueError):
    """An unusable bundle; ``str()`` is the DETAIL of a diagnostic (one line,
    no ';')."""


@dataclass(frozen=True, slots=True)
class SpdxData:
    """One version of the SPDX License List with the license texts."""

    version: str
    release_date: str | None
    licenses: tuple[SpdxLicenseEntry, ...]
    exceptions: tuple[SpdxExceptionEntry, ...]
    # licenseId -> text; an ID that is absent has no text file.
    texts: Mapping[str, str]

    @classmethod
    def from_bundle(cls, raw: bytes, expected: str | None) -> "SpdxData":
        """Parse and validate a bundle.

        *expected* is the version the caller asked for (``None``: any).
        Raises :class:`BundleError` for anything unusable.
        """
        doc = _load_document(raw)
        version, release_date = _release(doc, expected)
        licenses, texts = _entries(doc, "licenses", "licenseId", with_text=True)
        exceptions, _ = _entries(doc, "exceptions", "licenseExceptionId")
        return cls(
            version=version,
            release_date=release_date,
            licenses=tuple(licenses),  # type: ignore[arg-type]
            exceptions=tuple(exceptions),  # type: ignore[arg-type]
            texts=texts,
        )

    @classmethod
    def from_tarball(cls, path: Path) -> "SpdxData":
        """Read a ``license-list-data`` release tarball without extracting it.

        Only ``<root>/json/*.json`` and ``<root>/text/*.txt`` are read, so a
        member with an absolute or ``..`` name is never followed.
        ``tarfile.TarError``, ``EOFError``, ``zlib.error`` and ``OSError``
        propagate to the caller.
        """
        with tarfile.open(path, "r:gz") as tar:
            documents, texts_by_root = _scan_tarball(tar)
        root = _tarball_root(documents)
        lic_doc = _json_object(documents[f"{root}/json/licenses.json"], "licenses.json")
        exc_text = documents.get(f"{root}/json/exceptions.json")
        exc_doc = _json_object(exc_text, "exceptions.json") if exc_text else {}
        exc_doc.setdefault("exceptions", [])
        try:
            version, release_date = _release(lic_doc, None)
            licenses, _ = _entries(lic_doc, "licenses", "licenseId")
            exceptions, _ = _entries(exc_doc, "exceptions", "licenseExceptionId")
        except BundleError as exc:
            raise tarfile.ReadError(str(exc)) from exc
        found = texts_by_root.get(root, {})
        texts = {
            lic["licenseId"]: found[lic["licenseId"]]
            for lic in licenses
            if lic["licenseId"] in found
        }
        return cls(
            version=version,
            release_date=release_date,
            licenses=tuple(licenses),  # type: ignore[arg-type]
            exceptions=tuple(exceptions),  # type: ignore[arg-type]
            texts=texts,
        )


def _load_document(raw: bytes) -> dict[str, Any]:
    """Gunzip (capped), parse and check the envelope of a bundle."""
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            # A short read proves EOF, so gzip has checked the CRC.
            payload = gz.read(MAX_UNZIPPED + 1)
        if len(payload) > MAX_UNZIPPED:
            raise BundleError(f"larger than {MAX_UNZIPPED} bytes unzipped")
        doc = json.loads(payload)
    except BundleError:
        raise
    except (OSError, EOFError, zlib.error, ValueError, RecursionError) as exc:
        raise BundleError(typed(exc)) from exc
    if not isinstance(doc, dict):
        raise BundleError("not a JSON object")
    if doc.get("format") != BUNDLE_FORMAT or isinstance(doc.get("format"), bool):
        raise BundleError(f"format {doc.get('format')!r} is not {BUNDLE_FORMAT}")
    return doc


def _release(doc: dict[str, Any], expected: str | None) -> tuple[str, str | None]:
    """Version and release date of a document, validated; *expected* is the
    version the caller asked for (``None``: any)."""
    version = doc.get("licenseListVersion")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise BundleError("licenseListVersion is missing or invalid")
    if expected is not None and version != expected:
        raise BundleError(f"version {version} is not the expected {expected}")
    release_date = doc.get("releaseDate")
    if release_date is not None and not isinstance(release_date, str):
        raise BundleError("releaseDate is not a string")
    return version, release_date


def _entries(
    doc: dict[str, Any], key: str, id_key: str, with_text: bool = False
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validated entries of *key* (``text`` removed) and their texts."""
    items = doc.get(key)
    if not isinstance(items, list):
        raise BundleError(f"{key} is not a list")
    entries: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise BundleError(f"{key} has an entry that is not an object")
        ident = item.get(id_key)
        if not isinstance(ident, str) or not _ID_RE.fullmatch(ident):
            raise BundleError(f"{key} has an invalid {id_key}")
        if ident in seen:
            raise BundleError(f"{key} has a duplicate {id_key}")
        seen.add(ident)
        entry = {k: v for k, v in item.items() if k != "text"}
        text = item.get("text")
        if text is not None and not isinstance(text, str):
            raise BundleError(f"{key} has a text that is not a string")
        if with_text and text is not None:
            texts[ident] = text
        entries.append(entry)
    return entries, texts


def to_bundle(data: SpdxData) -> bytes:
    """*data* as a deterministic bundle: sorted keys, compact JSON, gzip with
    ``mtime`` 0, so a rebuild is byte-identical."""
    licenses = [
        {**lic, "text": data.texts.get(lic["licenseId"])} for lic in data.licenses
    ]
    doc = {
        "format": BUNDLE_FORMAT,
        "licenseListVersion": data.version,
        "releaseDate": data.release_date,
        "licenses": licenses,
        "exceptions": list(data.exceptions),
    }
    payload = json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(mode="wb", fileobj=buffer, mtime=0) as gz:
        gz.write(payload)
    return buffer.getvalue()


def packaged_bundle() -> bytes | None:
    """The snapshot shipped in the wheel, or ``None`` when there is none."""
    try:
        resource = resources.files("licenseid") / "data" / PACKAGED_NAME
        return resource.read_bytes()
    except (FileNotFoundError, NotADirectoryError, ModuleNotFoundError):
        return None


_JSON_FILES: Final = ("licenses.json", "exceptions.json")


def _scan_tarball(
    tar: tarfile.TarFile,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """The ``<root>/json`` files by member name and the ``<root>/text`` files
    by root and licence ID, read in one pass in archive order: a gzip stream
    cannot seek back, and every jump back decompresses from the start."""
    documents: dict[str, str] = {}
    texts: dict[str, dict[str, str]] = {}
    for member in tar:
        parts = member.name.split("/")
        if not member.isfile() or len(parts) != 3 or parts[0] in ("", ".", ".."):
            continue
        root, folder, base = parts
        if folder == "json" and base in _JSON_FILES:
            documents[member.name] = _tar_text(tar, member)
        elif folder == "text" and base.endswith(".txt"):
            texts.setdefault(root, {})[base[: -len(".txt")]] = _tar_text(tar, member)
    return documents, texts


def _tarball_root(documents: Mapping[str, str]) -> str:
    """The top-level directory that holds ``json/licenses.json``."""
    roots = sorted(
        name.split("/")[0] for name in documents if name.endswith("/json/licenses.json")
    )
    if not roots:
        raise tarfile.ReadError("json/licenses.json is missing")
    return roots[0]


def _json_object(text: str, name: str) -> dict[str, Any]:
    """The JSON object in *text*; *name* is for the error."""
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise tarfile.ReadError(f"{name} is not a JSON object")
    return doc


def _tar_text(tar: tarfile.TarFile, member: tarfile.TarInfo) -> str:
    """Text of *member* read as ``open(..., encoding="utf-8")`` reads a file:
    universal newlines, so CRLF becomes LF."""
    fileobj = tar.extractfile(member)
    if fileobj is None:  # pragma: no cover  # only a non-file; callers pass files
        raise tarfile.ReadError(f"{member.name} is not a file")
    with io.TextIOWrapper(fileobj, encoding="utf-8") as wrapper:
        return wrapper.read()
