# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A lone surrogate in a declared value (review item G1, task T4b).

A lone surrogate (Unicode category Cs: a command-line argument of invalid
UTF-8, or a string from an API) cannot be encoded for SQLite. The resolver
refuses it among its early refusals; the reason ``lone surrogate`` comes with
``Resolution.reason`` in T6.
"""

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

LONE = "\udcff"
WITH = "MIT WITH Classpath-exception-2.0"

#: Today's answers (characterisation): ``(expression, category)``, or
#: ``None`` when the call raises ``UnicodeEncodeError``.
TODAY: dict[str, tuple[str | None, str] | None] = {
    WITH + LONE: None,
    "MIT WITH " + LONE + "Classpath-exception-2.0": None,
    "MIT" + LONE: ("MIT", "separator"),
    LONE + "MIT": ("MIT", "separator"),
    "MIT" + LONE + LONE: ("MIT", "separator"),
    "MIT\ud800": ("MIT", "separator"),
    "MIT" + LONE + " WITH Classpath-exception-2.0": (WITH, "separator"),
    "GPL-2.0" + LONE + "+": ("GPL-2.0-or-later", "separator"),
    "Apache 2.0" + LONE: ("Apache-2.0", "separator"),
    "Apache2" + LONE: ("Apache-2.0", "version_spelling"),
    "(MIT" + LONE + ")": ("MIT", "separator"),
    "MIT OR " + LONE: (None, "expression"),
    "MI" + LONE + "T": (None, "unresolved"),
    LONE: (None, "unresolved"),
    "LicenseRef-" + LONE: (None, "unresolved"),
    "GPL-2.0+" + LONE: (None, "unresolved"),
    # a pair written as two escapes stays two code points in Python
    "\ud83d\ude00": (None, "unresolved"),
    "MIT\ud83d\ude00": ("MIT", "separator"),
}

#: Not surrogates: a valid astral character and a pair that Python keeps as
#: one character. They are no refusal of this rule.
VALID = [
    "\U0001f600",
    "MIT \U0001f600",
    "MIT\U00010000",
    "😀".encode("utf-16", "surrogatepass").decode("utf-16"),
]


def _ids(values: list[str]) -> list[str]:
    return [ascii(v)[:36] for v in values]


def _answer(db: LicenseDatabase, value: str) -> tuple[str | None, str] | None:
    try:
        result = resolve(value, db)
    except UnicodeEncodeError:
        return None
    return result["expression"], result["category"]


@pytest.mark.parametrize("value", list(TODAY), ids=_ids(list(TODAY)))
def test_today_a_lone_surrogate(corpus_db: LicenseDatabase, value: str) -> None:
    """Characterisation: the answer before G1 is fixed."""
    assert _answer(corpus_db, value) == TODAY[value]


@pytest.mark.parametrize("value", VALID, ids=_ids(VALID))
def test_a_valid_astral_character_is_no_surrogate(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Not refused for being a surrogate: encodable, and answered as before."""
    assert resolve(value, corpus_db)["category"] in {"separator", "unresolved"}
