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
from licenseid.identifiers import disambiguate_deprecated_id, normalize_identifier


@pytest.fixture
def db() -> LicenseDatabase:
    """Provide an in-memory LicenseDatabase with test licence fixtures."""
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_ident_{db_id}?mode=memory&cache=shared"
    db_manager = LicenseDatabase(db_path)

    with sqlite3.connect(db_path, uri=True) as conn:
        # pylint: disable=line-too-long
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, False, None),
        )
        # pylint: disable=line-too-long
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, False, None),
        )
        # pylint: disable=line-too-long
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            # superseded_by is NULL in the DB: SPDX does not define a canonical
            # replacement for bare GPL-2.0.  The '-only' fallback is applied by
            # the tool itself (DEPRECATED_BARE_LICENSE_IDS), not by the DB.
            ("GPL-2.0", "GNU GPL v2.0 only", True, True, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-2.0-only", "GNU GPL v2.0 only", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            (
                "CDDL-1.0",
                "Common Development and Distribution License 1.0",
                True,
                False,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) VALUES (?, ?, ?, ?)",
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
        # no disambiguating phrase — returns None
        ("GPL-2.0", None),
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
