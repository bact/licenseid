# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The lists a detection rests on (``Detection.lists``): the database's SPDX
License List, described by the builder ``match()`` uses
(``licenseid.resolverinfo.list_info``), in the API and in ``detect --json``.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from conftest import MIT_SEARCH_TEXT, RESULT_KEYS, invoke_match
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import LICENSE_LIST_VERSION, make_ready_file_db
from matcher_db import Lic, seeded_db

import licenseid
from licenseid import detector, resolverinfo
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.resolvertypes import ListInfo

SPDX_LIST: ListInfo = {
    "id": "spdx-license-list",
    "name": "SPDX License List",
    "version": LICENSE_LIST_VERSION,
    "source": "database",
    "url": (
        "https://github.com/spdx/license-list-data/releases/tag/"
        f"v{LICENSE_LIST_VERSION}"
    ),
    "license": "CC0-1.0",
    "provides": ["deprecation", "ids", "names", "texts"],
    "id_authority": True,
}


@pytest.fixture
def file_db(tmp_path: Path) -> Path:
    """A ready database of List version LICENSE_LIST_VERSION."""
    return make_ready_file_db(tmp_path / "licenses.db")


@pytest.fixture
def memory_db() -> Generator[str, None, None]:
    """A database of two licences."""
    rows = [
        Lic("MIT", "MIT License", True, True, True, search_text=MIT_SEARCH_TEXT),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True),
    ]
    yield from seeded_db("test_detection_lists", rows)


def test_a_detection_rests_on_the_database_list(file_db: Path) -> None:
    (result,) = LicenseDetector(str(file_db)).detect(license_id="MIT")
    assert set(result) == RESULT_KEYS
    assert result["lists"] == [SPDX_LIST]
    # The same description as match() gives of the same database.
    assert result["lists"] == licenseid.match("MIT", db=str(file_db))["lists"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"license_id": "MIT"},
        {"text": "SPDX-License-Identifier: MIT"},
        {"text": "MIT License"},
        {"text": MIT_SEARCH_TEXT},
    ],
    ids=["id", "tag", "name", "text"],
)
def test_every_method_and_result_has_its_lists(
    memory_db: str, kwargs: dict[str, str]
) -> None:
    results = LicenseDetector(memory_db).detect(**kwargs)
    assert results
    assert all(r["lists"] == [SPDX_LIST] for r in results)


def test_each_result_has_a_list_of_its_own(memory_db: str) -> None:
    matcher = LicenseDetector(memory_db)
    first, second = matcher.detect(text="MIT License or Apache License 2.0")[:2]
    first["lists"][0]["provides"].append("x")
    first["lists"].append(SPDX_LIST)
    assert second["lists"][0]["provides"][-1] == "texts"
    assert len(second["lists"]) == 1
    again = matcher.detect(text="MIT License or Apache License 2.0")
    assert again[0]["lists"][0]["provides"][-1] == "texts"


def test_detect_builds_with_the_builder_of_match(memory_db: str) -> None:
    """One builder: the detector asks resolverinfo, once per call."""
    matcher = LicenseDetector(memory_db)
    spy = mock.create_autospec(
        resolverinfo.list_info, side_effect=resolverinfo.list_info
    )
    with mock.patch.object(detector, "list_info", spy):
        results = matcher.detect(text="MIT License or Apache License 2.0")
    assert len(results) == 2
    spy.assert_called_once_with(matcher.db, "database")


def test_the_detect_function_has_lists_too(memory_db: str) -> None:
    fake = mock.create_autospec(get_default_db_path, return_value=memory_db)
    with mock.patch("licenseid.keptdetector.get_default_db_path", fake):
        (result,) = licenseid.detect(license_id="MIT")
    assert result["lists"][0]["source"] == "database"
    licenseid.keptdetector.reset()


def test_detect_json_carries_the_lists_and_the_text_line_does_not(
    file_db: Path,
) -> None:
    result = invoke_match(str(file_db), "--json", "--id", "MIT")
    record = json.loads(result.stdout)
    assert (result.exit_code, frozenset(record), record["lists"]) == (
        0,
        RESULT_KEYS,
        [SPDX_LIST],
    )
    result = invoke_match(str(file_db), "--id", "MIT")
    assert result.stdout == (
        "EXPRESSION=MIT\tMETHOD=id\tEXACT=true\tSCORE=1.0000\tSIMILARITY=\tCOVERAGE=\n"
    )


def test_no_answer_rests_on_no_list(file_db: Path) -> None:
    """The no-answer record of detect --json: every key null, lists too."""
    result = invoke_match(str(file_db), "--json", "--id", "No-Such-1.0")
    assert result.exit_code == 1
    assert json.loads(result.stdout) == dict.fromkeys(RESULT_KEYS)
