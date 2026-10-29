# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What task T7 changed in the reading of one licence: the key cap per WITH
half (Q16), ``AdditionRef-`` exceptions (Q20) and the "or later" grant
(Q14)."""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.resolveleaf import over_key_cap
from licenseid.versionkey import MAX_KEY_INPUT

_LONG = "x" * (MAX_KEY_INPUT + 1)


def _answer(value: str, db: LicenseDatabase) -> tuple[object, ...]:
    got = resolve(value, db)
    return got["expression"], got["category"], [s["kind"] for s in got["steps"]]


# -- Q16: the key cap per WITH half -----------------------------------------


@pytest.mark.parametrize(
    ("text", "over"),
    [
        ("x" * MAX_KEY_INPUT, False),
        (_LONG, True),
        (f"{'x' * MAX_KEY_INPUT} WITH {'y' * MAX_KEY_INPUT}", False),
        (f"{_LONG} WITH LLVM-exception", True),
        (f"MIT WITH {_LONG}", True),
        (f"LicenseRef-{_LONG}", False),
        (f"DocumentRef-d:LicenseRef-{_LONG}", False),
        (f"LicenseRef-{_LONG} WITH LLVM-exception", False),
        (f"MIT WITH AdditionRef-{_LONG}", False),
        (f"LicenseRef-{_LONG} WITH {_LONG}", True),
        # two WITHs are no WITH expression: the whole is the one half
        (f"a WITH b WITH {'c' * MAX_KEY_INPUT}", True),
        (f"LicenseRef-{_LONG} or later", True),  # a grant is not the reference
    ],
    ids=lambda v: v[:24] if isinstance(v, str) else str(v),
)
def test_the_key_cap_is_per_with_half(text: str, over: bool) -> None:
    assert over_key_cap(text) is over


def test_a_long_licence_name_with_an_exception_is_read(
    corpus_db: LicenseDatabase,
) -> None:
    """97 characters of listed name, then WITH: over the cap as a whole."""
    value = (
        "Creative Commons Attribution Non Commercial No Derivatives 2.5 Generic"
        " WITH RRDtool-FLOSS-exception-2.0"
    )
    assert _answer(value, corpus_db) == (
        "CC-BY-NC-ND-2.5 WITH RRDtool-FLOSS-exception-2.0",
        "listed_name",
        ["listed_name"],
    )


@pytest.mark.parametrize(
    "value",
    [f"LicenseRef-{_LONG}", f"DocumentRef-{_LONG}:LicenseRef-{_LONG}"],
    ids=["licenseref", "documentref"],
)
def test_a_long_reference_names_itself(corpus_db: LicenseDatabase, value: str) -> None:
    assert _answer(value, corpus_db) == (value, "exact", [])


@pytest.mark.parametrize(
    "value",
    [_LONG, f"{_LONG} WITH LLVM-exception", f"MIT WITH {_LONG}", f"{_LONG}+"],
    ids=["id", "licence-half", "exception-half", "plus"],
)
def test_a_long_word_still_names_nothing(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _answer(value, corpus_db) == (None, "unresolved", [])


def test_a_long_run_of_white_space_around_with_is_fast(
    corpus_db: LicenseDatabase,
) -> None:
    """The WITH split starts at the first space of a run: linear, not
    quadratic (1.6 s at 20,000 spaces before). Distinct values, 10 times
    the headroom of Python 3.10 on CI."""
    values = [f"MIT{' ' * size}WITH LLVM-exception x{size}" for size in (1_990,)]
    values += ["LicenseRef-a" + " " * 1_980 + "b", " " * 1_999 + "W"]
    start = time.monotonic()
    for value in values:
        resolve(value, corpus_db)
    assert time.monotonic() - start < 1.0
