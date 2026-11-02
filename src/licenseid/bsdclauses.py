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

# A numbered condition of a BSD licence: "2. Redistributions in binary
# form...", "3. Neither the name...", "3. All advertising materials...".
# The indent is white space other than a line break: `\s*` after `^` reaches
# across line breaks, so a run of blank lines was scanned once per line.
_RE_CONDITION: Final = re.compile(
    r"^[^\S\r\n]*(\d+)\.\s+(?:Redistribution|Neither\b|"
    r"All\s+advertising|The\s+(?:name|author))",
    re.MULTILINE | re.IGNORECASE,
)

_BY_COUNT: Final = {
    2: "BSD-2-Clause",
    3: "BSD-3-Clause",
    4: "BSD-4-Clause",
}


def bsd_clause_id(text: str) -> str | None:
    """The BSD-N-Clause ID the numbered conditions of a text point to.

    The highest condition number gives N (2, 3 or 4); any other count is no
    answer.
    """
    numbers = [int(number) for number in _RE_CONDITION.findall(text)]
    if not numbers:
        return None
    return _BY_COUNT.get(max(numbers))
