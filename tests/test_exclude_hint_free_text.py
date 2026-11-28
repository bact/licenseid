# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``exclude`` and ``hint`` of ``detect()`` act on free text only (roadmap
item 52).

A declaration (an SPDX tag, a ``license`` field, ``license_id``, a whole
input ``resolve()`` reads) is never filtered or hinted. Both options compare
IDs case-folded. A bare deprecated ID in either stands for its two twins and
warns ``option: deprecated ID``; a ``-with-`` ID is taken as written.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import PROSE, Lic, seeded_db

from licenseid.deprecatedids import BARE_TO_OR_LATER, DEPRECATED_BARE_LICENSE_IDS
from licenseid.detector import LicenseDetector
from licenseid.idoptions import excluded_ids, free_text_hits, upgraded_options
from licenseid.normalize import normalize_text
from licenseid.types import DetectOptions, RawMatch

LONG = Path(__file__).parent / "fixtures" / "license-text-long"
MIT = json.loads((LONG / "MIT.json").read_text(encoding="utf-8"))["license_text"]
BODY = MIT.split("\n", 2)[2]  # MIT's text without its heading
GPL = "GNU General Public License v2.0"
GPL_BODY = f"{GPL} only\n{PROSE * 2}"  # a title the prose markers read
SHORT_PROSE = (
    "This project is released under the terms of the MIT License, "
    "see the LICENSE file for details."
)
ONLY, LATER = "GPL-2.0-only", "GPL-2.0-or-later"
ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text=normalize_text(MIT)),
    Lic(ONLY, f"{GPL} only", True, True, True, search_text=f"{GPL} only".lower()),
    Lic(LATER, f"{GPL} or later", True, True, search_text=f"{GPL} or later".lower()),
    Lic(
        "GPL-2.0",
        GPL,
        is_deprecated=True,
        superseded_by=ONLY,
        search_text=GPL.lower(),
    ),
)


@pytest.fixture(scope="module")
def detector() -> Generator[LicenseDetector, None, None]:
    for path in seeded_db("test_exclude_hint_free_text", ROWS):
        yield LicenseDetector(path)


def answers(detector: LicenseDetector, **kwargs: Any) -> list[str]:
    return [r["expression"] for r in detector.detect(**kwargs)]


# --- A declaration is never filtered or hinted ---

DECLARED = {
    "license_id": {"license_id": "MIT"},
    "tag": {"text": f"{PROSE}SPDX-License-Identifier: MIT\n"},
    "tag_over_gpl_text": {"text": f"SPDX-License-Identifier: MIT\n{GPL_BODY}"},
    "field": {"text": '{"license": "MIT"}'},
    "whole_id": {"text": "MIT"},
}


@pytest.mark.parametrize("kwargs", DECLARED.values(), ids=list(DECLARED))
def test_a_declaration_is_never_filtered_or_hinted(
    detector: LicenseDetector, given: GivenWarnings, kwargs: dict[str, Any]
) -> None:
    options = {"exclude": ["MIT", "GPL-2.0"], "hint": ["GPL-2.0", ONLY]}
    assert answers(detector, **kwargs, **options) == ["MIT"]
    assert given.take() == []  # nothing acted on, nothing upgraded


def test_a_name_hit_beside_a_tag_of_no_id_is_a_declaration(
    detector: LicenseDetector,
) -> None:
    """``resolve()`` read "MIT" (no similarity): exclude never drops it."""
    text = "MIT\nSPDX-License-Identifier: NotAnId"
    assert answers(detector, text=text, exclude=["MIT"]) == ["MIT"]


def test_a_declared_deprecated_id_is_no_guess_of_exclude(
    detector: LicenseDetector,
) -> None:
    assert answers(detector, license_id=ONLY, exclude=[ONLY]) == [ONLY]


# --- A bare deprecated ID stands for its two twins ---

BARE = sorted(DEPRECATED_BARE_LICENSE_IDS)


@pytest.mark.parametrize("option", ["exclude", "hint"])
@pytest.mark.parametrize("bare", BARE)
def test_a_bare_deprecated_id_becomes_its_twins(
    given: GivenWarnings, option: str, bare: str
) -> None:
    got = upgraded_options({option: [bare.upper(), "MIT"]})  # type: ignore[misc]
    assert got[option] == [  # type: ignore[literal-required]
        DEPRECATED_BARE_LICENSE_IDS[bare],
        BARE_TO_OR_LATER[bare],
        "MIT",
    ]
    assert given.lines() == (
        f"WARNING: option: deprecated ID: {option} {bare}; "
        f"using {DEPRECATED_BARE_LICENSE_IDS[bare]}, {BARE_TO_OR_LATER[bare]}\n"
    )


