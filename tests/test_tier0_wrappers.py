# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A short value ``resolve()`` refuses, and a quoted manifest field, on the
paths of ``detect()`` (tech-debt roadmap, item 48).

Tier 0 read the normalised text of such a value, so a wrapper and a "+" had
gone: ``「GPL-2.0+」`` was ``GPL-2.0-only``, ``「MIT++」`` was ``MIT``, and a
quoted INI ``GPL-2.0+`` lost its operator. A value ``resolve()`` reads is the
answer of ``detect()`` whatever brings it; one it refuses is matched by name
only. A database of the whole List (``corpus_db``)."""
# pylint: disable=missing-function-docstring

import time
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.resolvereason import ends_a_word_with_plus, refuses_text_match
from licenseid.types import Detection

Answer = tuple[str, str, bool] | None


def _top(found: list[Detection]) -> Answer:
    if not found:
        return None
    return (found[0]["expression"], found[0]["method"], found[0]["exact"])


def _whole(_: Path, value: str) -> str:
    return value


def _ini(_: Path, value: str) -> str:
    return f'[metadata]\nlicense = "{value}"\n'


def _ini_file(_: Path, value: str) -> str:
    return _ini(_, value)


MAKE: dict[str, Callable[[Path, str], str]] = {
    "whole": _whole,
    "ini": _ini,
    "ini file": _ini_file,
}


def _detect(detector: LicenseDetector, tmp: Path, route: str, value: str) -> Answer:
    text = MAKE[route](tmp, value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if route == "ini file":  # the CLI's file with no extension
            path = tmp / "manifest"
            path.write_text(text, encoding="utf-8")
            return _top(detector.detect(file_path=str(path)))
        return _top(detector.detect(text=text))


# (value, route, answer). The rows of item 48: each was a wrong answer.
OR_LATER: Answer = ("GPL-2.0-or-later", "id", True)
PINS: list[tuple[str, str, Answer]] = [
    ("「GPL-2.0+」", "whole", OR_LATER),  # was GPL-2.0-only: the "+" lost
    ("<GPL-2.0+>", "whole", None),
    ("「GPL-2.0-only+」", "whole", None),  # was GPL-2.0-only, exact
    ("「MIT++」", "whole", None),  # was MIT, exact
    ("<MIT>", "whole", None),  # resolve() refuses: character dropped
    ("*MIT*", "whole", None),
    ("MIT*", "whole", None),
    ("「MIT」", "whole", ("MIT", "id", True)),  # read as quotes
    ("『MIT OR ISC』", "whole", ("ISC OR MIT", "id", True)),
    ("BSD (3 clause)", "whole", ("BSD-3-Clause", "name", True)),
    ("GPL-2.0+", "ini", ("GPL-2.0-or-later", "field", True)),  # was -only
    ("GPL-2+", "ini", ("GPL-2.0-or-later", "field", True)),
    ("AGPLv3+", "ini", ("AGPL-3.0-or-later", "field", True)),
    ("GPL-2.0+", "ini file", ("GPL-2.0-or-later", "field", True)),
    ("MIT OR ISC", "ini", ("ISC OR MIT", "field", True)),  # was no answer
    ("Apache 2.0 License", "ini", ("Apache-2.0", "field", True)),
    ("MIT++", "ini", None),
    ("「MIT++」", "ini", None),
]


@pytest.mark.parametrize(("value", "route", "expected"), PINS)
def test_pins(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    value: str,
    route: str,
    expected: Answer,
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert _detect(detector, tmp_path, route, value) == expected


# A value that stays refused, or must not change.
ADVERSARIAL = [
    "「MIT」x",
    "「MIT",
    "MIT」",
    "「MIT」」",
    "<<MIT>>",
    "**MIT**",
    "<GPL-2.0>+",
    "「MIT」 +",
    "MIT (C++)",
    "C++ MIT",
    "(MIT",  # resolve() refuses an unbalanced bracket; no ID from the text
    "MIT)",
]


@pytest.mark.parametrize("value", ADVERSARIAL)
def test_a_wrapper_or_plus_resolve_refuses_answers_no_licence(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert _detect(detector, tmp_path, "whole", value) is None
    assert _detect(detector, tmp_path, "ini", value) is None


def test_a_name_resolve_refuses_is_still_matched_by_name(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    """Names are Tier 0's own: only the ID readers went."""
    detector = LicenseDetector(corpus_db.location)
    found = _detect(detector, tmp_path, "whole", "Licensed under the MIT License")
    assert found is not None
    assert found[0] == "MIT"


