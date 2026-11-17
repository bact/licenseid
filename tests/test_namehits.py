# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules that doubt a name hit (``licenseid.namehits``, item 47), on
made-up rows shaped as cases of the List: a nested tie, two licences, a cut
version, an exception, another ID. ``test_name_tier_leftovers`` has the real
ones. A rule is checked by the hit it drops and by the answer of
``detect()`` after it: a refusal is no answer from 10 words on, and under
ten words the value still says it is no licence value."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator

import pytest
from conftest import GivenWarnings
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.shorttext import match_name_tier, match_short_text

ROWS = [
    # A nested pair: the longer name holds the shorter one's words.
    Lic("Nest-1.0", "Nest Name"),
    Lic("Nest-Inner-1.0", "Nest Name Inner"),
    # Two licences that are no pair, and the words that hold both.
    Lic("Left-1.0", "Left Name"),
    Lic("Right-1.0", "Right Name"),
    # A name and a longer one that holds the first and generic words.
    Lic("Gen-1.0", "Gen Name"),
    Lic("Gen-Special-1.0", "Gen Name Special License"),
    # A name and a longer one, the input's extra word is no generic one.
    Lic("Pad-1.0", "Pad Name"),
    Lic("Pad-Plus-1.0", "Pad Name Plus Edition"),
    # Versions: 1.1 (cut by "1"), 2.0 (is "2"), 3.0.1 (cut by "3" and "3.0").
    Lic("Cut-1.1", "Cut Name 1.1"),
    Lic("Cut-2.0", "Cut Name 2.0"),
    Lic("Dot-3.0.1", "Dot Name 3.0.1"),
    Lic("Zero-1.2.0", "Zero Name 1.2.0"),
    # A name, and two longer ones that hold the input's words and are named
    # by neither (two holders: no tie): a fragment.
    Lic("Frag-1.0", "Frag Name License"),
    Lic("Frag-A-1.0", "Frag Name Future Alpha Edition Of The Thing"),
    Lic("Frag-B-1.0", "Frag Name Future Beta Edition Of The Thing"),
    # A name that no rule touches.
    Lic("Glue-1.0", "Glue Name"),
    Lic("Exc-1.0", "Exc Name"),
    # A name with a "with" of its own, followed by an exception's words.
    Lic("Wth-1.0", "Wth Name with Linux note"),
    # IDs: with a digit, upper case, an ordinary word.
    Lic("Digit-2.0", "Digit Name 2.0"),
    Lic("ZZ", "Zed Name"),
    Lic("Word", "Wordy Thing"),
    Lic("Base-1.0", "Base Name"),
]
# Exceptions whose words are common ones: "or" (the name of PS-or-PDF-font-
# exception), and "the" with "license".
EXCEPTIONS = ("Linux-note", "PS-or-PDF-note", "The-License-note")


@pytest.fixture(scope="module")
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_namehits", ROWS, exception_ids=EXCEPTIONS):
        yield LicenseDatabase(path)


def hits(db: LicenseDatabase, text: str) -> list[str]:
    """The IDs of the hits above 1 that stand for *text*."""
    found = match_short_text(db, normalize_text(text), text)
    return [m["license_id"] for m in found if m["score"] > 1.0]


