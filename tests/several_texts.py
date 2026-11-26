# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Made-up files that hold several licence texts, built from the recipes of
``tests/fixtures/several-texts/cases.json`` (``tests/fixtures/README.md``,
section 20).

A part ``@ID`` is ``license_text`` of ``license-text-long/ID.json``; any
other part is literal text. Parts join with :data:`SEPARATOR`. The test of
the first-text rule (``test_several_texts.py``) and the golden part
``several`` (``harness_golden``) share :func:`several_text_cases`."""

import json
from pathlib import Path
from typing import NamedTuple

FIXTURES = Path(__file__).parent / "fixtures"
CASES = FIXTURES / "several-texts" / "cases.json"
LONG_TEXTS = FIXTURES / "license-text-long"
SEPARATOR = "\n\n----\n\n"


class Expected(NamedTuple):
    """What ``detect`` gives a case: its answer (None: none), the ``REASON``
    of the record of no answer (None on an answer) and ``TEXTS``."""

    answer: str | None
    reason: str | None
    texts: tuple[str, ...]


def _part(part: str) -> str:
    """The text of one part of a recipe."""
    if not part.startswith("@"):
        return part
    data = json.loads((LONG_TEXTS / f"{part[1:]}.json").read_text(encoding="utf-8"))
    text = data["license_text"]
    assert isinstance(text, str), part
    return text


def several_text_cases() -> list[tuple[str, str, Expected]]:
    """``(case, text, expected)`` of every recipe, in file order."""
    recipes = json.loads(CASES.read_text(encoding="utf-8"))
    return [
        (
            recipe["case"],
            SEPARATOR.join(_part(part) for part in recipe["parts"]),
            Expected(recipe["answer"], recipe["reason"], tuple(recipe["texts"])),
        )
        for recipe in recipes
    ]


def several_text(case: str) -> str:
    """The text of the recipe *case*."""
    return next(text for name, text, _ in several_text_cases() if name == case)
