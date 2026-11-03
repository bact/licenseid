# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The helpers task ``resolverfix`` added, each on its own: white space as
Unicode has it, quote marks around nothing, the marks at the end of a value,
the case of a reference prefix, an ID cut inside a word, a stated qualifier
and the detail of a reason."""
# pylint: disable=missing-function-docstring

import re
import time

import pytest

from licenseid import classify
from licenseid.classify import grant_at, grant_spans
from licenseid.dropguard import marks_at_end
from licenseid.errors import one_line, reason_detail
from licenseid.exprtokens import (
    WHITE_SPACE,
    canonical_ref,
    cut_inside_word,
    is_white_space,
)
from licenseid.identifiers import leading_expression
from licenseid.looseid import grant_end
from licenseid.plusoperator import plus_after_qualifier, states_qualifier
from licenseid.quotes import encloses_nothing


def test_white_space_is_str_isspace_without_the_information_separators() -> None:
    every = {chr(c) for c in range(0x110000) if chr(c).isspace()}
    assert set(WHITE_SPACE) == every - set("\x1c\x1d\x1e\x1f")
    assert len(WHITE_SPACE) == len(set(WHITE_SPACE))


@pytest.mark.parametrize(
    ("char", "expected"),
    [(" ", True), ("\t", True), ("\x85", True), ("\u3000", True)]
    + [(chr(c), False) for c in range(0x1C, 0x20)]
    + [("x", False), ("\x00", False), ("\u200b", False)],
)
def test_is_white_space(char: str, expected: bool) -> None:
    assert is_white_space(char) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('""', True),
        ("''", True),
        ('" "', True),
        (' "" ', True),
        ('""""', True),
        ("'\"\"'", True),
        ("\u201c\u201d", True),
        ("\u00ab\u00bb", True),
        ('"', False),  # one mark pairs with nothing
        ("\"'", False),  # two kinds
        ("", False),  # no marks at all
        ("  ", False),
        ('"MIT"', False),
        ('"x"', False),
        ("\u2032\u2032", True),  # primes pair, as unquote reads them
        ('"\x1c"', False),  # a control character is no white space
    ],
)
def test_encloses_nothing(text: str, expected: bool) -> None:
    assert encloses_nothing(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(MIT)-", ("(MIT)", "-")),
        ("(MIT)--", ("(MIT)", "--")),
        ('"(MIT;)".', ('"(MIT)"', ";.")),
        ('"LicenseRef-a.;".', ('"LicenseRef-a."', ";.")),
        ("LicenseRef-a.-", None),  # the dot and the dash are the ID's
        ("(LicenseRef-a-)?", ("(LicenseRef-a-)", "?")),
        ("LicenseRef-a+-", ("LicenseRef-a+", "-")),
        ("MIT -", ("MIT ", "-")),
        ("[MIT] ;", ("[MIT] ", ";")),
        ("(MIT", None),
        ("MIT", None),
        ("(MIT)", None),
        ("", None),
        ("-", ("", "-")),
        ("(-)", ("()", "-")),
        ("MIT\u2013", ("MIT", "\u2013")),
    ],
)
def test_marks_at_end(text: str, expected: tuple[str, str] | None) -> None:
    assert marks_at_end(text) == expected


@pytest.mark.parametrize(
    "text", ["x" + "." * 2000, "LicenseRef-a" + ".-" * 1000, "(" * 1000 + ")-" * 1000]
)
def test_marks_at_end_is_fast(text: str) -> None:
    start = time.monotonic()
    marks_at_end(text)
    assert time.monotonic() - start < 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("licenseref-foo", "LicenseRef-foo"),
        ("LICENSEREF-Foo.Bar-1", "LicenseRef-Foo.Bar-1"),
        ("LicenseRef-foo", "LicenseRef-foo"),
        ("additionref-x", "AdditionRef-x"),
        ("documentref-D:licenseref-L", "DocumentRef-D:LicenseRef-L"),
        ("DocumentRef-d:LICENSEREF-l", "DocumentRef-d:LicenseRef-l"),
        ("documentref-licenseref:licenseref-x", "DocumentRef-licenseref:LicenseRef-x"),
        ("licenseref-licenseref-x", "LicenseRef-licenseref-x"),
    ],
)
def test_canonical_ref(text: str, expected: str) -> None:
    assert canonical_ref(text) == expected


@pytest.mark.parametrize(
    ("text", "end", "expected"),
    [
        ("LicenseRef-caf\u00e9", 14, True),
        ("MIT\u00e9", 3, True),
        ("MIT.\u00e9", 3, True),
        ("MIT_\u00e9", 3, True),
        ("MIT:\u00e9", 3, True),
        ("MIT-\u0661", 3, True),
        ("cafe\u0301", 4, True),  # a combining mark
        ("MIT", 3, False),
        ("MIT ", 3, False),
        ("MIT \u00e9", 3, False),
        ("MIT\u20ac", 3, False),
        ("MIT.", 3, False),
        ("MIT-.", 3, False),
        ("(MIT)\u00e9", 5, False),  # a bracket ends no word
        ("MIT+\u00e9", 4, False),
        ("", 0, False),
    ],
)
def test_cut_inside_word(text: str, end: int, expected: bool) -> None:
    assert cut_inside_word(text, end) is expected


