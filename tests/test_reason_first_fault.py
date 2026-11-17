# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A refusal names the first fault of a value, not a cut version beside it.

``version ambiguous`` (a bare major the List has another minor of, item 54)
is the reason of a value whose only fault is the cut ID. A value with another
fault says that one: ``LGPL-2 WITH Classpath-exception-2.0+`` is ``malformed``
(``plus after an exception``), as ``LGPL-2.1 WITH Classpath-exception-2.0+``
is. No answer changes: each of these was refused already, and none is read by
``detect()``.
"""
# pylint: disable=missing-function-docstring

import json

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector

EXCEPTION = "Classpath-exception-2.0"

#: A cut version and a "+" on the exception: the "+" is named.
PLUS_FIRST = [
    f"LGPL-2 WITH {EXCEPTION}+",
    f"LGPLv2 WITH {EXCEPTION} +",
    f"LGPLv2 WITH {EXCEPTION}++",
    f"Apache-1 WITH {EXCEPTION}+",
    f"LGPL-2+ WITH {EXCEPTION}+",
    f"LGPL-2 with {EXCEPTION.lower()}+",
    f"LGPL-2 or later WITH {EXCEPTION}+",
    f"LGPL-2.1 WITH {EXCEPTION}+",  # no cut: always so
]

#: The cut is the only fault: its own reason.
AMBIGUOUS = {
    "LGPLv2": "LGPL-2.0, LGPL-2.1",
    "LGPL-2": "LGPL-2.0, LGPL-2.1",
    f"LGPL-2 WITH {EXCEPTION}": "LGPL-2.0, LGPL-2.1",
    "Apache-1 WITH LLVM-exception": "Apache-1.0, Apache-1.1",
    "LGPLv2 only": "LGPL-2.0-only, LGPL-2.1-only",
    "LGPLv2-only": "LGPL-2.0-only, LGPL-2.1-only",
    "LGPLv2 OR ISC": "LGPL-2.0, LGPL-2.1",  # a real compound
    "LGPLv2 or ISC": "LGPL-2.0, LGPL-2.1",
    "LGPLv2 OR foo": "LGPL-2.0, LGPL-2.1",  # upper case: an operand's own reason
    "LGPLv2 or (later)": "LGPL-2.0, LGPL-2.1",  # a grant a text match would read
    "(LGPLv2) or later": "LGPL-2.0, LGPL-2.1",
}

#: A cut version and words that name nothing after a lower-case ``or``: prose,
#: as ``LGPLv2.1 or above`` is, so the reason is the value's.
PROSE = [
    "LGPLv2 or above",
    "Apache-1 or above",
    "LGPLv2 or foo",
    "LGPLv2 and above",
    "LGPLv2.1 or above",
    "MIT or above",
]


@pytest.mark.parametrize("value", PLUS_FIRST, ids=lambda v: v[:34])
def test_a_plus_on_the_exception_comes_before_a_cut_version(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "malformed")
    assert got["reason"] == f"plus after an exception: {value}"
    assert LicenseDetector(corpus_db.location).detect(text=value) == []
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("value", sorted(AMBIGUOUS), ids=lambda v: v[:34])
def test_a_cut_version_alone_is_ambiguous(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"version ambiguous: {AMBIGUOUS[value]}"
    assert LicenseDetector(corpus_db.location).detect(text=value) == []
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("value", PROSE, ids=lambda v: v[:34])
def test_a_cut_version_beside_prose_is_not_found(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"not found: {value}"
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize(
    "value", [*PROSE, *sorted(AMBIGUOUS), *PLUS_FIRST], ids=lambda v: v[:34]
)
def test_no_reason_here_gives_an_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    """``not found`` is no reason that stops a text match (``version
    ambiguous`` is): none of these may start to answer by name or by text."""
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=value) == []
    if value != "(LGPLv2) or later":  # a field reads this one on main too
        field = json.dumps({"name": "x", "license": value})
        assert detector.detect(text=field) == []
    assert given.conditions() <= {"too few words for text"}
