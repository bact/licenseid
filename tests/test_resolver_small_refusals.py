# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Four small refusals of ``match()`` (0.8 list; decisions P120 to P123).
Characterisation first: today's answers, so that each fix shows as a flip of
the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, match
from licenseid.resolver import match_with
from licenseid.resolvertypes import Source

#: Item 1: a value that is no string.
NOT_TEXT: list[object] = [None, b"MIT", 1]

#: Answers that do not move: ``(expression, reason)``.
STAYS: dict[str, tuple[str | None, str | None]] = {
    "MIT -": (None, "character dropped: U+002D"),
    "MIT;": ("MIT", None),
    "MIT,": ("MIT", None),
    'MIT,"': ("MIT", None),
    'MIT."': ("MIT", None),
    "LicenseRef-a;": ("LicenseRef-a", None),
    "LicenseRef-a;;": (None, "character dropped: U+003B"),
    "LicenseRef-a?": (None, "character dropped: U+003F"),
    "MIT-": ("MIT", None),
    "MIT--": ("MIT", None),
    "MIT+": ("MIT+", None),
    '"MIT"': ("MIT", None),
    '"MIT"..': (None, "character dropped: U+0022 U+002E"),
    '"MIT".,': (None, "character dropped: U+0022 U+002E U+002C"),
    '"MIT;"': ("MIT", None),
}

#: MOVES (item 2): refused with no reason.
SILENT_DASH: dict[str, tuple[str | None, str | None]] = {
    "MIT+-": (None, None),
    "MIT+--": (None, None),
    "MIT License--": (None, None),
}

#: MOVES (item 3): refused with the reason of two marks.
REF_MARK: dict[str, tuple[str | None, str | None]] = {
    "LicenseRef-a.;": (None, "character dropped: U+002E U+003B"),
}

#: MOVES (item 4): quote marks, then one end mark.
QUOTED_END: dict[str, tuple[str | None, str | None]] = {
    '"MIT".': (None, "character dropped: U+0022"),
    '"MIT",': (None, "character dropped: U+0022"),
    '"MIT";': (None, "character dropped: U+0022 U+003B"),
}


@pytest.mark.parametrize("value", sorted(STAYS), ids=lambda v: v[:20])
def test_an_answer_that_does_not_move(corpus_db: LicenseDatabase, value: str) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == STAYS[value]


@pytest.mark.parametrize(
    "value",
    sorted({**SILENT_DASH, **REF_MARK, **QUOTED_END}),
    ids=lambda v: v[:20],
)
def test_an_answer_that_moves(corpus_db: LicenseDatabase, value: str) -> None:
    today = {**SILENT_DASH, **REF_MARK, **QUOTED_END}
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == today[value]


@pytest.mark.parametrize("value", NOT_TEXT, ids=lambda v: type(v).__name__)
def test_a_value_that_is_no_string_is_a_type_error(
    corpus_db: LicenseDatabase, value: object
) -> None:
    message = f"value must be str, not {type(value).__name__}"
    with pytest.raises(TypeError, match=message):
        match(value, corpus_db)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=message):
        match_with(corpus_db, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("source", ["auto", "database", "packaged"])
def test_the_type_is_judged_before_any_list_is_read(source: Source) -> None:
    """No database and no packaged list in this environment: reading the
    list would raise ``DatabaseNotReadyError``; the type comes first."""
    with pytest.raises(TypeError):
        match(None, source=source)  # type: ignore[arg-type]


def test_a_string_subclass_is_a_string(corpus_db: LicenseDatabase) -> None:
    class Text(str):
        """A caller's own string type."""

    assert match(Text("MIT"), corpus_db)["expression"] == "MIT"
