# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Characterisation of the rules `records.build_records` applies to a
release: which licences are kept, indexed, and what a deprecated one points
to. The full rows and the order of the lists are pinned."""

from list_entries import exc_entry, lic_entry

from licenseid.records import build_records
from licenseid.spdxdata import SpdxData


def test_licence_rows_and_index_in_input_order() -> None:
    """Every kept/dropped combination, with the full rows."""
    data = SpdxData(
        "3.99",
        None,
        (
            lic_entry("Act-1.0", "Active One", None),  # key absent = active
            lic_entry("NoText-1.0", "No Text"),  # active without text: dropped
            lic_entry("Dep-1.0", "Dep Text", True),  # deprecated with text
            lic_entry("DepNo-1.0", "Dep No Text", True),  # metadata-only
            lic_entry("Act-2.0", "Active Two"),
        ),
        (),
        {"Act-1.0": "Hello World", "Dep-1.0": "Old Text", "Act-2.0": ""},
    )
    recs = build_records(data, {"Act-1.0": 7})
    assert recs.licenses == [
        ("Act-1.0", "Active One", None, True, False, False, False, False, None,
         7, 2, "act 1 0", "active one"),
        ("Dep-1.0", "Dep Text", None, True, False, False, False, True, None,
         1, 2, "dep 1 0", "dep text"),
        ("DepNo-1.0", "Dep No Text", None, True, False, False, False, True,
         None, 1, 0, "depno 1 0", "dep no text"),
        ("Act-2.0", "Active Two", None, True, False, False, False, False, None,
         1, 0, "act 2 0", "active two"),
    ]  # fmt: skip
    assert recs.index_entries == [
        ("Act-1.0", "hello world"),
        ("Dep-1.0", "old text"),
        ("Act-2.0", ""),
    ]
    assert recs.exceptions == []


def test_successors_beside_texts() -> None:
    """A successor is recorded on a row with a text and on a metadata row."""
    data = SpdxData(
        "3.99",
        None,
        (
            lic_entry("GPL-2.0+", "GPL two plus", True),
            lic_entry("GPL-2.0-or-later", "GPL two or later"),
            lic_entry("StandardML-NJ", "Standard ML of NJ", True),
            lic_entry("SMLNJ", "standard ml of nj"),
            lic_entry("GPL-2.0", "GPL two only", True),
            lic_entry("GPL-2.0-only", "GPL two only"),
            lic_entry("Two-0", "Shared", True),
            lic_entry("TwoA", "shared"),
            lic_entry("TwoB", "SHARED"),
            lic_entry("Lone+", "Lone", True),
        ),
        (),
        {"StandardML-NJ": "t", "GPL-2.0+": "t"},
    )
    rows = {r[0]: (r[8], r[10]) for r in build_records(data, {}).licenses}
    assert rows == {
        "GPL-2.0+": ("GPL-2.0-or-later", 1),
        "StandardML-NJ": ("SMLNJ", 1),
        "GPL-2.0": (None, 0),
        "Two-0": (None, 0),
        "Lone+": (None, 0),
    }
    assert list(rows) == [
        "GPL-2.0+",
        "StandardML-NJ",
        "GPL-2.0",
        "Two-0",
        "Lone+",
    ]


def test_exceptions_rows_and_order() -> None:
    """A deprecated exception points to the active one of the same name,
    compared with str.lower(); an exception with none, or a deprecated
    holder, gets None."""
    data = SpdxData(
        "3.99",
        None,
        (),
        (
            exc_entry("Old-exc", "Some Exception", True),
            exc_entry("New-exc", "SOME exception"),
            exc_entry("Absent-exc", "Nothing here", True),
            exc_entry("Flag-less", "Flagless", None),
            exc_entry("Dep-holder", "Held by deprecated", True),
            exc_entry("Dep-holder2", "held by deprecated", True),
        ),
        {},
    )
    assert build_records(data, {}).exceptions == [
        ("Old-exc", "Some Exception", True, "New-exc"),
        ("New-exc", "SOME exception", False, None),
        ("Absent-exc", "Nothing here", True, None),
        ("Flag-less", "Flagless", False, None),
        ("Dep-holder", "Held by deprecated", True, None),
        ("Dep-holder2", "held by deprecated", True, None),
    ]


def test_licences_fold_with_casefold_and_exceptions_with_lower() -> None:
    """The two rules differ today: 'ß' casefolds to 'ss' but lowers to 'ß'.
    Kept as it is."""
    data = SpdxData(
        "3.99",
        None,
        (lic_entry("Old", "Straße", True), lic_entry("New", "STRASSE")),
        (exc_entry("Old-exc", "Straße", True), exc_entry("New-exc", "STRASSE")),
        {},
    )
    recs = build_records(data, {})
    assert recs.licenses[0][8] == "New"
    assert recs.exceptions[0][3] is None


def test_the_same_sharp_s_name_matches_in_both_rules() -> None:
    """Whichever way a name is folded, the same name on both sides matches."""
    data = SpdxData(
        "3.99",
        None,
        (lic_entry("Old", "STRASSE", True), lic_entry("New", "Straße")),
        (exc_entry("Old-exc", "Straße", True), exc_entry("New-exc", "Straße")),
        {},
    )
    recs = build_records(data, {})
    assert recs.licenses[0][8] == "New"
    assert recs.exceptions[0][3] == "New-exc"