@pytest.mark.parametrize(
    "options",
    [
        DetectOptions(),
        DetectOptions(exclude=[], hint=["GPL-2.0-with-classpath-exception"]),
        DetectOptions(
            exclude=["GPL-2.0-only", "MIT", "GPL-2.0-", "GPL-2.0-only+", "MIT+"]
        ),
        DetectOptions(only_common=True, enable_popularity=True),
    ],
    ids=["none", "with_id", "not_bare", "flags"],
)
def test_nothing_else_is_upgraded(given: GivenWarnings, options: DetectOptions) -> None:
    """A ``-with-`` ID has no twin: it stays as written, with no warning."""
    assert upgraded_options(options) == options
    assert given.take() == []


def test_the_caller_keeps_its_own_lists(given: GivenWarnings) -> None:
    ids = ["GPL-2.0"]
    upgraded_options({"exclude": ids})
    assert ids == ["GPL-2.0"]
    assert given.conditions() == {"deprecated ID"}


def test_a_bare_deprecated_id_is_excluded_as_both_twins(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    assert {ONLY, LATER} <= set(answers(detector, text=GPL_BODY))
    assert not given.take()  # the title says "only": no guess
    got = answers(detector, text=GPL_BODY, exclude=["gpl-2.0"])
    assert {ONLY, LATER, "GPL-2.0"}.isdisjoint(got)
    assert given.lines() == (
        f"WARNING: option: deprecated ID: exclude GPL-2.0; using {ONLY}, {LATER}\n"
    )


def test_a_bare_deprecated_id_is_hinted_as_both_twins(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    assert answers(detector, text=BODY) == ["MIT"]
    got = detector.detect(text=BODY, hint=["GPL-2.0"])
    assert {r["expression"] for r in got[1:]} == {ONLY, LATER}  # not GPL-2.0
    # Both twins have a text of their own, and rank on it (a bare row has none).
    assert all(r["score"] > 0 for r in got[1:])
    assert given.lines() == (
        f"WARNING: option: deprecated ID: hint GPL-2.0; using {ONLY}, {LATER}\n"
    )


def test_a_bare_deprecated_id_is_warned_of_once(given: GivenWarnings) -> None:
    upgraded_options({"exclude": ["GPL-2.0", "gpl-2.0", "GPL-2.0"]})
    assert len(given.take()) == 1


@pytest.mark.parametrize(
    ("exclude", "text", "gone"),
    [
        # A title or mention names the deprecated row itself.
        (["GPL-2.0"], f"GPL-2.0\n\n{PROSE}", "GPL-2.0"),
        ([ONLY, LATER], f"GPL-2.0\n\n{PROSE}", "GPL-2.0"),
        # Short prose, answered by name (Tier 0), is free text too.
        (
            ["MIT"],
            SHORT_PROSE,
            "MIT",
        ),
    ],
    ids=["bare", "both_twins", "short_prose"],
)
def test_exclude_reaches_the_deprecated_rows_and_short_prose(
    detector: LicenseDetector,
    given: GivenWarnings,
    exclude: list[str],
    text: str,
    gone: str,
) -> None:
    assert gone in answers(detector, text=text)
    assert gone not in answers(detector, text=text, exclude=exclude)
    given.take()


def test_one_twin_excluded_keeps_the_bare_row(detector: LicenseDetector) -> None:
    """Excluding only ``-only`` says nothing of the ambiguous bare ID."""
    text = f"GPL-2.0\n\n{PROSE}"
    assert "GPL-2.0" in answers(detector, text=text, exclude=[ONLY])


def test_a_hint_in_mixed_content_is_upgraded_too(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    mixed = PROSE * 2 + "Licensed under the MIT License, see below.\n" + PROSE
    got = answers(detector, text=mixed, hint=["GPL-2.0"])
    assert got == answers(detector, text=mixed, hint=[ONLY, LATER])
    assert LATER in got
    given.take()


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        (["MIT"], {"mit"}),
        (["GPL-2.0"], {"gpl-2.0", "gpl-2.0-only", "gpl-2.0-or-later", "gpl-2.0+"}),
        (["GPL-2.0-only", "GPL-2.0-OR-LATER"], {"gpl-2.0", "gpl-2.0+"}),
        (["GPL-2.0-or-later"], {"gpl-2.0+"}),
        (["GPL-2.0-only"], set()),
    ],
    ids=["plain", "bare", "both_twins", "or_later", "only"],
)
def test_the_deprecated_forms_an_exclude_reaches(
    ids: list[str], expected: set[str]
) -> None:
    got = excluded_ids(ids)
    assert expected <= got
    assert ("gpl-2.0" in got) == ("gpl-2.0" in expected)


def test_a_name_read_as_a_declaration_is_never_excluded(
    detector: LicenseDetector,
) -> None:
    """``resolve()`` reads "GPL-2.0+," whole: a declaration, so exclude is
    not read."""
    assert answers(detector, text="GPL-2.0+,", exclude=[LATER]) == [LATER]


SHORT_NAME = "This is licensed under GNU General Public License v2.0 only"
TITLE_22 = (
    "This software is licensed under the GNU General Public License v2.0 only, "
    "and you may use it as that licence says."
)


@pytest.mark.parametrize("text", [SHORT_NAME, TITLE_22], ids=["short", "22_words"])
def test_a_short_text_warns_of_the_deprecated_id_too(
    detector: LicenseDetector, given: GivenWarnings, text: str
) -> None:
    """Tier 0 reads the options too: the twins are excluded, and said so."""
    got = answers(detector, text=text, exclude=["GPL-2.0"])
    assert {ONLY, LATER, "GPL-2.0"}.isdisjoint(got)
    assert given.lines() == (
        f"WARNING: option: deprecated ID: exclude GPL-2.0; using {ONLY}, {LATER}\n"
    )


# --- "GPL-2.0+" is GPL-2.0-or-later, as the List reads a "+" ---


@pytest.mark.parametrize("option", ["exclude", "hint"])
@pytest.mark.parametrize("written", ["GPL-2.0+", "gpl-2.0+"])
def test_a_deprecated_plus_id_becomes_its_or_later_twin(
    given: GivenWarnings, option: str, written: str
) -> None:
    got = upgraded_options({option: [written, "MIT"]})  # type: ignore[misc]
    assert got[option] == [LATER, "MIT"]  # type: ignore[literal-required]
    assert given.lines() == (
        f"WARNING: option: deprecated ID: {option} GPL-2.0+; using {LATER}\n"
    )


def test_a_deprecated_plus_id_is_warned_of_once(given: GivenWarnings) -> None:
    upgraded_options({"exclude": ["GPL-2.0+", "gpl-2.0+", "GPL-2.0+"]})
    assert len(given.take()) == 1


def test_a_deprecated_plus_id_is_excluded_with_its_or_later_twin(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    assert LATER in answers(detector, text=GPL_BODY)
    got = answers(detector, text=GPL_BODY, exclude=["GPL-2.0+"])
    assert {LATER, "GPL-2.0+"}.isdisjoint(got)
    assert ONLY in got  # the "-only" twin stays
    assert given.conditions() == {"deprecated ID"}  # "only" is stated
    assert {"gpl-2.0+", "gpl-2.0-or-later"} <= excluded_ids(["GPL-2.0-or-later"])


def test_a_hint_without_the_text_adds_the_twins_not_the_bare_row(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    """Text of no licence words: only what the hint adds is left."""
    text = PROSE * 3
    got = answers(detector, text=text, hint=["GPL-2.0"])
    assert set(got) == set(answers(detector, text=text, hint=[ONLY, LATER]))
    assert {ONLY, LATER} <= set(got)
    assert "GPL-2.0" not in got
    given.take()


def _hit(license_id: str, score: float, similarity: float | None = 0.9) -> RawMatch:
    return RawMatch(
        license_id=license_id,
        method="name",
        exact=False,
        score=score,
        similarity=similarity,
        coverage=None,
    )


@pytest.mark.parametrize(
    ("hits", "excluded", "kept"),
    [
        ([("A", 1.01), ("B", 0.94)], (), ["A", "B"]),
        ([("A", 1.01), ("B", 0.94)], ("b",), ["A"]),
        ([("A", 1.01), ("B", 0.94)], ("a",), []),  # a near name of the one excluded
        ([("A", 1.01), ("B", 1.01), ("C", 0.94)], ("a",), ["B"]),  # a tie stays
        ([("A", 0.1 + 0.2), ("B", 0.3)], ("a",), ["B"]),  # up to float rounding
        ([("A", 0.94), ("B", 1.01), ("C", 0.9)], ("a",), ["B"]),
        ([("A", 1.01), ("B", 0.94), ("C", 0.9)], ("a", "b"), []),
        ([("A", 1.01), ("B", 0.94), ("C", 0.9)], ("a", "c"), []),  # the best bars
    ],
    ids=str,
)
def test_a_name_hit_under_the_best_one_excluded_is_cut(
    hits: list[tuple[str, float]], excluded: tuple[str, ...], kept: list[str]
) -> None:
    found = free_text_hits([_hit(lid, s) for lid, s in hits], frozenset(excluded))
    assert [m["license_id"] for m in found] == kept


def test_a_declaration_is_no_bar_and_never_cut() -> None:
    read = _hit("A", 0.5, similarity=None)
    found = free_text_hits([_hit("B", 1.01), read], {"b"})
    assert found == [read]
    found = free_text_hits([_hit("A", 1.01, similarity=None), _hit("B", 0.94)], {"a"})
    assert [m["license_id"] for m in found] == ["A", "B"]
