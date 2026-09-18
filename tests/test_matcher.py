# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for AggregatedLicenseMatcher hybrid search flow."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

import os
import sqlite3
from collections.abc import Generator
from typing import NamedTuple

import pytest
from conftest import make_memory_db_path

from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.types import InternalMatch


@pytest.fixture(scope="module")
def test_db() -> Generator[str, None, None]:
    db_path, keep_alive = make_memory_db_path("test_matcher")

    with sqlite3.connect(db_path, uri=True) as conn:
        mit_text = (
            "permission is hereby granted free of charge to any person obtaining a copy"
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("MIT", "MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("APSL-2.0", "Apple Public Source License 2.0", True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved) "
            "VALUES (?, ?, ?, ?)",
            ("AML", "Apple MIT License", True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            ("MIT", mit_text),
        )
        conn.execute(
            "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by) "
            "VALUES (?, ?, ?, ?)",
            ("Font-exception-2.0", "Font exception 2.0", False, None),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
        conn.commit()

    yield db_path
    keep_alive.close()


@pytest.mark.skipif(
    os.getenv("SPDX_TOOLS_JAR") is None, reason="SPDX_TOOLS_JAR not set"
)
def test_matcher_detects_bundled_jar(test_db: str) -> None:
    jar_path = os.getenv("SPDX_TOOLS_JAR")
    matcher = AggregatedLicenseMatcher(test_db)
    assert matcher.jar_path == jar_path
    assert matcher.has_java is True


def test_hybrid_search_flow(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    input_text = (
        "Permission is hereby granted, free of charge, to any person"
        " obtaining a copy of this software"
    )

    results = matcher.match(text=input_text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"

    if matcher.has_java and matcher.jar_path:
        matcher_with_java = AggregatedLicenseMatcher(test_db, enable_java=True)
        results_with_java = matcher_with_java.match(text=input_text)
        assert len(results_with_java) > 0
        if results_with_java[0].get("java_verified"):
            assert results_with_java[0]["score"] == 1.0


def test_short_text_rejection(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)

    assert not matcher.match("")
    assert not matcher.match("   ")
    assert not matcher.match("\n\n")

    # Generic short string (should fail name matching because threshold is 90/85)
    assert not matcher.match("This")
    assert not matcher.match("Copyright 2024.")
    assert not matcher.match("One two three four")

    # Exact name matches (< 12 words)
    res_mit = matcher.match("MIT")
    assert res_mit and res_mit[0]["license_id"] == "MIT"
    res_aml = matcher.match("Apple MIT License")
    assert res_aml and res_aml[0]["license_id"] == "AML"

    # Partial name matches (< 12 words)
    res_apple = matcher.match("APPLE PUBLIC SOURCE LICENSE")
    assert len(res_apple) > 0 and res_apple[0]["license_id"] == "APSL-2.0"


def test_match_with_expression(test_db: str) -> None:
    """A well-formed 'license WITH exception' expression is a real match,
    not just a literal DB row lookup (there is no such row)."""
    matcher = AggregatedLicenseMatcher(test_db)

    results = matcher.match(license_id="MIT WITH Font-exception-2.0")
    assert len(results) == 1
    assert results[0]["license_id"] == "MIT WITH Font-exception-2.0"
    assert results[0]["score"] == 1.0
    assert results[0]["is_spdx"] is True

    assert matcher.is_spdx(license_id="MIT WITH Font-exception-2.0")

    # Mixed-cased/lowercase operators
    results_mixed = matcher.match(license_id="MIT wiTh Font-exception-2.0")
    assert len(results_mixed) == 1
    assert results_mixed[0]["license_id"] == "MIT WITH Font-exception-2.0"
    assert results_mixed[0]["score"] == 1.0
    assert results_mixed[0]["is_spdx"] is True

    assert matcher.is_spdx(license_id="MIT wiTh Font-exception-2.0")


def test_match_with_expression_unknown_exception(test_db: str) -> None:
    """An otherwise well-formed WITH expression naming an exception that
    isn't in the (live-downloaded) exceptions table is not a match."""
    matcher = AggregatedLicenseMatcher(test_db)

    assert not matcher.match(license_id="MIT WITH Not-A-Real-Exception")


def test_match_pathological_expression_does_not_crash(test_db: str) -> None:
    """A very long AND-chain passed as license_id must degrade to "no
    match", not crash.

    Regression test: py_spdx_license's AST construction is a plain
    recursive tree walk with no depth guard, so a long enough chain raises
    RecursionError (not ParseError) — _match_with_expression previously
    only caught ParseError, so this propagated out of match() uncaught.
    """
    matcher = AggregatedLicenseMatcher(test_db)
    expr = " AND ".join(f"LicenseRef-{i}" for i in range(400))

    assert not matcher.match(license_id=expr)


def _tied_gpl_matches(only_score: float, or_later_score: float) -> list[InternalMatch]:
    return [
        InternalMatch(
            license_id="GPL-2.0-only",
            score=only_score,
            similarity=only_score,
            coverage=only_score,
            base_score=only_score,
            pop_score=0,
            best_window="",
        ),
        InternalMatch(
            license_id="GPL-2.0-or-later",
            score=or_later_score,
            similarity=or_later_score,
            coverage=or_later_score,
            base_score=or_later_score,
            pop_score=0,
            best_window="",
        ),
    ]


class _TiebreakCase(NamedTuple):
    only_score: float
    or_later_score: float
    is_pure: bool
    expected_winner: str
    adjusted: bool


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _TiebreakCase(0.90, 0.90, True, "GPL-2.0-only", True),
            id="pure_text_defaults_to_only",
        ),
        pytest.param(
            _TiebreakCase(0.90, 0.90, False, "GPL-2.0-or-later", True),
            id="mixed_text_with_granting_language_prefers_or_later",
        ),
        pytest.param(
            _TiebreakCase(0.95, 0.80, False, "GPL-2.0-only", False),
            id="not_tied_no_adjustment",
        ),
    ],
)
def test_version_suffix_tiebreaker(test_db: str, case: _TiebreakCase) -> None:
    """Pure license text: the body is identical either way, so a genuine
    tie defaults to -only regardless of any 'or later' wording present
    (e.g. the GPL appendix quotes it too, so it isn't a reliable signal
    on pure text). Mixed/source-file text with explicit granting language
    ties toward -or-later instead. Scores differing by more than 0.01 are
    not a genuine tie: trust the similarity score, don't adjust or
    reorder."""
    matcher = AggregatedLicenseMatcher(test_db)
    ranked = _tied_gpl_matches(case.only_score, case.or_later_score)

    result = matcher._apply_version_suffix_tiebreaker(
        ranked, "or (at your option) any later version", is_pure=case.is_pure
    )

    assert result[0]["license_id"] == case.expected_winner
    if case.adjusted:
        assert result[0]["score"] > result[1]["score"]
    else:
        assert result[0]["score"] == case.only_score
        assert result[1]["score"] == case.or_later_score
