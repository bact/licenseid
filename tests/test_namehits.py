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
from licenseid.namehits import refusal_answer
from licenseid.normalize import normalize_text
from licenseid.resolvefirst import MIN_TEXT_WORDS
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
    # An -or-later ID names a cut version that a grant of its own qualifies
    # ("Cutg License 1 or later"); its family is the letters of the ID.
    Lic("Egx-1.1.0", "Egx Public License 1.1.0"),
    Lic("Rng-1.6.35", "Rng Reference License v1 (for rng 0.5 through 1.6.35)"),
    Lic("Cutg-1.1-only", "Cutg License 1.1 only"),
    Lic("Cutg-1.1-or-later", "Cutg License 1.1 or later"),
    # A deprecated "+" ID carries the grant as well.
    Lic("Plusg-1.1+", "Plusg License 1.1 or later"),
    # GPL IDs of a made-up name: "General Public" after a word more is
    # another licence's name (Lesser, Library, Affero).
    Lic("GPL-9.0-only", "Zed General Public License v9.0 only"),
    Lic("GPL-9.0-or-later", "Zed General Public License v9.0 or later"),
    # A name, and two longer ones that hold the input's words and are named
    # by neither (two holders: no tie): a fragment.
    Lic("Frag-1.0", "Frag Name License"),
    Lic("Frag-A-1.0", "Frag Name Future Alpha Edition Of The Thing"),
    Lic("Frag-B-1.0", "Frag Name Future Beta Edition Of The Thing"),
    # Generic words ("see", "file") in a longer name: no evidence of it.
    Lic("Frag-D-1.0", "Frag Name See File Notice"),
    # Two licences of one name: no nesting, nothing to tell them by.
    Lic("Twin-1.0", "Twin Name"),
    Lic("Twin-2.0", "Twin Name"),
    # A name ending in a dash: the name itself (exact), whatever it says.
    Lic("Dsh-1.0", "Dsh Name-"),
    # Names whose words another name has from here and there.
    Lic("Fnt-1.1", "Fnt Open License 1.1"),
    Lic("Sft-1.1", "Open Software License 1.1"),
    Lic("Gen-2.0-only", "Gnu Gen License v2.0 only"),
    Lic("Lib-2.0-only", "Gnu Library Gen License v2.0 only"),
    # Versions that nest only by their digits: 1.1 holds the word "1".
    Lic("Num-1.0", "Num Name 1.0"),
    Lic("Num-1.1", "Num Name 1.1"),
    Lic("Ntp-1.0", "Ntp License"),
    Lic("Mot-1.0", "Mot License"),
    Lic("Dg-1.1", "Dg Name 1.1"),
    Lic("Dg-1.0.2", "Dg Name 1.0.2"),
    Lic("Sc-1.0", "Zeta Eta"),
    Lic("Sc-2.0", "Zeta Theta Iota Eta"),
    Lic("Wide-1.0", "Wide Big Name"),
    Lic("Pv-1.0", "Plain Name v2.0"),
    Lic("Fn-1.0", "Fn Name of Things"),
    Lic("Rch-1.0", "Rch Name"),
    Lic("Gl-1.0", "Gl Name License"),
    Lic("Sh-1.0", "Sh Alpha 1"),
    Lic("Sh-2.0", "Sh Beta 2"),
    Lic("Yak-1.0", "Yak Name"),
    Lic("Ver-1.1", "Ver Name 1.1"),
    Lic("Ver-2.1", "Ver Name 2.1"),
    Lic("Gap-1.0", "Gap Name 1.0"),
    Lic("Gap-1.1", "Gap Name 1.1"),
    Lic("Tri-0.3.0", "Tri Name 0.3.0"),
    Lic("Tri-0.3.1", "Tri Name 0.3.1"),
    # Another licence whose name lacks the "v" the input has not: two names.
    Lic("Univ-1.0", "Univ Name v1.0"),
    Lic("Plain-1.0", "Plain Name 1.0"),
    Lic("Plain-2.0", "Plain Name 2.0"),
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
EXCEPTIONS = ("Linux-note", "PS-or-PDF-note", "The-License-note", "Gcc-exception")


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
        # One name of two licences: not one nested in the other (a strict
        # "nested" test).
        ("Used under Twin Name", []),
        # A name written whole beats one put together from scattered words.
        (
            "This Font Software is licensed under the Fnt Open License, Version 1.1",
            ["Fnt-1.1"],
        ),
        (
            "This library is free software under the Gnu Gen License v2.0 only",
            ["Gen-2.0-only"],
        ),
        # Versions that differ by a digit: the one written whole.
        ("Num Name 1.1, release 1.0 of the project", ["Num-1.1"]),
        ("Num Name 1 and 0", []),  # the digits of a version are adjacent
        # Both versions are written whole ("1) Grant"): the nearer number wins.
        ("Ver Name Version 2.1 1) Grant", ["Ver-2.1"]),
        # The number of a version may follow the name after two words.
        ("Gap Name (GN) Version 1.0 1. Definitions", ["Gap-1.0"]),
        ("Tri Name 0.3.0, see section 1 for the grants", ["Tri-0.3.0"]),
        # Where no name is written whole, a name nests in a longer one that
        # adds a word, not a digit.
        ("Name Nest Inner", ["Nest-Inner-1.0"]),
        ("1.1 1.0 Num Name", []),
        # "Ntp License" is no name written whole where "Ntp" and "License"
        # stand apart.
        ("Base Name License, synchronises with Ntp servers here", ["Base-1.0"]),
        # "License" may stand a few words after the name's word ("Mot Open
        # Source License"), where "Ntp" ends the text and has none after it.
        ("Mot Open Source License applies to Ntp products", ["Mot-1.0"]),
        # An ordinary word is at most one word after the last of its name.
        ("Rch Foo Bar Name and Yak Name", ["Yak-1.0"]),
        # Two titles from one word, tighter or not: two licences.
        ("Sh Alpha Beta 1 2", []),
        # Two versions written whole, apart: two licences, not the tighter.
        ("Ver Name Version 2.1 and later Ver Name 1.1", []),
        # Names that differ by digits only nest in no longer name.
        ("1.1 1.0.2 Dg Name", []),
        # Scattered names nest by their words, in any order.
        ("Eta Iota Theta Zeta", ["Sc-2.0"]),
        # Two whole names of other words: two licences, whatever their length.
        ("Left Name or Wide Big Name", []),
        # A word between two words of a name (and the Library GPL's).
        (
            "This library is free software under the Gnu Super Gen License v2.0 only",
            ["Gen-2.0-only"],
        ),
        # Two names, the other's lacks the "v" of its version only.
        ("Univ Name 1.0 or Plain Name 2.0", []),
        ("Plain Name 2.0, see the terms", ["Plain-2.0"]),
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
        # A grant of the licence exempts the cut only where the hit carries
        # it: Cut-1.1 has no -or-later ID, so "Cut Name 1 or later" names
        # another licence (``resolve()`` reads Cut-1+), and no answer is
        # given (decided in the PR that read grants by their subject).
        ("Cut Name 1 or later", []),
        ("Cut Name 1+", []),
        # A grant of another number is no grant of the cut one.
        ("Cut Name 1. Requires Java 8 or later", []),
        ("Cut Name 1. Needs Firefox 3+ to run it", []),
    ],
)
def test_a_cut_version(db: LicenseDatabase, text: str, stands: list[str]) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        # A grant of the licence itself qualifies the cut number of an
        # -or-later hit: it is that ID.
        ("Cutg License 1 or later", ["Cutg-1.1-or-later"]),
        # The grant of the licence is read for the number it qualifies, not
        # the first number written.
        ("Requires Java 8. Cutg License 1 or later", ["Cutg-1.1-or-later"]),
        ("Plusg License 1 or later", ["Plusg-1.1+"]),
        # The same number written twice, one grant: one is not the licence's.
        ("Requires Java 1. Plusg License 1 or later", []),
        # "+" is dropped before scoring: no -or-later name is its top hit, and
        # the -only twin it scores for carries no grant.
        ("Cutg License 1+, see the file COPYING", []),
        # A grant of a tool's is not (the family is "java", not "cutg").
        ("Cutg License 1. Requires Java 1 or later", []),
        ("Cutg License 1. Needs Firefox 1+ to run it", []),
        # One own grant takes out one written number, not every equal one.
        ("Cutg License 1 or later. Requires Java 1 or later", []),
        # The version written in full beats the cut, a tool's number does not
        # count: only a number that touches the name does.
        ("Cutg License 1.1. Requires Java 1 or later", ["Cutg-1.1-or-later"]),
        ("Cutg License 1. Requires Java 1.1", []),
        ("Cut Name 1. Requires Java 1.1 or later", []),
        ("Cut Name 1.1. Requires Java 1", ["Cut-1.1"]),
        ("Cut Name 1.1 and Java 1.1", ["Cut-1.1"]),
        ("Cut Name version 1.1; Java 1", ["Cut-1.1"]),
        # The place is the name's: its second number follows "through".
        (
            "Licensed under the Rng Reference License v1 (for rng 0.5 through 1.6.35)",
            ["Rng-1.6.35"],
        ),
        ("Rng Reference License v1. Needs Java 1.6.35 or later", []),
        # ... a few: a number far from the name's word is a tool's.
        ("Cut Name is required by the Java 1.1 runtime, see Cut Name 1", []),
        ("Cut Name is required by the Java 1.1 runtime, see Cut Name 1.1", ["Cut-1.1"]),
        # Words of the licence's title may stand between name and number.
        (
            (
                "EGX PUBLIC LICENSE AGREEMENT\nVersion 1.1.0\n\nThis agreement is "
                "based on a widely accepted open source license.\n\n1."
            ),
            ["Egx-1.1.0"],
        ),
    ],
)
def test_a_grant_exempts_a_cut_by_its_subject(
    db: LicenseDatabase, text: str, stands: list[str]
) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        ("Zed Lesser General Public License v9.0 or later", []),
        ("Zed Library General Public License v9.0 only", []),
        ("Used under the Zed Affero General Public License v9.0 or later", []),
        ("Zed lesser general public license v9.0 only", []),
        # A GNU between is no word: the modifier stands before it.
        ("Zed Lesser GNU General Public License v9.0 only", []),
        # Both written: the GPL's name is in the input too (and no modifier
        # that is not before "General Public" counts).
        (
            (
                "Zed General Public License v9.0 only. Not the Zed Lesser General "
                "Public License"
            ),
            ["GPL-9.0-only"],
        ),
        (
            "General Public License v9.0 only. See Zed Affero General Public License",
            ["GPL-9.0-only"],
        ),
        ("Zed Lesser General Notes. Public License v9.0 only", ["GPL-9.0-only"]),
        # The modifier must stand right before "General Public".
        ("Zed General Public License v9.0 only, a Lesser one", ["GPL-9.0-only"]),
        ("Used under Zed General Public License v9.0 or later", ["GPL-9.0-or-later"]),
        # A grant elsewhere is the variant's business, not the family's.
        (
            "Zed General Public License v9.0\nRequires Python 9.0 or later",
            ["GPL-9.0-or-later"],
        ),
    ],
)
def test_another_gnu_licence_by_its_modifier(
    db: LicenseDatabase, text: str, stands: list[str]
) -> None:
    assert hits(db, text) == stands


