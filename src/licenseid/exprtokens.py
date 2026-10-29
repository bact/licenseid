# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The words of an SPDX licence expression: its operators, its IDs and its
references, the one definition of each (review gap G11).

``licenseid.identifiers`` tokenises tags and declared expressions with
:data:`RE_TOKEN`; the compound reader of ``match()``
(``licenseid.exprcanon``) finds its operators with :data:`RE_OPERATOR`.
Standard library only, so any module can import it.
"""

import re
from typing import Final

# An identifier starts and ends alphanumeric, so a trailing full stop is
# punctuation, not part of it. A ":" joins two identifiers
# (DocumentRef-x:LicenseRef-y is one ID) and is nothing on its own. "_" is no
# part of an SPDX ID but is part of a word, so "and_mask" stays one token
# instead of becoming the AND operator.
ID_WORD: Final = r"[a-zA-Z0-9]+(?:[._-]+[a-zA-Z0-9]+)*"
OPERATOR: Final = r"(?<![a-zA-Z0-9._:-])(?:AND|OR|WITH)(?![a-zA-Z0-9._:-])"
#: An operator word in any case, never inside an ID ("GPL-2.0-or-later").
RE_OPERATOR: Final = re.compile(OPERATOR, re.IGNORECASE)
#: A token of an expression: a bracket, an operator, a "+" or an ID.
RE_TOKEN: Final = re.compile(
    rf"\(|\)|{OPERATOR}|\+|{ID_WORD}(?::{ID_WORD})*",
    re.IGNORECASE,
)
OPERATORS: Final = ("AND", "OR", "WITH")

# A whole reference, its idstrings as SPDX defines them
# (idstring = 1*(ALPHA / DIGIT / "-" / "."); ABNF strings ignore case).
_DOCUMENT_REF = r"(?:DocumentRef-[A-Za-z0-9.-]+:)?"
_RE_WHOLE_LICENSE_REF = re.compile(
    rf"{_DOCUMENT_REF}LicenseRef-[A-Za-z0-9.-]+", re.IGNORECASE
)
_RE_WHOLE_ADDITION_REF = re.compile(
    rf"{_DOCUMENT_REF}AdditionRef-[A-Za-z0-9.-]+", re.IGNORECASE
)


def is_license_ref(text: str) -> bool:
    """Whether *text* is one ``LicenseRef-*``, with its ``DocumentRef-*:`` if
    any, and nothing else."""
    return _RE_WHOLE_LICENSE_REF.fullmatch(text) is not None


def is_addition_ref(text: str) -> bool:
    """Whether *text* is one ``AdditionRef-*`` (SPDX 3: an exception of the
    author's own, beside ``LicenseRef-*``), with its ``DocumentRef-*:`` if
    any, and nothing else."""
    return _RE_WHOLE_ADDITION_REF.fullmatch(text) is not None
