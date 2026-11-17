# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Roadmap item 47: what the name tier answers for a few words, row by row,
on a database of the whole 3.29.0 List (``licenseid.namehits`` holds the
rules).

A row marked ``# BUG: (item 47)`` is a wrong answer that no rule of the item
touches: it pins today's answer and is flipped when the leftover is built.
The other rows are decided answers, keepers (answers that must stay) and
guards: the name tier's refusal must never stop Tier 1 where the name tier
found nothing, so a licence text of 10 to 29 words, the Apache notice and
the heads of BSD, MIT and 0BSD answer by text as they did.

The database holds the text of the near neighbours of the resolver corpus
(``resolver_corpus.NEIGHBOURS``) and, for the guards, the text of HIDAPI,
which no other test database has: a guard on a database without its text
passes for the wrong reason.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
import time
from collections.abc import Generator
from typing import Any, NamedTuple

import pytest
from conftest import GivenWarnings, make_memory_db_path
from resolver_corpus import _search_text, corpus_db_path
from timing import slack

from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.resolvefirst import MIN_TEXT_WORDS

#: The CLI's default bar: a result below it is no answer.
BAR = 0.85


class Top(NamedTuple):
    """The top answer at the bar: expression, method, exact."""

    expression: str
    method: str
    exact: bool


@pytest.fixture(scope="module")
def detector() -> Generator[LicenseDetector, None, None]:
    for path in corpus_db_path("name_tier_leftovers", make_memory_db_path):
        with sqlite3.connect(path, uri=True) as conn:
            conn.execute(
                "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
                ("HIDAPI", _search_text("HIDAPI")),
            )
        yield LicenseDetector(path)


def top(detector: LicenseDetector, text: str, **options: Any) -> Top | None:
    found = [r for r in detector.detect(text=text, **options) if r["score"] >= BAR]
    if not found:
        return None
    return Top(found[0]["expression"], found[0]["method"], found[0]["exact"])


def window(license_id: str, words: int, tail: bool = False) -> str:
    """*words* words from the head (or tail) of a licence's text."""
    text = _search_text(license_id).split()
    return " ".join(text[-words:] if tail else text[:words])


NAME = "name"

# Answers that moved by a decision of item 47.
DECIDED = [
    # D47-1: of tied whole names the most specific wins (the longest holds
    # the others), generic words ("license", "see", "file") aside.
    (
        "Licensed under the Apple Public Source License 1.2",
        Top("APSL-1.2", NAME, False),  # was APSL-1.1, first by ID
    ),
    (
        "Licensed under the Artistic License 1.0 (Perl)",
        Top("Artistic-1.0-Perl", NAME, False),  # was Artistic-1.0
    ),
    (
        "Released under the MIT License (modern variant)",
        Top("MIT-Modern-Variant", NAME, False),  # was MIT
    ),
    ("MIT No Attribution (see LICENSE)", Top("MIT-0", NAME, False)),  # was MIT
    # D47-1: two names not nested are two licences: no answer.
    ("Universal Permissive License 1.0 or Apache License 2.0", None),
    ("MIT -or- Apache License 2.0", None),
    ("MIT, The Unlicense", None),  # "MIT" is an upper-case ID, written whole
    (  # the name of the other licence lacks the hit's "v" only: two licences
        "Licensed under the GNU Affero General Public License v3.0 or the MIT License",
        None,
    ),
    ("zlib/libpng License", None),
    # D47-4: a fragment of a longer name, a dash glued to a word end.
    ("MIT Future License", None),
    ("License: MIT-", None),
    # D47-3: a cut version (the warning stays: under 10 words).
    ("Licensed under the Apache-1 license", None),
    ("MVT-1", None),
    ("Sendmail-8", None),
    ("Apache License 1", None),
    # D47-4: "with <exception>" (the word, or a name of the List).
    ("Apache License 2.0 with LLVM exception", None),
    # The default of the item: "vN" is "vN.0" (variant not stated).
    (
        "GNU Lesser General Public License v3",
        Top("LGPL-3.0-only", NAME, False),
    ),
    ("GNU General Public License v2", Top("GPL-2.0-only", NAME, False)),
    # Review round 2b: two versions written apart are two licences.
    (
        (
            "Licensed under the Apache License, Version 2.0; earlier releases "
            "used the Apache License 1.1"
        ),
        None,
    ),
    ("Eclipse Public License, Version 2.0, replaces Eclipse Public License 1.0", None),
    ("Licensed under the MIT License (ISC)", None),
    # Review round 2: a cut version with a grant of another number, a second
    # licence by its ID, an exception by its words, still no answer.
    ("Apache License 1. Requires Java 8 or later", None),
    ("Licensed under the Mozilla Public License 1. Needs Firefox 3+ to run it", None),
    # A grant of a tool's is no grant of the cut version, nor is a grant of
    # a licence that has no -or-later ID (Apache), nor one that names the
    # LGPL or the AGPL by words that hold the GPL's name.
    ("Apache License 1. Requires Java 1 or later", None),
    ("Mozilla Public License 1. Needs Firefox 1+ to run it", None),
    ("Apache License 1 or later", None),
    ("GNU Lesser General Public License v2.0 or later", None),
    ("GNU Affero General Public License v2.0 only", None),
    ("BSD-3-Clause, Apache License 2.0", None),
    ("ISC License and Apache-2.0 apply to this package", None),
    ("GNU General Public License v2.0 only with Classpath exception", None),
    (
        "Licensed under the Apache License 2.0 with the LLVM exception for everyone",
        None,
    ),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [pytest.param(text, top_, id=text[:40]) for text, top_ in DECIDED],
)
def test_decided_answers(
    detector: LicenseDetector,
    given: GivenWarnings,
    text: str,
    expected: Top | None,
) -> None:
    assert top(detector, text) == expected
    if expected is None and len(normalize_text(text).split()) < MIN_TEXT_WORDS:
        # The refusal does not take away the reason: a short value says it
        # is no licence value.
        [line] = given.lines().splitlines()
        assert line.startswith("WARNING: input: too few words for text: ")
    else:
        given.take()


