# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A short input answers by what it names or what it is, not by a word it
shares with a licence.

``Foo`` answered 3D-Slicer-1.0 by text at 1.0 (coverage 0.0006) on the
3.29.0 list, and ``the`` MirOS by name at 1.0: a word found inside a long
licence text, or inside a name, scored as a perfect match. The rows below
are real licences with their real texts and names (the fixtures), so the
near neighbours that gave those answers are here: a database without texts
would answer nothing and pass for the wrong reason.

Since ``detect()`` asks ``resolve()`` first (``licenseid.resolvefirst``), an
input under ten words that it refuses gets no text match: ``Foo`` is no
answer there, before its length is weighed. The name tier still answers
before that cut, so its pins stand as they were; the text pins that weigh
a short input are of Han and kana, which the cut exempts.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import NO_DETECTION, GivenWarnings, predicate_line
from matcher_db import Lic, seeded_db

from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.similarity import EVIDENCE_COLUMNS, text_evidence
from licenseid.types import Detection

FIXTURES = Path(__file__).parent / "fixtures" / "license-text-long"

# Each a real licence: the near neighbours of the inputs below on the
# 3.29.0 list (the names holding "the", "gpl" and "license", the texts
# holding "foo" and "this program is free software").
IDS = (
    "0BSD",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "AML",
    "Apache-1.0",
    "Apache-1.1",
    "Apache-2.0",
    "BSD-1-Clause",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-SA-2.1-JP",
    "CDDL-1.0",
    "CDDL-1.1",
    "CNRI-Python-GPL-Compatible",
    "ESA-PL-permissive-2.4",
    "ESA-PL-strong-copyleft-2.4",
    "FSFAP",
    "GPL-1.0-only",
    "GPL-1.0-or-later",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "HPND",
    "ISC",
    "Interbase-1.0",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "MIT",
    "MIT-0",
    "MirOS",
    "MulanPSL-1.0",
    "MulanPSL-2.0",
    "PHP-3.0",
    "PHP-3.01",
    "Parity-7.0.0",
    "Unlicense",
    "WTFPL",
)


def fixture(license_id: str) -> dict[str, str]:
    data = json.loads((FIXTURES / f"{license_id}.json").read_text(encoding="utf-8"))
    return {"name": str(data["name"]), "text": str(data["license_text"])}


def head(license_id: str, lines: int) -> str:
    """The first *lines* lines of a licence that are not blank."""
    kept = [line for line in fixture(license_id)["text"].splitlines() if line.strip()]
    return "\n".join(kept[:lines])


@pytest.fixture(scope="module")
def db_path() -> Generator[str, None, None]:
    rows = [
        Lic(
            lid,
            fixture(lid)["name"],
            search_text=normalize_text(fixture(lid)["text"]),
        )
        for lid in IDS
    ]
    # A deprecated ID with a name of its own, as on the list.
    rows.append(
        Lic(
            "AGPL-3.0",
            "GNU Affero General Public License v3.0",
            is_deprecated=True,
            search_text=normalize_text(fixture("AGPL-3.0-only")["text"]),
        )
    )
    # The deprecated ID that shares GPL-2.0-only's name, as on the list.
    rows.append(
        Lic(
            "GPL-2.0",
            "GNU General Public License v2.0 only",
            is_deprecated=True,
            search_text=normalize_text(fixture("GPL-2.0-only")["text"]),
        )
    )
    # The bare ID that GPL-3.0's title names.
    rows.append(
        Lic(
            "GPL-3.0",
            "GNU General Public License v3.0 only",
            is_deprecated=True,
            search_text=normalize_text(fixture("GPL-3.0-only")["text"]),
        )
    )
    yield from seeded_db("test_shorttext_evidence", rows)


def detect(db_path: str, text: str) -> list[Detection]:
    return LicenseDetector(db_path).detect(text=text)


def answers(db_path: str, text: str) -> list[str]:
    """The answers at the CLI's default threshold."""
    return [r["expression"] for r in detect(db_path, text) if r["score"] >= 0.85]


