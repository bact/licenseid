# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Direct unit tests for LicenseDetector._get_candidates() (the
retrieval in licenseid.retrieval): what Tier 1 looks up, the
only_spdx/only_common/exclude filters on its candidates, and the hinted
candidates. The rules over the score table: test_gramselect.
"""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

import sqlite3
from collections.abc import Generator
from typing import Any

import pytest
from conftest import make_memory_db_path
from seed_sql import fill_norm_columns

from licenseid import database, retrieval
from licenseid.detector import LicenseDetector
from licenseid.textgrams import GramTable
from licenseid.types import DetectOptions


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    path, keep_alive = make_memory_db_path("test_get_candidates")
    # One row no test text matches, so the database is ready when the
    # matcher fixture builds (see licenseid.dbcheck).
    _seed(path, "READY-ROW", "readiness placeholder", is_spdx=False)
    yield path
    keep_alive.close()


@pytest.fixture
def matcher(db_path: str) -> LicenseDetector:
    return LicenseDetector(db_path)


def _seed(db_path: str, license_id: str, search_text: str, **flags: bool) -> None:
    """Insert a license + license_index row. Recognized **flags: is_spdx
    (default True), is_high_usage, is_osi_approved, is_fsf_libre
    (default False)."""
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses "
            "(license_id, name, is_spdx, is_high_usage, is_osi_approved, "
            "is_fsf_libre, word_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                license_id,
                license_id,
                flags.get("is_spdx", True),
                flags.get("is_high_usage", False),
                flags.get("is_osi_approved", False),
                flags.get("is_fsf_libre", False),
                len(search_text.split()),
            ),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (license_id, search_text),
        )
        conn.commit()
        fill_norm_columns(conn)


def _words(n: int, prefix: str = "term") -> str:
    """N distinct, normalize_text()-stable tokens: "term0 term1 ... termN-1"."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def _gram_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, int | None]]:
    """Each text Tier 1 looks the grams of up, with its bound."""
    calls: list[tuple[str, int | None]] = []
    original = database.gram_scores

    def spy(db: Any, norm_text: str, limit: int | None = None) -> GramTable:
        calls.append((norm_text, limit))
        return original(db, norm_text, limit)

    monkeypatch.setattr("licenseid.retrieval.gram_scores", spy)
    return calls


@pytest.mark.parametrize("words", [3, 150, 250])
def test_one_lookup_of_the_whole_normalised_text(
    matcher: LicenseDetector, monkeypatch: pytest.MonkeyPatch, words: int
) -> None:
    """The grams of the whole text, normalised once, looked up once, with
    the bound of gramselect."""
    calls = _gram_texts(monkeypatch)

    matcher._get_candidates(DetectOptions(), _words(words).upper())

    assert calls == [(_words(words), 50000)]