@pytest.mark.parametrize(
    ("license_id", "expected"),
    [
        ("GPL-2.0-only", True),
        ("GPL-2.0-or-later", True),
        ("gpl-2.0-ONLY", True),
        ("GPL-2.0", False),
        ("GPL-2.0+", False),
        ("MIT", False),
        ("", False),
        ("only", False),
    ],
)
def test_states_qualifier(license_id: str, expected: bool) -> None:
    assert states_qualifier(license_id) is expected


@pytest.mark.parametrize(
    ("value", "expected"), [("GPL-2.0-only+", True), ("GPL-2.0+", False)]
)
def test_plus_after_qualifier_reads_the_same_qualifiers(
    value: str, expected: bool
) -> None:
    assert plus_after_qualifier(value) is expected


@pytest.mark.parametrize(
    ("value", "detail", "diagnostic"),
    [
        ("Foo;Bar", "Foo;Bar", "Foo,Bar"),
        ("a\n\tb ;  c", "a b ; c", "a b , c"),
        (";" * 70, ";" * 60 + "...", "," * 60 + "..."),
        ("", "", ""),
    ],
)
def test_reason_detail_keeps_the_semicolon(
    value: str, detail: str, diagnostic: str
) -> None:
    assert reason_detail(value) == detail
    assert one_line(value) == diagnostic


def test_a_grant_probe_reads_a_window_not_the_line() -> None:
    """One probe per "or" after a stated qualifier: copying the rest of the
    line for each would be quadratic on a minified line."""
    value = "GPL-2.0-only or " * 20000 + "MIT"
    start = time.monotonic()
    assert leading_expression(value) == value
    assert time.monotonic() - start < 5


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("GPL-2.0-only or later", ""),
        ("GPL-2.0-only or" + " " * 150 + "later", ""),
        ("GPL-2.0-only or" + " " * 195 + "later", ""),
        ("GPL-2.0-only or" + " " * 5000 + "later", ""),
        ("GPL-2.0-only OR MIT", "GPL-2.0-only OR MIT"),
        ("GPL-2.0 or later", "GPL-2.0"),
        ("LicenseRef-caf\u00e9", ""),
        ("LicenseRef-caf \u00e9", "LicenseRef-caf"),
    ],
)
def test_leading_expression(value: str, expected: str) -> None:
    assert leading_expression(value) == expected


#: What may follow an ID that states its qualifier: grants and not.
AFTER_QUALIFIER = [
    "or later",
    "OR LATER",
    "or  later",
    "or\tlater",
    "or-later",
    "or later version",
    "or any later version",
    "or (at your option) any later version",
    "or, at your option, any later version",
    "or newer",
    "or MIT",
    "OR Apache-2.0",
    "or laterx",
    "or sooner",
    "or",
    # Past the window: the white space after "or" is read whole, as
    # resolve() reads it (review item 8).
    "or" + " " * 195 + "later",
    "or" + " " * 400 + "later",
    "or" + "\n" * 300 + "later",
    "or" + " " * 400 + "MIT",
]


@pytest.mark.parametrize("tail", AFTER_QUALIFIER)
def test_the_tag_reads_a_grant_as_resolve_reads_it(tail: str) -> None:
    """``classify.grant_at`` and ``looseid.grant_end`` (the reader of
    ``resolve()``) find the same grant after "GPL-2.0-only ", or none."""
    text = f"GPL-2.0-only {tail}"
    operator = re.compile("or", re.IGNORECASE).search(text, 12)
    assert operator is not None
    ours = grant_at(text, operator, grant_spans(text), True)
    assert ours == grant_end(text, operator.start())


def test_a_probe_reads_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe after a stated qualifier copies a bounded window of the
    line, never the rest of it: one per "or" would make a long line
    quadratic. A match where the "or" stands copies nothing."""
    probed: list[int] = []
    phrase = classify.OR_LATER_PHRASE

    class Spy:  # pylint: disable=too-few-public-methods
        """Records the length of each copy the phrase is matched on."""

        @staticmethod
        def match(text: str, pos: int = 0) -> re.Match[str] | None:
            if not pos:
                probed.append(len(text))
            return phrase.match(text, pos)

    monkeypatch.setattr(classify, "OR_LATER_PHRASE", Spy)
    text = "GPL-2.0-only or " + "x " * 5000
    operator = re.compile("or").search(text)
    assert operator is not None
    assert grant_at(text, operator, ([], []), True) is None
    assert probed and max(probed) <= len("1 or ") + 200


def test_no_probe_without_a_stated_qualifier() -> None:
    text = "GPL-2.0 or later"
    operator = re.compile("or").search(text)
    assert operator is not None
    assert grant_at(text, operator, ([], []), False) is None
    assert grant_at(text, operator, ([], []), True) == len(text)
