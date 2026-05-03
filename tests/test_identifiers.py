import pytest
import sqlite3
import uuid
from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier


@pytest.fixture
def db():
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_ident_{db_id}?mode=memory&cache=shared"
    db_manager = LicenseDatabase(db_path)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, False, None),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_deprecated, superseded_by) VALUES (?, ?, ?, ?, ?)",
            ("GPL-2.0", "GNU GPL v2.0 only", True, True, "GPL-2.0-only"),
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
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) VALUES (?, ?, ?, ?)",
            ("Linux-syscall-note", "Linux Syscall Note", False, None),
        )
    return db_manager


def test_normalize_simple_id(db):
    assert normalize_identifier("GPL-2.0", db) == "GPL-2.0-only"
    assert normalize_identifier("MIT", db) == "MIT"


def test_normalize_with_plus(db):
    assert normalize_identifier("GPL-2.0+", db) == "GPL-2.0-or-later"
    assert normalize_identifier("Apache-2.0+", db) == "Apache-2.0+"


def test_normalize_deprecated_with(db):
    assert (
        normalize_identifier("GPL-2.0-with-font-exception", db)
        == "GPL-2.0-only WITH Font-exception-2.0"
    )


def test_normalize_expression(db):
    assert normalize_identifier("MIT AND Apache-2.0", db) == "MIT AND Apache-2.0"
    assert normalize_identifier("(MIT OR Apache-2.0)", db) == "(MIT OR Apache-2.0)"
    assert (
        normalize_identifier("GPL-2.0 WITH Linux-syscall-note", db)
        == "GPL-2.0-only WITH Linux-syscall-note"
    )


def test_normalize_expression_complex(db):
    expr = "(GPL-2.0+ AND MIT) OR Apache-2.0"
    expected = "(GPL-2.0-or-later AND MIT) OR Apache-2.0"
    assert normalize_identifier(expr, db) == expected


def test_normalize_case_insensitivity(db):
    assert normalize_identifier("mit and apache-2.0", db) == "MIT AND Apache-2.0"
    assert (
        normalize_identifier("GPL-2.0 with Linux-syscall-note", db)
        == "GPL-2.0-only WITH Linux-syscall-note"
    )
