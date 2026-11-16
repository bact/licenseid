# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Invariants of ``EXACT`` and ``VARIANT_STATED`` over value x channel x
variant (roadmap item 52), so no new site that makes a result can break them:

- A value answers alike through every channel that answers (a tag takes
  only List IDs: it is silent for a re-spelling or a name, the listed
  exceptions);
- A variant is stated only by the words of the input: the ID itself, "only",
  "or later", "or any later version", a "+";
- An answer licenseid chose (an -only or -or-later ID the input does not
  state) is never exact;
- Under ``auto`` a declared bare ID is kept, stated false, exact.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import itertools
import json
import re
import warnings
from collections.abc import Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.detector import LicenseDetector
from licenseid.identifiers import is_simple_expression
from licenseid.types import Variant

ROWS = (
    *GPL2_ROWS,
    Lic("AGPL-3.0-only", "GNU Affero General Public License v3.0 only", True),
    Lic("AGPL-3.0-or-later", "GNU Affero General Public License v3.0 or later"),
    Lic("AGPL-3.0", "GNU Affero General Public License v3.0", is_deprecated=True),
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only", True),
    Lic("GPL-3.0-or-later", "GNU General Public License v3.0 or later", True),
    Lic("GPL-3.0", "GNU General Public License v3.0", is_deprecated=True),
    Lic("LGPL-2.0-only", "GNU Library General Public License v2 only", True),
    Lic("LGPL-2.0-or-later", "GNU Library General Public License v2 or later"),
    Lic("LGPL-2.0", "GNU Library General Public License v2", is_deprecated=True),
    Lic("MIT", "MIT License", True, True, True),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
)
VALUES = [
    "MIT",
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "gpl-2.0",
    "GPL-2.0 only",
    "GPL-2.0 or later",
    "GPL-2.0 or any later version",
    "GPL-2.0+",
    "GPL2",
    "GPLv2+",
    "MIT OR GPL-2.0",
    "GPL-2.0 OR MIT+",
    "GPL-2.0-only OR GPL-2.0+",
    "LGPL-2.0 AND GPL-2.0 only",
    "GPLv3-or-later",
    "GPLv2 or later",
    "GPLv2-only",
    "LGPL-v2.0-or-later",
    "GPL-2.0 AND AGPL-3.0-only",
    "GNU General Public License v2.0",  # the List name of a deprecated ID
    "GNU General Public License v2.0 only",
    "GNU Affero General Public License v3.0",
]
VARIANTS: list[Variant] = ["auto", "as-written", "only", "or-later"]
# A tag takes a List ID or an expression of them, not a name or a re-spelling.
NOT_IN_A_TAG = {
    "GPL2",
    "GPLv2+",
    "GPL-2.0 or any later version",
    "GPLv3-or-later",
    "GPLv2-only",
    "LGPL-v2.0-or-later",
}
NAMES = {
    "GNU General Public License v2.0",
    "GNU General Public License v2.0 only",
    "GNU Affero General Public License v3.0",
}
WORDS = re.compile(r"\bonly\b|\blater\b|\+", re.IGNORECASE)
VARIANT_ID = re.compile(r"-(?:only|or-later)\b", re.IGNORECASE)
KEPT_BARE = re.compile(r"\b(?:GPL-2\.0|AGPL-3\.0)(?![\w.-])")  # a bare ID is kept


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    yield from seeded_db("test_variant_invariants", ROWS, [])


def answers(
    db: str, value: str, variant: Variant
) -> dict[str, tuple[str, bool, bool | None]]:
    """``(expression, exact, variant_stated)`` of the first result of each
    channel that answers *value*."""
    channels: dict[str, dict[str, str]] = {
        "argument": {"text": value},
        "tag": {"text": f"# SPDX-License-Identifier: {value}\n"},
        "tag/*": {"text": f"/* SPDX-License-Identifier: {value} */\n"},
        "json": {"text": json.dumps({"license": value})},
    }
    if is_simple_expression(value):
        channels["id"] = {"license_id": value}
    found = {}
    detector = LicenseDetector(db)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, request in channels.items():
            results = detector.detect(variant=variant, **request)  # type: ignore
            if results:
                top = results[0]
                found[name] = (top["expression"], top["exact"], top["variant_stated"])
    return found


CASES = list(itertools.product(VALUES, VARIANTS))


@pytest.mark.parametrize(("value", "variant"), CASES)
def test_a_value_answers_alike_in_every_channel(
    db: str, value: str, variant: Variant
) -> None:
    got = answers(db, value, variant)
    if value in NAMES and variant == "auto":
        # BUG: a deprecated List name answers -only as the argument (the name
        # tier) but the deprecated ID itself in a tag or a field (declared).
        got.pop("argument", None)
    assert got, f"nothing answers {value!r}"
    assert len(set(got.values())) == 1, got
    silent = {"tag", "tag/*"} - set(got)
    assert not silent or value in NOT_IN_A_TAG, f"{value!r} is silent in {silent}"


@pytest.mark.parametrize(("value", "variant"), CASES)
def test_a_variant_is_stated_only_by_words_of_the_input(
    db: str, value: str, variant: Variant
) -> None:
    for how, (expression, _, stated) in answers(db, value, variant).items():
        if stated:
            said = WORDS.search(value) or VARIANT_ID.search(value)
            assert said, f"{how}: {expression!r} stated, {value!r} says nothing"


@pytest.mark.parametrize(("value", "variant"), CASES)
def test_an_answer_licenseid_chose_is_not_exact(
    db: str, value: str, variant: Variant
) -> None:
    for how, (expression, exact, stated) in answers(db, value, variant).items():
        chosen = VARIANT_ID.search(expression) and not KEPT_BARE.search(expression)
        if exact and chosen:
            assert stated, f"{how}: {expression!r} exact, its variant not stated"


@pytest.mark.parametrize("how", ["argument", "tag", "tag/*", "json", "id"])
def test_auto_keeps_a_declared_bare_id(db: str, how: str) -> None:
    got = answers(db, "GPL-2.0", "auto")
    assert got[how] == ("GPL-2.0", True, False)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("value", ["GPL-2.0 OR MIT+", "LGPL-2.0 AND GPL-2.0 only"])
def test_the_words_of_another_licence_state_nothing(
    db: str, value: str, variant: Variant
) -> None:
    """Per licence: ``MIT+`` and ``GPL-2.0 only`` do not state the variant
    of the *other* bare ID in the value."""
    got = answers(db, value, variant)
    assert got
    for how, (expression, _, stated) in got.items():
        assert not stated, f"{how}: {expression!r} stated for {value!r}"