# Words and phrases that occur in a licence text, none a licence: each was
# the top answer by text at 1.0.
SHORT_TEXT_WORDS = [
    ("Foo", "PHP-3.0"),
    ("copyright notice", "GPL-2.0-only"),
    ("This program is free software", "GPL-2.0-only"),
    ("the software is provided as is", "0BSD"),
]

# The same in Han and kana, which the cut by words exempts: weighed by length.
TEXT_WORDS = [
    ("日本語", "CC-BY-SA-2.1-JP"),
    ("许可证", "MulanPSL-1.0"),
]


@pytest.mark.parametrize(("text", "was"), SHORT_TEXT_WORDS)
def test_a_short_phrase_of_a_licence_text_is_no_answer(
    db_path: str, given: GivenWarnings, text: str, was: str
) -> None:
    """Under ten words, refused by resolve(): no text match at all."""
    del was
    assert not detect(db_path, text)
    assert (
        given.lines() == f"WARNING: input: too few words for text: not found: {text}\n"
    )


@pytest.mark.parametrize(("text", "top"), TEXT_WORDS)
def test_a_word_inside_a_licence_text_is_no_answer(
    db_path: str, text: str, top: str
) -> None:
    """The word still aligns with a window of the licence (similarity 1),
    but an input this short counts for little in the score."""
    results = detect(db_path, text)
    assert results[0]["expression"] == top  # the order is unchanged
    assert results[0]["method"] == "text"
    assert results[0]["similarity"] == 1.0
    assert results[0]["score"] < 0.85
    assert answers(db_path, text) == []


@pytest.mark.parametrize(("text", "top"), TEXT_WORDS)
def test_the_score_is_the_similarity_scaled_by_length(
    db_path: str, text: str, top: str
) -> None:
    """Similarity 1 times the evidence, plus at most the fingerprint
    bonus (0.05) of a phrase that one licence family uses."""
    del top
    evidence = text_evidence(normalize_text(text))
    assert evidence < 0.85
    assert evidence <= detect(db_path, text)[0]["score"] <= evidence + 0.05


# Words of a licence name that name no licence: each was the top answer by
# name at 1.0.
NAME_WORDS = [
    ("the", "MirOS"),
    ("GPL", "CNRI-Python-GPL-Compatible"),
    ("license", "0BSD"),
    ("software", "MulanPSL-1.0"),
    ("GNU General Public License", "AGPL-3.0-only"),
    ("Apache License", "Apache-1.0"),
    ("Creative Commons", "CC-BY-SA-2.1-JP"),
    ("GNU Lesser General Public License", "LGPL-2.1-only"),
    ("BSD License", "0BSD"),
    # A word only the ESA-PL names hold.
    ("PL", "ESA-PL-strong-copyleft-2.4"),
    ("PL v2.", "ESA-PL-strong-copyleft-2.4"),
    # The names of one licence's two grants, without its version.
    ("GNU Affero General Public License", "AGPL-3.0-only"),
]


def test_a_deprecated_name_is_still_answered(
    db_path: str, given: GivenWarnings
) -> None:
    """AGPL-3.0's name is held by the names that replaced it: they come
    first, the narrower a guess said aloud, and the deprecated row is the
    exact name."""
    text = "GNU Affero General Public License v3.0"
    results = detect(db_path, text)
    assert [(r["expression"], r["exact"]) for r in results[:3]] == [
        ("AGPL-3.0-only", False),
        ("AGPL-3.0-or-later", False),
        ("AGPL-3.0", True),
    ]
    assert results[0]["score"] == 1.0
    assert given.lines() == (
        f"WARNING: input: variant not stated: {text}; using AGPL-3.0-only\n"
    )


# A List name without its grant: held by the two rows of one licence, its
# -only and its -or-later, and by deprecated rows of the same licence.
GRANT_LEFT_OUT = [
    ("GNU General Public License v2.0", "GPL-2.0"),
    ("GNU General Public License v1.0", "GPL-1.0"),
    ("GNU General Public License v3.0", "GPL-3.0"),  # was AGPL-3.0-only
    ("GNU Lesser General Public License v2.1", "LGPL-2.1"),
    ("GNU Lesser General Public Licence v2.1", "LGPL-2.1"),  # British spelling
    ("gnu lesser general public license v2.1", "LGPL-2.1"),
]