@pytest.mark.parametrize(
    ("text", "stands"),
    [
        ("Glue Name- terms", []),
        ("Glue Name_ terms", []),
        ("Glue -or- Name", []),
        ("Glue Name terms", ["Glue-1.0"]),
        ("Glue Name - terms", ["Glue-1.0"]),  # a spaced dash is the author's
        # A dash that touches no word of the name is about something else.
        ("Glue Name terms. Copyright 2015- present the authors", ["Glue-1.0"]),
        ("Glue Name, covers the pre- and post-processing scripts", ["Glue-1.0"]),
        ("Glue Name, see the __version__ attribute of this package", ["Glue-1.0"]),
        # One that stands beside a word of it is not.
        ("Glue Name 2014- Foo Bar", []),
        # An exact name is the input, whatever dash ends it.
        ("Dsh Name-", ["Dsh-1.0"]),
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
        ("Exc Name with PS pdf note", []),
        # Words that tell the exception come right after the "with".
        ("Exc Name with other thing and Linux note", ["Exc-1.0"]),
        # One word of an exception's name is no exception by itself.
        ("Exc Name. Built with GCC and CMake on every platform", ["Exc-1.0"]),
        ("Exc Name with GCC", ["Exc-1.0"]),
        ("Exc Name with the GCC exception", []),
        # "exception" must be near: five words after the "with", not "no
        # exceptions", and the "with" must follow the name.
        ("Exc Name with one two three four exception", []),
        ("Exc Name with one two three four five exception", ["Exc-1.0"]),
        ("Exc Name with no exceptions", ["Exc-1.0"]),
        # "with the exception of" four words after the name's sentence.
        (
            "Exc Name. Please use it with the exception of the logo",
            ["Exc-1.0"],
        ),
        # "License" ends a name and is no evidence that a "with" follows it.
        ("Gl Name License. Use it with the exception of the logo", ["Gl-1.0"]),
        # A function word of the name ("of") is no name word before a "with".
        (
            (
                "Fn Name of Things, we ship it, see notes of the build "
                "with the other exception"
            ),
            ["Fn-1.0"],
        ),
        (
            "Exc Name is fine, it ships all over the world with the other exception",
            ["Exc-1.0"],
        ),
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
        ("Base Name and ZZ", []),
        ("ZZ, the Base Name", []),
        # An upper-case ID that is an acronym in prose, no list of IDs.
        (
            "Base Name, copyright (c) 2020 The ZZ Group, all rights reserved",
            ["Base-1.0"],
        ),
        (
            "Base Name. The scripting layer is written in ZZ for the old tools",
            ["Base-1.0"],
        ),
        # The "The" before an acronym is no name word; a name's own "of" is no
        # name word either.
        ("Base Name. The ZZ Group holds the copyright", ["Base-1.0"]),
        ("Fn Name of Things, written by the Team of ZZ", ["Fn-1.0"]),
        # An ID of another sentence, or in the name's own sentence but not
        # joined to it, is no second licence; a list of IDs is.
        ("Base Name. Depends on Digit-2.0 for the display", ["Base-1.0"]),
        ("Base Name. ZZ scripts are included", ["Base-1.0"]),
        ("Base Name (ZZ module)", ["Base-1.0"]),
        ("Base Name (ZZ)", []),
        ("Base Name, the ZZ", ["Base-1.0"]),
        ("Fn Name of Things is fine for the rest of, ZZ people", ["Fn-1.0"]),
        ("Base Name (Digit-2.0)", []),
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


def test_a_refusal_is_no_answer_from_ten_words_exactly() -> None:
    at_ten = refusal_answer(MIN_TEXT_WORDS)
    assert at_ten is not None
    assert not at_ten
    assert refusal_answer(MIN_TEXT_WORDS - 1) is None


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
