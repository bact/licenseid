# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads the title a licence's own text gives itself
(``licenseid.resolvetitle``), and ``detect()`` answers it through
``resolve()``."""
# pylint: disable=missing-function-docstring

import json
import re
from pathlib import Path

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.resolveleaf import Found
from licenseid.resolvetitle import TITLES, read_title

TEXTS = Path(__file__).parent / "fixtures" / "license-text-long"


def _folded_text(license_id: str) -> str:
    data = json.loads((TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return " ".join(str(data["license_text"]).split()).casefold()


@pytest.mark.parametrize(
    ("title", "texts"),
    [
        ("cc0 1.0 universal", ["CC0-1.0"]),
        (
            "gnu general public license version 3, 29 june 2007",
            ["GPL-3.0-only", "GPL-3.0-or-later"],  # both IDs of the bare one
        ),
        ("mulan psl v2", ["MulanPSL-2.0"]),
    ],
)
def test_the_text_of_each_id_writes_its_title(title: str, texts: list[str]) -> None:
    """A title is read only because the licence's own text writes it."""
    assert TITLES[title] == texts[0].removesuffix("-only")
    for license_id in texts:
        assert title in _folded_text(license_id), license_id


def test_the_cc0_text_names_itself_without_its_version() -> None:
    """``CC0`` alone is a title too: the text calls itself so ("apply CC0 to
    the Work"), not only within ``CC0 1.0 Universal``."""
    alone = re.findall(r"\bcc0\b(?! 1\.0)", _folded_text("CC0-1.0"))
    assert len(alone) >= 3
    assert TITLES["cc0"] == "CC0-1.0"


def test_every_title_is_checked_against_a_text() -> None:
    assert sorted(TITLES) == [
        "cc0",
        "cc0 1.0 universal",
        "gnu general public license version 3, 29 june 2007",
        "mulan psl v2",
    ]
    assert all(title == title.casefold() for title in TITLES)


def test_the_v2_title_is_not_in_the_v1_text() -> None:
    """The title names one version: the Mulan PSL v1 text does not write it.
    (The LGPL-3.0 text does cite the GPL's title: it names the GPL.)"""
    assert "mulan psl v2" not in _folded_text("MulanPSL-1.0")


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("CC0 1.0 Universal", "CC0-1.0"),
        ("cc0 1.0 universal", "CC0-1.0"),
        ("CC0", "CC0-1.0"),  # no version: an exception to P47
        ("cc0", "CC0-1.0"),
        ("Mulan PSL v2", "MulanPSL-2.0"),
        ("MULAN PSL V2", "MulanPSL-2.0"),
    ],
)
def test_a_title_is_read_as_its_licence(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        expression,
        "text_title",
        "resolver_rule",
    )
    (the_step,) = got["steps"]
    assert (the_step["kind"], the_step["from"], the_step["to"]) == (
        "text_title",
        value,
        expression,
    )
    assert the_step["list"] == "spdx-license-list"
    assert (got["candidates"], got["expansions"], got["reason"]) == ([], [], None)
    assert [e["id"] for e in got["lists"]] == ["spdx-license-list"]
    assert got["operands"][0]["steps"] == got["steps"]


@pytest.mark.parametrize(
    "value",
    [
        "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007",
        "GNU General Public License Version 3, 29 June 2007",
    ],
)
def test_the_gpl_title_line_is_the_bare_id(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The title writes version 3 and no grant: ``GPL-3.0``, never narrowed
    (P49), as a trove name that writes no grant."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        "GPL-3.0",
        "assumed_only",
        "none",
    )
    assert got["candidates"] == ["GPL-3.0-only", "GPL-3.0-or-later"]
    assert [s["kind"] for s in got["steps"]] == ["text_title"]


def test_a_title_takes_one_end_mark(corpus_db: LicenseDatabase) -> None:
    got = resolve("CC0 1.0 Universal.", corpus_db)
    assert got["expression"] == "CC0-1.0"
    assert [s["kind"] for s in got["steps"]] == ["separator", "text_title"]


@pytest.mark.parametrize(
    "value",
    [
        "Universal Permissive License",  # no title, no trove name
        "CC0 2.0 Universal",
        "CC 0",
        "The CC0 1.0 Universal",
        "CC0 1.0 Universal License",
        "CC0 1.0 Universe",
        "Mulan PSL v1",  # no title of the table
        "Mulan PSL",
        "Mulan PSL v2 (MulanPSL-2.0)",
        "GNU GENERAL PUBLIC LICENSE Version 3",  # the title line cut short
        "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2008",
        "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",  # not measured
        # Distorted spellings of the fixtures, which a text match once took
        "theUnlicense",
        "fehLicense",
        "bitstreamCharterFontLicense",
        "Unlicen",
        "ImageMagi",
        "W3C Software Notice and License (200212-31)",
        "open software v 3.0.0",
    ],
)
def test_a_value_that_is_no_title_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")


