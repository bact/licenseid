# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How ``TEXTS`` names the texts the search found (``textnames.named_texts``):
the answer's group by the answer's ID, any other group as ``detect()`` names
an unstated text of it under ``--variant``, one ID for each, sorted."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.textnames import named_texts
from licenseid.types import Variant

GPL3 = ("GPL-3.0-only", "GPL-3.0-or-later")
GFDL = (
    "GFDL-1.1-invariants-only",
    "GFDL-1.1-invariants-or-later",
    "GFDL-1.1-no-invariants-only",
    "GFDL-1.1-no-invariants-or-later",
    "GFDL-1.1-only",
    "GFDL-1.1-or-later",
)
MPL = ("MPL-2.0", "MPL-2.0-no-copyleft-exception")
OFL = ("OFL-1.1", "OFL-1.1-RFN", "OFL-1.1-no-RFN")
GROUPS = {
    **dict.fromkeys(GPL3, GPL3),
    **dict.fromkeys(GFDL, GFDL),
    **dict.fromkeys(MPL, MPL),
    **dict.fromkeys(OFL, OFL),
}


def _names(rows: list[str], answer: str, variant: Variant) -> list[str]:
    return named_texts(rows, answer, variant, GROUPS)


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("auto", "GPL-3.0-only"),
        ("only", "GPL-3.0-only"),
        ("or-later", "GPL-3.0-or-later"),
        ("as-written", "GPL-3.0-only"),
    ],
)
def test_another_family_is_named_as_the_variant_names_an_unstated_text(
    variant: Variant, expected: str
) -> None:
    assert _names(["GPL-3.0-only"], "A-1.0", variant) == [expected]


@pytest.mark.parametrize("variant", ["auto", "as-written", "only", "or-later"])
@pytest.mark.parametrize(
    ("answer", "shown"),
    [
        ("GPL-3.0-only", "GPL-3.0-only"),
        ("GPL-3.0-or-later", "GPL-3.0-or-later"),
        ("GPL-3.0", "GPL-3.0"),  # the bare ID as-written answers
        ("GPL-3.0+", "GPL-3.0+"),
        ("GPL-3.0-only WITH Classpath-exception-2.0", "GPL-3.0-only"),
    ],
)
def test_the_group_of_the_answer_is_the_answers_id(
    variant: Variant, answer: str, shown: str
) -> None:
    assert _names(["GPL-3.0-only"], answer, variant) == [shown]


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("auto", "GFDL-1.1-only"),
        ("or-later", "GFDL-1.1-or-later"),
        ("as-written", "GFDL-1.1-only"),
    ],
)
def test_a_large_group_shows_its_plain_form(variant: Variant, expected: str) -> None:
    assert _names(["GFDL-1.1-invariants-only"], "MIT", variant) == [expected]


@pytest.mark.parametrize("variant", ["auto", "as-written", "only", "or-later"])
@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("MPL-2.0-no-copyleft-exception", "MPL-2.0"),
        ("OFL-1.1-RFN", "OFL-1.1"),
        ("MIT", "MIT"),  # alone: no group
    ],
)
def test_a_group_with_no_variant_shows_its_shortest_id(
    variant: Variant, row: str, expected: str
) -> None:
    assert _names([row], "A-1.0", variant) == [expected]


def test_the_ids_keep_the_order_of_the_rows_and_are_named_once() -> None:
    """The rows come in the order the input holds them: TEXTS keeps it."""
    rows = ["MPL-2.0", "GPL-3.0-only", "GPL-3.0-or-later", "Apache-2.0", "MPL-2.0"]
    assert _names(rows, "Zlib", "auto") == ["MPL-2.0", "GPL-3.0-only", "Apache-2.0"]


def test_the_answers_group_and_another_family_are_named_apart() -> None:
    rows = ["GPL-3.0-only", "GFDL-1.1-only"]
    assert _names(rows, "GPL-3.0-or-later", "auto") == [
        "GPL-3.0-or-later",
        "GFDL-1.1-only",
    ]
    assert _names(rows, "GPL-3.0-or-later", "as-written") == [
        "GPL-3.0-or-later",
        "GFDL-1.1-only",
    ]


def test_no_row_is_no_ids() -> None:
    assert not _names([], "MIT", "auto")
