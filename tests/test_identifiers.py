# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Identifier normalization tests."""

import sqlite3
import uuid

import pytest

# pylint: disable=redefined-outer-name
from licenseid.database import LicenseDatabase
from licenseid.identifiers import (
    _MAX_CANONICALIZE_OPERATORS,
    _is_expression,
    disambiguate_deprecated_id,
    normalize_identifier,
    normalize_operator_casing,
)


@pytest.fixture
def db() -> LicenseDatabase:
    """Provide an in-memory LicenseDatabase with test licence fixtures."""
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_ident_{db_id}?mode=memory&cache=shared"
    db_manager = LicenseDatabase(db_path)

    insert_license = (
        "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, "
        "superseded_by) VALUES (?, ?, ?, ?, ?)"
    )
    insert_exception = (
        "INSERT INTO exceptions (exception_id, name, is_deprecated, "
        "superseded_by) VALUES (?, ?, ?, ?)"
    )

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            insert_license,
            ("MIT", "MIT License", True, False, None),
        )
        conn.execute(
            insert_license,
            ("Apache-2.0", "Apache License 2.0", True, False, None),
        )
        conn.execute(
            insert_license,
            # superseded_by is NULL in the DB: SPDX does not define a canonical
            # replacement for bare GPL-2.0.  The '-only' fallback is applied by
            # the tool itself (DEPRECATED_BARE_LICENSE_IDS), not by the DB.
            ("GPL-2.0", "GNU GPL v2.0 only", True, True, None),
        )
        conn.execute(
            insert_license,
            ("GPL-2.0-only", "GNU GPL v2.0 only", True, False, None),
        )
        conn.execute(
            insert_license,
            ("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, False, None),
        )
        conn.execute(
            insert_license,
            (
                "CDDL-1.0",
                "Common Development and Distribution License 1.0",
                True,
                False,
                None,
            ),
        )
        conn.execute(
            insert_exception,
            ("Linux-syscall-note", "Linux Syscall Note", False, None),
        )
    return db_manager


def test_normalize_simple_id(
    db: LicenseDatabase,
) -> None:
    # GPL-2.0 is deprecated and technically ambiguous (the license texts of
    # GPL-2.0-only and GPL-2.0-or-later are identical).  When no granting
    # context is available the tool uses '-only' as a conservative fallback.
    """Normalise simple deprecated and non-deprecated IDs."""
    assert normalize_identifier("GPL-2.0", db) == "GPL-2.0-only"
    assert normalize_identifier("MIT", db) == "MIT"


def test_normalize_with_plus(db: LicenseDatabase) -> None:
    """Normalise deprecated '+' suffix forms."""
    # Known deprecated '+' forms resolve via DEPRECATED_SPDX_LICENSE_IDS.
    assert normalize_identifier("GPL-2.0+", db) == "GPL-2.0-or-later"
    # IDs whose base is in the DB but have no '-or-later' variant keep '+'.
    # Exact base match:
    assert normalize_identifier("CDDL-1.0+", db) == "CDDL-1.0+"
    # Exact base match (correctly-cased already):
    assert normalize_identifier("Apache-2.0+", db) == "Apache-2.0+"
    # Prefix base match: "Apache-2" resolves to canonical "Apache-2.0", '+' retained.
    assert normalize_identifier("Apache-2+", db) == "Apache-2.0+"


def test_normalize_deprecated_with(db: LicenseDatabase) -> None:
    """Normalise deprecated '-with-' compound IDs."""
    assert (
        normalize_identifier("GPL-2.0-with-font-exception", db)
        == "GPL-2.0-only WITH Font-exception-2.0"
    )


def test_normalize_expression(db: LicenseDatabase) -> None:
    """Normalise SPDX expression strings.

    Operand order is canonicalised (alphabetical) by the structural
    AND/OR sort pass, not preserved verbatim from the input.
    """
    assert normalize_identifier("MIT AND Apache-2.0", db) == "Apache-2.0 AND MIT"
    assert normalize_identifier("(MIT OR Apache-2.0)", db) == "Apache-2.0 OR MIT"
    assert (
        normalize_identifier("GPL-2.0 WITH Linux-syscall-note", db)
        == "GPL-2.0-only WITH Linux-syscall-note"
    )


def test_normalize_expression_complex(db: LicenseDatabase) -> None:
    """Normalise complex SPDX expressions with multiple operators.

    The parens around the AND subexpression are semantically redundant
    (AND binds tighter than OR) and are dropped by canonicalisation.
    """
    expr = "(GPL-2.0+ AND MIT) OR Apache-2.0"
    expected = "GPL-2.0-or-later AND MIT OR Apache-2.0"
    assert normalize_identifier(expr, db) == expected


def test_normalize_case_insensitivity(db: LicenseDatabase) -> None:
    """Normalise case-insensitive SPDX expressions to canonical casing."""
    assert normalize_identifier("mit and apache-2.0", db) == "Apache-2.0 AND MIT"
    assert (
        normalize_identifier("GPL-2.0 with Linux-syscall-note", db)
        == "GPL-2.0-only WITH Linux-syscall-note"
    )


def test_normalize_operator_casing_combinations(db: LicenseDatabase) -> None:
    """Test various operator casing combinations and ensure that single
    identifiers containing 'or', 'and', 'with' are not split or altered.
    """
    # 1. Operators inside expressions
    assert normalize_operator_casing("MIT and Apache-2.0") == "MIT AND Apache-2.0"
    assert normalize_operator_casing("MIT oR Apache-2.0") == "MIT OR Apache-2.0"
    assert (
        normalize_operator_casing("MIT wiTh Font-exception-2.0")
        == "MIT WITH Font-exception-2.0"
    )
    assert (
        normalize_operator_casing("MIT AND(Apache-2.0 OR BSD-3-Clause)")
        == "MIT AND(Apache-2.0 OR BSD-3-Clause)"
    )

    # 2. Operators casing combinations in identifier-like strings
    # (Should NOT be transformed because they are part of single identifiers)
    assert normalize_operator_casing("LGPL-2.0-or-later") == "LGPL-2.0-or-later"
    assert normalize_operator_casing("orig") == "orig"
    assert normalize_operator_casing("without") == "without"
    assert normalize_operator_casing("or-later") == "or-later"

    # 3. Via normalize_identifier
    assert normalize_identifier("mit And apache-2.0", db) == "Apache-2.0 AND MIT"
    assert normalize_identifier("mit oR apache-2.0", db) == "Apache-2.0 OR MIT"
    assert normalize_identifier("LGPL-2.0-or-later", db) == "LGPL-2.0-or-later"
    assert normalize_identifier("orig", db) == "orig"
    assert normalize_identifier("without", db) == "without"
    assert normalize_identifier("or-later", db) == "or-later"


def test_normalize_expression_does_not_split_embedded_operator_words(
    db: LicenseDatabase,
) -> None:
    """A real ID that contains "or"/"with" as a substring (e.g. the
    "-or-later" suffix) must tokenise as one identifier, not get split on
    the embedded operator word.

    The tokenizer regex lists AND/OR/WITH as alternatives before the
    catch-all identifier pattern, but the catch-all's greedy "+" always
    consumes a full contiguous run of identifier characters starting from
    its first character, so "GPL-2.0-or-later" is matched whole before the
    engine ever considers "or" as a standalone alternative partway through.
    """
    assert (
        normalize_identifier("GPL-2.0-or-later AND MIT", db)
        == "GPL-2.0-or-later AND MIT"
    )


@pytest.mark.parametrize(
    "identifier, expected",
    [
        # single IDs: not expressions, even though they contain AND/OR/WITH
        # as a substring of their own name.
        ("MIT", False),
        ("GPL-2.0-or-later", False),
        ("GPL-2.0-with-font-exception", False),
        ("LicenseRef-BRANDing-1.0", False),
        # malformed multi-word garbage with no genuine reserved token: not
        # an expression either — must stay on the single-ID passthrough
        # path rather than being reformatted by _normalize_expression.
        ("n M z", False),
        ("   ", False),
        ("***", False),
        ("", False),
        # real expressions: genuine operators, "+", or parentheses.
        ("MIT AND Apache-2.0", True),
        ("MIT OR Apache-2.0", True),
        ("MIT WITH Font-exception-2.0", True),
        ("Apache-2.0+", True),
        ("(MIT)", True),
    ],
)
def test_is_expression(identifier: str, expected: bool) -> None:
    """_is_expression must not misfire on single IDs containing "and"/"or"/
    "with" as a substring (regression: normalize_identifier's top-level
    dispatch used to do a plain substring check, routing such IDs through
    the full expression-normalisation pipeline unnecessarily), nor on
    malformed input with no genuine reserved token at all (regression:
    an early version of the tokenizer-based fix treated "more than one
    token" as sufficient, which misfired on garbage like "n M z" or
    whitespace-only input)."""
    assert _is_expression(identifier) is expected


def test_normalize_identifier_garbage_passthrough(db: LicenseDatabase) -> None:
    """Whitespace-only, symbol-only, or otherwise unrecognised input passes
    through unchanged rather than being reformatted or emptied out by
    _normalize_expression."""
    assert normalize_identifier("   ", db) == "   "
    assert normalize_identifier("***", db) == "***"
    assert normalize_identifier("n M z", db) == "n M z"


def test_normalize_expression_dedup(db: LicenseDatabase) -> None:
    """Structurally identical AND/OR operands collapse to one (issue #18)."""
    assert normalize_identifier("(MIT AND MIT)", db) == "MIT"
    assert normalize_identifier("(MIT OR MIT)", db) == "MIT"
    assert (
        normalize_identifier("(MIT AND Apache-2.0) AND (Apache-2.0 AND MIT)", db)
        == "Apache-2.0 AND MIT"
    )


def test_normalize_with_exception_casing(db: LicenseDatabase) -> None:
    """The WITH right-hand side is looked up as an exception, not a license.

    Regression test: previously the exception ID after WITH was normalised
    with the license-oriented lookup, which never matched the exceptions
    table, so a mis-cased exception ID passed through unchanged.
    """
    assert (
        normalize_identifier("GPL-2.0-only WITH linux-syscall-note", db)
        == "GPL-2.0-only WITH Linux-syscall-note"
    )


def test_normalize_expression_plus_fallback(db: LicenseDatabase) -> None:
    """Expressions with a literal '+' (no '-or-later' variant) can't be
    parsed by py_spdx_license and fall back to the pre-canonicalisation
    string instead of raising or dropping content."""
    assert normalize_identifier("CDDL-1.0+ AND MIT", db) == "CDDL-1.0+ AND MIT"


def test_normalize_expression_skips_canonicalization_when_large() -> None:
    """Expressions past _MAX_CANONICALIZE_OPERATORS skip the py_spdx_license
    sort() pass entirely instead of paying its (observed super-linear) cost.

    Uses LicenseRef- IDs (no DB needed) so this stays a fast, deterministic
    unit test rather than a timing-based one.
    """
    n = _MAX_CANONICALIZE_OPERATORS + 2
    expr = " AND ".join(f"LicenseRef-{i}" for i in range(n))
    # Capped: returned unchanged (not deduplicated/reordered), since there
    # are no duplicates to begin with in this input.
    assert normalize_identifier(expr, None) == expr

    small_expr = "LicenseRef-B AND LicenseRef-A"
    # Under the cap: still canonicalised (reordered).
    assert normalize_identifier(small_expr, None) == "LicenseRef-A AND LicenseRef-B"


@pytest.mark.parametrize(
    "text, expected",
    [
        # or-later prose
        ("GPL-2.0 or later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or any later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or a later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or (at your option) any later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or newer", "GPL-2.0-or-later"),
        # only prose
        ("GPL-2.0 only", "GPL-2.0-only"),
        # sentence-ending/list punctuation directly after the bare ID (no
        # space) must not block matching the disambiguating phrase later on.
        ("Licensed under GPL-2.0. This version only, not later.", "GPL-2.0-only"),
        ("Licensed under GPL-2.0, or any later version.", "GPL-2.0-or-later"),
        # no disambiguating phrase — returns None
        ("GPL-2.0", None),
        # already-canonical suffixed IDs must not be re-matched as the bare
        # ID via their "-only"/"-or-later" suffix (regression: the bare-ID
        # boundary check must not treat "-" as a non-continuing boundary).
        ("GPL-2.0-only", None),
        ("GPL-2.0-or-later", None),
        # no deprecated ID present
        ("MIT", None),
        # normalize_identifier must apply the prose check too
    ],
)
def test_disambiguate_deprecated_id(text: str, expected: str | None) -> None:
    """Disambiguate deprecated bare IDs via prose context clues."""
    assert disambiguate_deprecated_id(text) == expected


def test_normalize_identifier_or_later_prose(db: LicenseDatabase) -> None:
    """normalize_identifier applies prose disambiguation before tokenisation."""
    assert normalize_identifier("GPL-2.0 or later version", db) == "GPL-2.0-or-later"
    assert normalize_identifier("GPL-2.0 only", db) == "GPL-2.0-only"
