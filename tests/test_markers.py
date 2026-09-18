# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for license marker and heading detection."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring
# pylint: disable=protected-access

import sqlite3
import uuid
from collections.abc import Generator

import pytest

from licenseid.database import LicenseDatabase
from licenseid.markers import MarkerDetector
from licenseid.matcher import AggregatedLicenseMatcher

_GPL_FAMILY_IDS = (
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
)


def _make_gpl_detector(extra_ids: tuple[str, ...] = ()) -> MarkerDetector:
    """Build a MarkerDetector over an in-memory DB seeded with the GPL
    family (plus any extra_ids), for testing _detect_gpl_headers()
    directly rather than through the full matching pipeline."""
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_gpl_headers_{db_id}?mode=memory&cache=shared"
    # LicenseDatabase holds its own keep-alive connection open for the
    # instance's lifetime (see LicenseDatabase.__init__), and MarkerDetector
    # holds a reference to it below, so the shared in-memory DB stays alive
    # for as long as the returned detector does.
    db_manager = LicenseDatabase(db_path)

    insert = "INSERT INTO licenses (license_id, name, is_spdx) VALUES (?, ?, ?)"
    with sqlite3.connect(db_path, uri=True) as conn:
        for lic_id in _GPL_FAMILY_IDS + extra_ids:
            conn.execute(insert, (lic_id, lic_id, True))
        conn.commit()

    return MarkerDetector(db_manager)


@pytest.fixture
def gpl_detector() -> MarkerDetector:
    """MarkerDetector backed by a DB with the plain GPL/LGPL/AGPL family
    (no compound WITH-exception rows)."""
    return _make_gpl_detector()


@pytest.fixture
def gpl_detector_with_font_exception_row() -> MarkerDetector:
    """MarkerDetector whose DB also has a compound WITH-exception row,
    to exercise _detect_gpl_headers' DB-backed font-exception branch
    (real production DBs don't store compound IDs like this, so this
    fixture exists purely to reach that branch)."""
    return _make_gpl_detector(extra_ids=("GPL-2.0-only WITH Font-exception-2.0",))


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_markers_{db_id}?mode=memory&cache=shared"

    # pylint: disable-next=unused-variable
    db_manager = LicenseDatabase(db_path)  # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True),
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, "
            "is_osi_approved, is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("Apache-2.0", "Apache License 2.0", True, True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "MIT",
                (
                    "permission is hereby granted free of charge to any person "
                    "obtaining a copy"
                ),
            ),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "Apache-2.0",
                "apache license version 2.0 provides a grant of copyright license",
            ),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
    yield db_path
    keep_alive.close()


