# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Copies of the Apache-2.0 text are not BSD-4-Clause.

Its section "4. Redistribution." was read as the fourth BSD condition; the
marker's floor (0.95 x 0.95) then beat the text score of two or more copies
(0.155 at two, 0.017 at twenty), which the length ratio keeps low.
"""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Generator
from functools import cache
from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db

from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text

LONG = Path(__file__).parent / "fixtures" / "license-text-long"
ROWS = ("Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause", "MIT")


@cache
def text(lic_id: str) -> str:
    with open(LONG / f"{lic_id}.json", encoding="utf-8") as f:
        value: str = json.load(f)["license_text"]
    return value


@pytest.fixture(name="db_path", scope="module")
def _db_path() -> Generator[str, None, None]:
    rows = [
        Lic(lic_id, lic_id, search_text=normalize_text(text(lic_id))) for lic_id in ROWS
    ]
    yield from seeded_db("test_apache_copies_marker", rows)


def answers(db_path: str, value: str) -> list[str]:
    results = LicenseDetector(db_path).detect(text=value)
    return [r["expression"] for r in results]


@pytest.mark.parametrize("copies", [1, 2, 5, 20])
def test_copies_of_apache_2_0_do_not_answer_bsd_4_clause(
    db_path: str, copies: int
) -> None:
    value = "\n\n".join([text("Apache-2.0")] * copies)
    assert answers(db_path, value)[0] != "BSD-4-Clause"


def test_one_copy_of_apache_2_0_is_apache_2_0(db_path: str) -> None:
    assert answers(db_path, text("Apache-2.0"))[0] == "Apache-2.0"


@pytest.mark.parametrize("lic_id", ["BSD-3-Clause", "BSD-4-Clause"])
def test_two_copies_of_a_bsd_text_keep_their_answer(db_path: str, lic_id: str) -> None:
    value = "\n\n".join([text(lic_id)] * 2)
    assert answers(db_path, value)[0] == lic_id


@pytest.mark.parametrize(
    "order", [("Apache-2.0", "BSD-3-Clause"), ("BSD-3-Clause", "Apache-2.0")]
)
def test_apache_2_0_beside_a_bsd_3_text_does_not_answer_bsd_4_clause(
    db_path: str, order: tuple[str, str]
) -> None:
    value = "\n\n".join(text(lic_id) for lic_id in order)
    # The top, if any: where the Apache-2.0 text ranks first but comes second,
    # the first-text rule (firsttext) leaves no result.
    assert answers(db_path, value)[:1] != ["BSD-4-Clause"]
