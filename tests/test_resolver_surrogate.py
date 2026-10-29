# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A lone surrogate in a declared value (review item G1, task T4b).

A lone surrogate (Unicode category Cs: a command-line argument of invalid
UTF-8, or a string from an API) cannot be encoded for SQLite. The resolver
refuses it among its early refusals, with the reason ``lone surrogate``
(``Resolution.reason``, T6).
"""

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

LONE = "\udcff"
WITH = "MIT WITH Classpath-exception-2.0"

#: Every value holds a lone surrogate somewhere: alone, at the start, in the
#: middle, at the end, in a name, after ``+``, in a ``LicenseRef-``, doubled,
#: and a pair written as two escapes (Python keeps it as two code points).
#: Before the fix ``(expression, category)`` of these was, in order, a raise
#: for the first two, ``MIT`` or its relatives as ``separator`` (and
#: ``MIT OR <surrogate>`` as ``expression``).
REFUSED = [
    WITH + LONE,
    "MIT WITH " + LONE + "Classpath-exception-2.0",
    "MIT WITH Classpath-exception-2.0\ud800",
    "MIT" + LONE,
    LONE + "MIT",
    "MIT" + LONE + LONE,
    "MIT\ud800",
    "MIT" + LONE + " WITH Classpath-exception-2.0",
    "GPL-2.0" + LONE + "+",
    "GPL-2.0+" + LONE,
    "Apache 2.0" + LONE,
    "Apache2" + LONE,
    "(MIT" + LONE + ")",
    "[MIT" + LONE + "]",
    "MIT OR " + LONE,
    "MI" + LONE + "T",
    LONE,
    "LicenseRef-" + LONE,
    "LicenseRef-Acme" + LONE,
    "GNU General Public License v2.0" + LONE,
    "\ud83d\ude00",
    "MIT\ud83d\ude00",
    " MIT" + LONE + " ",
]

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


@pytest.mark.parametrize("value", REFUSED, ids=_ids(REFUSED))
def test_a_lone_surrogate_is_unresolved(corpus_db: LicenseDatabase, value: str) -> None:
    """No raise, no expression, no step and no candidate; the input is kept."""
    result = resolve(value, corpus_db)
    assert result["expression"] is None
    assert result["category"] == "unresolved"
    assert result["trust"] == "none"
    assert result["steps"] == []
    assert result["candidates"] == []
    assert result["input"] == value


@pytest.mark.parametrize("value", VALID, ids=_ids(VALID))
def test_a_valid_astral_character_is_no_surrogate(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Not refused for being a surrogate: it encodes. ``MIT`` plus an emoji
    would drop the emoji, which the drop guard (T6) refuses, with its own
    reason; the others name no licence."""
    result = resolve(value, corpus_db)
    assert (result["expression"], result["category"]) == (None, "unresolved")
    assert result["reason"] != "lone surrogate"
    if value == "MIT \U0001f600":
        assert result["reason"] == "character dropped: U+1F600"