def test_a_title_is_no_operand(corpus_db: LicenseDatabase) -> None:
    got = resolve("MIT OR CC0 1.0 Universal", corpus_db)
    assert got["expression"] is None
    assert got["reason"] == "operand of several words: CC0 1.0 Universal"


def test_a_one_word_title_is_an_operand(corpus_db: LicenseDatabase) -> None:
    """An operand reads as it would alone: ``CC0`` is one word."""
    got = resolve("CC0 OR MIT", corpus_db)
    assert (got["expression"], got["category"]) == ("CC0-1.0 OR MIT", "text_title")
    assert resolve("CC0+", corpus_db)["expression"] is None  # no grant on a title


def test_a_title_whose_id_the_list_lacks_names_nothing() -> None:
    for path in seeded_db("title_lacks", [Lic("MIT", "MIT License")]):
        db = LicenseDatabase(path, create=False)
        assert resolve("CC0 1.0 Universal", db)["expression"] is None
        found = Found()
        with db.reading():
            assert not read_title(db, "CC0 1.0 Universal", found)
        assert (found.expression, found.steps) == (None, [])


def test_read_title_says_whether_the_value_is_a_title(
    corpus_db: LicenseDatabase,
) -> None:
    found = Found()
    with corpus_db.reading():
        assert not read_title(corpus_db, "MIT License", found)
        assert found.steps == []
        assert read_title(corpus_db, "Mulan PSL v2", found)
    assert found.expression == "MulanPSL-2.0"


@pytest.mark.parametrize(
    ("text", "expression", "exact"),
    [
        ("CC0 1.0 Universal", "CC0-1.0", True),
        ("CC0", "CC0-1.0", True),
        ("Mulan PSL v2", "MulanPSL-2.0", True),
        ("Universal Permissive License (UPL)", "UPL-1.0", True),  # trove name
    ],
)
def test_detect_answers_a_title_through_resolve(
    corpus_db: LicenseDatabase, text: str, expression: str, exact: bool
) -> None:
    (found,) = LicenseDetector(corpus_db.location).detect(text)
    assert (found["expression"], found["method"], found["exact"]) == (
        expression,
        "name",
        exact,
    )


def test_detect_narrows_the_gpl_title_line_aloud(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    text = "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007"
    (found,) = LicenseDetector(corpus_db.location).detect(text)
    assert (found["expression"], found["method"], found["exact"]) == (
        "GPL-3.0-only",
        "name",
        False,
    )
    assert given.lines() == (
        f"WARNING: input: variant not stated: {text}; using GPL-3.0-only\n"
    )


@pytest.mark.parametrize("value", ["Mulan P\u017fl v2", "\u212a"])
def test_case_folds_in_ascii_only(corpus_db: LicenseDatabase, value: str) -> None:
    """A long s or a KELVIN SIGN folds to no ASCII letter of a title."""
    found = Found()
    assert read_title(corpus_db, value, found) is False


@pytest.mark.parametrize("value", ["CC0", "cc0"])
def test_an_explicit_id_reads_the_one_word_title(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """``--id CC0`` answers as the argument ``CC0`` does."""
    detector = LicenseDetector(corpus_db.location)
    (by_id,) = detector.detect(license_id=value)
    (by_text,) = detector.detect(value)
    assert by_id == by_text
    assert (by_id["expression"], by_id["method"], by_id["exact"]) == (
        "CC0-1.0",
        "name",
        True,
    )
    assert detector.is_fsf(license_id=value) is by_id["is_fsf_libre"]


def test_a_tag_does_not_read_a_title_until_0_8(corpus_db: LicenseDatabase) -> None:
    """A tag keeps its own reader, which reads no title: documented in
    docs/python-api.md, to change when it goes through resolve()."""
    text = "SPDX-License-Identifier: CC0\nint main(void);\n"
    found = LicenseDetector(corpus_db.location).detect(text)
    assert "CC0-1.0" not in [result["expression"] for result in found]


def test_a_manifest_field_reads_a_title_through_resolve(
    corpus_db: LicenseDatabase,
) -> None:
    """A field no marker reader takes is read by resolve() (item 48)."""
    text = '{"name": "x", "license": "CC0"}'
    found = LicenseDetector(corpus_db.location).detect(text)
    assert [result["expression"] for result in found][:1] == ["CC0-1.0"]


@pytest.mark.parametrize("value", ["Foo-9", "CC0x", "GPL-9.0"])
def test_an_explicit_id_resolve_refuses_has_no_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert LicenseDetector(corpus_db.location).detect(license_id=value) == []


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("CC0  1.0 Universal", "CC0-1.0"),
        ("Mulan\tPSL v2", "MulanPSL-2.0"),
        ("CC0 1.0\u00a0Universal", "CC0-1.0"),  # a no-break space
        # the heading as the GPL v3 text writes it, on two lines
        ("GNU GENERAL PUBLIC LICENSE\n   Version 3, 29 June 2007", "GPL-3.0"),
    ],
    ids=["two-spaces", "tab", "no-break", "two-lines"],
)
def test_a_run_of_white_space_in_a_title_is_one_space(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert got["steps"][0]["kind"] == "text_title"
