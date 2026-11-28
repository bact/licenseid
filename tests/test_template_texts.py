# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``TEXTS`` of copies that fill a template's variable parts with their own
words (``licenseid.textmask``), on a database ``update`` builds with the
templates (``template_texts``): the recipes name their own text, as they did
not before; a near twin keeps its name; no answer at 0.85 moves; the build
stores the regions and a lookup reads them back, or builds without them."""
# pylint: disable=missing-function-docstring,protected-access

import hashlib
import sqlite3
from pathlib import Path
from types import MappingProxyType

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from list_entries import lic_entry
from packaged_list import database_of
from stored_texts import all_texts, no_stored_codes
from template_texts import Case, template_cases, template_texts_db

from licenseid import textmask
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.textcorpus import RunChars, TextCorpus, VarRegion
from licenseid.textstore import CORE_VARS, PATTERNS, TEXT_VARS

CASES = template_cases()


@pytest.fixture(name="db_path", scope="module")
def _db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return template_texts_db(tmp_path_factory.mktemp("template-texts"))


def _texts(path: Path, text: str) -> list[str] | None:
    detector = LicenseDetector(db_path=str(path))
    results = detector.detect(text=text)
    if results:
        found = results[0].get("texts")
        return None if found is None else list(found)
    return detector.texts(text=text)


def _answer(path: Path, text: str) -> str | None:
    results = LicenseDetector(db_path=str(path)).detect(text=text)
    if results and results[0]["score"] >= 0.85:
        return str(results[0]["expression"])
    return None


def _corpus(path: Path) -> TextCorpus:
    return all_texts(LicenseDatabase(str(path), create=False))


def test_the_recipes_are_the_27_cases() -> None:
    assert len(CASES) == 27
    assert len({case.case for case in CASES}) == 27


@pytest.mark.parametrize("case", CASES, ids=[case.case for case in CASES])
def test_a_filled_copy_names_its_text(case: Case, db_path: Path) -> None:
    assert tuple(_texts(db_path, case.text) or ()) == case.texts


@pytest.mark.parametrize("case", CASES, ids=[case.case for case in CASES])
def test_without_regions_the_texts_are_those_of_before(
    case: Case, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corpus coded in memory (no stored rows, so no regions) gives what
    the search gave before the regions: the recipes test the regions."""
    no_stored_codes(monkeypatch)
    assert tuple(_texts(db_path, case.text) or ()) == case.before


def test_the_recipes_that_move() -> None:
    """Six of the ten known cases and two OpenLDAP copies gain their name;
    the OLDAP-1.1 core with a third holder loses it (NBPL-1.0's core ties
    it); MIT-CMU with two vars side by side gains it; PostgreSQL with
    fills shorter than its List words gains it."""
    moved = [case.case for case in CASES if case.texts != case.before]
    assert moved == [
        "bsd3-regents",
        "bsd3-regents-mit",
        "bsd3-author",
        "bsd3-contact",
        "mit-cmu-holder",
        "ncsa-project",
        "oldap-2.2-holder",
        "oldap-2.8-holder",
        "oldap-1.1-core-holder",
        "mit-cmu-disclaims",
        "postgresql-acme",
        "postgresql-shortest",
    ]


HOLDERS = [
    case for case in CASES if case.case in ("oldap-2.2-holder", "oldap-2.8-holder")
]


@pytest.mark.parametrize("case", HOLDERS, ids=[case.case for case in HOLDERS])
def test_a_long_holder_line_keeps_the_answer(case: Case, db_path: Path) -> None:
    """A twin (OLDAP-2.2.1, OLDAP-2.7) never keys above the true text for a
    fill longer than both: the answer and ``TEXTS`` are the true text."""
    expected = case.case.removesuffix("-holder").upper()
    assert _answer(db_path, case.text) == expected
    assert case.texts == (expected,)


@pytest.mark.parametrize("case", CASES, ids=[case.case for case in CASES])
def test_no_answer_at_085_moves(
    case: Case, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = _answer(db_path, case.text)
    no_stored_codes(monkeypatch)
    assert _answer(db_path, case.text) == answer


def test_the_build_stores_the_regions(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        kinds = {
            kind for (kind,) in conn.execute("SELECT DISTINCT kind FROM text_codes")
        }
    assert {TEXT_VARS, CORE_VARS, PATTERNS} <= kinds
    by_id = {entry.text.row_id: entry for entry in _corpus(db_path).entries}
    assert by_id["BSD-3-Clause"].text.regions[0] == VarRegion(0, 4, ".{0,5000}")
    assert not by_id["ISC"].text.regions  # no template
    core = by_id["MIT"].core
    assert core is not None and core.regions


def test_least_is_each_text_with_its_variable_parts_cut(db_path: Path) -> None:
    """``CodedText.least`` is the length ``textmask`` leaves of each text and
    core of real templates with every run of non-empty parts cut out."""
    by_id = {}
    for entry in _corpus(db_path).entries:
        for coded in (entry.text, entry.core):
            if coded is None or not coded.regions:
                continue
            runs = textmask._merged(
                [(r.start, r.end) for r in coded.regions if r.end > r.start]
            )
            kept = textmask._cut(coded.text, RunChars(coded.text), runs)
            assert coded.least == len(kept), coded.row_id
            by_id[coded.row_id, coded.is_core] = coded.least
    assert by_id["BSD-3-Clause", False] == 1159
    assert by_id["MIT", False] == 843
    assert by_id["PostgreSQL", False] == 896
    assert by_id["PostgreSQL", True] == 812


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "body",
    ["[[0, 99999, 0]]", "[[0, 4, 9999]]", "not json", "[[0, 4, 0], [1]]"],
    ids=["past-the-end", "no-pattern", "not-json", "short-item"],
)
def test_damaged_regions_code_in_memory_without_regions(
    db_path: Path, tmp_path: Path, body: str
) -> None:
    copy = tmp_path / "copy.db"
    copy.write_bytes(db_path.read_bytes())
    with sqlite3.connect(copy) as conn:
        conn.execute(
            "UPDATE text_codes SET body = ? WHERE kind = ? AND owner_id = ?",
            (body, TEXT_VARS, "BSD-3-Clause"),
        )
    before = _digest(copy)
    entries = _corpus(copy).entries
    assert [entry.text.codes for entry in entries] == [
        entry.text.codes for entry in _corpus(db_path).entries
    ]
    assert not any(entry.text.regions for entry in entries)
    assert _digest(copy) == before  # a lookup never writes


def _var(name: str, original: str, match: str = ".+") -> str:
    return f'<<var;name="{name}";original="{original}";match="{match}">>'


def test_twins_whose_templates_differ_share_their_common_regions(
    tmp_path: Path,
) -> None:
    """X-only and X-or-later have one text; each template lets a part vary
    that the other does not (GPL-2.0-only and -or-later): neither is a
    region, only the holder both let vary."""
    body = " ".join(f"term{i} of the licence" for i in range(12))
    text = f"version 2 of this licence only {body} the holder"
    holder = _var("h", "the holder")
    only = f"version {_var('v', '2')} of this licence only {body} {holder}"
    later = f"version 2 of this licence {_var('o', 'only')} {body} {holder}"
    raw = to_bundle(
        SpdxData(
            "9.99",
            None,
            (lic_entry("X-only"), lic_entry("X-or-later")),
            (),
            MappingProxyType({"X-only": text, "X-or-later": text}),
            MappingProxyType({"X-only": only, "X-or-later": later}),
        )
    )
    (entry,) = all_texts(database_of(raw, tmp_path / "twins.db")).entries
    assert entry.text.regions == (VarRegion(54, 56, ".+"),)
