# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The name tier on a few words: which names a short input holds as a name
of its own (``shorttext._partial_names``), and when its answer is the
narrower grant of a name that states none (``shorttext.narrowed_name``).
The rows are made up, each shaped as a case of the List;
``test_shorttext_evidence`` has the real ones."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from collections.abc import Generator

import pytest
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.shorttext import match_short_text, narrowed_name
from licenseid.types import RawMatch


@pytest.fixture(scope="module")
def names_db() -> Generator[LicenseDatabase, None, None]:
    rows = [
        Lic("Four-1.0", "Alpha Beta Gamma Delta"),
        Lic("Twin-1.0", "Omega Sigma Kappa"),
        Lic("Twin-2.0", "Omega Sigma Lambda"),
        Lic("Short-1.0", "Alpha Beta"),
        # A deprecated name of its own, and the names that replaced it.
        Lic("Old-1.0", "Old Name", is_deprecated=True),
        Lic("Old-1.0-only", "Old Name only"),
        Lic("Old-1.0-or-later", "Old Name or later"),
        # A name in use that a deprecated row shares, as GPL-2.0 shares
        # GPL-2.0-only's, and a name that holds it.
        Lic("Same-1.0", "Same Name"),
        Lic("Same-0.9", "Same Name", is_deprecated=True),
        Lic("Same-Plus-1.0", "Same Name Plus"),
        # One licence's two grants, its deprecated ID with the name of one,
        # and another version of it.
        Lic("Pair-1.0-only", "Pair Name v1 only"),
        Lic("Pair-1.0-or-later", "Pair Name v1 or later"),
        Lic("Pair-1.0", "Pair Name v1 only", is_deprecated=True),
        Lic("Pair-2.0-only", "Pair Name v2 only"),
        # A deprecated row of another licence that holds the pair's words,
        # as GPL-2.0-with-GCC-exception holds "GNU General Public License
        # v2.0".
        Lic("Pair-1.0-with-x", "Pair Name v1 with x", is_deprecated=True),
        # A deprecated name that no row in use holds the words of.
        Lic("Gone-1.0", "Gone Name Here", is_deprecated=True),
        # A pair with no other version, and a version held by two rows.
        Lic("Solo-3.0-only", "Solo Name v3 only"),
        Lic("Solo-3.0-or-later", "Solo Name v3 or later"),
        Lic("Ver-1.0.6", "Ver Name v1.0.6"),
        Lic("Ver-1.0.5", "Ver Name v1.0.5", is_deprecated=True),
        # The deprecated "+" form of the pair's -or-later, as GPL-2.0+.
        Lic("Pair-1.0+", "Pair Name v1 or later", is_deprecated=True),
        # A name in use that is also a pair's name without its grant.
        Lic("Dup-1.0", "Dup Name"),
        Lic("Dup-2.0-only", "Dup Name only"),
        Lic("Dup-2.0-or-later", "Dup Name or later"),
        # Two licences whose pairs have one name.
        Lic("Twice-1.0-only", "Twice Name only"),
        Lic("Twice-1.0-or-later", "Twice Name or later"),
        Lic("Twice-2.0-only", "Twice Name only"),
        Lic("Twice-2.0-or-later", "Twice Name or later"),
        # Half a pair: an ID with no grant, a deprecated -only, or one grant
        # only, beside the other.
        Lic("Odd-1.0", "Odd Name only"),
        Lic("Odd-1.0-or-later", "Odd Name or later"),
        Lic("Dep-1.0-only", "Dep Name only", is_deprecated=True),
        Lic("Dep-1.0-or-later", "Dep Name or later"),
        Lic("Late-1.0-or-later", "Late Name or later"),
        Lic("Late-1.0-x", "Late Name x"),
        Lic("Early-1.0-only", "Early Name only"),
        Lic("Early-1.0-x", "Early Name x"),
        # Names that end in as many letters as a grant, but in none.
        Lic("Cut-1.0-only", "Cut Name v1 xxxx"),
        Lic("Cut-1.0-or-later", "Cut Name v1 xxxxxxxx"),
        # A licence whose name holds a pair's name without its grant, and
        # a word more.
        Lic("Solo-3.0-extra", "Solo Name v3 extra plus"),
    ]
    for path in seeded_db("test_shorttext_evidence_names", rows):
        yield LicenseDatabase(path)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Half the words of the one name that holds them: that name.
        ("beta delta", [("Four-1.0", 1.01)]),
        ("delta gamma alpha", [("Four-1.0", 1.01)]),
        # Fewer than half: a word of the name, not the name.
        ("delta", []),
        # Two names hold them: neither is named.
        ("omega sigma", []),
        # The same words in another order are the name itself.
        ("sigma kappa omega", [("Twin-1.0", 1.01)]),
        # The input is a name: Four-1.0 only holds its words.
        ("alpha beta", [("Short-1.0", 1.02)]),
        # A deprecated name: the names that replaced it hold its words, and
        # answer it as before (with the deprecated row, exact, after them).
        ("old name", [("Old-1.0-only", 1.01), ("Old-1.0-or-later", 1.01)]),
        # Not so for a word of it.
        ("old", []),
        # A name in use, though a deprecated row has it too: the name that
        # holds it is not named.
        ("same name", [("Same-1.0", 1.02)]),
        # The words of one licence's two grants (and of a deprecated row
        # that the List split into them): both, the name of neither.
        ("pair name v1", [("Pair-1.0-only", 1.01), ("Pair-1.0-or-later", 1.01)]),
        # Without its grant and a word more: no name of either.
        ("name v1", []),
        ("solo name", []),  # the version left out
        # Fewer than half the words of either: a word of the name.
        ("pair", []),
        # Two versions hold them: neither is named.
        ("pair name", []),
        ("solo name v3", [("Solo-3.0-only", 1.01), ("Solo-3.0-or-later", 1.01)]),
        # A word of two rows, one deprecated: neither, as for bzip2.
        ("ver name", []),
        # Without the grant of two licences' names: neither.
        ("twice name", []),
        # No pair of grants in use: no guess, and never the wider one.
        ("odd name", []),
        ("dep name", []),
        ("late name", []),
        ("early name", []),
        ("cut name v1", []),
        # The pair's name without its grant and a word: the one name that
        # holds them.
        ("solo name v3 extra", [("Solo-3.0-extra", 1.01)]),
    ],
)
def test_a_name_with_words_left_out(
    names_db: LicenseDatabase, text: str, expected: list[tuple[str, float]]
) -> None:
    found = [
        (m["license_id"], round(m["score"], 6))
        for m in match_short_text(names_db, text)
        if m["score"] > 1.0
    ]
    assert found == expected


