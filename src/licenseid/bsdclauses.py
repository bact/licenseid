# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Which BSD-N-Clause a text is, by its numbered conditions.

Standard library only. `licenseid.markers.MarkerDetector` turns the answer
into a structural marker candidate.
"""

import re
from typing import Final

# Each word with an "i", "s" or "k" ignores case in ASCII only ("(?a:"):
# Python's IGNORECASE alone folds "\u0130", "\u0131", "\u017f" and the
# Kelvin sign into them. White space stays Unicode's.

# A numbered condition of a BSD licence: "2. Redistributions in binary
# form...", "3. Neither the name...", "3. All advertising materials...".
# "Redistribution" counts only before "of" or "in": the Apache-2.0 section
# "4. Redistribution. You may reproduce..." is no BSD condition.
# The indent is white space other than a line break: `\s*` after `^` reaches
# across line breaks, so a run of blank lines was scanned once per line.
_RE_CONDITION: Final = re.compile(
    r"^[^\S\r\n]*(\d+)\.\s+(?:(?a:Redistributions?)\s+(?a:of|in)\b|"
    r"(?a:Neither)\b|All\s+(?a:advertising)|The\s+(?:name|author))",
    re.MULTILINE | re.IGNORECASE,
)

# BSD-1-Clause's one condition: the first condition of BSD-2, 3 and 4 too.
_RE_SOURCE_CONDITION: Final = re.compile(
    r"^[^\S\r\n]*1\.\s+(?a:Redistributions?)\s+of\s+(?a:source)\s+code\s+"
    r"(?a:must)\s+(?a:retain)\b",
    re.MULTILINE | re.IGNORECASE,
)

# The BSD disclaimer, which in BSD-1-Clause follows its one condition.
_RE_DISCLAIMER: Final = re.compile(
    r"\b(?a:THIS)\s+(?a:SOFTWARE)\s+(?a:IS)\s+(?a:PROVIDED)\b", re.IGNORECASE
)

# The words of the conditions BSD-1-Clause lacks (the binary-form,
# advertising and endorsement conditions of BSD-2, 3 and 4), numbered or not.
_RE_LATER_CONDITION: Final = re.compile(
    r"\b(?a:Redistributions?)\s+(?a:in)\s+(?a:binary)\s+form\b|"
    r"\b(?a:advertising)\s+(?a:materials)\b|\b(?a:endorse)\s+or\s+promote\b",
    re.IGNORECASE,
)

_BY_COUNT: Final = {
    2: "BSD-2-Clause",
    3: "BSD-3-Clause",
    4: "BSD-4-Clause",
}


def _is_one_clause(text: str) -> bool:
    """Whether a text whose only numbered condition is 1 is BSD-1-Clause.

    A BSD-2, 3 or 4 text cut short after its condition 1 holds the same
    condition, so the count alone does not tell them apart. BSD-1-Clause is
    the whole licence: the disclaimer follows its condition, and no word of
    a later condition appears anywhere.
    """
    source = _RE_SOURCE_CONDITION.search(text)
    return (
        source is not None
        and _RE_DISCLAIMER.search(text, source.end()) is not None
        and _RE_LATER_CONDITION.search(text) is None
    )


def bsd_clause_id(text: str) -> str | None:
    """The BSD-N-Clause ID the numbered conditions of a text point to.

    The conditions found must be numbered 1 to N with no gap (a text may
    repeat them, as two copies of a licence do). The highest number then
    gives N (2, 3 or 4). Condition 1 alone is BSD-1-Clause only when
    `_is_one_clause` holds; any other count is no answer. A gap means the
    lines are not the conditions of a BSD text. `_RE_CONDITION` skips the
    Apache-2.0 section "4. Redistribution." by its words; the gap rule
    covers a numbered line of another text that it reads as a condition.
    """
    numbers = {int(number) for number in _RE_CONDITION.findall(text)}
    if not numbers:
        return None
    highest = max(numbers)
    if numbers != set(range(1, highest + 1)):
        return None
    if highest == 1:
        return "BSD-1-Clause" if _is_one_clause(text) else None
    return _BY_COUNT.get(highest)
