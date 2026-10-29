# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve`` on the shapes around one licence: an exception after WITH, a
``LicenseRef-*``, a qualifier stated twice, a character that hides, and the
"or later" readers it shares with ``match``."""
# pylint: disable=missing-function-docstring

import re
import sqlite3
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db
from ordering_helpers import PHRASES
from resolver_helpers import GPL2, summary

from licenseid import LicenseDatabase
from licenseid.classify import is_negated
from licenseid.looseid import declared_grant_id_text, granted_id_text
from licenseid.resolver import resolve
from licenseid.resolvertypes import CATEGORY_ORDER, TRUST

ROWS = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
    *GPL2,
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only"),
    Lic("GPL-3.0-or-later", "GNU General Public License v3.0 or later"),
    Lic("GPL-3.0", "GNU General Public License v3.0 only", is_deprecated=True),
)
# (ID, deprecated, successor): one in use, one renamed, one with no successor.
EXCEPTIONS = (
    ("Classpath-exception-2.0", False, None),
    ("LLVM-exception", False, None),
    ("New-exception", False, None),
    ("Old-exception", True, "New-exception"),
    ("Gone-exception", True, None),
)
CP = "Classpath-exception-2.0"


@pytest.fixture(name="db")
def _db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_resolver_shapes", ROWS):
        with sqlite3.connect(path, uri=True) as conn:
            conn.executemany(
                "INSERT INTO exceptions"
                " (exception_id, name, is_deprecated, superseded_by)"
                " VALUES (?, ?, ?, ?)",
                [(e, e, deprecated, after) for e, deprecated, after in EXCEPTIONS],
            )
        yield LicenseDatabase(path, create=False)


NONE: tuple[object, ...] = (None, "unresolved", [], [], [])
MALFORMED: tuple[object, ...] = (None, "malformed", [], [], [])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # WITH: one licence and its exception, each read as on its own
        (f"GPL-2.0-only WITH {CP}", (f"GPL-2.0-only WITH {CP}", "exact", [], [], [])),
        (
            f"gpl-2.0-only with {CP.lower()}",
            (
                f"GPL-2.0-only WITH {CP}",
                "lexical",
                ["operator_case", "id_case", "id_case"],
                [],
                [],
            ),
        ),
        # Q17: the case and the spacing of WITH are steps; exact is as written
        (
            f"GPL-2.0-only With {CP}",
            (f"GPL-2.0-only WITH {CP}", "lexical", ["operator_case"], [], []),
        ),
        (
            f"GPL-2.0-only \tWITH  {CP}",
            (f"GPL-2.0-only WITH {CP}", "lexical", ["whitespace"], [], []),
        ),
        (
            f"GPL-2.0-only\u00a0with {CP}",
            (
                f"GPL-2.0-only WITH {CP}",
                "lexical",
                ["operator_case", "whitespace"],
                [],
                [],
            ),
        ),
        (
            f"(GPL-2.0-only WITH {CP})",
            (f"GPL-2.0-only WITH {CP}", "lexical", ["brackets"], [], []),
        ),
        (
            "Apache2 WITH LLVM-exception",
            (
                "Apache-2.0 WITH LLVM-exception",
                "version_spelling",
                ["separator", "version_spelling"],
                [],
                [],
            ),
        ),
        (
            f"GPL-2.0+ WITH {CP}",
            (
                f"GPL-2.0-or-later WITH {CP}",
                "plus_to_or_later",
                [],
                [("plus_to_or_later", True)],
                [],
            ),
        ),
        (
            f"GPL-2.0 or later WITH {CP}",
            (
                f"GPL-2.0-or-later WITH {CP}",
                "stated_qualifier",
                [],
                [("stated_qualifier", True)],
                [],
            ),
        ),
        (
            f"GPL-3.0 WITH {CP}",
            (
                f"GPL-3.0 WITH {CP}",
                "assumed_only",
                [],
                [("assumed_only", False)],
                [f"GPL-3.0-only WITH {CP}", f"GPL-3.0-or-later WITH {CP}"],
            ),
        ),
        (
            "MIT WITH Old-exception",
            (
                "MIT WITH New-exception",
                "deprecated_equal_successor",
                ["deprecated_equal_successor"],
                [],
                [],
            ),
        ),
        (
            "MIT WITH Gone-exception",
            (
                "MIT WITH Gone-exception",
                "deprecated_ambiguous",
                [],
                [("deprecated_ambiguous", False)],
                [],
            ),
        ),
        (
            "LicenseRef-foo WITH LLVM-exception",
            ("LicenseRef-foo WITH LLVM-exception", "exact", [], [], []),
        ),
        # WITH: a part that is broken or names nothing gives no answer
        (f"GPL-2.0-only+ WITH {CP}", MALFORMED),
        ("LicenseRef-foo+ WITH LLVM-exception", MALFORMED),
        # Q14: MIT has no -or-later ID, so the grant is "+" (was unresolved)
        (
            "MIT or later WITH LLVM-exception",  # P35
            (
                "MIT+ WITH LLVM-exception",
                "stated_qualifier",
                [],
                [("stated_qualifier", True)],
                [],
            ),
        ),
        ("MIT WITH Foo-exception", NONE),  # no such exception: not two licences
        ("MIT WITH GCC-exception-3.1", NONE),  # an SPDX exception not in this db
        ("Foo WITH LLVM-exception", NONE),
        ("(MIT) WITH LLVM-exception", NONE),  # WITH takes an ID, not a bracket
        ("MIT WITH LLVM-exception WITH LLVM-exception", NONE),
        ("MIT WITH", NONE),
        ("LLVM-exception", NONE),
        (
            "MIT WITH LLVM-exception OR Apache-2.0",
            ("Apache-2.0 OR MIT WITH LLVM-exception", "lexical", ["reorder"], [], []),
        ),
        # a LicenseRef names itself, as written; it takes no "+" and no grant
        ("LicenseRef-foo", ("LicenseRef-foo", "exact", [], [], [])),
        ("licenseref-Foo.2", ("licenseref-Foo.2", "exact", [], [], [])),
        (
            "DocumentRef-spdx-tool-1.2:LicenseRef-MIT-Style-2",
            ("DocumentRef-spdx-tool-1.2:LicenseRef-MIT-Style-2", "exact", [], [], []),
        ),
        (
            " (LicenseRef-foo) ",
            ("LicenseRef-foo", "lexical", ["trim", "brackets"], [], []),
        ),
        ("LicenseRef-foo+", MALFORMED),
        ("LicenseRef-foo +", MALFORMED),
        ("LicenseRef-foo or later", NONE),
        ("LicenseRef-", NONE),
        ("LicenseRef-foo_bar", NONE),  # "_" is no idstring character
        ("LicenseRef-foo bar", NONE),
        ("DocumentRef-x:", NONE),
        # a qualifier stated twice is malformed, however it is written
        ("GPLv3+ or later", MALFORMED),
        ("GPL-3.0+ (or later)", MALFORMED),
        ("GPLv2+ or any later version", MALFORMED),
        ("GPL-2.0 + or later", MALFORMED),
        ("Foo+ or later", NONE),  # nothing named: not malformed
        ("MIT+ or later", MALFORMED),
        # a "+" follows a licence ID, never a bracket
        ("(GPL-2.0)+", MALFORMED),
        ("((GPL-2.0))+", MALFORMED),
        ("(GPL-2.0) +", MALFORMED),
        ("(Foo)+", NONE),
        ("(MIT OR Apache-2.0)+", NONE),
        # a character that hides or reorders text is no part of a value
        ("MIT\u200b", NONE),
        ("\u202eMIT", NONE),
        ("M\u2060IT", NONE),
        ("\ufeffMIT", NONE),
        ("Apache\u00ad2", NONE),  # a soft hyphen is a format character too
        ("MIT\u00a0", ("MIT", "lexical", ["trim"], [], [])),  # white space is not
    ],
    ids=lambda v: ascii(v)[:40] if isinstance(v, str) else "",
)
def test_a_shape_resolves_with_its_steps(
    db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert summary(resolve(value, db)) == expected


# -- the "or later" readers ------------------------------------------------


@pytest.mark.parametrize("phrase", sorted(PHRASES))
def test_the_declared_grant_reader_reads_a_phrase_as_the_others_do(
    phrase: str,
) -> None:
    """The declared reader and the prose reader find a grant in the same
    phrasings; the declared one also without a number before it."""
    reads = PHRASES[phrase][0]
    assert (declared_grant_id_text(f"GPL-3.0-only {phrase}") is not None) == reads
    assert (granted_id_text(f"GPL-3.0 {phrase}") is not None) == reads


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("GPL-3.0-only or later", "GPL-3.0-only"),
        ("GPL-3.0-only (or later)", "GPL-3.0-only"),
        ("GPL-3.0-only [or later]", "GPL-3.0-only"),
        ("GPL-3.0-only  \t or any later version.", "GPL-3.0-only"),
        ("MIT OR GPL-3.0-only or later", "MIT OR GPL-3.0-only"),
        ("sooner or later", "sooner"),  # the caller finds no ID in "sooner"
        ("GPL-3.0-only or later or MIT", None),  # the grant does not end it
        ("GPL-3.0-only-or later", None),  # "or" inside a word
        ("GPL-3.0-only not or later", None),
        ("GPL-3.0-only NO or newer", None),
        ("or later", None),  # no licence before it
        ("GPL-3.0-only or", None),
        ("GPL-3.0-only", None),
    ],
)
def test_a_declared_grant_ends_the_value(text: str, named: str | None) -> None:
    assert declared_grant_id_text(text) == named


@pytest.mark.parametrize(
    ("before", "negated"),
    [
        ("GPL not ", True),
        ("GPL NO ", True),
        ("not ", True),
        ("GPL knot ", False),  # a word that ends in "not"
        ("GPL not  ", False),  # as OR_LATER_PHRASE: one space only
        ("GPL not", False),
        ("GPL nothing ", False),
        ("", False),
    ],
)
def test_a_negation_takes_back_the_phrase_after_it(before: str, negated: bool) -> None:
    assert is_negated(before) is negated


# -- the name index --------------------------------------------------------


def test_a_name_is_looked_up_without_a_pass_over_every_row(
    db: LicenseDatabase,
) -> None:
    db.get_active_ids_by_name()  # built once
    with mock.patch.object(
        LicenseDatabase, "get_all_names_and_ids", autospec=True
    ) as scan:
        for _ in range(3):
            assert resolve("mit license", db)["expression"] == "MIT"
    scan.assert_not_called()


def test_a_name_held_by_a_deprecated_row_only_is_no_listed_name() -> None:
    rows = (
        Lic("SMLNJ", "Standard ML of New Jersey License"),
        Lic("Old-1.0", "Old License", is_deprecated=True),
    )
    for path in seeded_db("test_resolver_shapes_names", rows):
        db = LicenseDatabase(path, create=False)
        assert db.get_active_ids_by_name() == {
            "standard ml of new jersey license": ["SMLNJ"]
        }
        assert resolve("Old License", db)["category"] == "unresolved"


def test_the_readme_lists_every_category_in_order_with_its_trust() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(\w+)` \| `(\w+)` \|", readme, re.MULTILINE)
    assert rows == [(c, TRUST[c]) for c in CATEGORY_ORDER]
