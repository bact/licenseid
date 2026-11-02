# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The review of task ``resolverfix``: what its first fix left (the
information separators before an end mark, a grant after a qualifier that
does not start at an operator, an ID cut before a script written without
spaces, case folding outside ASCII, operand and value reasons, one end mark
after a bracket or a name, quote marks around nothing before a mark, a
grant after a reference).

Characterisation first: each table pins today's answer; an entry marked
``# BUG:`` is what the fix moves."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from spdx_tag_helpers import Answers, answers, tag_db

from licenseid import LicenseDatabase, match
from licenseid.resolvertypes import Resolution

Answer = tuple[str | None, str, list[str], str | None]
NOTHING = Answers(None, None, None, False)


def answer(got: Resolution) -> Answer:
    steps = [s["kind"] + ("" if s["applied"] else "!") for s in got["steps"]]
    return got["expression"], got["category"], steps, got["reason"]


def named(expression: str, spdx: bool = True) -> Answers:
    return Answers(expression, spdx, expression, spdx)


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_resolverfix_review")


MATCHED: dict[str, Answer] = {
    # 1: an information separator before the end mark after quote marks
    '"MIT"\x1c.': ("MIT", "separator", ["separator", "unquote"], None),  # BUG
    '"MIT" \x1d ;': ("MIT", "separator", ["separator", "unquote"], None),  # BUG
    '"MIT"\x1f,': ("MIT", "separator", ["separator", "unquote"], None),  # BUG
    # 4: case folding outside ASCII
    "LicenseRef-\u017f": ("LicenseRef-\u017f", "exact", [], None),  # BUG
    "LicenseRef-\u0131": ("LicenseRef-\u0131", "exact", [], None),  # BUG
    "L\u0130CENSEREF-a": ("L\u0130CENSEREF-a", "exact", [], None),  # BUG
    "licen\u017feref-a": ("LicenseRef-a", "lexical", ["id_case"], None),  # BUG
    # 5: the value's reason and its operand's
    "LicenseRef-a+- AND MIT": (
        None,
        "unresolved",  # BUG: malformed
        [],
        "operand not resolved: LicenseRef-a+-",  # BUG
    ),
    "MIT++- AND MIT": (None, "unresolved", [], "operand not resolved: MIT++-"),  # BUG
    "LicenseRef-a+ AND MIT": (
        None,
        "malformed",
        [],
        "qualifier on a reference: LicenseRef-a+",
    ),
    # 6: one end mark after a bracket, a trove name or path, a name
    "(MIT).": (None, "unresolved", [], "not found: (MIT)."),  # BUG
    "[MIT].": (None, "unresolved", [], "not found: [MIT]."),  # BUG
    "(GPLv3).": (None, "unresolved", [], "not found: (GPLv3)."),  # BUG
    "Apache License 2.0.": (None, "unresolved", [], "not found: Apache License 2.0."),
    "MIT License (MIT).": (None, "unresolved", [], "not found: MIT License (MIT)."),
    "The Unlicense.": (None, "unresolved", [], "not found: The Unlicense."),  # BUG
    "(MIT);": (None, "unresolved", [], "not found: (MIT);"),  # BUG
    "License :: OSI Approved :: MIT License.": (
        None,
        "unresolved",
        [],
        "not found: License :: OSI Approved :: MIT License.",  # BUG
    ),
    "(MIT)..": (None, "unresolved", ["drop!"], "character dropped: U+002E"),
    # 9: a grant after a reference
    "LicenseRef-x-only or later": (
        None,
        "malformed",
        [],
        "qualifier stated twice: LicenseRef-x-only or later",  # BUG
    ),
    "LicenseRef-a or later": (
        None,
        "unresolved",
        [],
        "qualifier on a reference: LicenseRef-a or later",
    ),
    # 11: quote marks around nothing, then a mark
    '"".': (None, "unresolved", [], 'not found: "".'),  # BUG: empty
    '"";': (None, "unresolved", [], 'not found: "";'),  # BUG: empty
    '""+': (None, "unresolved", [], 'not found: ""+'),  # BUG: empty
}


@pytest.mark.parametrize("value", list(MATCHED), ids=ascii)
def test_match(corpus_db: LicenseDatabase, value: str) -> None:
    assert answer(match(value, corpus_db)) == MATCHED[value]


TAGS: dict[str, Answers] = {
    # 2: a grant after a stated qualifier, not at an operator
    "GPL-2.0-only, or any later version": named("GPL-2.0-only"),  # BUG
    "GPL-2.0-only (or later)": named("GPL-2.0-only"),  # BUG
    "GPL-2.0-only or-later": named("GPL-2.0-only"),  # BUG
    "GPL-2.0-only. Or any later version": named("GPL-2.0-only"),  # BUG
    "GPL-2.0-only; or any later version": named("GPL-2.0-only"),  # BUG
    "GPL-2.0-or-later, or any later version": named("GPL-2.0-or-later"),  # BUG
    "GPL-2.0-only, see COPYING for any later version": named("GPL-2.0-only"),  # BUG
    "GPL-2.0, see COPYING for any later version": named("GPL-2.0-or-later"),
    # 3: a script written without spaces after the ID
    "MIT\u8bb8\u53ef\u8bc1": NOTHING,  # BUG: MIT
    "Apache-2.0\u30e9\u30a4\u30bb\u30f3\u30b9": NOTHING,  # BUG: Apache-2.0
    "GPL-2.0-or-later\u3067\u3059": NOTHING,  # BUG: GPL-2.0-or-later
    "MIT\ub77c\uc774\uc120\uc2a4": NOTHING,  # BUG: MIT
    "MIT\u00e9": NOTHING,
    # 8: a grant past the window of the probe
    "GPL-2.0-only or" + " " * 195 + "later": Answers(
        "GPL-2.0-only OR later",
        False,
        "GPL-2.0-only OR later",
        False,  # BUG
    ),
    # 9: a grant after a reference
    "LicenseRef-a or later": Answers(
        "LicenseRef-a OR later",
        False,
        "LicenseRef-a OR later",
        False,  # BUG
    ),
    "LicenseRef-a, or any later version": named("LicenseRef-a", False),  # BUG
    "LicenseRef-x-only or later": NOTHING,
    # 13: a "+" after a qualifier, then a grant
    "GPL-2.0-only+ or later": NOTHING,
}


@pytest.mark.parametrize("tag", list(TAGS), ids=lambda t: ascii(t)[:40])
def test_tag(db: str, tag: str, tmp_path: Path) -> None:
    assert answers(db, tag, tmp_path) == TAGS[tag]
