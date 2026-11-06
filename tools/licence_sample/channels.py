# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where each channel keeps its licence values, and how to read them.

A channel's top packages come from ecosyste.ms (one ranking for all of
them); the values themselves come from the channel's own registry, as the
package declares them, so nothing is normalised before ``resolve()`` sees
it. Each reader returns a list of ``{"field": ..., "value": ...}``: every
value the package states, in order (a POM may list several licences, each
with a name and a URL).
"""

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any, Final

Value = dict[str, str]
Fetch = Callable[[str], bytes | None]

ECOSYSTEMS_URL: Final = (
    "https://packages.ecosyste.ms/api/v1/registries/{registry}/packages"
    "?sort={sort}&order=desc&per_page=100&page={page}"
)
#: The ecosyste.ms registry of each channel, and what ranks its packages
#: (Maven Central reports no downloads there).
REGISTRIES: Final = {
    "pypi": ("pypi.org", "downloads"),
    "npm": ("npmjs.org", "downloads"),
    "cargo": ("crates.io", "downloads"),
    "maven": ("repo1.maven.org", "dependent_packages_count"),
    "nuget": ("nuget.org", "downloads"),
    "huggingface": ("huggingface.co", "downloads"),
}
CHANNELS: Final = tuple(REGISTRIES)
#: Parent POMs followed for licences a POM does not state itself.
MAX_PARENTS: Final = 4
_XML_DECLARATIONS: Final = re.compile(rb"<!(DOCTYPE|ENTITY)", re.IGNORECASE)


def _json(raw: bytes | None) -> Any:
    try:
        return None if raw is None else json.loads(raw)
    except ValueError:
        return None


def _text(value: object) -> str | None:
    """*value* when it is a non-blank string, stripped."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _values(*pairs: tuple[str, object]) -> list[Value]:
    return [
        {"field": field, "value": text}
        for field, value in pairs
        if (text := _text(value)) is not None
    ]


def xml_root(raw: bytes | None) -> ET.Element | None:
    """The root of the XML document *raw*, or None. A document that declares
    a DTD or an entity is refused unread: no registry needs one, and an
    entity can expand without bound."""
    if raw is None or _XML_DECLARATIONS.search(raw):
        return None
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _child_text(element: ET.Element, name: str) -> str | None:
    found = _children(element, name)
    return _text(found[0].text) if found else None


def pom_licences(root: ET.Element) -> list[Value]:
    """The ``<licenses>`` of a POM: each licence's name, then its URL."""
    values: list[Value] = []
    for licences in _children(root, "licenses"):
        for licence in _children(licences, "license"):
            values += _values(
                ("name", _child_text(licence, "name")),
                ("url", _child_text(licence, "url")),
            )
    return values


def pom_parent(root: ET.Element) -> tuple[str, str, str] | None:
    """``(groupId, artifactId, version)`` of a POM's parent, or None."""
    parents = _children(root, "parent")
    if not parents:
        return None
    parts = [
        _child_text(parents[0], key) for key in ("groupId", "artifactId", "version")
    ]
    return None if None in parts else (parts[0] or "", parts[1] or "", parts[2] or "")


def pom_url(group: str, artifact: str, version: str) -> str:
    """The URL of a POM on Maven Central."""
    path = "/".join([*group.split("."), artifact, version, f"{artifact}-{version}.pom"])
    return "https://repo1.maven.org/maven2/" + urllib.parse.quote(path)


def maven(name: str, version: str, fetch: Fetch) -> list[Value]:
    """The licences of a Maven artifact ``group:artifact``, from its POM or,
    when it states none, the nearest parent POM that does (``parent:``
    before the field)."""
    group, _, artifact = name.partition(":")
    coordinates: tuple[str, str, str] | None = (group, artifact, version)
    prefix = ""
    for _ in range(MAX_PARENTS + 1):
        if coordinates is None:
            break
        root = xml_root(fetch(pom_url(*coordinates)))
        if root is None:
            break
        values = pom_licences(root)
        if values:
            return [{"field": prefix + v["field"], "value": v["value"]} for v in values]
        coordinates, prefix = pom_parent(root), "parent:"
    return []


