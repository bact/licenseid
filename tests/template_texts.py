# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Made-up copies of List texts whose template variables (``<<var>>``) hold
other words, and the database they are searched on, from the recipes of
``tests/fixtures/template-texts/cases.json`` (``tests/fixtures/README.md``,
section 21).

A part ``@ID`` is ``license_text`` of ``license-text-long/ID.json`` (else
``template-texts/texts/ID.txt``); a part ``{"template": ID, "fills": {name:
words}}`` is the template of ID with each named var written as *words* and
every other var as its ``original``, optional parts kept unless
``"optional": false``; any other part is literal text. Parts join with
``several_texts.SEPARATOR``.

The database is built as ``update`` builds one (``packaged_list.database_of``)
from those texts of :data:`IDS` and their templates
(``template-texts/templates``, else ``license-template``)."""

import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, NamedTuple

import pytest
from list_entries import lic_entry
from packaged_list import database_of
from several_texts import LONG_TEXTS, SEPARATOR

from licenseid.coretext import pieces
from licenseid.spdxdata import SpdxData, to_bundle

FIXTURES = Path(__file__).parent / "fixtures"
FOLDER = FIXTURES / "template-texts"
CASES = FOLDER / "cases.json"
PATTERNS = FOLDER / "patterns.json"
TEMPLATE_DIRS = (FOLDER / "templates", FIXTURES / "license-template")

#: The licences of the database: the texts of the recipes and their near
#: twins (the BSD-3-Clause family, X11's and MIT-CMU's neighbours, OpenLDAP
#: versions, NBPL-1.0 (OLDAP-1.1 but for its vars), LPPL versions, PostgreSQL
#: beside Cornell-Lossless-JPEG); ISC has no template, so no regions.
IDS = (
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSD-3-Clause-Attribution",
    "BSD-3-Clause-Clear",
    "BSD-3-Clause-HP",
    "BSD-4-Clause",
    "Cornell-Lossless-JPEG",
    "HPND",
    "ISC",
    "LPPL-1.1",
    "LPPL-1.2",
    "MIT",
    "MIT-CMU",
    "NBPL-1.0",
    "NCSA",
    "OLDAP-1.1",
    "OLDAP-2.2",
    "OLDAP-2.2.1",
    "OLDAP-2.2.2",
    "OLDAP-2.7",
    "OLDAP-2.8",
    "PostgreSQL",
    "X11",
    "X11-distribute-modifications-variant",
)

_NAME = re.compile(r'<<var;name="([^"]*)"')


def long_text(license_id: str) -> str:
    """``license_text`` of the long-text fixture of *license_id*, else the
    List text in ``template-texts/texts``."""
    path = LONG_TEXTS / f"{license_id}.json"
    if not path.is_file():
        return (FOLDER / "texts" / f"{license_id}.txt").read_text(encoding="utf-8")
    text = json.loads(path.read_text(encoding="utf-8"))["license_text"]
    assert isinstance(text, str), license_id
    return text


def template(license_id: str) -> str | None:
    """The List template of *license_id* in the fixtures, or None."""
    for folder in TEMPLATE_DIRS:
        path = folder / f"{license_id}.template.txt"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def filled(license_id: str, fills: dict[str, str], optional: bool = True) -> str:
    """The template of *license_id* with each var named in *fills* written
    as its words, the others as their ``original``, optional parts kept
    unless not *optional*."""
    source = template(license_id)
    assert source is not None, license_id
    walked = pieces(source)
    assert walked is not None, license_id
    names = iter(_NAME.findall(source))
    parts = []
    for piece in walked:
        if piece.kind == "var":
            words = fills.get(next(names), piece.text)
            if optional or not piece.depth:
                parts.append(words)
        elif piece.kind in ("plain", "text") and (optional or not piece.depth):
            parts.append(piece.text)
        elif piece.kind == "end" and not optional and not piece.depth:
            parts.append(" ")  # a word boundary, as ``coretext.core_text``
    assert not set(fills) - set(_NAME.findall(source)), fills
    return "".join(parts)


def _part(part: str | dict[str, Any]) -> str:
    if isinstance(part, dict):
        return filled(
            part["template"], part.get("fills", {}), part.get("optional", True)
        )
    return long_text(part[1:]) if part.startswith("@") else part


class Case(NamedTuple):
    """A recipe: its name, its text, ``TEXTS`` with the regions and without
    (before this build), and why."""

    case: str
    text: str
    texts: tuple[str, ...]
    before: tuple[str, ...]
    like: str


def template_cases() -> list[Case]:
    """Every recipe, in file order."""
    return [
        Case(
            recipe["case"],
            SEPARATOR.join(_part(part) for part in recipe["parts"]),
            tuple(recipe["texts"]),
            tuple(recipe["before"]),
            recipe["like"],
        )
        for recipe in json.loads(CASES.read_text(encoding="utf-8"))
    ]


def _raw() -> bytes:
    templates = {i: t for i in IDS if (t := template(i)) is not None}
    return to_bundle(
        SpdxData(
            "3.29.0",
            None,
            tuple(lic_entry(i, f"Name {i}") for i in IDS),
            (),
            MappingProxyType({i: long_text(i) for i in IDS}),
            MappingProxyType(templates),
        )
    )


def template_texts_db(directory: Path) -> Path:
    """A database of :data:`IDS` built by ``update`` in *directory*, under a
    home of its own there (never the real cache)."""
    home = directory / "home"
    home.mkdir()
    path = directory / "licenses.db"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(home))
        patch.setenv("USERPROFILE", str(home))
        patch.setattr(Path, "home", staticmethod(lambda: home))
        database_of(_raw(), path)
    return path
