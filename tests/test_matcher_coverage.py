# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for the matcher paths the other suites never reach.

Each test names the behaviour it pins, not the line it covers: the
default-database fallback, the SPDX-tag short circuit, bare deprecated
ID disambiguation, WITH expressions whose halves are unknown to this
database, the deprecated-alias penalty in short-text matching, and the
windowed keyword search used for mixed content.
"""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from matcher_db import PROSE, Lic, seeded_db

from licenseid.database import get_default_db_path
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.ranking import DEP_PENALTY
from licenseid.types import CandidateMatch, MatchRequest

_MIT_TEXT = "permission is hereby granted free of charge to any person obtaining a copy"
_APACHE_TEXT = "apache license version 2.0 terms and conditions for use reproduction"


@pytest.fixture
def marker_db() -> Generator[str, None, None]:
    """MIT and Apache-2.0, both indexed, for SPDX-tag marker tests."""
    yield from seeded_db(
        "test_cov_marker",
        [
            Lic("MIT", "MIT License", True, True, True, search_text=_MIT_TEXT),
            Lic(
                "Apache-2.0",
                "Apache License 2.0",
                True,
                True,
                True,
                search_text=_APACHE_TEXT,
            ),
        ],
    )


@pytest.fixture
def gpl_db() -> Generator[str, None, None]:
    """The GPL-2.0 family: canonical pair plus the deprecated bare alias.

    GPL-3.0-or-later is deliberately absent, so a text disambiguated to
    it has no database row to read flags from.
    """
    yield from seeded_db(
        "test_cov_gpl",
        [
            Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True),
            Lic(
                "GPL-2.0-or-later",
                "GNU General Public License v2.0 or later",
                True,
                True,
            ),
            Lic(
                "GPL-2.0",
                "GNU General Public License v2.0",
                True,
                True,
                False,
                True,
                "GPL-2.0-only",
            ),
        ],
    )


# -- Default database path -------------------------------------------------


@pytest.mark.parametrize("db_path_arg", [None, ""], ids=["none", "empty"])
def test_default_db_path_used_when_no_path_given(
    marker_db: str, monkeypatch: pytest.MonkeyPatch, db_path_arg: str | None
) -> None:
    """No usable db_path falls back to get_default_db_path(), and the
    returned path is what the matcher actually opens."""
    fake = mock.create_autospec(get_default_db_path, return_value=marker_db)
    monkeypatch.setattr("licenseid.matcher.get_default_db_path", fake)

    matcher = AggregatedLicenseMatcher(db_path_arg)

    assert fake.call_count == 1
    results = matcher.match("MIT")
    assert [r["license_id"] for r in results] == ["MIT"]


def test_explicit_db_path_skips_default_lookup(
    marker_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller-supplied path must not consult the default location."""
    fake = mock.create_autospec(get_default_db_path, return_value=marker_db)
    monkeypatch.setattr("licenseid.matcher.get_default_db_path", fake)

    matcher = AggregatedLicenseMatcher(marker_db)

    fake.assert_not_called()
    assert matcher.match("MIT")[0]["license_id"] == "MIT"


# -- SPDX-License-Identifier short circuit ---------------------------------


def test_spdx_tag_in_source_file_short_circuits(marker_db: str) -> None:
    """A tag in a file long enough for marker detection is the final
    answer, with the flags of the database row it resolved to."""
    text = (
        "/*\n * Copyright (c) 2026 Example Corp.\n"
        f" * SPDX-License-Identifier: MIT\n{PROSE} */\n"
    )

    results = AggregatedLicenseMatcher(marker_db).match(text=text)

    assert [r["license_id"] for r in results] == ["MIT"]
    assert results[0]["score"] == 1.0
    assert results[0]["similarity"] == 1.0
    assert results[0]["coverage"] == 1.0
    assert results[0]["is_spdx"] is True
    assert results[0]["is_osi_approved"] is True
    assert results[0]["is_fsf_libre"] is True


def test_two_spdx_tags_return_both_matches(marker_db: str) -> None:
    """Two different tags in one file yield both IDs, each scored 1.0. (The
    order of the results is not asserted.)"""
    text = (
        "/*\n * SPDX-License-Identifier: MIT\n"
        f"{PROSE} * SPDX-License-Identifier: Apache-2.0\n */\n"
    )

    results = AggregatedLicenseMatcher(marker_db).match(text=text)

    assert {r["license_id"] for r in results} == {"MIT", "Apache-2.0"}
    assert len(results) == 2
    assert [r["score"] for r in results] == [1.0, 1.0]


def test_repeated_spdx_tag_returns_one_match(marker_db: str) -> None:
    """The same tag repeated is one result: MarkerDetector.detect()
    already deduplicates by license_id before the matcher sees it."""
    text = (
        "/*\n * SPDX-License-Identifier: MIT\n"
        f"{PROSE} * SPDX-License-Identifier: MIT\n */\n"
    )

    results = AggregatedLicenseMatcher(marker_db).match(text=text)

    assert [r["license_id"] for r in results] == ["MIT"]


