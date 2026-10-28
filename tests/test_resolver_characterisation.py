# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve`` pinned whole: the full result of each single-value case.

``tests/fixtures/resolver_characterisation.json`` holds the SPDX 3.29.0 rows
the cases need (read from a real 3.29.0 build, each with a stub search text)
and, for each value, the complete ``resolve()`` result as the code before the
split of ``resolver.py`` returned it. A refactor of the single-value reading
must not change one key of any of them. Every case gives the same answer on
a real 3.29.0 database, except ``MIT WITH Old-exception-1.0``: 3.29.0 has no
such exception (the real database answers unresolved), so the case is
synthetic, seeded to reach a deprecated exception that has a successor. The
``resolver`` block moves with a release: the test builds it from
``licenseid.__version__``. A case may carry a ``note``.

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
from resolver_corpus import _INSERT_EXCEPTION, _INSERT_INDEX, _INSERT_LICENSE

import licenseid
from licenseid import LicenseDatabase
from licenseid.resolver import resolve
from licenseid.resolvertypes import CATEGORY_ORDER

FIXTURE = Path(__file__).parent / "fixtures" / "resolver_characterisation.json"


def load_fixture() -> dict[str, Any]:
    """The fixture as a dict."""
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def seed(db_path: str, spec: dict[str, Any]) -> None:
    """Write the fixture's rows, exceptions and list version to *db_path*."""
    with sqlite3.connect(db_path, uri=True) as conn:
        for lid, name, deprecated, successor in spec["rows"]:
            conn.execute(_INSERT_LICENSE, (lid, name, deprecated, successor))
            conn.execute(_INSERT_INDEX, (lid, f"stub text of {lid}"))
        for row in spec["exceptions"]:
            conn.execute(_INSERT_EXCEPTION, tuple(row))
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
    """A short, readable test ID: the first 30 characters of the value."""
    return ascii(case["value"])[:30]


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_resolve_result_is_unchanged(
    db: LicenseDatabase,
    case: dict[str, Any],
) -> None:
    """The whole result dict equals the pinned one, every key."""
    version = licenseid.__version__
    expected: dict[str, Any] = {
        **case["result"],
        "resolver": {
            "name": "licenseid",
            "version": version,
            "url": f"https://github.com/bact/licenseid/releases/tag/v{version}",
            "purl": f"pkg:pypi/licenseid@{version}",
        },
    }
    assert dict(resolve(case["value"], db)) == expected


def test_every_category_a_value_can_reach_is_pinned() -> None:
    """The cases reach each category and step kind a single value can."""
    categories = {case["result"]["category"] for case in CASES}
    kinds = {
        step["kind"]
        for case in CASES
        for step in case["result"]["steps"] + case["result"]["expansions"]
    }
    assert categories == set(CATEGORY_ORDER)
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
