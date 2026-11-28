# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where ``TEXTS`` is never printed it is never named: the ``is-*``
commands, the ``is_*()`` predicates and the terse ``detect``. The search
itself runs once per call everywhere, for the first-text rule
(``licenseid.firsttext``), so every output gives one answer; ``TEXTS`` reuses
it. The search is counted through the ``found_rows`` fixture (calls, not
time); the answers of the other fields do not change."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import FoundRows
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from texts_db import A, texts_database

from licenseid import firsttext, textnames
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.retrieval import text_candidates
from licenseid.types import Variant

MORE = A + " extra words here"  # A-1.0 by text, not exactly


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from texts_database("test_texts_skipped")


def _run(db_path: str, *args: str) -> Any:
    return CliRunner().invoke(cli, ["--db", db_path, *args, "--text", MORE])


@pytest.mark.terse_cli
@pytest.mark.parametrize(
    ("args", "searches"),
    [
        (["detect"], 1),
        (["detect", "--top", "2"], 1),
        (["detect", "-v"], 1),
        (["detect", "--json"], 1),
        (["is-osi"], 1),
        (["is-fsf"], 1),
        (["is-spdx"], 1),
    ],
    ids=["terse", "terse-top", "verbose", "json", "is-osi", "is-fsf", "is-spdx"],
)
def test_the_cli_searches_once_everywhere(
    db_path: str, found_rows: FoundRows, args: list[str], searches: int
) -> None:
    found_rows.rows = ["A-1.0"]
    _run(db_path, *args)
    assert len(found_rows.calls) == searches


@pytest.mark.terse_cli
def test_the_terse_answer_is_what_the_verbose_answer_starts_with(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    terse = _run(db_path, "detect").stdout.splitlines()
    verbose = _run(db_path, "detect", "-v").stdout.splitlines()
    assert terse == ["A-1.0", "B-1.0"]
    assert [x.split("\t")[0] for x in verbose] == [f"EXPRESSION={x}" for x in terse]


@pytest.mark.parametrize("predicate", ["is_osi", "is_fsf", "is_spdx"])
def test_a_predicate_searches_once_and_follows_the_rule(
    db_path: str, found_rows: FoundRows, predicate: str
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    detector = LicenseDetector(db_path)
    assert getattr(detector, predicate)(text=MORE) is not None
    # Tier 2's search, then the answer's: two texts found.
    assert [answer for _, answer in found_rows.calls] == ["", "A-1.0"]
    found_rows.first = "B-1.0"  # A-1.0's text is not first: no answer
    assert getattr(detector, predicate)(text=MORE) is None


def test_the_api_detect_searches(db_path: str, found_rows: FoundRows) -> None:
    found_rows.rows = ["A-1.0"]
    results = LicenseDetector(db_path).detect(text=MORE)
    assert len(found_rows.calls) == 1
    assert results[0]["texts"] == ["A-1.0"]


def test_the_skip_ends_with_its_block(db_path: str, found_rows: FoundRows) -> None:
    found_rows.rows = ["A-1.0"]
    detector = LicenseDetector(db_path)
    with textnames.skipped():
        assert detector.detect(text=MORE)[0]["texts"] is None
    assert detector.detect(text=MORE)[0]["texts"] == ["A-1.0"]


def test_an_exact_short_text_is_its_own_text(
    db_path: str, found_rows: FoundRows
) -> None:
    """A List text under 40 tokens (FSFUL) holds itself: no token gate for an
    exact answer, and no search."""
    short = " ".join(normalize_text(A).split()[:12])
    db = LicenseDetector(db_path).db
    result: Any = {"exact": True, "method": "text", "license_id": "A-1.0"}
    variant: Variant = "auto"
    with db.reading():
        settled, found = firsttext.settle_texts(
            [result], text_candidates(db, short, short), db
        )
        assert textnames.held_texts(db, settled, variant, found) == ["A-1.0"]
        result["exact"] = False  # not exact: still the gate
        settled, found = firsttext.settle_texts(
            [result], text_candidates(db, short, short), db
        )
        assert textnames.held_texts(db, settled, variant, found) is None
    assert not found_rows.calls