@pytest.mark.parametrize("prefix", [";", ";;", "///", "**"])
def test_comment_prefixes_are_stripped_before_normalisation(
    matcher: LicenseDetector, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    """normalize_text() does not strip these prefixes itself, so a list marker
    after one (`; 1. term`) would survive into the grams: the raw-text strip
    in get_candidates() is not redundant."""
    calls = _gram_texts(monkeypatch)

    matcher._get_candidates(
        DetectOptions(), f"{prefix} 1. term0 term1\n{prefix} (a) term2"
    )

    assert [text for text, _ in calls] == ["term0 term1 term2"]


def test_the_text_of_each_candidate_is_its_own(
    db_path: str, matcher: LicenseDetector
) -> None:
    """A candidate carries its row's text and flags, read by rowid."""
    _seed(db_path, "FIRST", _words(30), is_high_usage=True)
    _seed(db_path, "SECOND", _words(30, "word"))

    found = matcher._get_candidates(DetectOptions(), _words(30)).found

    assert [c["license_id"] for c in found] == ["FIRST"]
    assert found[0]["search_text"] == _words(30)
    assert found[0]["is_high_usage"]
    assert not matcher._get_candidates(DetectOptions(), _words(2)).found


# --- filtering: only_spdx / only_common / exclude ---


def test_get_candidates_only_spdx_true_excludes_non_spdx(
    db_path: str, matcher: LicenseDetector
) -> None:
    text = _words(30)
    _seed(db_path, "NON-SPDX", text, is_spdx=False)

    result = matcher._get_candidates(DetectOptions(only_spdx=True), text).found

    assert all(c["license_id"] != "NON-SPDX" for c in result)


def test_get_candidates_only_spdx_false_includes_non_spdx(
    db_path: str, matcher: LicenseDetector
) -> None:
    text = _words(30)
    _seed(db_path, "NON-SPDX", text, is_spdx=False)

    result = matcher._get_candidates(DetectOptions(only_spdx=False), text).found

    assert any(c["license_id"] == "NON-SPDX" for c in result)


def test_get_candidates_only_common_excludes_low_usage_non_osi(
    db_path: str, matcher: LicenseDetector
) -> None:
    text = _words(30)
    _seed(
        db_path,
        "OBSCURE",
        text,
        is_high_usage=False,
        is_osi_approved=False,
        is_fsf_libre=False,
    )

    result = matcher._get_candidates(
        DetectOptions(only_spdx=False, only_common=True), text
    ).found

    assert all(c["license_id"] != "OBSCURE" for c in result)


def test_get_candidates_only_common_includes_high_usage(
    db_path: str, matcher: LicenseDetector
) -> None:
    text = _words(30)
    _seed(db_path, "POPULAR", text, is_high_usage=True)

    result = matcher._get_candidates(
        DetectOptions(only_spdx=False, only_common=True), text
    ).found

    assert any(c["license_id"] == "POPULAR" for c in result)


def test_get_candidates_only_common_includes_osi_approved_low_usage(
    db_path: str, matcher: LicenseDetector
) -> None:
    """Boundary: is_high_usage=False but is_osi_approved=True still passes
    (the filter condition is an OR of the three flags)."""
    text = _words(30)
    _seed(db_path, "OSI-NICHE", text, is_high_usage=False, is_osi_approved=True)

    result = matcher._get_candidates(
        DetectOptions(only_spdx=False, only_common=True), text
    ).found

    assert any(c["license_id"] == "OSI-NICHE" for c in result)


def test_get_candidates_exclude_list_filters_named_id(
    db_path: str, matcher: LicenseDetector
) -> None:
    text = _words(30)
    _seed(db_path, "EXCLUDE-ME", text)

    result = matcher._get_candidates(
        DetectOptions(only_spdx=False, exclude=["EXCLUDE-ME"]), text
    ).found

    assert all(c["license_id"] != "EXCLUDE-ME" for c in result)


# --- hints (added after the filters by retrieval.hinted_candidates) ---


def test_get_candidates_adds_no_hint(db_path: str, matcher: LicenseDetector) -> None:
    """A hint is no part of Tier 1: detector._run_tier1_and_tier2 adds it
    last, after the markers."""
    _seed(db_path, "HINTED", "totally unrelated other text")

    result = matcher._get_candidates(
        DetectOptions(only_spdx=False, hint=["HINTED"]), _words(30)
    ).found

    assert all(c["license_id"] != "HINTED" for c in result)


def test_hinted_candidates_has_the_text_of_a_missing_id(
    db_path: str, matcher: LicenseDetector
) -> None:
    """A hinted ID that's in the DB but no gram candidate is a
    candidate with its own text, so it ranks on its similarity."""
    _seed(db_path, "HINTED", "totally unrelated other text")

    result = retrieval.hinted_candidates(
        matcher.db, DetectOptions(only_spdx=False, hint=["HINTED"]), []
    )

    assert [c["license_id"] for c in result] == ["HINTED"]
    assert result[0]["search_text"] == "totally unrelated other text"


def test_hinted_candidates_skips_an_id_already_present(
    db_path: str, matcher: LicenseDetector
) -> None:
    """A hinted ID that's already a candidate is not added twice (case
    folded)."""
    _seed(db_path, "ALREADY-THERE", _words(30))

    result = retrieval.hinted_candidates(
        matcher.db,
        DetectOptions(only_spdx=False, hint=["already-there"]),
        ["ALREADY-THERE"],
    )

    assert not result


def test_hinted_candidates_skips_an_unknown_id(matcher: LicenseDetector) -> None:
    """A hinted ID that isn't in the DB at all is silently skipped, not an
    error."""
    result = retrieval.hinted_candidates(
        matcher.db, DetectOptions(only_spdx=False, hint=["NO-SUCH-LICENSE"]), []
    )

    assert not result
