# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect()`` and a ``/`` between licences (roadmap item 43). It agrees
with ``resolve()`` on a value that reads as ``OR``, and answers every other
value as 0.8.3 did (``fixtures/slash_detect_main.json``, recorded on
``main``) on two databases: one of the near licences, each with its text
(a row with none is never retrieved and a negative test passes for nothing),
and the whole List."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from conftest import make_memory_db_path
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import seeded_db
from resolver_corpus import corpus_db_path
from slash_detect_db import rows
from slash_values import ACCEPTED

from licenseid.detector import LicenseDetector

PINNED: dict[str, dict[str, list[list[Any]]]] = json.loads(
    (Path(__file__).parent / "fixtures" / "slash_detect_main.json").read_text("utf-8")
)


@pytest.fixture(scope="module", params=["seeded", "full"])
def kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="module")
def detector(kind: str) -> Generator[LicenseDetector, None, None]:
    if kind == "seeded":
        paths = seeded_db("slash", rows())
    else:
        paths = corpus_db_path("slashfull", make_memory_db_path)
    for path in paths:
        yield LicenseDetector(path)


def answers(detector: LicenseDetector, text: str) -> list[list[Any]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # `too few words for text` is a warning
        found = detector.detect(text=text)
    return [[r["expression"], r["method"], r["exact"], r["score"]] for r in found]


@pytest.mark.parametrize(("value", "expression", "operands"), ACCEPTED)
def test_an_id_pair_is_answered_as_its_or_form(
    detector: LicenseDetector,
    value: str,
    expression: str,
    operands: list[tuple[str, object]],
) -> None:
    got = answers(detector, value)
    assert got == answers(detector, " OR ".join(text for text, _ in operands))
    if "GPL" not in value:  # `detect` narrows GPL-2.0, which is not exact
        assert got == [[expression, "id", True, 1.0]]


def test_the_golden_row_is_read_not_guessed(detector: LicenseDetector) -> None:
    # 0.8.0 answered ECL-2.0 at 0.8571 (a text match); 0.8.3 answered nothing
    assert answers(detector, "MIT/Apache-2.0") == [
        ["Apache-2.0 OR MIT", "id", True, 1.0]
    ]


def test_every_other_value_answers_as_on_0_8_3(
    detector: LicenseDetector, kind: str
) -> None:
    for value, expected in PINNED[kind].items():
        assert answers(detector, value) == expected, value


def test_the_pinned_names_stay_names(detector: LicenseDetector) -> None:
    assert answers(detector, "TCL/TK")[0][:2] == ["TCL", "name"]
    assert answers(detector, "LICENSE/MIT")[0][:2] == ["MIT", "name"]
    assert answers(detector, "/MIT") == []  # 0.8.3: MIT; #195 made it consistent
    assert answers(detector, "MIT/X11") == []
    assert answers(detector, "zlib/libpng") == []
