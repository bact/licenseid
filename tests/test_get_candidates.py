# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Direct unit tests for AggregatedLicenseMatcher._get_candidates().

Characterization tests written before the matcher.py complexity refactor
(see working-docs/design/complexity-and-file-size-roadmap.md, item 1) to
pin down behaviour that was previously only reachable incidentally
through match()'s public surface: the head/tail retrieval-window word
thresholds, the tail-only candidate cap, hint injection, and the
only_spdx/only_common/exclude filters.
"""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

import sqlite3
from collections.abc import Callable, Generator
from typing import Any

import pytest
from conftest import make_memory_db_path

from licenseid import matcher as matcher_module
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.types import MatchRequest


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    path, keep_alive = make_memory_db_path("test_get_candidates")
    # One row no test text matches, so the database is ready when the
    # matcher fixture builds (see licenseid.dbcheck).
    _seed(path, "READY-ROW", "readiness placeholder", is_spdx=False)
    yield path
    keep_alive.close()


@pytest.fixture
def matcher(db_path: str) -> AggregatedLicenseMatcher:
    return AggregatedLicenseMatcher(db_path)


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


def _words(n: int, prefix: str = "term") -> str:
    """N distinct, normalize_text()-stable tokens: "term0 term1 ... termN-1"."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def _install_search_spy(
    matcher: AggregatedLicenseMatcher,
) -> list[tuple[Any, ...]]:
    """Wrap matcher.db.search_candidates to record each call's args while
    still delegating to the real implementation."""
    calls: list[tuple[Any, ...]] = []
    original: Callable[..., Any] = matcher.db.search_candidates

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(*args, **kwargs)

    matcher.db.search_candidates = spy  # type: ignore[method-assign]
    return calls


# --- retrieval branch: head/tail word-count thresholds ---


