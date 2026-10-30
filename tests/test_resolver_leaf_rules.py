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

from licenseid import LicenseDatabase, match
from licenseid.resolveleaf import over_key_cap
from licenseid.versionkey import MAX_KEY_INPUT

_LONG = "x" * (MAX_KEY_INPUT + 1)


def _answer(value: str, db: LicenseDatabase) -> tuple[object, ...]:
    got = match(value, db)
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
        match(value, corpus_db)
    assert time.monotonic() - start < 1.0


# -- Q20: AdditionRef- --------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MIT WITH AdditionRef-x", ("MIT WITH AdditionRef-x", "exact", [])),
        (
            "LicenseRef-a WITH DocumentRef-d:AdditionRef-b.1",
            ("LicenseRef-a WITH DocumentRef-d:AdditionRef-b.1", "exact", []),
        ),
        (
            "mit with additionref-X",
            ("MIT WITH additionref-X", "lexical", ["operator_case", "id_case"]),
        ),
        (
            "GPL-2.0+ WITH AdditionRef-x",
            ("GPL-2.0-or-later WITH AdditionRef-x", "plus_to_or_later", []),
        ),
        ("MIT WITH AdditionRef-", (None, "unresolved", [])),
        ("MIT WITH AdditionRef-x_y", (None, "unresolved", [])),
        ("MIT WITH AdditionRef-x+", (None, "unresolved", [])),
        ("AdditionRef-x", (None, "unresolved", [])),  # an exception, no licence
        ("Foo WITH AdditionRef-x", (None, "unresolved", [])),
    ],
    ids=lambda v: v[:32] if isinstance(v, str) else "",
)
def test_an_addition_ref_is_read_as_written(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(value, corpus_db) == expected


# -- Q14: the "or later" grant ------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("GPL-2.0 or-later", ("GPL-2.0-or-later", "stated_qualifier", [])),
        ("LGPL-2.1 OR-LATER", ("LGPL-2.1-or-later", "stated_qualifier", [])),
        ("GPL-2.0 (or-later)", ("GPL-2.0-or-later", "stated_qualifier", [])),
        ("GPL-2.0-only or-later", (None, "malformed", [])),
        ("GPL-2.0-or-later", ("GPL-2.0-or-later", "exact", [])),  # an ID
        ("GPL-2.0 not or-later", (None, "unresolved", [])),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_the_hyphenated_grant_is_a_grant(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(value, corpus_db) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Apache 2.0 or later", ("Apache-2.0+", "separator", ["separator"])),
        ("Apache-2.0 or any later version", ("Apache-2.0+", "stated_qualifier", [])),
        ("MPL-1.1 or later", ("MPL-1.1+", "stated_qualifier", [])),
        # P35 decided by the maintainer: any ID with no -or-later form
        ("MIT (or later)", ("MIT+", "stated_qualifier", [])),
        ("MIT or later", ("MIT+", "stated_qualifier", [])),
        ("BSD-3-Clause or later", ("BSD-3-Clause+", "stated_qualifier", [])),
        (
            "StandardML-NJ or later",
            ("SMLNJ+", "stated_qualifier", ["deprecated_equal_successor"]),
        ),
        ("eCos-2.0 or later", ("eCos-2.0+", "deprecated_ambiguous", [])),
        ("GPL-2.0 or later", ("GPL-2.0-or-later", "stated_qualifier", [])),
        ("LicenseRef-x or later", (None, "unresolved", [])),
        ("DocumentRef-d:LicenseRef-x or later", (None, "unresolved", [])),
        ("MIT-only or later", (None, "unresolved", [])),
        ("LicenseRef-x-1.0 or later", (None, "unresolved", [])),  # takes no "+"
        ("Foo or later", (None, "unresolved", [])),
        ("MIT+ or later", (None, "malformed", [])),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_a_grant_on_an_id_with_no_or_later_form_is_the_plus_operator(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    """The grant is applied as SPDX writes it, "+", and stated in an
    expansion; the answer resolves to itself (a fixed point; a deprecated ID
    stays deprecated_ambiguous)."""
    assert _answer(value, corpus_db) == expected
    got = match(value, corpus_db)
    if got["expression"] is not None:
        assert [(s["kind"], s["to"]) for s in got["expansions"]][-1] == (
            "stated_qualifier",
            got["expression"],
        )
        assert match(got["expression"], corpus_db)["expression"] == (got["expression"])


_CP = "Classpath-exception-2.0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f"GPL-2.0 WITH {_CP} or later", (f"GPL-2.0-or-later WITH {_CP}", [])),
        (f"GPL-2.0 WITH {_CP} (or later)", (f"GPL-2.0-or-later WITH {_CP}", [])),
        (
            f"GPLv2 with {_CP} or any later version",
            (
                f"GPL-2.0-or-later WITH {_CP}",
                ["operator_case", "separator", "version_spelling"],
            ),
        ),
        ("MIT WITH LLVM-exception or later", ("MIT+ WITH LLVM-exception", [])),  # P35
        (f"GPL-2.0-only WITH {_CP} or later", (None, [])),  # malformed
        (f"GPL-2.0 or later WITH {_CP} or later", (None, [])),  # twice
        ("LicenseRef-x WITH LLVM-exception or later", (None, [])),
        (f"GPL-2.0 WITH {_CP} sooner or later", (None, [])),
    ],
    ids=lambda v: v[:40] if isinstance(v, str) else "",
)
def test_a_grant_after_with_qualifies_the_licence(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    """As an SPDX tag reads it: the grant is the licence's, not the
    exception's; the expansion names the licence and its grant."""
    got = match(value, corpus_db)
    assert (got["expression"], [s["kind"] for s in got["steps"]]) == expected