def refused(db: LicenseDatabase, text: str) -> bool:
    return match_name_tier(db, normalize_text(text), text).refused


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        # The longest of nested names wins, the shorter one tied is dropped.
        ("Used under Nest Name Inner terms", ["Nest-Inner-1.0"]),
        ("Used under Nest Name terms", ["Nest-1.0"]),
        # Two licences, not nested: none.
        ("Left Name or Right Name", []),
        # Generic words are no evidence: Gen's name and "license".
        ("Gen Name License", ["Gen-1.0"]),
        ("Gen Name (see LICENSE file)", ["Gen-1.0"]),
        # Another word ties with a name the input holds in part: none.
        ("Pad Name Plus", []),
    ],
)
def test_ties_of_whole_names(db: LicenseDatabase, text: str, stands: list[str]) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        ("Cut Name 1", []),  # 1.1 cut short
        ("Cut Name 1.1", ["Cut-1.1"]),  # whole
        ("Cut Name 2", ["Cut-2.0"]),  # "2" is "2.0"
        ("Cut Name 2.0", ["Cut-2.0"]),
        ("Dot Name 3", []),  # 3.0.1 cut short
        ("Dot Name 3.0", []),
        ("Dot Name 3.0.1", ["Dot-3.0.1"]),
        # "1.2" is "1.2.0": the rest is all zeros, no cut.
        ("Zero Name 1.2", ["Zero-1.2.0"]),
        # A grant read off the text exempts the cut (#217).
        ("Cut Name 1 or later", ["Cut-1.1"]),
        ("Cut Name 1+", ["Cut-1.1"]),
    ],
)
def test_a_cut_version(db: LicenseDatabase, text: str, stands: list[str]) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        ("Glue Name- terms", []),
        ("Glue Name_ terms", []),
        ("Glue -or- Name", []),
        ("Glue Name terms", ["Glue-1.0"]),
        ("Glue Name - terms", ["Glue-1.0"]),  # a spaced dash is the author's
    ],
)
def test_a_dash_glued_to_a_word_end(
    db: LicenseDatabase, text: str, stands: list[str]
) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        # An exception of the List, by its distinctive words after "with".
        ("Exc Name with Linux note", []),
        ("Exc Name with Linux note and other words", []),
        # The word, whether the List names it or not.
        ("Exc Name with the other exception", []),
        ("Exc Name with exceptions", []),
        # One word of an exception's name is no exception ("works with Linux").
        ("Exc Name works with Linux", ["Exc-1.0"]),
        ("Exc Name with other thing", ["Exc-1.0"]),
        # The name's own "with" is no doubt.
        ("Wth Name with Linux note under terms", ["Wth-1.0"]),
        # "with" alone, or with common words.
        ("Exc Name with or without modification", ["Exc-1.0"]),
        ("Exc Name in compliance with the License", ["Exc-1.0"]),
        # "or" lies in the name of one exception: a function word, no name.
        ("Exc Name with or", ["Exc-1.0"]),
    ],
)
def test_an_exception(db: LicenseDatabase, text: str, stands: list[str]) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        # An ID with a digit, written whole (in any case).
        ("Base Name, Digit-2.0", []),
        ("Base Name, digit-2.0", []),
        # An upper-case ID, written so.
        ("Base Name, ZZ", []),
        ("Base Name, zz", ["Base-1.0"]),
        # An ID that is an ordinary word.
        ("Base Name, Word", ["Base-1.0"]),
        # The hit's own ID is no other licence.
        ("Base Name, Base-1.0", ["Base-1.0"]),
    ],
)
def test_another_id_written_whole(
    db: LicenseDatabase, text: str, stands: list[str]
) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        # The rest of the input lies in a longer name: a fragment of it.
        ("Frag Name Future License", []),
        # Generic words only: the name itself.
        ("Frag Name License (see file)", ["Frag-1.0"]),
        # Words that lie in no longer name: more words, the same licence.
        ("Frag Name License of mine", ["Frag-1.0"]),
    ],
)
def test_a_fragment_of_a_longer_name(
    db: LicenseDatabase, text: str, stands: list[str]
) -> None:
    assert hits(db, text) == stands


def test_a_stray_plus_in_a_section_is_no_guess() -> None:
    """The sections of a mixed text reach ``match_short_text`` without
    ``refuses_text_match``: a "＋" that normalize_text drops must not leave
    the narrower grant of a name that states none."""
    rows = [
        Lic("Pair-1.0-only", "Pair Name v1 only"),
        Lic("Pair-1.0-or-later", "Pair Name v1 or later"),
    ]
    for path in seeded_db("test_namehits_plus", rows):
        pair = LicenseDatabase(path)
        for plus, stands in (("", ["Pair-1.0-only", "Pair-1.0-or-later"]), (" ＋", [])):
            text = f"Pair Name v1{plus}"
            found = match_short_text(pair, normalize_text(text), text)
            assert [m["license_id"] for m in found if m["score"] > 1.0] == stands


def test_a_refusal_is_final_only_above_one(db: LicenseDatabase) -> None:
    """A dropped hit that would have answered says so; a fuzzy one (below
    1.0) leaves the text tiers to run."""
    assert refused(db, "Left Name or Right Name")
    assert refused(db, "Cut Name 1")
    # A fuzzy hit of "Cut Name 1.1" (below 1.0) is dropped, and not final.
    assert hits(db, "Cut Nam 1") == []
    assert not refused(db, "Cut Nam 1")
    assert not refused(db, "Used under Nest Name Inner terms")
    assert not refused(db, "Nothing like any name here")


def test_the_detector_gives_no_text_answer_from_ten_words(
    given: GivenWarnings,
) -> None:
    """The value is the text of a licence on the database: only the final
    refusal keeps Tier 1 from answering it."""
    value = "Left Name or Right Name as stated in the notice of this package"
    assert len(value.split()) >= 10
    rows = [*ROWS, Lic("Stated-1.0", "Stated Name", search_text=normalize_text(value))]
    for path in seeded_db("test_namehits_final", rows):
        detector = LicenseDetector(path)
        assert detector.detect(text=value) == []
        assert not given.take()


def test_the_detector_says_why_under_ten_words(
    db: LicenseDatabase, given: GivenWarnings
) -> None:
    detector = LicenseDetector(str(db.db_path))
    assert detector.detect(text="Cut Name 1") == []
    assert (
        given.lines()
        == "WARNING: input: too few words for text: not found: Cut Name 1\n"
    )
