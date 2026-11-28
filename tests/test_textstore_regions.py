# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The regions of the variable parts in the stored form of a corpus
(``textstore``): they read back with the codes, and a stored form whose
regions are not exactly those of the build (swapped, cut, out of range, of
another shape, without their patterns) gives None, so the caller builds
without them: the check finds it, and the reader refuses a region that does
not index its text whatever the check says."""
# pylint: disable=missing-function-docstring

import json

import pytest
from textstore_rows import checks_of, read_back

from licenseid import textstore
from licenseid.textcorpus import TextCorpus, TextRow, VarRegion
from licenseid.textstore import (
    CORE_VARS,
    PATTERNS,
    TEXT_VARS,
    StoredRow,
    stored_rows,
)

A_REGIONS = (VarRegion(0, 2, ".+"), VarRegion(4, 4, "(x)?"))
ROWS = (
    TextRow(
        "A-1.0",
        "alpha beta gamma delta epsilon",
        "beta gamma",
        ("A-1.0",),
        A_REGIONS,
        (VarRegion(1, 2, ".+"),),
    ),
    TextRow("B-1.0", "one two three", None, ("B-1.0",), (VarRegion(2, 3, "a|b"),)),
    TextRow("C-1.0", "one two three four", None, ("C-1.0",)),
)
# The same rows as a database gives them: no regions (no templates there).
READ = tuple(TextRow(r.license_id, r.text, r.core, r.group) for r in ROWS)


def _stored() -> list[StoredRow]:
    return stored_rows(TextCorpus.build(ROWS))


CHECKS = checks_of(READ, _stored())


def restore(rows: object, stored: list[StoredRow]) -> TextCorpus | None:
    """The corpus read back from *stored* under the checks of the build."""
    return read_back(rows, stored, CHECKS)  # type: ignore[arg-type]


def _with(kind: str, owner: str, body: str | None) -> list[StoredRow]:
    """The stored rows with the body of (*kind*, *owner*) changed, or the row
    dropped (None)."""
    rows = [row for row in _stored() if (row[0], row[1]) != (kind, owner)]
    return rows if body is None else [*rows, (kind, owner, body)]


def test_the_regions_read_back_with_the_codes() -> None:
    built = TextCorpus.build(ROWS)
    restored = restore(READ, stored_rows(built))  # the checks of this build
    assert restored is not None
    assert restored == built
    assert restored.entries[0].text.regions == A_REGIONS
    core = restored.entries[0].core
    assert core is not None and core.regions == (VarRegion(1, 2, ".+"),)
    assert not restored.entries[2].text.regions


def test_the_patterns_are_stored_once_in_order() -> None:
    rows = {(kind, owner): body for kind, owner, body in _stored()}
    assert json.loads(rows[(PATTERNS, "")]) == ["(x)?", ".+", "a|b"]
    assert json.loads(rows[(TEXT_VARS, "A-1.0")]) == [[0, 2, 1], [4, 4, 0]]
    assert json.loads(rows[(CORE_VARS, "A-1.0")]) == [[1, 2, 1]]
    assert (TEXT_VARS, "C-1.0") not in rows  # no regions, no row


def test_the_coding_is_version_2() -> None:
    assert textstore.CODING_VERSION == 2


@pytest.mark.parametrize(
    "stored",
    [
        _with(TEXT_VARS, "A-1.0", None),
        _with(CORE_VARS, "A-1.0", None),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,2],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1],[4,4,3]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1],[4,6,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1],[4,3,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[-1,2,1],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,true],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1.0],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", '{"a": 1}'),
        _with(TEXT_VARS, "A-1.0", "not json"),
        _with(TEXT_VARS, "C-1.0", "[[0,1,0]]"),
        _with(CORE_VARS, "B-1.0", "[[0,1,0]]"),
        _with(PATTERNS, "", None),
        _with(PATTERNS, "", '["(x)?",".+"]'),
        _with(PATTERNS, "", '[".+","(x)?","a|b"]'),
        _with(PATTERNS, "", '"not a list"'),
        _with(PATTERNS, "", "[1]"),
    ],
    ids=[
        "text-vars-missing",
        "core-vars-missing",
        "text-vars-cut",
        "pattern-swapped",
        "pattern-out-of-range",
        "end-past-text",
        "end-before-start",
        "negative-start",
        "bool-number",
        "float-number",
        "short-item",
        "not-a-list",
        "not-json",
        "vars-of-a-text-without",
        "vars-of-a-missing-core",
        "patterns-missing",
        "patterns-cut",
        "patterns-swapped",
        "patterns-not-a-list",
        "patterns-not-strings",
    ],
)
def test_regions_not_of_the_build_give_none(stored: list[StoredRow]) -> None:
    assert restore(READ, stored) is None


@pytest.mark.parametrize(
    "stored",
    [
        _with(TEXT_VARS, "A-1.0", "[[0,2,1],[4,6,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,1],[4,3,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[-1,2,1],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2,true],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "[[0,2],[4,4,0]]"),
        _with(TEXT_VARS, "A-1.0", "not json"),
        _with(CORE_VARS, "A-1.0", "[[1,2,9]]"),
        _with(PATTERNS, "", '"not a list"'),
        _with(PATTERNS, "", "[" * 100_000),
    ],
    ids=[
        "end-past-text",
        "end-before-start",
        "negative-start",
        "bool-number",
        "short-item",
        "not-json",
        "core-pattern-out-of-range",
        "patterns-not-a-list",
        "patterns-nested-too-deep",
    ],
)
def test_regions_that_do_not_read_give_none_under_their_own_check(
    stored: list[StoredRow],
) -> None:
    """Checks made for the damaged rows: the reader refuses them all the
    same."""
    assert read_back(READ, stored, checks_of(READ, stored)) is None


def test_a_corpus_without_regions_reads_back() -> None:
    built = TextCorpus.build(READ)
    stored = stored_rows(built)
    assert read_back(READ, stored, checks_of(READ, stored)) == built


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (None, ()),
        ("[]", ()),
        ("[[0,3,0]]", (VarRegion(0, 3, "p"),)),
        ("[[3,3,0]]", (VarRegion(3, 3, "p"),)),
        ("[[0,4,0]]", None),
        ("[[2,1,0]]", None),
        ("[[-1,1,0]]", None),
        ("[[0,1,1]]", None),
        ("[[0,1,-1]]", None),
        ("[" * 100_000, None),
    ],
    ids=[
        "none",
        "empty",
        "whole",
        "point-at-end",
        "past-end",
        "reversed",
        "negative",
        "no-pattern",
        "negative-pattern",
        "nested-too-deep",
    ],
)
def test_a_region_is_read_only_inside_its_text(
    body: str | None, expected: tuple[VarRegion, ...] | None
) -> None:
    """The check of the build would refuse these too; the reader does not
    rely on it (a region must index its text whatever the check says)."""
    # pylint: disable-next=protected-access
    assert textstore._parse_regions(body, 3, ["p"]) == expected


def test_json_nested_too_deep_is_none() -> None:
    """``json`` raises RecursionError, not ValueError, past its depth."""
    # pylint: disable-next=protected-access
    assert textstore._loaded("[" * 100_000) is None


def test_a_patterns_row_nested_too_deep_gives_none() -> None:
    assert restore(READ, _with(PATTERNS, "", "[" * 100_000)) is None