@pytest.mark.parametrize(("text", "stem"), GRANT_LEFT_OUT)
def test_a_name_without_its_grant_is_the_narrower_guess(
    db_path: str, given: GivenWarnings, text: str, stem: str
) -> None:
    """Both grants hold the words, so neither is the input's name: the
    narrower is answered, not exact, and said aloud (as GPL2 is)."""
    results = detect(db_path, text)
    assert [(r["expression"], r["method"], r["exact"]) for r in results[:2]] == [
        (f"{stem}-only", "name", False),
        (f"{stem}-or-later", "name", False),
    ]
    assert results[0]["score"] == results[1]["score"] == 1.0
    assert given.lines() == (
        f"WARNING: input: variant not stated: {text}; using {stem}-only\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "GNU General Public License v2.0+",
        "GNU General Public License v2.0 +",
        "GNU Lesser General Public License v2.1+",
        "GNU General Public License v2.0 or later only",
        "only GNU General Public License v2.0 or later",
    ],
)
def test_a_name_with_a_grant_stated_twice_or_by_plus_is_no_guess(
    db_path: str, given: GivenWarnings, text: str
) -> None:
    """Never the -only guess for a grant the input states: none at all."""
    assert not detect(db_path, text)
    assert given.conditions() == {"too few words for text"}


@pytest.mark.parametrize(
    "text",
    [
        "GNU General Public License v2.0 only",
        "GNU General Public License v2.0 or later",
        "GNU Public License v2.0 only",  # a word left out, but the grant stated
        "MIT License",
    ],
)
def test_a_stated_grant_is_no_guess(
    db_path: str, given: GivenWarnings, text: str
) -> None:
    assert detect(db_path, text)
    assert given.take() == []


@pytest.mark.parametrize(("text", "was"), NAME_WORDS)
def test_a_word_of_a_name_is_no_answer(
    db_path: str, given: GivenWarnings, text: str, was: str
) -> None:
    del was
    assert not detect(db_path, text)
    assert given.conditions() == {"too few words for text"}


def test_a_name_that_holds_the_input_is_not_listed(db_path: str) -> None:
    """``MIT License`` is MIT's name; Apple MIT License only holds it."""
    results = detect(db_path, "MIT License")
    assert [(r["expression"], r["exact"], r["score"]) for r in results] == [
        ("MIT", True, 1.0)
    ]


def test_the_predicates_judge_no_licence(db_path: str, given: GivenWarnings) -> None:
    matcher = LicenseDetector(db_path)
    assert matcher.is_spdx(text="Foo") is None
    assert matcher.is_osi(text="the") is None
    assert given.conditions() == {"too few words for text"}


@pytest.mark.parametrize("command", ["detect", "is-osi", "is-spdx"])
@pytest.mark.parametrize("text", ["Foo", "the", "GPL", "BSD License", "PL"])
def test_the_cli_answers_no(db_path: str, command: str, text: str) -> None:
    result = CliRunner().invoke(cli, ["--db", db_path, command, text])
    assert result.exit_code == 1
    assert result.stdout == (
        NO_DETECTION if command == "detect" else predicate_line(command, "", None)
    )
    warning = f"WARNING: input: too few words for text: not found: {text}"
    assert warning in result.stderr.splitlines()


