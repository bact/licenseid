# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` and a mark after a ``+``, an exception or a ``LicenseRef-``,
and a lone dash after a prose form (task T8b; decision P80). The readers of
those shapes returned before the drop guard, so a mark that says something
(``GPL-2.0+?``) was unresolved with no reason, and one end mark (``MIT+;``)
was not an ending as it is after an ID."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

EXCEPTION = "GPL-2.0-only WITH Classpath-exception-2.0"

#: One end mark is an ending: read without it, a ``separator`` step.
READ = {
    "MIT+;": ("MIT+", "separator"),
    "MIT+ ;": ("MIT+", "separator"),
    "MIT+:": ("MIT+", "separator"),
    "MIT+,": ("MIT+", "separator"),
    "GPL-2.0+.": ("GPL-2.0-or-later", "separator"),
    f"{EXCEPTION};": (EXCEPTION, "separator"),
    f"{EXCEPTION} .": (EXCEPTION, "separator"),
    "GPL-2.0 WITH Classpath-exception-2.0:": (
        "GPL-2.0 WITH Classpath-exception-2.0",
        "assumed_only",  # the bare split ID is the weakest step
    ),
    "LicenseRef-a;": ("LicenseRef-a", "separator"),
    "LicenseRef-a:": ("LicenseRef-a", "separator"),
}
#: A mark that says something, or two or more marks: refused with the marks.
REFUSED = {
    "MIT+;;": "U+003B",
    "MIT+.,": "U+002E U+002C",
    "MIT+...": "U+002E",
    "GPL-2.0+?": "U+003F",
    "GPL-2.0+ ?": "U+003F",
    "GPL-2.0+!": "U+0021",
    "GPL-2.0+ ? !": "U+003F U+0021",
    f"{EXCEPTION}?": "U+003F",
    f"{EXCEPTION} *": "U+002A",
    f"{EXCEPTION};;": "U+003B",
    "LicenseRef-a?": "U+003F",
    "LicenseRef-a;;": "U+003B",
    "MIT License -": "U+002D",
    "MIT License --": "U+002D",
    "MIT License &": "U+0026",  # white space is kept only for dots and dashes
    "MIT License & ": "U+0026",
    "BSD 3-Clause License &": "U+0026",
    "Apache License, Version 2.0 &": "U+0026",
    "Apache License, Version 2.0 -": "U+002D",
    "MIT+ License -": "U+002D",
    "Apache-2.0 License+?": "U+003F",  # the prose form P1 reads, then the mark
}
#: Not of the shape, or its core names nothing: as before, no reason.
SILENT = [
    "Foo+;",
    "Foo+?",
    "Foo WITH Bar?",
    "MIT WITH Foo?",  # the exception is not listed
    "LicenseRef?",
    "MIT+)",
    "Apache-2.0++?",
    "LicenseRef-x+?",
    "+;",
    ";",
    "?",
]


@pytest.mark.parametrize("value", sorted(READ), ids=lambda v: v[:24])
def test_one_end_mark_after_the_core_is_an_ending(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == READ[value]
    assert got["reason"] is None
    assert got["steps"][0]["kind"] == "separator"
    assert got["steps"][0]["detail"] == "end mark"


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: v[:24])
def test_a_mark_that_says_something_is_refused_with_its_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["category"] == "unresolved"
    assert got["reason"] == f"character dropped: {REFUSED[value]}"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]
    assert got["operands"][0]["reason"] == got["reason"]


@pytest.mark.parametrize("value", SILENT, ids=lambda v: v[:24])
def test_a_value_whose_core_names_nothing_stays_as_it_was(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert not [s for s in got["steps"] if s["kind"] in ("drop", "separator")]


def test_the_refusal_names_the_licence_it_stopped(corpus_db: LicenseDatabase) -> None:
    step = resolve("GPL-2.0+?", corpus_db)["steps"][0]
    assert (step["from"], step["to"]) == ("GPL-2.0+?", "GPL-2.0-or-later")


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("MIT+", "MIT+"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
        (EXCEPTION, EXCEPTION),
        ("LicenseRef-a", "LicenseRef-a"),
        ("LicenseRef-a.", "LicenseRef-a."),  # a dot is an ID character
        ("MIT;", "MIT"),
        ("MIT License ;", "MIT"),
    ],
)
def test_the_neighbours_that_keep_their_answer(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == expression


def test_a_refused_operand_gives_its_reason_to_the_compound(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve("MIT OR GPL-2.0+?", corpus_db)
    assert got["expression"] is None
    assert got["reason"] == "character dropped: U+003F"
    assert [o["expression"] for o in got["operands"]] == ["MIT", None]


def test_an_ending_in_a_compound_operand_is_read(corpus_db: LicenseDatabase) -> None:
    assert resolve("GPL-2.0+; OR MIT", corpus_db)["expression"] == (
        "GPL-2.0-or-later OR MIT"
    )
