# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.grantsubject``: whose grant an "or later" phrase is.

``grants`` reads what stands right before a phrase (a version number, the
word before it, "the License") and returns the licence's version and family
it names; ``grants_licence`` asks whether that is a given licence's. Nothing
here reads a database.
"""
# pylint: disable=missing-function-docstring

import time

import pytest
from timing import slack

from licenseid.grantsubject import (
    Grant,
    constant,
    grants,
    grants_licence,
    has_unowned_phrase,
    lazy_signal,
    onlys,
)

#: (text, [(version, family)]): the grants of the text, in order.
GRANTED = [
    # A licence's own words.
    ("GPL-2.0 or later", [("2.0", "gpl")]),
    ("GPLv2 or any later version", [("2", "gpl")]),
    ("GNU General Public License v2.0 or later", [("2.0", "gpl")]),
    ("gpl v2 or later", [("2", "gpl")]),
    ("the GPL (v2 or later)", [("2", "gpl")]),
    ("GPL-2.0 (or later)", [("2.0", "gpl")]),
    ("GPL-2.0 or-later", [("2.0", "gpl")]),
    ("GPL-2.0- or later", [("2.0", "gpl")]),
    ("GPL or any later version", [(None, "gpl")]),
    (
        "GNU General Public License, or (at your option) any later version",
        [(None, "gpl")],
    ),
    # The shorthand.
    ("GPLv2+", [("2", "gpl")]),
    ("LGPL v2.1+", [("2.1", "lgpl")]),
    # The GPL notice, wrapped or not.
    (
        "either version 2 of the License, or (at your option) any later version",
        [("2", None)],
    ),
    (
        "version 2.1 of the License, or\n * (at your option) any later version",
        [("2.1", None)],
    ),
    (
        (
            "either version\n        2 of the License, or (at your option) any "
            "later version"
        ),
        [("2", None)],
    ),
    ("# either version 2 of the License,\n# or any later version", [("2", None)]),
    ("of the License, or (at your option) any later version", [(None, None)]),
    (
        "either version of the License, or (at your option) any later version",
        [(None, None)],
    ),
    ("version 2 of the GPL, or (at your option) any later version", [("2", "gpl")]),
    (
        (
            "version 2 of the GNU General Public License, or (at your option) any "
            "later version"
        ),
        [("2", "gpl")],
    ),
    (
        (
            "under the terms of version 2 of the GNU General Public License as "
            "published by the Free Software Foundation, or (at your option) any "
            "later version"
        ),
        [("2", "gpl")],
    ),
    # The Free Software Foundation before the version; a notice JSON-escaped.
    (
        (
            "GNU General Public License as published by the Free Software "
            "Foundation, version 2 or later"
        ),
        [("2", "gpl")],
    ),
    (
        (
            "published by the Free Software Foundation; version 3 of the License, "
            "or (at your option) any later version"
        ),
        [("3", None)],
    ),
    (
        "version 2 of the License, or\\n(at your option) any later version",
        [("2", None)],
    ),
    ("of the\\nLicense, or any later version", [(None, None)]),
    ("GPL-2.0 WITH Classpath-exception-2.0 or later", [("2.0", "gpl")]),
    ("GPL-2.0 split\\tand more or later", []),
    ("GNU General Public License v2 0 or later", [("2.0", "gpl")]),  # v2.0, spaced
    ("GFDL v1 1 or later", [("1.1", "gfdl")]),
    # The family of a GNU name.
    ("GNU Lesser GPL v2.1 or later", [("2.1", "lgpl")]),
    ("GNU Library GPL v2 or later", [("2", "lgpl")]),
    ("GNU Lesser General Public License v2.1 or later", [("2.1", "lgpl")]),
    ("GNU Library General Public License v2 or later", [("2", "lgpl")]),
    ("GNU Affero GPL v3 or later", [("3", "agpl")]),
    ("GNU Affero General Public License v3.0 or later", [("3.0", "agpl")]),
    ("GNU FDL 1.3 or later", [("1.3", "gfdl")]),
    (
        "GNU Free Documentation License version 1.3 or any later version",
        [("1.3", "gfdl")],
    ),
    # Another version's grant stays another's: the version is read as written.
    ("GPL-2.0, version 3 or later", [("3", None)]),
    # A licence other than the GNU families is still a licence's grant.
    ("Apache License 2.0 or later", [("2.0", "apache")]),
    ("Mozilla Public License 2.0 or later", [("2.0", "mozilla")]),
]

#: A tool's version: a grant, but of a word that is no licence's.
TOOLS = [
    ("Requires Python 3.8 or later.", [("3.8", "python")]),
    ("Python 3.10 or newer", [("3.10", "python")]),
    ("Works with Python 3.8 or any later version.", [("3.8", "python")]),
    ("Python version 3 or later", [("3", "python")]),
    ("CMake version 3.0 or newer", [("3.0", "cmake")]),
    ("Docker version 19.03.0 or newer", [("19.03.0", "docker")]),
    ("clang-3.3 or newer", [("3.3", "clang")]),
    ("rustc 1.88.0 or newer", [("1.88.0", "rustc")]),
    ("Requires Java 1 or later", [("1", "java")]),
    ("Node.js 12 or newer", [("12", "js")]),
    ("JDK 8 or later", [("8", "jdk")]),
    ("Ubuntu 20.04 or later", [("20.04", "ubuntu")]),
]

#: No grant at all: no subject, or not a phrase.
NONE = [
    "g++-4.7.2 or newer",
    "GPL v\u00b2 or any later version",  # a superscript is no digit
    "Needs Firefox 1+ to run it",
    "sooner or later",
    "not any later version",
    "2 or later",  # a number alone
    "in 3 or later",
    "of 3 or later",
    "GPL-2.0-or-later",  # an ID is no phrase
    "Python 3.8. Or any later version of it.",  # a full stop ends the sentence
    "",
]


@pytest.mark.parametrize(("text", "expected"), [*GRANTED, *TOOLS])
def test_the_subject_of_a_grant(
    text: str, expected: list[tuple[str | None, str | None]]
) -> None:
    assert [(g.version, g.family) for g in grants(text)] == expected


@pytest.mark.parametrize("text", NONE)
def test_a_phrase_with_no_subject_is_no_grant(text: str) -> None:
    assert not grants(text)


def test_a_grant_says_where_it_stands() -> None:
    text = "Copyright Jane. Licensed under GPL-2.0 or later; see COPYING."
    found = grants(text)
    assert len(found) == 1
    grant = found[0]
    assert text[grant.start : grant.end] == "2.0 or later"
    assert grants_licence(grant, "GPL-2.0-or-later")


@pytest.mark.parametrize(
    ("grant", "license_id", "expected"),
    [
        (("2.1", "lgpl"), "GPL-2.0-only", False),
        (("2.1", "lgpl"), "LGPL-2.1-only", True),
        (("2", None), "GPL-2.0-only", True),  # "2" is "2.0"
        (("2.0", None), "LGPL-2.1-only", False),
        (("2", None), "LGPL-2.1-only", True),  # "version 2": the 2.x series
        (("2", "lgpl"), "LGPL-2.1-or-later", True),
        (("2.1", None), "GPL-2.0-only", False),
        (("3", None), "GPL-2.0-only", False),
        ((None, None), "GPL-2.0-only", True),
        (("1.2", None), "GFDL-1.2-only", True),
        (("1.2", "gfdl"), "GFDL-1.2-invariants-or-later", True),
        (("2", "gpl"), "GPL-2.0-or-later WITH Classpath-exception-2.0", True),
        (("2", "gpl"), "gpl-2.0-only", True),  # any case
        (("3", "python"), "GPL-3.0-only", False),  # a tool's version
        (("8", "jdk"), "LGPL-3.0-only", False),
        ((None, "gpl"), "LGPL-2.1-only", False),
        ((None, "gpl"), "GPL-3.0-or-later", True),
        (("2", None), "LicenseRef-x", False),  # no version to compare
        ((None, None), "LicenseRef-x", True),
    ],
)
def test_a_grant_is_for_one_licence(
    grant: tuple[str | None, str | None], license_id: str, expected: bool
) -> None:
    assert grants_licence(Grant(0, 0, *grant), license_id) is expected


def test_every_phrase_of_the_reader_after_an_id_is_a_grant_of_it() -> None:
    """Whatever ``classify.OR_LATER_PHRASE`` reads after "GPL-2.0" grants GPL-2.0
    (``tests/ordering_helpers.PHRASES`` is the table of phrasings)."""
    from ordering_helpers import PHRASES  # pylint: disable=import-outside-toplevel

    wrong = [
        phrase
        for phrase, (reads, _) in PHRASES.items()
        if reads
        and not any(
            grants_licence(g, "GPL-2.0-only") for g in grants(f"GPL-2.0 {phrase}")
        )
    ]
    assert not wrong
    assert not [
        p for p, (reads, _) in PHRASES.items() if not reads and grants(f"GPL-2.0 {p}")
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("GPL-2.0 only", [("2.0", "gpl")]),
        ("version 2 only", [("2", None)]),
        ("v2.0 only", [("2.0", None)]),
        ("(GPLv2 only)", [("2", "gpl")]),
        ("Supports Python 3 only.", [("3", "python")]),
        ("2 only", []),  # a number alone
        ("Version 2 only if you agree", [("2", None)]),  # the word is "only"
    ],
)
def test_the_subject_of_an_only(
    text: str, expected: list[tuple[str | None, str | None]]
) -> None:
    assert [(g.version, g.family) for g in onlys(text)] == expected


def test_a_signal_asks_the_text_once_and_only_when_asked() -> None:
    reads: list[str] = []

    def found() -> list[Grant]:
        reads.append("read")
        return grants("GPL-2.0 or later")

    signal = lazy_signal(found)
    assert not reads
    assert signal("GPL-2.0-or-later") is True
    assert signal("LGPL-2.1-or-later") is False
    assert reads == ["read"]


def test_a_constant_signal_is_the_same_for_every_licence() -> None:
    assert constant(True)("GPL-2.0-only") is True
    assert constant(False)("GPL-2.0-only") is False


@pytest.mark.parametrize(
    "text",
    [
        "GPL v\u00b2 or any later version",  # a superscript is no digit
        "GPL-" + "1" * 5_000 + "+",  # a number of any size
        "GPL-" + "1" * 5_000 + " or later",
        "GPL-1.0 only " + "9" * 5_000 + " only",
    ],
)
def test_a_number_of_any_size_or_kind_is_read_without_an_error(text: str) -> None:
    grants(text)
    onlys(text)
    signal = lazy_signal(lambda: grants(text))
    assert signal("GPL-2.0-only") is False


def test_a_signal_asks_each_kind_of_grant_once() -> None:
    """A hundred thousand "GPLv2+" are one kind: twenty licence questions
    cost what one does."""
    text = "GPLv2+ " * 100_000
    signal = lazy_signal(lambda: grants(text))
    start = time.monotonic()
    for i in range(20):
        signal(f"GPL-{i}.0-only")
    assert time.monotonic() - start < slack(1.5)
    assert signal("GPL-2.0-only") is True


def _took(text: str, bound: float) -> None:
    start = time.monotonic()
    grants(text)
    onlys(text)
    assert time.monotonic() - start < slack(bound)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Python 3.8 or later. " * 2_000, id="python"),
        pytest.param("GPL v2 or later " * 2_000, id="gpl"),
        pytest.param("of the License, or any later version " * 1_000, id="notice"),
        pytest.param("version 2 only " * 2_000, id="only"),
        pytest.param("1 " * 10_000, id="digits"),
        pytest.param("x" + " " * 20_000, id="spaces"),
        pytest.param("or" + " " * 20_000, id="or"),
        pytest.param("1" + "-" * 20_000, id="dashes"),
        pytest.param("or (" * 5_000, id="parens"),
        pytest.param("version " * 5_000 + "2 or later", id="versions"),
        pytest.param("License " * 5_000 + "or any later version", id="licences"),
        pytest.param("1." * 10_000 + " or later", id="dots"),
        pytest.param("Free Software Foundation, " * 2_000 + "or any later", id="fsf"),
    ],
)
def test_the_subject_reader_does_not_backtrack(text: str) -> None:
    _took(text, 1.0)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Python 3.8 or later. " * 20_000, id="python"),
        pytest.param("GPL v2 or later " * 20_000, id="gpl"),
        pytest.param("version 2 only " * 20_000, id="only"),
        pytest.param("version " * 50_000 + "2 or later", id="versions"),
        pytest.param("1." * 100_000 + " or later", id="dots"),
        pytest.param("or" + " " * 200_000, id="or"),
    ],
)
def test_the_subject_reader_is_linear_at_scale(text: str) -> None:
    _took(text, 3.0)


def test_unusual_characters_cannot_break_it() -> None:
    for text in ("٣ or later", "2\u200b or later", "GPL\ud800 2 or later"[:0], "\x00"):
        assert isinstance(grants(text), list)


@pytest.mark.parametrize(
    ("text", "unowned"),
    [
        # A later-version phrase no subject owns: the licence's own grant may be
        # one the subject rule cannot read.
        ("licensed under the GPL License version 3.0 or any version later.", True),
        ("any later version", True),
        ("or any later version of the GPL", True),
        ("or newer version", True),
        ("Needs Python 3.8 or later. Plugins may use any later version.", True),
        # Owned: a licence's or a tool's own grant.
        ("Requires Python 3.8 or any later version.", False),
        ("GPL or any later version", False),
        ("version 2 of the License, or (at your option) any later version", False),
        ("GPL-2.0 or later", False),
        # Not a phrase.
        ("sooner or later", False),
        ("not any later version", False),
        ("no any version later", False),
        ("", False),
    ],
)
def test_a_phrase_no_subject_owns(text: str, unowned: bool) -> None:
    assert has_unowned_phrase(text) is unowned
