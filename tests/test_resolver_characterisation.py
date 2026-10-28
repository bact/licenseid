# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve`` pinned whole: the full result of each single-value case.

``tests/fixtures/resolver_characterisation.json`` holds the SPDX 3.29.0 rows
the cases need (copied from a real build, with a stub search text) and, for
each value, the complete ``resolve()`` result as the code at the time of the
split of ``resolver.py`` returned it. A refactor of the single-value reading
must not change one key of any of them. The ``resolver`` block carries the
package version, which moves with a release: it is compared by shape and
replaced by the live one before the whole dict is compared.

Lone surrogates survive the JSON file as ``\\udXXX`` escapes
(``ensure_ascii=True``), and ``json.loads`` gives them back.
"""

import json
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from conftest import make_memory_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.resolver import resolve

FIXTURE = Path(__file__).parent / "fixtures" / "resolver_characterisation.json"
_INSERT_LICENSE = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved,"
    " is_fsf_libre, is_deprecated, superseded_by) VALUES (?, ?, 1, 0, 0, ?, ?)"
)
_INSERT_INDEX = "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)"
_INSERT_EXCEPTION = (
    "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?)"
)


def load_fixture() -> dict[str, Any]:
    """The fixture as a dict."""
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def seed(db_path: str, spec: dict[str, Any], *, with_seed_only: bool = True) -> None:
    """Write the fixture's rows, exceptions and list version to *db_path*."""
    with sqlite3.connect(db_path, uri=True) as conn:
        for lid, name, deprecated, successor in spec["rows"]:
            conn.execute(_INSERT_LICENSE, (lid, name, deprecated, successor))
            conn.execute(_INSERT_INDEX, (lid, f"stub text of {lid}"))
        for row in spec["exceptions"]:
            if with_seed_only or not row[4]:
                conn.execute(_INSERT_EXCEPTION, tuple(row[:4]))
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
            ("license_list_version", spec["list_version"]),
        )


@pytest.fixture(name="db")
def _db() -> Generator[LicenseDatabase, None, None]:
    spec = load_fixture()
    db_path, keep_alive = make_memory_db_path("resolver_characterisation")
    seed(db_path, spec)
    yield LicenseDatabase(db_path, create=False)
    keep_alive.close()


CASES = load_fixture()["cases"]


def case_id(case: dict[str, Any]) -> str:
    """A short, readable test ID: the value's first 24 characters."""
    return ascii(case["value"])[:30]


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_resolve_result_is_unchanged(
    db: LicenseDatabase,
    case: dict[str, Any],
) -> None:
    """The whole result dict equals the pinned one, every key."""
    got: dict[str, Any] = dict(resolve(case["value"], db))
    expected: dict[str, Any] = dict(case["result"])
    resolver = got.pop("resolver")
    expected_resolver = expected.pop("resolver")
    assert resolver["name"] == expected_resolver["name"] == "licenseid"
    assert resolver["purl"] == f"pkg:pypi/licenseid@{resolver['version']}"
    assert got == expected


def test_every_category_a_value_can_reach_is_pinned() -> None:
    """The cases reach each category and step kind a single value can."""
    categories = {case["result"]["category"] for case in CASES}
    kinds = {
        step["kind"]
        for case in CASES
        for step in case["result"]["steps"] + case["result"]["expansions"]
    }
    assert categories >= {
        "exact",
        "lexical",
        "listed_name",
        "deprecated_equal_successor",
        "plus_to_or_later",
        "stated_qualifier",
        "separator",
        "version_spelling",
        "deprecated_ambiguous",
        "assumed_only",
        "expression",
        "malformed",
        "unresolved",
    }
    assert kinds >= {
        "brackets",
        "deprecated_ambiguous",
        "deprecated_equal_successor",
        "id_case",
        "listed_name",
        "assumed_only",
        "plus_to_or_later",
        "separator",
        "stated_qualifier",
        "trim",
        "version_spelling",
        "whitespace",
    }