def test_spdx_identifier(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "Some source code\nSPDX-License-Identifier: MIT\nMore code"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"
    assert results[0]["score"] >= 0.95


def test_license_field(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "Metadata:\nLicense: Apache License 2.0\nVersion: 1.0"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "Apache-2.0"


def test_markdown_heading(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "# README\n\n## License\n\nMIT"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"


def test_ascii_heading_underline(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "LICENSE\n=======\n\nApache License 2.0"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "Apache-2.0"


def test_ascii_heading_box(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    text = "#################\n#    LICENSE    #\n#################\n\nMIT"
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"


def test_mixed_content_windowed_search(test_db: str) -> None:
    matcher = AggregatedLicenseMatcher(test_db)
    # A large README with license info buried
    text = (
        "Project Name\n"
        + "Junk text " * 100
        + "\nLicense\n"
        + "Permission is hereby granted free of charge to any person obtaining a copy"
        + "\n"
        + "More junk " * 100
    )
    results = matcher.match(text=text)
    assert len(results) > 0
    assert results[0]["license_id"] == "MIT"


# --- _detect_gpl_headers() -----------------------------------------------
#
# Characterization tests for MarkerDetector._detect_gpl_headers(), written
# directly against the method (bypassing AggregatedLicenseMatcher/detect())
# since that's the unit under test.  Written and verified against the
# CURRENT (unrefactored) implementation before extracting helper methods
# out of it, so a later refactor cannot silently change any of these rules.

_GPL2_GRANT_ONLY = (
    "This program is free software; you can redistribute it and/or "
    "modify it under the terms of the GNU General Public License as "
    "published by the Free Software Foundation; version 2 of the "
    "License."
)
_GPL2_GRANT_OR_LATER = (
    "This program is free software; you can redistribute it and/or "
    "modify it under the terms of the GNU General Public License as "
    "published by the Free Software Foundation; either version 2 of "
    "the License, or (at your option) any later version."
)


def test_gpl_headers_plain_grant_is_only(gpl_detector: MarkerDetector) -> None:
    """A bare 'version 2' grant with no or-later phrase is GPL-2.0-only."""
    candidates = gpl_detector._detect_gpl_headers(_GPL2_GRANT_ONLY)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-only"]


def test_gpl_headers_or_later_grant(gpl_detector: MarkerDetector) -> None:
    """The standard '...or (at your option) any later version' phrasing
    resolves to the -or-later variant."""
    candidates = gpl_detector._detect_gpl_headers(_GPL2_GRANT_OR_LATER)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


def test_gpl_headers_lgpl_modifier(gpl_detector: MarkerDetector) -> None:
    """The 'Lesser' modifier classifies as LGPL, not GPL."""
    text = (
        "Licensed under the GNU Lesser General Public License as "
        "published by the Free Software Foundation; version 2.1 of "
        "the License."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["LGPL-2.1-only"]


def test_gpl_headers_agpl_modifier(gpl_detector: MarkerDetector) -> None:
    """The 'Affero' modifier classifies as AGPL, not GPL."""
    text = (
        "Licensed under the GNU Affero General Public License as "
        "published by the Free Software Foundation; version 3 of "
        "the License."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["AGPL-3.0-only"]


def test_gpl_headers_version_without_decimal(gpl_detector: MarkerDetector) -> None:
    """'version 2' (no decimal point) normalises to 'GPL-2.0', not 'GPL-2'."""
    candidates = gpl_detector._detect_gpl_headers(_GPL2_GRANT_ONLY)
    assert candidates[0]["license_id"] == "GPL-2.0-only"


def test_gpl_headers_case_insensitive_modifier(gpl_detector: MarkerDetector) -> None:
    """A lower-cased 'gnu lesser general public license' still resolves
    to LGPL (the family regex and modifier classification are both
    case-insensitive)."""
    text = (
        "licensed under the gnu lesser general public license; "
        "version 2.1 of the license."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["LGPL-2.1-only"]


def test_gpl_headers_no_version_no_candidate(gpl_detector: MarkerDetector) -> None:
    """A GPL-family mention with no version number anywhere nearby
    produces no candidate at all for that match."""
    text = "Licensed under the GNU General Public License."
    candidates = gpl_detector._detect_gpl_headers(text)
    assert candidates == []


def test_gpl_headers_no_match_at_all(gpl_detector: MarkerDetector) -> None:
    """Text with no GPL-family mention returns no candidates."""
    candidates = gpl_detector._detect_gpl_headers(
        "This is the MIT License. Permission is hereby granted..."
    )
    assert candidates == []


def test_gpl_headers_duplicate_grant_deduped(gpl_detector: MarkerDetector) -> None:
    """Two mentions of the identical grant collapse to one candidate."""
    text = _GPL2_GRANT_ONLY + "\n\n" + _GPL2_GRANT_ONLY
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-only"]


def test_gpl_headers_multiple_distinct_grants(gpl_detector: MarkerDetector) -> None:
    """Two different, well-separated GPL-family grants (different family
    and version) in one document both appear as separate candidates.

    The two grants are kept over 1000 chars apart deliberately: see
    test_gpl_headers_nearby_grants_dont_bleed below for the case where
    they're close together instead.
    """
    text = (
        _GPL2_GRANT_ONLY
        + "\n\n"
        + "Unrelated padding text so the two grants don't share a "
        "lookahead window. "
        * 20
        + "\n\nA separately-licensed component is under the GNU Lesser "
        "General Public License; either version 3 of the License, or "
        "(at your option) any later version."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == [
        "GPL-2.0-only",
        "LGPL-3.0-or-later",
    ]


def test_gpl_headers_nearby_grants_dont_bleed(
    gpl_detector: MarkerDetector,
) -> None:
    """Regression test for a fixed bug: the or-later lookahead window is
    now capped at the *next* GPL-family match, so a second grant's own
    or-later wording can no longer leak into an earlier, nearby, plain
    grant's window. Here the first grant is a bare 'version 2' with no
    or-later wording of its own; a second GPL-family grant less than
    1000 chars later that IS or-later must not affect it."""
    text = (
        _GPL2_GRANT_ONLY
        + "\n\nA separately-licensed component is under the GNU Lesser "
        "General Public License; either version 3 of the License, or "
        "(at your option) any later version."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == [
        "GPL-2.0-only",
        "LGPL-3.0-or-later",
    ]


def test_gpl_headers_appendix_real_layout_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """Regression test for a fixed bug: the real, canonical GPL-2.0
    appendix text ('How to Apply These Terms to Your New Programs...')
    places the '<one line to give the program's name...>' placeholder,
    then a 'Copyright (C) <year> <name of author>' line, then the
    license grant sentence — in that order. The suppression check
    requires both anchors, in order, within a bounded backward window,
    so it correctly fires for the actual upstream boilerplate: a
    document consisting of (or quoting) the verbatim GPL-2.0 license
    text must not be misclassified as GPL-2.0-or-later from its own
    appendix example, since that example isn't a statement about this
    document's own licensing."""
    text = (
        "How to Apply These Terms to Your New Programs\n\n"
        "  To do so, attach the following notices to the program.\n\n"
        "    <one line to give the program's name and a brief idea of "
        "what it does.>\n"
        "    Copyright (C) <year>  <name of author>\n\n"
        "    This program is free software; you can redistribute it "
        "and/or modify it under the terms of the GNU General Public "
        "License as published by the Free Software Foundation; either "
        "version 2 of the License, or (at your option) any later "
        "version."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-only"]


def test_gpl_headers_appendix_placeholder_too_far_back_not_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """The backward lookback for the appendix anchors is bounded to 300
    chars (comfortably above the ~220-char gap measured in the real
    GPL-2.0 appendix), not an unbounded scan back to appendix_start.
    Both anchors are present here (placeholder + copyright line) to
    isolate the distance limit from the anchor-pairing requirement
    covered by the tests below — pushed well past 300 chars, they must
    NOT suppress the grant's or-later signal."""
    text = (
        "How to Apply These Terms to Your New Programs\n\n"
        "    <one line to give the program's name and a brief idea of "
        "what it does.>\n"
        "    Copyright (C) <year>  <name of author>\n\n"
        + ("Padding text to push the grant past the 300-char lookback. ") * 15
        + _GPL2_GRANT_OR_LATER
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


def test_gpl_headers_appendix_placeholder_without_copyright_not_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """Regression test for a bug found by review of the fix above: an
    earlier version of the appendix-suppression fix looked backward for
    the '<one line to give the program's name...>' placeholder ALONE,
    with no requirement that a 'Copyright (C)' line also sit between it
    and the grant. That let a document which merely quotes the
    placeholder elsewhere (e.g. contributor guidance on how to license
    new code, or a FAQ) wrongly suppress a real, separate, genuinely
    or-later grant that happens to follow within the lookback window —
    reproduced directly against that version: a CONTRIBUTING.md-style
    doc quoting the placeholder for reference, followed ~150 chars
    later by 'This project itself is licensed under the GNU General
    Public License, either version 2 ... or (at your option) any later
    version', was misclassified as GPL-2.0-only instead of
    GPL-2.0-or-later. Requiring the copyright-line anchor between the
    placeholder and the grant (matching the actual template structure)
    fixes this without reintroducing the original bug."""
    text = (
        "## Licensing your contribution\n\n"
        "For reference, here is the standard GPL guidance:\n\n"
        "How to Apply These Terms to Your New Programs\n\n"
        "    <one line to give the program's name and a brief idea of "
        "what it does.>\n\n"
        "## This project's actual license\n\n"
        "This project itself is licensed under the GNU General Public "
        "License, either version 2 of the License, or (at your option) "
        "any later version."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


def test_gpl_headers_appendix_copyright_before_placeholder_not_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """Adversarial: both the placeholder AND a 'Copyright (C)' line are
    present in the lookback window, but in the WRONG order relative to
    the real template (copyright line first, placeholder second) — this
    must not be treated as a match for the canonical structure."""
    text = (
        "How to Apply These Terms to Your New Programs\n\n"
        "    Copyright (C) <year>  <name of author>\n\n"
        "    <one line to give the program's name and a brief idea of "
        "what it does.>\n\n" + _GPL2_GRANT_OR_LATER
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


def test_gpl_headers_grant_before_appendix_not_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """Adversarial: the real grant comes BEFORE the appendix in the
    document (a common layout: notice at the top, full license text
    with its appendix pasted below), and the appendix's sample-notice
    phrase happens to land inside the grant's 1000-char lookahead
    window anyway. Suppression is keyed on position
    (``m.start() > appendix_start``), not just "phrase is somewhere in
    the window" — so this grant's or-later signal must NOT be
    suppressed."""
    text = (
        _GPL2_GRANT_OR_LATER + "\n\nHow to Apply These Terms to Your New Programs\n\n"
        "    <one line to give the program's name and a brief idea of "
        "what it does.>"
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


_TERMS_EXPLANATION_SENTENCE = (
    "specifies a version number of this License which applies to it "
    'and "any later version"'
)


def test_gpl_headers_terms_explanation_suppresses_or_later(
    gpl_detector: MarkerDetector,
) -> None:
    """GPL-2.0 Section 9's explanation of the 'or later' wording mentions
    the phrase without being a grant itself; a grant found close by
    (within 500 chars) must have its or-later signal suppressed."""
    text = (
        f"Section 9. Each version is given a distinguishing version "
        f"number. If the Program {_TERMS_EXPLANATION_SENTENCE}, you "
        "have the option of following that version or any later one. "
        + _GPL2_GRANT_OR_LATER
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-only"]


def test_gpl_headers_terms_explanation_far_away_not_suppressed(
    gpl_detector: MarkerDetector,
) -> None:
    """The same terms-explanation sentence, but far enough away (well
    over the 500-char window) from the grant, must NOT suppress the
    grant's own or-later signal — pins the direction of the distance
    check rather than just that suppression exists at all."""
    text = (
        f"Section 9. Each version is given a distinguishing version "
        f"number. If the Program {_TERMS_EXPLANATION_SENTENCE}, you "
        "have the option of following that version or any later one. "
        + ("Padding text to push the grant well past the 500-char window. ") * 15
        + _GPL2_GRANT_OR_LATER
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["GPL-2.0-or-later"]


def test_gpl_headers_terms_explanation_unrelated_grant_nearby(
    gpl_detector: MarkerDetector,
) -> None:
    """KNOWN RESIDUAL RISK, same bug class as the appendix false-positive
    fixed above, deliberately NOT fixed here: the terms-explanation
    suppression is a bare proximity check with no structural anchor, so
    a document that quotes GPL Section 9's exact wording for unrelated
    reference (e.g. a licensing FAQ) can wrongly suppress a real,
    separate or-later grant that happens to follow within 500 chars.
    Reproduced directly: a FAQ explaining "or later version" via the
    verbatim Section 9 sentence, followed shortly after by a project's
    own genuine or-later statement, is misclassified as GPL-2.0-only.

    Left unfixed (unlike the appendix case) because the anchor here is
    already much narrower — an exact, unusual legal sentence, not a
    generic instructional phrase — and the real, official GPL-2.0/3.0
    license text's own Section 9/14 wording doesn't actually trigger
    this path in the first place: GPL-2.0 section 9 says "the General
    Public License" (no "GNU" prefix, so _RE_GPL_FAMILY never matches
    it), and GPL-3.0 section 14's "GNU General Public License" mention
    has no digit immediately after "version" nearby (so _RE_GPL_VERSION
    never matches it, and the match is skipped via `continue` before
    reaching this suppression at all). Pinned here so a future change
    can't silently make this worse, and so the residual risk is
    visible rather than undiscovered."""
    sentence = (
        "specifies a version number of this License which applies to "
        'it and "any later version"'
    )
    text = (
        'Q: What does "or later version" mean in the GPL?\n'
        f"A: Section 9 of the GPL {sentence}, meaning you may choose.\n\n"
        "This project itself is licensed under the GNU General Public "
        "License, either version 2 of the License, or (at your option) "
        "any later version."
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == [
        "GPL-2.0-only"  # KNOWN GAP: arguably should be GPL-2.0-or-later
    ]


_FONT_EXCEPTION_TEXT = (
    "As a special exception, if you create a document which uses this "
    "font, and embed this font or unaltered portions of this font into "
    "the document, this font does not by itself cause the resulting "
    "document to be covered by the GNU General Public License."
)


def test_gpl_headers_font_exception_synthetic(gpl_detector: MarkerDetector) -> None:
    """GPL + font-exception phrase, with no compound WITH-exception row
    in the DB (the realistic case — production DBs don't store compound
    IDs): falls back to a synthetic candidate for the WITH expression."""
    text = _GPL2_GRANT_ONLY + "\n\n" + _FONT_EXCEPTION_TEXT
    candidates = gpl_detector._detect_gpl_headers(text)
    assert len(candidates) == 1
    assert candidates[0]["license_id"] == "GPL-2.0-only WITH Font-exception-2.0"
    assert candidates[0]["score"] == pytest.approx(0.88)


def test_gpl_headers_font_exception_db_backed(
    gpl_detector_with_font_exception_row: MarkerDetector,
) -> None:
    """When the DB does have a matching compound-ID row, that row's
    details are used instead of a synthetic candidate."""
    text = _GPL2_GRANT_ONLY + "\n\n" + _FONT_EXCEPTION_TEXT
    candidates = gpl_detector_with_font_exception_row._detect_gpl_headers(text)
    assert len(candidates) == 1
    assert candidates[0]["license_id"] == "GPL-2.0-only WITH Font-exception-2.0"
    assert candidates[0]["score"] == pytest.approx(0.88)


def test_gpl_headers_font_exception_not_applied_to_lgpl(
    gpl_detector: MarkerDetector,
) -> None:
    """The font-exception is GPL-specific (family == "GPL"); an LGPL
    grant alongside the same font-exception phrase must NOT produce a
    WITH-exception candidate — only the plain LGPL one."""
    text = (
        "Licensed under the GNU Lesser General Public License; "
        "version 2.1 of the License.\n\n" + _FONT_EXCEPTION_TEXT
    )
    candidates = gpl_detector._detect_gpl_headers(text)
    assert [c["license_id"] for c in candidates] == ["LGPL-2.1-only"]