def test_get_candidates_short_text_single_query(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """<=100 normalized words: a single search_candidates call, and the
    matching candidate is returned."""
    text = _words(50)
    _seed(db_path, "SHORT-1", text)
    calls = _install_search_spy(matcher)

    result = matcher._get_candidates(MatchRequest(), text)

    assert len(calls) == 1
    assert any(c["license_id"] == "SHORT-1" for c in result)


@pytest.mark.parametrize(
    ("word_count", "expected_call_count"),
    [
        pytest.param(100, 1, id="100_words_exact_single_query"),
        pytest.param(101, 1, id="101_words_head_query_only"),
        pytest.param(200, 1, id="200_words_exact_head_query_only"),
        pytest.param(201, 2, id="201_words_head_and_tail_queries"),
    ],
)
def test_get_candidates_retrieval_call_count_by_word_count(
    db_path: str,
    matcher: AggregatedLicenseMatcher,
    word_count: int,
    expected_call_count: int,
) -> None:
    """search_candidates() call count by normalized word count: at or
    below a boundary uses a single query; both ">100" (head query) and
    ">200" (additional tail query) are strict boundaries, so exactly 100
    or exactly 200 words does not yet cross them."""
    text = _words(word_count)
    _seed(db_path, "IRRELEVANT", "unrelated filler")
    calls = _install_search_spy(matcher)

    matcher._get_candidates(MatchRequest(), text)

    assert len(calls) == expected_call_count


def test_get_candidates_single_query_passes_full_text(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """<=100 normalized words: the full text is passed through unchanged
    (not sliced), unlike the head/tail queries used for longer input."""
    text = _words(100)
    _seed(db_path, "IRRELEVANT", "unrelated filler")
    calls = _install_search_spy(matcher)

    matcher._get_candidates(MatchRequest(), text)

    assert calls[0][0].split() == text.split()


def test_get_candidates_head_query_truncates_at_101_words(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """101 normalized words: the head query passes only the first 100
    words on, dropping the 101st."""
    text = _words(101)
    _seed(db_path, "IRRELEVANT", "unrelated filler")
    calls = _install_search_spy(matcher)

    matcher._get_candidates(MatchRequest(), text)

    passed_words = calls[0][0].split()
    assert passed_words == [f"term{i}" for i in range(100)]
    assert "term100" not in passed_words


def test_get_candidates_tail_query_carries_last_20_words(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """201 normalized words: the tail query carries exactly the last 20
    words."""
    text = _words(201)
    _seed(db_path, "IRRELEVANT", "unrelated filler")
    calls = _install_search_spy(matcher)

    matcher._get_candidates(MatchRequest(), text)

    tail_words = calls[1][0].split()
    assert tail_words == [f"term{i}" for i in range(181, 201)]


def test_get_candidates_tail_only_cap_enforced(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """Tail-only additions (candidates found only via the tail query, not
    the head query) are capped at _TAIL_ONLY_CAP, even when more would
    otherwise match.
    """
    expected_cap = matcher_module._TAIL_ONLY_CAP
    # 200 head-window filler words the 40 tail-only candidates must NOT
    # match, followed by 20 distinct tail words used to build 40 tail-only
    # candidates (2 candidates per tail word, well over the cap).
    text = _words(200, prefix="head") + " " + _words(20, prefix="tail")
    for i in range(40):
        tail_word = f"tail{i % 20}"
        _seed(db_path, f"TAIL-ONLY-{i}", f"{tail_word} filler{i} content{i}")

    result = matcher._get_candidates(MatchRequest(only_spdx=False), text)

    tail_only_ids = {c["license_id"] for c in result if "TAIL-ONLY" in c["license_id"]}
    assert len(tail_only_ids) == expected_cap


def test_get_candidates_tail_query_dedup_against_head(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """A candidate found by both the head and tail queries is not
    double-counted, and doesn't consume tail-cap budget."""
    text = _words(200, prefix="head") + " " + _words(20, prefix="tail")
    # Matches both the head query (contains "head0") and the tail query
    # (contains "tail0").
    _seed(db_path, "BOTH", "head0 tail0 shared content")

    result = matcher._get_candidates(MatchRequest(only_spdx=False), text)

    matches = [c for c in result if c["license_id"] == "BOTH"]
    assert len(matches) == 1


# --- filtering: only_spdx / only_common / exclude ---


def test_get_candidates_only_spdx_true_excludes_non_spdx(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    text = _words(30)
    _seed(db_path, "NON-SPDX", text, is_spdx=False)

    result = matcher._get_candidates(MatchRequest(only_spdx=True), text)

    assert all(c["license_id"] != "NON-SPDX" for c in result)


def test_get_candidates_only_spdx_false_includes_non_spdx(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    text = _words(30)
    _seed(db_path, "NON-SPDX", text, is_spdx=False)

    result = matcher._get_candidates(MatchRequest(only_spdx=False), text)

    assert any(c["license_id"] == "NON-SPDX" for c in result)


def test_get_candidates_only_common_excludes_low_usage_non_osi(
    db_path: str, matcher: AggregatedLicenseMatcher
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
        MatchRequest(only_spdx=False, only_common=True), text
    )

    assert all(c["license_id"] != "OBSCURE" for c in result)


def test_get_candidates_only_common_includes_high_usage(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    text = _words(30)
    _seed(db_path, "POPULAR", text, is_high_usage=True)

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, only_common=True), text
    )

    assert any(c["license_id"] == "POPULAR" for c in result)


def test_get_candidates_only_common_includes_osi_approved_low_usage(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """Boundary: is_high_usage=False but is_osi_approved=True still passes
    (the filter condition is an OR of the three flags)."""
    text = _words(30)
    _seed(db_path, "OSI-NICHE", text, is_high_usage=False, is_osi_approved=True)

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, only_common=True), text
    )

    assert any(c["license_id"] == "OSI-NICHE" for c in result)


def test_get_candidates_exclude_list_filters_named_id(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    text = _words(30)
    _seed(db_path, "EXCLUDE-ME", text)

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, exclude=["EXCLUDE-ME"]), text
    )

    assert all(c["license_id"] != "EXCLUDE-ME" for c in result)


# --- hint injection ---


def test_get_candidates_hint_injects_missing_id(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """A hinted ID that's in the DB but wasn't returned by search is
    force-included as a synthetic candidate."""
    text = _words(30)
    _seed(db_path, "HINTED", "totally unrelated other text")

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, hint=["HINTED"]), text
    )

    hinted = [c for c in result if c["license_id"] == "HINTED"]
    assert len(hinted) == 1
    assert hinted[0]["search_text"] == ""


def test_get_candidates_hint_skips_id_already_in_filtered(
    db_path: str, matcher: AggregatedLicenseMatcher
) -> None:
    """A hinted ID that's already present from real search results is not
    duplicated."""
    text = _words(30)
    _seed(db_path, "ALREADY-THERE", text)

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, hint=["ALREADY-THERE"]), text
    )

    matches = [c for c in result if c["license_id"] == "ALREADY-THERE"]
    assert len(matches) == 1


def test_get_candidates_hint_skips_unknown_id(
    matcher: AggregatedLicenseMatcher,
) -> None:
    """A hinted ID that isn't in the DB at all is silently skipped, not an
    error."""
    text = _words(30)

    result = matcher._get_candidates(
        MatchRequest(only_spdx=False, hint=["NO-SUCH-LICENSE"]), text
    )

    assert all(c["license_id"] != "NO-SUCH-LICENSE" for c in result)