def test_license_field_marker_does_not_short_circuit(marker_db: str) -> None:
    """A "License:" field scores 0.95, not 1.0, so it is only a ranking
    signal: the result comes from Tier 2 scoring and is below 1.0."""
    text = f"/*\n * License: MIT\n{PROSE} */\n"

    results = AggregatedLicenseMatcher(marker_db).match(text=text)

    assert results[0]["license_id"] == "MIT"
    assert results[0]["score"] < 1.0


def test_source_file_without_any_marker_has_no_match(marker_db: str) -> None:
    """Prose with no tag and no license text matches nothing."""
    text = f"/*\n * There is no machine readable tag in this file.\n{PROSE} */\n"

    assert not AggregatedLicenseMatcher(marker_db).match(text=text)


# -- Bare deprecated ID disambiguation -------------------------------------


def test_bare_deprecated_id_with_or_later_prose(gpl_db: str) -> None:
    """The phrase 'GPL-2.0 or later' resolves to the canonical or-later
    ID, with the flags of its database row."""
    results = AggregatedLicenseMatcher(gpl_db).match("Licensed under GPL-2.0 or later")

    assert [r["license_id"] for r in results] == ["GPL-2.0-or-later"]
    assert results[0]["score"] == 1.02
    assert results[0]["is_osi_approved"] is True


def test_bare_deprecated_id_with_only_prose(gpl_db: str) -> None:
    """The phrase 'GPL-2.0 only' resolves to the -only ID."""
    results = AggregatedLicenseMatcher(gpl_db).match("Licensed under GPL-2.0 only")

    assert [r["license_id"] for r in results] == ["GPL-2.0-only"]
    assert results[0]["score"] == 1.02


def test_disambiguated_id_missing_from_database(gpl_db: str) -> None:
    """The disambiguated ID is returned even when this database has no row
    for it. Current behaviour, not a documented contract: it comes from a
    fixed table of canonical SPDX IDs, so is_spdx is assumed true, and the
    approval flags default to false although the real license is approved."""
    results = AggregatedLicenseMatcher(gpl_db).match("Licensed under GPL-3.0 or later")

    assert [r["license_id"] for r in results] == ["GPL-3.0-or-later"]
    assert results[0]["is_spdx"] is True
    assert results[0]["is_osi_approved"] is False
    assert results[0]["is_fsf_libre"] is False


def test_canonical_id_is_not_disambiguated(gpl_db: str) -> None:
    """An already-canonical ID is matched as an ID, not treated as a bare
    deprecated alias with a "-only" suffix bolted on."""
    results = AggregatedLicenseMatcher(gpl_db).match("GPL-2.0-or-later")

    assert [r["license_id"] for r in results] == ["GPL-2.0-or-later"]


# -- WITH expressions ------------------------------------------------------


@pytest.fixture
def with_db() -> Generator[str, None, None]:
    """MIT plus one exception row; Apache-2.0 and GCC-exception-2.0 are
    known to SPDX but deliberately absent here."""
    yield from seeded_db(
        "test_cov_with",
        [Lic("MIT", "MIT License", True, True, True, search_text=_MIT_TEXT)],
        exception_ids=["Font-exception-2.0"],
    )


def test_with_expression_both_halves_known(with_db: str) -> None:
    results = AggregatedLicenseMatcher(with_db).match(
        license_id="MIT WITH Font-exception-2.0"
    )

    assert [r["license_id"] for r in results] == ["MIT WITH Font-exception-2.0"]
    assert results[0]["score"] == 1.0


@pytest.mark.parametrize(
    "expression", ["MIT WITH GCC-exception-2.0", "Apache-2.0 WITH Font-exception-2.0"]
)
def test_with_expression_half_missing_from_db(with_db: str, expression: str) -> None:
    """One half has no row in this database: a valid SPDX expression still,
    so it matches, but neither OSI nor FSF can be claimed for it."""
    results = AggregatedLicenseMatcher(with_db).match(license_id=expression)
    assert [r["license_id"] for r in results] == [expression]
    assert results[0]["is_spdx"] is True
    assert results[0]["is_osi_approved"] is False
    assert results[0]["is_fsf_libre"] is False


# -- Deprecated penalty in short-text matching -----------------------------


