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
from unittest import mock

import pytest
from matcher_db import PROSE, Lic, seeded_db

from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.errors import InvalidInputError
from licenseid.normalize import normalize_text
from licenseid.ranking import DEP_PENALTY
from licenseid.shorttext import match_short_text

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


def test_default_db_path_used_when_no_path_given(
    marker_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No db_path falls back to get_default_db_path(), and the returned path
    is what the matcher actually opens. A blank one is refused."""
    fake = mock.create_autospec(get_default_db_path, return_value=marker_db)
    monkeypatch.setattr("licenseid.detector.get_default_db_path", fake)

    with pytest.raises(InvalidInputError, match="database: missing: db_path"):
        LicenseDetector("")
    matcher = LicenseDetector(None)

    assert fake.call_count == 1
    results = matcher.detect("MIT")
    assert [r["expression"] for r in results] == ["MIT"]


def test_explicit_db_path_skips_default_lookup(
    marker_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller-supplied path must not consult the default location."""
    fake = mock.create_autospec(get_default_db_path, return_value=marker_db)
    monkeypatch.setattr("licenseid.detector.get_default_db_path", fake)

    matcher = LicenseDetector(marker_db)

    fake.assert_not_called()
    assert matcher.detect("MIT")[0]["expression"] == "MIT"


# -- SPDX-License-Identifier short circuit ---------------------------------


def test_spdx_tag_in_source_file_short_circuits(marker_db: str) -> None:
    """A tag in a file long enough for marker detection is the final
    answer, with the flags of the database row it resolved to."""
    text = (
        "/*\n * Copyright (c) 2026 Example Corp.\n"
        f" * SPDX-License-Identifier: MIT\n{PROSE} */\n"
    )

    results = LicenseDetector(marker_db).detect(text=text)

    # The result's shape for a tag: test_public_result.
    assert [(r["expression"], r["method"]) for r in results] == [("MIT", "tag")]
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

    results = LicenseDetector(marker_db).detect(text=text)

    assert {r["expression"] for r in results} == {"MIT", "Apache-2.0"}
    assert len(results) == 2
    assert [r["score"] for r in results] == [1.0, 1.0]


def test_repeated_spdx_tag_returns_one_match(marker_db: str) -> None:
    """The same tag repeated is one result: MarkerDetector.detect()
    already deduplicates by license_id before the matcher sees it."""
    text = (
        "/*\n * SPDX-License-Identifier: MIT\n"
        f"{PROSE} * SPDX-License-Identifier: MIT\n */\n"
    )

    results = LicenseDetector(marker_db).detect(text=text)

    assert [r["expression"] for r in results] == ["MIT"]


def test_license_field_marker_does_not_short_circuit(marker_db: str) -> None:
    """A "License:" field scores 0.95, not 1.0, so it is only a ranking
    signal: the result comes from Tier 2 scoring and is below 1.0."""
    text = f"/*\n * License: MIT\n{PROSE} */\n"

    results = LicenseDetector(marker_db).detect(text=text)

    assert results[0]["expression"] == "MIT"
    assert results[0]["score"] < 1.0


def test_source_file_without_any_marker_has_no_match(marker_db: str) -> None:
    """Prose with no tag and no license text matches nothing."""
    text = f"/*\n * There is no machine readable tag in this file.\n{PROSE} */\n"

    assert not LicenseDetector(marker_db).detect(text=text)


# -- Bare deprecated ID disambiguation -------------------------------------


@pytest.mark.parametrize(
    ("text", "license_id"),
    [
        ("Licensed under GPL-2.0 or later", "GPL-2.0-or-later"),
        ("Licensed under GPL-2.0 only", "GPL-2.0-only"),
    ],
)
def test_bare_deprecated_id_with_prose(gpl_db: str, text: str, license_id: str) -> None:
    """The phrase resolves to the canonical ID, with the flags of its
    database row. (The result's shape: test_public_result.)"""
    results = LicenseDetector(gpl_db).detect(text)
    assert [(r["expression"], r["method"]) for r in results] == [(license_id, "id")]
    assert results[0]["is_osi_approved"] is True


def test_disambiguated_id_missing_from_database(gpl_db: str) -> None:
    """The disambiguated ID is returned even when this database has no row
    for it. Current behaviour, not a documented contract: it comes from a
    fixed table of canonical SPDX IDs. The database is the List, so it is
    not on it, and nobody judged it: the flags are None, not a false
    "no"."""
    results = LicenseDetector(gpl_db).detect("Licensed under GPL-3.0 or later")

    assert [r["expression"] for r in results] == ["GPL-3.0-or-later"]
    assert results[0]["is_spdx"] is False
    assert results[0]["is_osi_approved"] is None
    assert results[0]["is_fsf_libre"] is None


def test_canonical_id_is_not_disambiguated(gpl_db: str) -> None:
    """An already-canonical ID is matched as an ID, not treated as a bare
    deprecated alias with a "-only" suffix bolted on."""
    results = LicenseDetector(gpl_db).detect("GPL-2.0-or-later")

    assert [r["expression"] for r in results] == ["GPL-2.0-or-later"]


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
    results = LicenseDetector(with_db).detect(license_id="MIT WITH Font-exception-2.0")

    assert [r["expression"] for r in results] == ["MIT WITH Font-exception-2.0"]
    assert results[0]["score"] == 1.0


@pytest.mark.parametrize(
    "expression",
    ["MIT WITH GCC-exception-2.0", "Apache-2.0 WITH Font-exception-2.0"],
)
def test_with_expression_half_missing_from_db(with_db: str, expression: str) -> None:
    """One half has no row in this database. It was a match not on this List;
    an ID the List does not have is no operand, as resolve() reads it,
    so the declared ID matches nothing."""
    assert not LicenseDetector(with_db).detect(license_id=expression)


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
    keeps it. Either way the exact-name match leads. resolve() reads the
    listed name first, so detect() answers it alone; the name tier still
    ranks both for a name it is given."""
    deprecated = "deprecated" in request.node.callspec.id
    text = "GNU General Public License v2.0 only"

    # The raw scores of the name tier.
    matcher = LicenseDetector(alias_db)
    results = match_short_text(matcher.db, normalize_text(text), text)
    public = matcher.detect(text)
    assert [(r["expression"], r["method"]) for r in public] == [
        ("GPL-2.0-only", "name")
    ]

    assert [r["license_id"] for r in results] == ["GPL-2.0-only", "GPL-2.0"]
    assert results[0]["score"] == pytest.approx(1.02)
    assert results[1]["score"] == pytest.approx(
        1.01 - (DEP_PENALTY if deprecated else 0)
    )


# -- A partially built database ---------------------------------------------


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


def test_an_id_without_a_row_is_answered_by_tier_0(broken_successor_db: str) -> None:
    """A deprecated ID whose successor has no row of its own: Tier 0 answers
    the successor it names; no phantom row is read."""
    matcher = LicenseDetector(broken_successor_db)

    assert [r["expression"] for r in matcher.detect("Unlicense")] == ["Unlicense-2.0"]