def nuget(name: str, version: str, fetch: Fetch) -> list[Value]:
    """The ``<license>`` (an expression or a file) and ``<licenseUrl>`` of a
    package's ``.nuspec``."""
    lower = name.lower()
    root = xml_root(
        fetch(
            "https://api.nuget.org/v3-flatcontainer/"
            f"{urllib.parse.quote(lower)}/{urllib.parse.quote(version.lower())}/"
            f"{urllib.parse.quote(lower)}.nuspec"
        )
    )
    metadata = _children(root, "metadata") if root is not None else []
    if not metadata:
        return []
    values: list[Value] = []
    for licence in _children(metadata[0], "license"):
        values += _values((f"license:{licence.get('type', '?')}", licence.text))
    return values + _values(("licenseUrl", _child_text(metadata[0], "licenseUrl")))


def npm(name: str, version: str, fetch: Fetch) -> list[Value]:
    """``license`` (a string, or the old ``{type, url}``) and the old
    ``licenses`` list of the ``package.json`` of *version*."""
    quoted = urllib.parse.quote(name, safe="@")
    doc = _json(
        fetch(f"https://registry.npmjs.org/{quoted}/{urllib.parse.quote(version)}")
    )
    if not isinstance(doc, dict):
        return []
    values: list[Value] = []
    for field in ("license", "licenses"):
        items = doc.get(field)
        for item in items if isinstance(items, list) else [items]:
            if isinstance(item, dict):
                values += _values(
                    (f"{field}.type", item.get("type")),
                    (f"{field}.url", item.get("url")),
                )
            else:
                values += _values((field, item))
    return values


def pypi(name: str, version: str, fetch: Fetch) -> list[Value]:
    """``License-Expression``, ``License`` and the ``License ::`` classifiers
    of the release *version*."""
    doc = _json(
        fetch(
            f"https://pypi.org/pypi/{urllib.parse.quote(name)}/"
            f"{urllib.parse.quote(version)}/json"
        )
    )
    info = doc.get("info") if isinstance(doc, dict) else None
    if not isinstance(info, dict):
        return []
    classifiers = [
        c
        for c in info.get("classifiers") or []
        if isinstance(c, str) and c.startswith("License ::")
    ]
    return _values(
        ("License-Expression", info.get("license_expression")),
        ("License", info.get("license")),
        *(("Classifier", c) for c in classifiers),
    )


def huggingface(name: str, version: str, fetch: Fetch) -> list[Value]:
    """``license``, ``license_name`` and ``license_link`` of the model
    card's metadata at the commit *version*."""
    doc = _json(
        fetch(
            f"https://huggingface.co/api/models/{urllib.parse.quote(name)}"
            f"/revision/{urllib.parse.quote(version)}"
        )
    )
    card = doc.get("cardData") if isinstance(doc, dict) else None
    if not isinstance(card, dict):
        return []
    licences = card.get("license")
    items = licences if isinstance(licences, list) else [licences]
    return _values(
        *(("license", item) for item in items),
        ("license_name", card.get("license_name")),
        ("license_link", card.get("license_link")),
    )


def cargo(
    _name: str, _version: str, _fetch: Fetch, listed: object = None
) -> list[Value]:
    """``license`` of ``Cargo.toml`` as ecosyste.ms lists it (*listed*):
    crates.io asks crawlers for one request a second, and its index holds no
    licence."""
    return _values(("license", listed))


READERS: Final[dict[str, Callable[..., list[Value]]]] = {
    "pypi": pypi,
    "npm": npm,
    "cargo": cargo,
    "maven": maven,
    "nuget": nuget,
    "huggingface": huggingface,
}