def _hit(license_id: str, score: float = 1.01, **fields: object) -> RawMatch:
    match = RawMatch(
        license_id=license_id,
        method="name",
        exact=False,
        score=score,
        similarity=1.0,
        coverage=None,
    )
    match.update(fields)  # type: ignore[typeddict-item]
    return match


@pytest.mark.parametrize(
    ("found", "expected"),
    [
        ([_hit("X-1.0-only"), _hit("X-1.0-or-later")], "X-1.0-only"),
        ([_hit("X-1.0-only"), _hit("X-1.0-or-later"), _hit("Y")], "X-1.0-only"),
        ([], None),
        ([_hit("X-1.0-only")], None),
        ([_hit("X-1.0-only"), _hit("X-1.0-or-later", 1.0)], None),  # not tied
        ([_hit("X-1.0-only"), _hit("X-2.0-or-later")], None),  # two licences
        ([_hit("X-1.0-or-later"), _hit("X-1.0-only")], None),  # the wider first
        ([_hit("X-1.0-only", exact=True), _hit("X-1.0-or-later")], None),
        ([_hit("X-1.0-only"), _hit("X-1.0-or-later", exact=True)], None),
        ([_hit("X-1.0-only", method="id"), _hit("X-1.0-or-later")], None),
        ([_hit("X-1.0-only"), _hit("X-1.0-or-later", method="text")], None),
        ([_hit("X-1.0"), _hit("X-1.0-or-later")], None),  # no -only
    ],
    ids=lambda v: ascii(v)[:40],
)
def test_narrowed_name(found: list[RawMatch], expected: str | None) -> None:
    assert narrowed_name(found) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The deprecated row of another licence only holds the pair's words:
        # its plain ratio judges it, and it is no answer.
        (
            "pair name v1",
            [
                ("Pair-1.0-only", 1.01),
                ("Pair-1.0-or-later", 1.01),
                ("Pair-1.0", 0.98),
                ("Pair-1.0+", 0.98),
                ("Pair-2.0-only", 0.857143),  # a plain ratio, like-named
            ],
        ),
        # Held by one deprecated row and no row in use: that row, as before.
        ("gone name", [("Gone-1.0", 0.98)]),
        # A name in use: that name alone, not the pair it is the start of.
        ("dup name", [("Dup-1.0", 1.02)]),
    ],
)
def test_every_result_of_a_partial_name(
    names_db: LicenseDatabase, text: str, expected: list[tuple[str, float]]
) -> None:
    found = [
        (m["license_id"], round(m["score"], 6))
        for m in match_short_text(names_db, text)
    ]
    assert found == expected