# Wrong answers that no rule of the item touches: leftovers.
BUGS = [
    # A name hit under 1.0 for 10 words falls through to Tier 1, where a
    # text of another licence answers (MPL-2.0 on the real database).
    # BUG: (item 47)
    (
        "Licensed under the GNU Affero General Public License v3.0",
        Top("MPL-2.0-no-copyleft-exception", "text", False),
    ),
    # A one-word ID that is an ordinary word is no second licence.
    # BUG: (item 47)
    ("Unlicense, ISC License", Top("ISC", NAME, False)),
    # Two licences named, one by a grant-less GPL name or a short BSD form:
    # only tied names are weighed against each other. BUG: (item 47)
    ("GNU General Public License v2.0 or MIT License", Top("MIT", NAME, False)),
    ("MIT License or BSD 3-Clause", Top("MIT", NAME, False)),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [pytest.param(text, top_, id=text[:40]) for text, top_ in BUGS],
)
def test_leftovers_answer_as_before(
    detector: LicenseDetector, given: GivenWarnings, text: str, expected: Top
) -> None:
    assert top(detector, text) == expected
    given.take()


def test_a_short_refusal_with_a_variant_warning(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    text = "GNU Lesser General Public License v3"
    assert top(detector, text) == Top("LGPL-3.0-only", NAME, False)
    assert given.lines() == (
        "WARNING: input: variant not stated: LGPL-3.0; using LGPL-3.0-only\n"
    )


# A cut version of a licence that has no version 2.0 stays no answer.
def test_a_cut_version_warns_too_few_words(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    text = "Mozilla Public License 2"
    assert top(detector, text) is None
    assert given.lines() == (
        f"WARNING: input: too few words for text: not found: {text}\n"
    )


# Answers that must stay.
KEEPERS = [
    ("Licensed under the MIT License", Top("MIT", NAME, False)),
    ("Apache License 2.0 (c) 2019 Example Corp", Top("Apache-2.0", NAME, False)),
    ("Python Software Foundation License", Top("PSF-2.0", NAME, False)),
    ("LGPL-2+", Top("LGPL-2.0-or-later", "id", False)),
    # "2" is "2.0": no cut.
    ("Apache License 2", Top("Apache-2.0", NAME, False)),
    # A grant read off the text exempts a cut version (#217).
    (
        "GNU Lesser General Public License v2 or later",
        Top("LGPL-2.1-or-later", NAME, False),
    ),
    # Generic words ("license") are no evidence of another licence: ANTLR-PD
    # ties with ANTLR-PD-fallback, whose name holds "license".
    ("License: ANTLR Software Rights Notice", Top("ANTLR-PD", NAME, False)),
    # An ID that is an ordinary word ("Intel") is no second licence.
    (
        "MIT License. Copyright (c) 2020 Intel Corporation",
        Top("MIT", NAME, False),
    ),
    # One word of an exception's name is no exception ("works with Linux").
    ("MIT License, compatible with GPL", Top("MIT", NAME, False)),
    ("Released under the MIT License, works with Linux", Top("MIT", NAME, False)),
    # A letter glued to a version: read through versionkey.
    ("BSD 4.3 TAHOE License", Top("BSD-4.3TAHOE", NAME, True)),
    # Review round 2: the rules read what touches the name, not the whole input.
    ("Licensed under the MIT License. TCL scripts included.", Top("MIT", NAME, False)),
    ("Apache License 2.0 (JSON module)", Top("Apache-2.0", NAME, False)),
    ("Licensed under the MIT License. Uses X11 for display.", Top("MIT", NAME, False)),
    ("License: MIT. NCSA Mosaic heritage", Top("MIT", NAME, False)),
    ("Licensed under the MIT License. Follows the W3C spec.", Top("MIT", NAME, False)),
    # "ICU License", "NTP License" and "DOC License" are no names written
    # whole where the acronym and "License" stand apart.
    (
        "MIT License. Synchronises the clock with NTP servers on the local network",
        Top("MIT", NAME, False),
    ),
    (
        (
            "Apache License 2.0. Uses ICU for Unicode normalisation and collation "
            "in every locale"
        ),
        Top("Apache-2.0", NAME, False),
    ),
    (
        "MIT License. See DOC for the user guide and examples of use",
        Top("MIT", NAME, False),
    ),
    (
        "Licensed under copyleft-next 0.3.0, see section 1 for the grants",
        Top("copyleft-next-0.3.0", NAME, False),
    ),
    (
        "Licensed under the Reciprocal Public License 1.1, see section 5 for the terms",
        Top("RPL-1.1", NAME, False),
    ),
    (
        (
            "Licensed under the European Union Public Licence 1.1; see "
            "clause 2 for details"
        ),
        Top("EUPL-1.1", NAME, False),
    ),
    (
        "Licensed under the Apple Public Source License 1.1, chapter 2 has details",
        Top("APSL-1.1", NAME, False),
    ),
    (
        "Licensed under the Apache License 1.1, release 1.0 of the Jakarta project",
        Top("Apache-1.1", NAME, False),
    ),
    (
        (
            "Licensed under the Mozilla Public License 1.1 since release "
            "0.9 of this package"
        ),
        Top("MPL-1.1", NAME, False),
    ),
    (
        "Released under the MIT License. Copyright 2015- present the authors",
        Top("MIT", NAME, False),
    ),
    (
        "Copyright (C) 2010- Foo Ltd. Licensed under the Apache License, Version 2.0",
        Top("Apache-2.0", NAME, False),
    ),
    (
        "MIT License; covers the pre- and post-processing scripts in this repository",
        Top("MIT", NAME, False),
    ),
    (
        (
            "MIT License, see the __version__ attribute for the release "
            "number of this package"
        ),
        Top("MIT", NAME, False),
    ),
    (
        (
            "The MIT License (MIT) Copyright (c) 2014- Foo Bar "
            "Permission is hereby granted"
        ),
        Top("MIT", NAME, False),
    ),
    (
        "Apache License 2.0. Built with GCC and CMake on every supported platform",
        Top("Apache-2.0", NAME, False),
    ),
    ("Apache License 2.0; tested with GCC 12 on Linux", Top("Apache-2.0", NAME, False)),
    (
        "MIT License. This package is compatible with Swift 5 and iOS 13 and newer",
        Top("MIT", NAME, False),
    ),
    (
        "MIT License, use it with the font of your choice in every document",
        Top("MIT", NAME, False),
    ),
    (
        "MIT License, use it with no exceptions and no warranty of any kind at all",
        Top("MIT", NAME, False),
    ),
    (
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        Top("OFL-1.1", NAME, False),
    ),
    (
        (
            "This library is free software licensed under the GNU "
            "General Public License v2.0 only"
        ),
        Top("GPL-2.0-only", NAME, False),
    ),
    (
        "MIT License, copyright (c) 2020 The IPA Group, all rights reserved",
        Top("MIT", NAME, False),
    ),
    (
        "MIT License. The scripting layer is written in TCL for the old tools",
        Top("MIT", NAME, False),
    ),
    (
        "MIT License, (c) 2020 NCSA team at the University of Illinois at Urbana",
        Top("MIT", NAME, False),
    ),
    # "with" alone names no exception: "with or without modification".
    (
        "SIL Open Font License 1.1 with Reserved Font",
        None,  # a fragment of OFL-1.1-RFN's name: no answer
    ),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [pytest.param(text, top_, id=text[:40]) for text, top_ in KEEPERS],
)
def test_keepers(
    detector: LicenseDetector,
    given: GivenWarnings,
    text: str,
    expected: Top | None,
) -> None:
    assert top(detector, text) == expected
    given.take()


APACHE_NOTICE = (
    'Licensed under the Apache License, Version 2.0 (the "License"); you may not'
    " use this file except in compliance with the License."
)

# Guards for a refusal that is final: texts of 10 to 29 words that the name
# tier answers or leaves to Tier 1. (value, answer)
GUARDS = [
    # The whole text of HIDAPI, 22 words.
    (_search_text("HIDAPI"), Top("HIDAPI", "text", True)),
    (APACHE_NOTICE, Top("Apache-2.0", NAME, False)),
    (window("BSD-2-Clause", 24), Top("BSD-2-Clause", "text", False)),  # "with or"
    (window("MIT", 14, tail=True), Top("MIT", "text", False)),
    (window("0BSD", 24), Top("0BSD", "text", False)),
    # Two versions written whole ("2.1 1)" holds 1.1 as words): the nearer.
    (
        "under the Open Software License version 2.1 1) Grant of",
        Top("OSL-2.1", NAME, False),
    ),
    # "Licensev." is one word of the text, no "License" and a "v.".
    (
        "The Open Software Licensev. 2.1 This Open Software License (the",
        Top("OSL-2.1", NAME, False),
    ),
    # A title, an acronym and "Version" before the number: 1.0 is not 1.1.
    (
        (
            "COMMON DEVELOPMENT AND DISTRIBUTION LICENSE (CDDL) Version "
            "1.0 1. Definitions."
        ),
        Top("CDDL-1.0", NAME, False),
    ),
    # "Motosoto License" is written "Motosoto Open Source License".
    (
        (
            "MOTOSOTO OPEN SOURCE LICENSE - Version 0.9.1 This Motosoto Open Source "
            'License (the "License") applies to "Community Portal Server" and '
            "related software products as"
        ),
        Top("Motosoto", NAME, False),
    ),
    # The head of the copyleft-next-0.3.0 text holds the words of 0.3.1.
    (window("copyleft-next-0.3.0", 14), Top("copyleft-next-0.3.0", NAME, False)),
    (window("copyleft-next-0.3.0", 20), Top("copyleft-next-0.3.0", NAME, False)),
    (window("copyleft-next-0.3.0", 29), Top("copyleft-next-0.3.0", NAME, False)),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(text, top_, id=f"{i}-{text[:20]}")
        for i, (text, top_) in enumerate(GUARDS)
    ],
)
def test_a_short_licence_text_keeps_its_answer(
    detector: LicenseDetector, text: str, expected: Top
) -> None:
    assert 10 <= len(text.split()) < 30
    assert top(detector, text) == expected


def test_exclude_of_the_winner_leaves_no_tied_name(
    detector: LicenseDetector,
) -> None:
    """The names tied below the winner are not the answer either: with the
    winner excluded the answer is the fuzzy neighbour, not the less specific
    tied name (APSL-1.1)."""
    text = "Licensed under the Apple Public Source License 1.2"
    assert top(detector, text, exclude=["APSL-1.2"]) == Top("APSL-1.0", NAME, False)
    assert top(detector, text, exclude=["APSL-1.1"]) == Top("APSL-1.2", NAME, False)


def test_hint_does_not_undo_a_refusal(
    detector: LicenseDetector, given: GivenWarnings
) -> None:
    """A refusal bypasses ``hint``, as Tier 0 does."""
    assert top(detector, "zlib/libpng License", hint=["Libpng"]) is None
    given.take()
    text = "Universal Permissive License 1.0 or Apache License 2.0"
    assert top(detector, text, hint=["UPL-1.0"]) is None


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("auto", Top("LGPL-3.0-only", NAME, False)),
        ("as-written", Top("LGPL-3.0", NAME, False)),
        ("only", Top("LGPL-3.0-only", NAME, False)),
        ("or-later", Top("LGPL-3.0-or-later", NAME, False)),
    ],
)
def test_the_variant_of_a_name_without_its_zero(
    detector: LicenseDetector,
    given: GivenWarnings,
    variant: str,
    expected: Top,
) -> None:
    """ "v3" is "v3.0": the twins tie and ``--variant`` decides."""
    text = "GNU Lesser General Public License v3"
    assert top(detector, text, variant=variant) == expected
    given.take()


def test_the_rules_cost_little_on_the_whole_list(detector: LicenseDetector) -> None:
    """Item 47 timing: a name hit with extra words (every rule runs) and 29
    distinct words (no hit), 40 times each, on the whole List: a call took
    about 2 ms, so the bound has 10 times that headroom."""
    named = "Licensed under the Apple Public Source License 1.2 in this package"
    words = [f"{'abcdefghij'[i % 10]}{i}zq" for i in range(29)]
    start = time.monotonic()
    for i in range(40):
        detector.detect(text=named + f" {i}")
        detector.detect(text=" ".join(words) + f" w{i}")
    assert time.monotonic() - start < slack(2.5)
