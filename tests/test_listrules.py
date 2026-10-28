# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The pure rules of the SPDX License List (`licenseid.listrules`)."""

import pytest
from list_entries import exc_entry, lic_entry

from licenseid import listrules
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry


def _successor(*entries: SpdxLicenseEntry) -> str | None:
    """The successor of the first entry, given all of them."""
    return listrules.superseded_license(
        entries[0],
        listrules.active_ids(entries),
        listrules.active_ids_by_name(entries),
    )


def test_empty_inputs() -> None:
    """Nothing in, nothing out."""
    assert listrules.active_ids([]) == set()
    assert not listrules.active_ids_by_name([])
    assert not listrules.active_exceptions_by_name([])


@pytest.mark.parametrize(
    ("deprecated", "expected"),
    [(None, False), (False, False), (True, True)],
    ids=["absent", "false", "true"],
)
def test_is_deprecated(deprecated: bool | None, expected: bool) -> None:
    """A missing flag means in use."""
    assert listrules.is_deprecated(lic_entry("A", deprecated=deprecated)) is expected


def test_active_ids_skips_deprecated_and_reads_a_missing_flag_as_active() -> None:
    """Deprecated IDs are not in use."""
    entries = [
        lic_entry("A", deprecated=None),
        lic_entry("B", deprecated=True),
        lic_entry("C"),
    ]
    assert listrules.active_ids(entries) == {"A", "C"}


def test_active_ids_by_name_folds_case_and_keeps_order() -> None:
    """Names fold case; IDs keep the list order."""
    entries = [
        lic_entry("A", "Same Name"),
        lic_entry("Z", "same NAME", deprecated=None),
        lic_entry("D", "Same Name", deprecated=True),
        lic_entry("E", "Other"),
    ]
    assert listrules.active_ids_by_name(entries) == {
        "same name": ["A", "Z"],
        "other": ["E"],
    }


@pytest.mark.parametrize(
    ("deprecated", "has_text", "expected"),
    [
        (False, True, True),
        (False, False, False),
        (True, True, True),
        (True, False, True),
        (None, False, False),
    ],
    ids=["active-text", "active-bare", "dep-text", "dep-bare", "flag-absent"],
)
def test_kept(deprecated: bool | None, has_text: bool, expected: bool) -> None:
    """A text keeps a licence; a deprecated one is kept without."""
    assert listrules.kept(lic_entry("A", deprecated=deprecated), has_text) is expected


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        # '+' with its -or-later in use
        ([lic_entry("X+", deprecated=True), lic_entry("X-or-later")], "X-or-later"),
        # '+' without it
        ([lic_entry("X+", deprecated=True)], None),
        # '+' whose -or-later is itself deprecated: not in use
        (
            [
                lic_entry("X+", deprecated=True),
                lic_entry("X-or-later", deprecated=True),
            ],
            None,
        ),
        # the '+' branch ignores the name
        (
            [
                lic_entry("X+", "Same", True),
                lic_entry("Y", "Same"),
            ],
            None,
        ),
        # '+' wins over a lone holder of the name
        (
            [
                lic_entry("X+", "Same", True),
                lic_entry("Y", "Same"),
                lic_entry("X-or-later", "Q"),
            ],
            "X-or-later",
        ),
        # a rename
        ([lic_entry("O", "Nm", True), lic_entry("N", "NM")], "N"),
        # two holders
        (
            [lic_entry("O", "Nm", True), lic_entry("A", "Nm"), lic_entry("B", "nm")],
            None,
        ),
        # a deprecated holder does not count
        ([lic_entry("O", "Nm", True), lic_entry("P", "Nm", True)], None),
        # the split, by ID
        ([lic_entry("G", "Nm", True), lic_entry("G-only", "Nm")], None),
        ([lic_entry("G", "Nm", True), lic_entry("G-or-later", "Nm")], None),
        # a similar ID is no split
        ([lic_entry("G", "Nm", True), lic_entry("G-only2", "Nm")], "G-only2"),
        ([lic_entry("G", "Nm", True), lic_entry("H-only", "Nm")], "H-only"),
        # a '+' ID has no rename reading, and ends with '+' only at the end
        ([lic_entry("A+B", "Nm", True), lic_entry("C", "Nm")], "C"),
    ],
    ids=[
        "plus",
        "plus-absent",
        "plus-or-later-deprecated",
        "plus-ignores-name",
        "plus-over-name",
        "rename",
        "two-holders",
        "deprecated-holder",
        "only-split",
        "or-later-split",
        "only-lookalike",
        "other-only",
        "plus-inside",
    ],
)
def test_superseded_license(
    entries: list[SpdxLicenseEntry], expected: str | None
) -> None:
    """Only the '+' token and a unique rename give a successor."""
    assert _successor(*entries) == expected


def test_superseded_license_with_empty_context() -> None:
    """No ID in use, no successor."""
    assert listrules.superseded_license(lic_entry("O", "Nm", True), set(), {}) is None


def test_exception_rule_lowers_and_licence_rule_casefolds() -> None:
    """'ß' casefolds to 'ss', lowers to itself: kept as it was."""
    assert listrules.active_ids_by_name([lic_entry("A", "STRASSE")]) == {
        "strasse": ["A"]
    }
    by_name = listrules.active_exceptions_by_name([exc_entry("E", "STRASSE")])
    assert by_name == {"strasse": "E"}
    assert (
        listrules.exception_successor(exc_entry("O", "Straße", True), by_name) is None
    )
    assert (
        listrules.exception_successor(exc_entry("O", "strasse", True), by_name) == "E"
    )


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (exc_entry("O", "Nm", True), "N"),
        (exc_entry("O", "NM", True), "N"),
        (exc_entry("O", "Other", True), None),
        (exc_entry("N", "Nm", False), None),
        (exc_entry("N", "Nm", None), None),
    ],
    ids=["same", "case", "no-holder", "active", "flag-absent"],
)
def test_exception_successor(exc: SpdxExceptionEntry, expected: str | None) -> None:
    """A deprecated exception follows its holder of the name."""
    by_name = listrules.active_exceptions_by_name(
        [exc_entry("N", "nm"), exc_entry("D", "Other", True)]
    )
    assert listrules.exception_successor(exc, by_name) == expected


def test_active_exceptions_by_name_last_holder_wins() -> None:
    """As the build has always done."""
    both = [exc_entry("A", "Nm"), exc_entry("B", "NM")]
    assert listrules.active_exceptions_by_name(both) == {"nm": "B"}


def test_the_same_sharp_s_name_matches_under_each_rule() -> None:
    """A name with 'ß' on both sides matches whichever way it is folded; a
    folding applied to one side only (a build and a lookup that disagree)
    would break it."""
    assert _successor(lic_entry("O", "Straße", True), lic_entry("N", "STRASSE")) == "N"
    assert _successor(lic_entry("O", "STRASSE", True), lic_entry("N", "Straße")) == "N"
    by_name = listrules.active_exceptions_by_name([exc_entry("E", "Straße")])
    assert listrules.exception_successor(exc_entry("O", "Straße", True), by_name) == "E"
