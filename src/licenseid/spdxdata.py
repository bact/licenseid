# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
The SPDX License List as data, whatever its source: a bundle (gzipped JSON,
``format`` 1) or a release tarball.

A licence entry of a bundle may carry a ``template`` key: the licence template
(``template/<id>.template.txt`` of the release, with the ``<<beginOptional>>``
and ``<<var>>`` marks of the SPDX matching guidelines), a string or null. The
key is additive, so the format stays 1 and licenseid 0.9.1 reads these bundles
too. A bundle where no entry has the key, built before templates, is refused:
no source can build a database without them.

No ``requests``, ``click`` or ``rapidfuzz`` (the standard library,
``licenseid.errors`` and ``licenseid.types`` only), so the match path stays
light. It reads bytes and files; it never touches the network
or the database.
"""

import gzip
import io
import json
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from licenseid.errors import typed
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry

if TYPE_CHECKING:
    import tarfile  # imported where used: a bundle needs no tar reader (start-up)

BUNDLE_FORMAT: Final = 1
# Decompressed size cap: the bundle of 3.29.0 is about 10 MiB with its
# templates, so this leaves room and stops a gzip bomb.
MAX_UNZIPPED: Final = 32 * 2**20
PACKAGED_NAME: Final = "spdx-bundle.json.gz"

# Same idea as spdx_source's version rule (not imported: it needs requests):
# nothing that could carry a path separator or URL syntax.
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# All 826 IDs of list 3.29.0 pass.
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,99}")
_NUMERIC_VERSION = re.compile(r"\d+(?:\.\d+)*")


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
    # licenseId -> template (SPDX matching guidelines, B.3); an ID that is
    # absent has no template file.
    templates: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_bundle(
        cls, raw: bytes, expected: str | None, require_templates: bool = True
    ) -> "SpdxData":
        """Parse and validate a bundle.

        *expected* is the version the caller asked for (``None``: any).
        Raises :class:`BundleError` for anything unusable.
        """
        doc = _load_document(raw)
        version, release_date = _release(doc, expected)
        licenses, texts = _entries(doc, "licenses", "licenseId", _LICENSE_PARTS)
        if require_templates:
            _require_templates(doc)
        exceptions, _ = _entries(doc, "exceptions", "licenseExceptionId")
        return cls(
            version=version,
            release_date=release_date,
            licenses=tuple(licenses),  # type: ignore[arg-type]
            exceptions=tuple(exceptions),  # type: ignore[arg-type]
            texts=texts["text"],
            templates=texts["template"],
        )

    @classmethod
    def from_tarball(cls, path: Path, expected: str | None = None) -> "SpdxData":
        """Read a ``license-list-data`` release tarball without extracting it.

        *expected* is the version the caller asked for (``None``: any); a
        tarball of another version is a ``tarfile.ReadError``.

        Only ``<root>/json/*.json``, ``<root>/text/*.txt`` and
        ``<root>/template/*.template.txt`` are read, so a member with an
        absolute or ``..`` name is never followed.
        ``tarfile.TarError``, ``EOFError``, ``zlib.error`` and ``OSError``
        propagate to the caller.
        """
        import tarfile  # start-up

        with tarfile.open(path, "r:gz") as tar:
            documents, files = _scan_tarball(tar)
        root = _tarball_root(documents)
        lic_doc = _json_object(documents[f"{root}/json/licenses.json"], "licenses.json")
        exc_text = documents.get(f"{root}/json/exceptions.json")
        exc_doc = _json_object(exc_text, "exceptions.json") if exc_text else {}
        exc_doc.setdefault("exceptions", [])
        try:
            version, release_date = _release(lic_doc, expected)
            licenses, _ = _entries(lic_doc, "licenses", "licenseId")
            exceptions, _ = _entries(exc_doc, "exceptions", "licenseExceptionId")
        except BundleError as exc:
            raise tarfile.ReadError(str(exc)) from exc
        ids = [lic["licenseId"] for lic in licenses]
        return cls(
            version=version,
            release_date=release_date,
            licenses=tuple(licenses),  # type: ignore[arg-type]
            exceptions=tuple(exceptions),  # type: ignore[arg-type]
            texts=_of_licenses(files.get((root, "text"), {}), ids),
            templates=_of_licenses(files.get((root, "template"), {}), ids),
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


# The text parts of a licence entry in a bundle: each may be null or left out.
_LICENSE_PARTS: Final = ("text", "template")
# Never kept in an entry: they are in ``texts`` and ``templates``.
_PART_KEYS: Final = frozenset(("text", "template"))


def _entries(
    doc: dict[str, Any],
    key: str,
    id_key: str,
    wanted: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """Validated entries of *key* (text parts removed) and, for each part in
    *wanted*, the non-null strings by ID."""
    items = doc.get(key)
    if not isinstance(items, list):
        raise BundleError(f"{key} is not a list")
    entries: list[dict[str, Any]] = []
    found: dict[str, dict[str, str]] = {part: {} for part in wanted}
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
        if not isinstance(item.get("name"), str):
            raise BundleError(f"{key} has an invalid name")
        for part in wanted:
            value = _part(item, key, part)
            if value is not None:
                found[part][ident] = value
        entries.append({k: v for k, v in item.items() if k not in _PART_KEYS})
    return entries, found


def _part(item: dict[str, Any], key: str, part: str) -> str | None:
    """The *part* (``text``, ``template``) of a bundle entry of *key*: a
    string, or None for null or no key."""
    value = item.get(part)
    if value is not None and not isinstance(value, str):
        raise BundleError(f"{key} has a {part} that is not a string")
    return value


def _require_templates(doc: dict[str, Any]) -> None:
    """Refuse a bundle with licences where no entry has a ``template`` key (a
    null one is a licence with no template). Fail closed: by the key, so a
    bundle built before templates cannot become a database with no cores."""
    licenses = doc["licenses"]
    if licenses and not any("template" in item for item in licenses):
        raise BundleError("no templates")


def _numbers(version: str) -> tuple[int, ...] | None:
    """*version* as numbers without trailing zeros (``3.29.0`` is ``3.29``),
    or None if it is not all numbers (``3.0rc1``)."""
    if not _NUMERIC_VERSION.fullmatch(version):
        return None
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_older(version: str, than: str) -> bool:
    """Whether release *version* is older than *than*. Versions that are not
    all numbers are not compared: never older."""
    mine, theirs = _numbers(version), _numbers(than)
    return mine is not None and theirs is not None and mine < theirs


def to_bundle(data: SpdxData) -> bytes:
    """*data* as a deterministic bundle: sorted keys, compact JSON, gzip with
    ``mtime`` 0, so a rebuild is byte-identical."""
    licenses = [
        {
            **lic,
            "template": data.templates.get(lic["licenseId"]),
            "text": data.texts.get(lic["licenseId"]),
        }
        for lic in data.licenses
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
    from importlib import resources  # start-up: 4 ms, read only for a bundle

    try:
        resource = resources.files("licenseid") / "data" / PACKAGED_NAME
        return resource.read_bytes()
    except (FileNotFoundError, NotADirectoryError, ModuleNotFoundError):
        return None


_JSON_FILES: Final = ("licenses.json", "exceptions.json")
# The folders of text files a tarball has, and the suffix of each file name
# after its ID.
_TEXT_SUFFIXES: Final = {"text": ".txt", "template": ".template.txt"}


def _scan_tarball(
    tar: "tarfile.TarFile",
) -> tuple[dict[str, str], dict[tuple[str, str], dict[str, str]]]:
    """The ``<root>/json`` files by member name, and the ``<root>/text`` and
    ``<root>/template`` files by ``(root, folder)`` and ID, read in one pass in
    archive order: a gzip stream cannot seek back, and every jump back
    decompresses from the start."""
    documents: dict[str, str] = {}
    files: dict[tuple[str, str], dict[str, str]] = {}
    for member in tar:
        parts = member.name.split("/")
        if not member.isfile() or len(parts) != 3 or parts[0] in ("", ".", ".."):
            continue
        root, folder, base = parts
        suffix = _TEXT_SUFFIXES.get(folder)
        if folder == "json" and base in _JSON_FILES:
            documents[member.name] = _tar_text(tar, member)
        elif suffix is not None and base.endswith(suffix):
            ident = base[: -len(suffix)]
            files.setdefault((root, folder), {})[ident] = _tar_text(tar, member)
    return documents, files


def _of_licenses(found: Mapping[str, str], ids: list[str]) -> dict[str, str]:
    """The files in *found* whose ID is a licence of *ids*, in list order."""
    return {ident: found[ident] for ident in ids if ident in found}


def _tarball_root(documents: Mapping[str, str]) -> str:
    """The top-level directory that holds ``json/licenses.json``."""
    roots = sorted(
        name.split("/")[0] for name in documents if name.endswith("/json/licenses.json")
    )
    if not roots:
        import tarfile  # start-up

        raise tarfile.ReadError("json/licenses.json is missing")
    return roots[0]


def _json_object(text: str, name: str) -> dict[str, Any]:
    """The JSON object in *text*; *name* is for the error."""
    doc = json.loads(text)
    if not isinstance(doc, dict):
        import tarfile  # start-up

        raise tarfile.ReadError(f"{name} is not a JSON object")
    return doc


def _tar_text(tar: "tarfile.TarFile", member: "tarfile.TarInfo") -> str:
    """Text of *member* read as ``open(..., encoding="utf-8")`` reads a file:
    universal newlines, so CRLF becomes LF."""
    fileobj = tar.extractfile(member)
    if fileobj is None:  # pragma: no cover  # only a non-file; callers pass files
        import tarfile  # start-up

        raise tarfile.ReadError(f"{member.name} is not a file")
    with io.TextIOWrapper(fileobj, encoding="utf-8") as wrapper:
        return wrapper.read()
