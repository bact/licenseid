# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The "/" reader claims no text of the fixtures (roadmap item 43): not a
licence text, a name or a mixed-content file; only an ID pair is read."""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Iterator
from pathlib import Path

from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.resolveslash import slash_parts

FIXTURES = Path(__file__).parent / "fixtures"


def texts() -> Iterator[tuple[str, str]]:
    """Every string a fixture holds as a text, a name or an ID spelling."""
    for folder in ("license-text-long", "license-text-short"):
        for path in sorted((FIXTURES / folder).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(value, str):
                    yield f"{path.name}:{key}", value
    for name in ("license-id/license_ids.json", "license-name/license_names.json"):
        for index, row in enumerate(json.loads((FIXTURES / name).read_text("utf-8"))):
            for key, value in row.items():
                if isinstance(value, str):
                    yield f"{name}:{index}:{key}", value
    for path in sorted((FIXTURES / "mixed-content").rglob("*")):
        if path.is_file():
            yield str(path.name), path.read_text(encoding="utf-8", errors="replace")


def test_no_fixture_text_is_a_list_of_ids(corpus_db: LicenseDatabase) -> None:
    count = 0
    for where, text in texts():
        count += 1
        assert slash_parts(text.strip(), corpus_db) is None, where
    assert count > 15000