@pytest.fixture(params=[True, False], ids=["deprecated", "current"])
def alias_db(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """GPL-2.0-only plus a same-family alias that is deprecated or not,
    so the penalty can be measured against its own absence."""
    deprecated: bool = request.param
    yield from seeded_db(
        f"test_cov_alias_{int(deprecated)}",
        [
            Lic("GPL-2.0-only", "GNU General Public License v2.0 only", True, True),
            Lic(
                "GPL-2.0",
                "GNU General Public License v2.0",
                True,
                True,
                False,
                deprecated,
                "GPL-2.0-only" if deprecated else None,
            ),
        ],
    )


def test_deprecated_alias_is_penalised_in_short_text(
    alias_db: str, request: pytest.FixtureRequest
) -> None:
    """The alias matches the input name by token set (1.00 + 0.01 flex
    bonus). Deprecated, it loses DEP_PENALTY from that 1.01; current, it
    keeps it. Either way the exact-name match leads."""
    deprecated = "deprecated" in request.node.callspec.id

    results = AggregatedLicenseMatcher(alias_db).match(
        "GNU General Public License v2.0 only"
    )

    assert [r["license_id"] for r in results] == ["GPL-2.0-only", "GPL-2.0"]
    assert results[0]["score"] == pytest.approx(1.02)
    assert results[1]["score"] == pytest.approx(
        1.01 - (DEP_PENALTY if deprecated else 0)
    )


# -- Mixed content: windowed keyword sections ------------------------------


@pytest.fixture
def mixed_db() -> Generator[str, None, None]:
    """Two indexed licenses; only Acme-1.0's name is close to the input."""
    yield from seeded_db(
        "test_cov_mixed",
        [
            Lic(
                "Acme-1.0",
                "Acme Public License, Version 1.0",
                True,
                True,
                search_text=(
                    "acme public license version 1.0 you may use and redistribute"
                    " this software under the license terms"
                ),
            ),
            Lic(
                "Beta-2.0",
                "Beta Source License",
                search_text=(
                    "beta source license version 2.0 redistribution of this"
                    " software in source form is permitted"
                ),
            ),
        ],
    )


def test_mixed_content_keyword_sections(mixed_db: str) -> None:
    """A misspelt license name in a short notice: too weak for the Tier 0
    shortcut (0.87 < 1.0), so the windowed keyword search runs. It adds
    the near-name match as a candidate and skips every ID it has already
    seen -- both across the two "licens" windows and between the name
    match and the FTS window that re-finds it."""
    text = (
        "Distributed under the Acme Publik License, Version 1.0. See the LICENSE file."
    )
    matcher = AggregatedLicenseMatcher(mixed_db)

    results = matcher.match(text=text)
    found = [r["license_id"] for r in results]

    assert found == ["Acme-1.0", "Beta-2.0"]
    assert results[0]["score"] > results[1]["score"]

    # Asserted on the section search itself: a duplicate candidate would be
    # swallowed by the merge in _run_tier1_and_tier2(), which deduplicates
    # again, so the public result alone cannot show that this step is clean.
    sectioned = matcher._match_mixed_content(MatchRequest(), text)
    assert [c["license_id"] for c in sectioned] == ["Acme-1.0", "Beta-2.0"]


@pytest.fixture
def broken_successor_db() -> Generator[str, None, None]:
    """A deprecated row pointing at a successor that has no row of its
    own -- a partially built database."""
    yield from seeded_db(
        "test_cov_broken",
        [
            Lic(
                "Unlicense",
                "The Unlicense",
                True,
                False,
                False,
                True,
                "Unlicense-2.0",
            ),
            Lic("MIT", "MIT License", True, True, True, search_text=_MIT_TEXT),
        ],
    )


def test_mixed_content_skips_id_without_a_row(broken_successor_db: str) -> None:
    """A section resolving to a successor ID with no database row yields
    no candidate rather than a row-less phantom.

    Called directly: through match() the same input is answered by Tier 0
    before mixed content runs (asserted below).
    """
    matcher = AggregatedLicenseMatcher(broken_successor_db)

    assert not matcher._match_mixed_content(MatchRequest(), "Unlicense")
    assert [r["license_id"] for r in matcher.match("Unlicense")] == ["Unlicense-2.0"]


# -- The windowed search that augments Tier 1 --------------------------------


@pytest.mark.parametrize(
    "case",  # (candidates found, text is a standalone license, windowed search runs)
    [
        pytest.param((0, True, True), id="nothing-found-even-if-pure"),
        pytest.param((4, False, True), id="thin-results-on-mixed-text"),
        pytest.param((5, False, False), id="enough-results-on-mixed-text"),
        pytest.param((4, True, False), id="thin-results-on-pure-text"),
    ],
)
def test_the_windowed_search_runs_for_no_or_thin_results_on_mixed_text(
    ordering_matcher: AggregatedLicenseMatcher,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: tuple[int, bool, bool],
) -> None:
    """Fewer than five candidates on text that is not a standalone license
    (or none at all) also gets the windowed keyword search; pure text with
    a few candidates does not."""
    found, pure, windowed = case
    text = "filler word " * 20
    candidates = [
        CandidateMatch(license_id=f"L-{i}.0", search_text="") for i in range(found)
    ]
    monkeypatch.setattr(
        ordering_matcher, "_get_candidates", lambda *_args: list(candidates)
    )
    windowed_search = mock.Mock(return_value=[])
    monkeypatch.setattr(ordering_matcher, "_match_mixed_content", windowed_search)
    if pure:
        license_file = tmp_path / "LICENSE"
        license_file.write_text(text, encoding="utf-8")
        ordering_matcher.match(file_path=str(license_file))
    else:
        ordering_matcher.match(text=text)

    assert windowed_search.called is windowed