@pytest.mark.parametrize("route", sorted(MAKE))
@pytest.mark.parametrize("value", ["MIT", "GPL-2.0+", "Apache-2.0", "MIT OR ISC"])
def test_a_value_resolve_reads_gives_one_expression_by_every_route(
    corpus_db: LicenseDatabase, tmp_path: Path, route: str, value: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    found = _detect(detector, tmp_path, route, value)
    assert found is not None
    assert found[0] == resolve(value, corpus_db)["expression"]


# --- corner brackets: quote marks that pair by direction ----------------------

CORNERS = [
    ("「MIT」", "MIT"),
    ("『MIT』", "MIT"),
    ("「MIT」.", "MIT"),  # an end mark after the closing bracket
    ("「MIT」;", "MIT"),
    ("「 MIT 」", "MIT"),
    ("「「MIT」」", "MIT"),  # two layers
    ("“「MIT」”", "MIT"),  # mixed kinds, one layer each
    ("「MIT OR ISC」", "ISC OR MIT"),
    ("「MIT」 OR 「ISC」", "ISC OR MIT"),  # a pair round each operand
    ("『MIT』 or 『ISC』", "ISC OR MIT"),
    ("「Apache-2.0」 AND 「MIT」", "Apache-2.0 AND MIT"),
    ("「」", None),
    ("「MIT』", None),  # not a pair
    ("『MIT」", None),
    ("」MIT「", None),  # closer first
    ("「MIT", None),  # one end only
    ("MIT」", None),
    ("「MIT「」", None),  # a mark inside
    ("「MIT」」", None),
]


@pytest.mark.parametrize(("value", "expression"), CORNERS)
def test_corner_brackets_quote_a_value_as_a_pair(
    corpus_db: LicenseDatabase, value: str, expression: str | None
) -> None:
    assert resolve(value, corpus_db)["expression"] == expression


# --- the "+" that ends a word, and the one that does not ----------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("This C++ library is released under the MIT License; see LICENSE.", "MIT"),
        ("MIT License (C++ wrapper)", "MIT"),
        ("Copyright (c) Foo, MIT License, C++", "MIT"),
        ("MIT + file LICENSE", "MIT"),
    ],
)
def test_a_sentence_with_a_plus_that_ends_no_licence_word_is_matched_by_name(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, answer: str
) -> None:
    found = _detect(LicenseDetector(corpus_db.location), tmp_path, "whole", value)
    assert found is not None
    assert found[0] == answer


def test_a_sentence_of_ten_words_with_a_stray_plus_is_matched_by_name_still(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    """# BUG: ``MIT++`` is dropped and the name matched (inexact), as before
    item 48; under 10 words it has no answer. Roadmap item 50."""
    value = "This library is licensed under the MIT++ license, see the LICENSE file."
    found = _detect(LicenseDetector(corpus_db.location), tmp_path, "whole", value)
    assert found == ("MIT", "name", False)


@pytest.mark.parametrize(
    ("reason", "text", "refused"),
    [
        ("character dropped: U+002A", "MIT*", True),
        ("word dropped: x", "MIT x", True),
        ("control or format character: U+200B", "MIT\u200b", True),
        ("lone surrogate", "MIT\udc80", True),
        ("parse failed: Unexpected '('", "(MIT", True),
        ("plus after a space: MIT +", "MIT +", True),
        ("not found: MIT", "MIT++", True),
        ("not found: MIT", "MIT＋", True),  # the fullwidth plus
        ("not found: MIT", "MIT+++ and more", True),
        ("not found: MIT", "MIT + file LICENSE", False),
        ("not found: MIT", "GPL-2.0 (+)", True),  # a plus alone in marks
        ("not found: MIT", "GPL-2.0 (+) licensed", True),  # not the last word
        ("not found: MIT", "c+++ MIT", True),  # only ++ is a language
        ("not found: MIT", 'GPL-2.0 "+"', True),
        ("not found: MIT", "GPL-2.0 「+」", True),
        ("not found: MIT", "+GPL-2.0", True),  # a plus that starts a word
        ("not found: MIT", "MIT License (C/C++)", False),
        ("not found: MIT", "MIT License, for g++ users", False),
        ("not found: MIT", "MIT License (Objective-C++)", False),
        ("not found: MIT", "Notepad++ MIT", True),
        ("not found: MIT", "C++ MIT", False),
        ("not found: MIT", "(c++) MIT", False),
        ("not found: MIT", '"MIT +"', True),  # a plus apart, last
        ("not found: MIT", "MIT", False),
        (None, "MIT", False),
        ("not found: MIT", "MIT" + "+" * 20_000, True),
    ],
    ids=lambda v: ascii(v)[:30],
)
def test_what_refuses_a_text_match(
    reason: str | None, text: str, refused: bool
) -> None:
    assert refuses_text_match(reason, text) is refused


def test_a_sentence_of_ten_words_is_not_refused_for_a_plus() -> None:
    text = "This library is licensed under the MIT++ license, see the LICENSE file."
    assert not refuses_text_match("not found: x", text)
    assert refuses_text_match("character dropped: U+002A", text)


# --- what the field reader keeps ------------------------------------------------


@pytest.mark.parametrize("route", ["whole", "ini", "ini file"])
@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("GNU General Public License v3 (GPLv3)", ("GPL-3.0-only", "name", False)),
        ("OSL-3 0", ("OSL-3.0", "id", True)),  # the version key is still read
    ],
)
def test_a_value_read_by_name_or_version_key_answers_by_every_route(
    corpus_db: LicenseDatabase,
    tmp_path: Path,
    route: str,
    value: str,
    answer: tuple[str, str, bool],
) -> None:
    found = _detect(LicenseDetector(corpus_db.location), tmp_path, route, value)
    assert found is not None
    assert found[0] == answer[0]
    assert found[2] == answer[2]


@pytest.mark.parametrize(
    ("words", "refused"),
    [(8, True), (9, True), (10, False), (11, False)],
)
def test_a_plus_ending_a_word_refuses_under_ten_words_only(
    words: int, refused: bool
) -> None:
    text = " ".join(["MIT++"] + ["word"] * (words - 1))
    assert refuses_text_match("not found: x", text) is refused


@pytest.mark.parametrize(
    "make",
    [
        lambda n: "a" + "." * n + "," * n,
        lambda n: "MIT" + "(" * n + "+",
        lambda n: "+" * n,
    ],
    ids=["marks", "brackets", "pluses"],
)
def test_the_plus_check_is_linear_in_a_long_run_of_marks(
    make: Callable[[int], str],
) -> None:
    """The first version stripped with a run of marks as the strip set, which
    costs the square of its length (5 s at 320,000 marks)."""
    value = make(400_000)
    start = time.monotonic()
    ends_a_word_with_plus(value)
    assert time.monotonic() - start < 1.5