# A short input that names a licence, or is the start of one: the top
# answer, how it was found, and that it passes the CLI's threshold.
KEPT = [
    ("MIT", "MIT", "id"),
    ("Apache 2", "Apache-2.0", "id"),
    ("MIT License", "MIT", "name"),
    ("Licensed under the MIT License", "MIT", "name"),
    # A name with a word left out, which only one name holds.
    ("GNU Public License v2.0 only", "GPL-2.0-only", "name"),
    ("Interbase License v1.0", "Interbase-1.0", "name"),
    (head("GPL-3.0-only", 5), "GPL-3.0-only", "text"),
    (head("Apache-2.0", 10), "Apache-2.0", "text"),
    (head("BSD-3-Clause", 5), "BSD-3-Clause", "text"),
    # Japanese and Chinese: no spaces, and few characters say much.
    (head("CC-BY-SA-2.1-JP", 1), "CC-BY-SA-2.1-JP", "text"),
    (head("CC-BY-SA-2.1-JP", 2), "CC-BY-SA-2.1-JP", "text"),
    (head("MulanPSL-2.0", 2), "MulanPSL-2.0", "text"),
]


@pytest.mark.parametrize(("text", "top", "method"), KEPT, ids=lambda v: ascii(v)[:30])
def test_a_short_licence_input_keeps_its_answer(
    db_path: str, given: GivenWarnings, text: str, top: str, method: str
) -> None:
    results = detect(db_path, text)
    assert (results[0]["expression"], results[0]["method"]) == (top, method)
    assert results[0]["score"] >= 0.85
    assert given.take() == []


def test_the_two_title_lines_of_gpl_3_are_lost(
    db_path: str, given: GivenWarnings
) -> None:
    """A known loss, open for 0.8: the two title lines of GPL-3.0 (49
    characters) answered it by text; under ten words, they are now left to
    resolve(), whose title table has them on one line only."""
    text = head("GPL-3.0-only", 2)
    assert "\n" in text
    assert not detect(db_path, text)
    assert given.conditions() == {"too few words for text"}
    one_line = " ".join(text.split())
    assert detect(db_path, one_line)[0]["expression"] == "GPL-3.0-only"
    assert given.conditions() == {"variant not stated"}


@pytest.mark.parametrize(
    "license_id", ["ISC", "0BSD", "MIT-0", "Unlicense", "WTFPL", "FSFAP"]
)
def test_a_one_paragraph_licence_is_exact(db_path: str, license_id: str) -> None:
    results = detect(db_path, fixture(license_id)["text"])
    assert (results[0]["expression"], results[0]["exact"]) == (license_id, True)
    assert results[0]["score"] == 1.0


def test_a_common_licence_phrase_answers_its_licences(db_path: str) -> None:
    """Thirteen words that open many BSD-style licences: a licence text,
    though not one licence. (The ties among them are in the order of the
    list.)"""
    assert "BSD-2-Clause" in answers(
        db_path,
        "Redistribution and use in source and binary forms, with or without "
        "modification, are permitted",
    )


@pytest.mark.parametrize(
    "text",
    [
        "foo " * 20,  # long enough, but no licence says it
        # Ten words or more, so the text tiers weigh them.
        "notice copyright the software permission is granted provided above conditions",
        "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod",
        "日本語" * 7,  # 42 columns of a word the licence has once
    ],
    ids=["foo-x20", "licence-words-shuffled", "lorem", "nihongo-x7"],
)
def test_a_long_input_of_no_licence_text_is_no_answer(db_path: str, text: str) -> None:
    """Length alone answers nothing: the similarity must be there too."""
    assert len(normalize_text(text).split()) >= 10 or text.startswith("日")
    assert answers(db_path, text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 0.0),
        ("a", 1 / 40),
        ("x" * 39, 39 / 40),
        ("x" * 40, 1.0),
        ("x" * 4000, 1.0),
        ("日本語", 6 / 40),  # wide: two columns each
        ("ｆｏｏ", 6 / 40),  # fullwidth Latin: two columns each
        ("ｶﾀｶﾅ", 4 / 40),  # halfwidth katakana: one column each
        ("日" * 19 + "x", 39 / 40),
        ("日" * 20, 1.0),
        ("日" * 39, 1.0),  # under 40 characters, over 40 columns: at most 1
        ("é" * 10, 10 / 40),  # narrow, though not ASCII
    ],
    ids=lambda v: ascii(v)[:24],
)
def test_text_evidence_counts_columns(text: str, expected: float) -> None:
    assert EVIDENCE_COLUMNS == 40
    assert text_evidence(text) == pytest.approx(expected)
