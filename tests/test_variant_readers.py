# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``variants.stated_of`` and ``warn_overridden``: what the evidence of a
result says of its variant (roadmap item 52)."""
# pylint: disable=missing-function-docstring

import warnings

import pytest
from conftest import GivenWarnings

from licenseid.result import public_result
from licenseid.types import Evidence, InternalMatch, RawMatch, Variant
from licenseid.variants import (
    _PENDING,
    _chosen_by,
    _is_only,
    _prefer_or_later,
    family_of,
    settle_free_text,
    settle_text,
    stated_of,
    warn_overridden,
)


@pytest.mark.parametrize(
    ("expression", "value", "stated"),
    [
        ("MIT", "MIT", None),
        ("GPL-2.0", "GPL-2.0", False),  # kept bare
        ("GPL-2.0-only", "GPL-2.0-only", True),  # the ID is in the value
        ("GPL-2.0-only", "GPL-2.0", False),  # licenseid chose it
        ("GPL-2.0-only", "GNU GPL v2.0 only", True),  # the word "only"
        ("GPL-2.0-or-later", "GPL-2.0+", True),  # the "+"
        ("GPL-2.0-or-later", "GPL-2.0 or later", True),
        ("GPL-2.0-or-later", "GPL-2.0", False),
        ("GPL-2.0-with-classpath-exception", "GPL-2.0-with-classpath-exception", False),
        (
            "GPL-2.0-only WITH Classpath-exception-2.0",
            "GPL-2.0 only WITH Classpath-exception-2.0",
            True,
        ),
        # Two licences: the word is read beside its own.
        ("GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0 only OR LGPL-2.1", False),
        ("GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0 only OR LGPL-2.1 only", True),
    ],
)
def test_stated_of_judges_the_variant_of_an_expression(
    expression: str, value: str, stated: bool | None
) -> None:
    assert stated_of(expression, Evidence(value=value)) is stated
    assert stated_of(expression, None) in (None, False)  # no evidence: none


@pytest.mark.parametrize(
    ("variant", "expression", "value", "said"),
    [
        ("only", "GPL-2.0-or-later OR GPL-3.0-only", "GPL-2.0+ OR GPL-3.0", True),
        (
            "or-later",
            "GPL-2.0-only OR GPL-3.0-or-later",
            "GPL-2.0 only OR GPL-3.0",
            True,
        ),
        ("only", "GPL-2.0-or-later", "GPL-2.0", False),  # a guess states nothing
        ("only", "GPL-2.0-or-later", "GPL-2.0-or-later", True),
    ],
)
def test_a_stated_operand_of_a_guessed_compound_overrides(
    given: GivenWarnings, variant: Variant, expression: str, value: str, said: bool
) -> None:
    warn_overridden(variant, expression, Evidence(value=value))
    assert bool(given.take()) is said


@pytest.mark.parametrize(
    ("expression", "variant", "stated", "said"),
    [
        ("LicenseRef-acme-only", "or-later", None, False),
        ("DocumentRef-x-1.2:LicenseRef-acme-only", "or-later", None, False),
        ("MIT+", "only", None, False),  # a "+" on a licence with no variants
        ("LicenseRef-x-or-later", "only", None, False),
        ("MIT AND LicenseRef-x-or-later", "auto", None, False),
        ("GPL-2.0-only AND LicenseRef-x-or-later", "auto", True, False),
    ],
)
def test_a_reference_that_ends_in_a_variant_word_states_none(
    given: GivenWarnings,
    expression: str,
    variant: Variant,
    stated: bool | None,
    said: bool,
) -> None:
    assert stated_of(expression, Evidence(value=expression)) is stated
    warn_overridden(variant, expression, Evidence(value=expression))
    assert bool(given.take()) is said


@pytest.mark.parametrize(
    ("expression", "value", "stated"),
    [
        # Another licence's words are never read.
        ("GPL-2.0-or-later OR MIT+", "GPL-2.0 OR MIT+", False),
        ("GPL-2.0-or-later OR LGPL-2.1-or-later", "GPL-2.0 OR LGPL-2.1+", False),
        ("GPL-2.0-or-later OR GPL-2.0-only", "GPL-2.0+ OR GPL-2.0", False),
        ("GPL-2.0-only AND LGPL-2.0-only", "GPL-2.0 AND LGPL-2.0 only", False),
        ("GPL-2.0-only AND LGPL-2.0-only", "GPL-2.0 only AND LGPL-2.0 only", True),
        # Re-spelt IDs and names state it too.
        ("GPL-3.0-or-later", "GPLv3-or-later", True),
        ("GPL-2.0-only", "GPLv2-only", True),
        ("LGPL-2.0-or-later", "LGPL-v2.0-or-later", True),
        ("GPL-2.0-or-later", "GNU General Public Licence v2.0 or later", True),
        ("GPL-2.0-or-later", "(GPL-2.0) or later", True),
        ("GPL-2.0-or-later", "GPL-2.0, version 2 or later", True),
        ("GPL-2.0-or-later", "GPL-2.0, any later version", True),
        ("GPL-2.0-or-later", "GPL-2.0 any day now", False),
        # Another version's words are another licence's grant.
        ("GPL-2.0-only", "GPL-2.0 version 3 only", False),
        ("GPL-2.0-or-later", "GPL-2.0 version 3 or later", False),
        ("GPL-2.0-only", "GPL-2.0 version 2.0 only", True),
        ("GPL-2.0-or-later", "GPL-2.0 version 2.0.0 or later", True),
        ("GPL-2.0-or-later", "GPL-2.0 version 2.1 or later", False),
        # A grant wrapped onto a comment line (``classify`` reads it).
        ("GPL-2.0-or-later", "// GPL-2.0\n// or later", True),
        ("GPL-2.0-or-later", "/* GPL-2.0\n * or (at your option) any later\n", True),
        (
            "GPL-2.0-or-later WITH Classpath-exception-2.0",
            "GPL-2.0-with-classpath-exception+",
            True,
        ),
    ],
)
def test_the_words_of_the_licence_itself_state_its_variant(
    expression: str, value: str, stated: bool
) -> None:
    assert stated_of(expression, Evidence(value=value)) is stated


@pytest.mark.parametrize(
    ("value", "exact", "stated"),
    [("GPL-2.0", False, False), ("GPL-2.0-only", True, True)],
)
def test_a_variant_licenseid_chose_is_not_exact(
    value: str, exact: bool, stated: bool
) -> None:
    """The one rule, whichever site made the result (``public_result``)."""
    raw = RawMatch(
        evidence=Evidence(value=value),
        license_id="GPL-2.0-only",
        score=1.0,
        exact=True,
        method="id",
        similarity=None,
        coverage=None,
    )
    result = public_result(raw, [])
    assert (result["exact"], result["variant_stated"]) == (exact, stated)


def _hit(license_id: str, score: float) -> RawMatch:
    return RawMatch(
        evidence=Evidence(value=""),
        license_id=license_id,
        score=score,
        exact=False,
        method="text",
        similarity=None,
        coverage=None,
    )


WITH = " WITH Font-exception-2.0"


def test_a_with_answer_is_judged_by_its_licence_id() -> None:
    """The exception ends neither ``-only`` nor ``-or-later``: the head ID is
    what the helpers read, and the peer keeps the exception."""
    only, later = (
        _hit(f"GPL-2.0-only{WITH}", 0.95),
        _hit(f"GPL-2.0-or-later{WITH}", 0.9),
    )
    assert _is_only(only) and not _is_only(later)
    scores = {
        f"gpl-2.0-only{WITH}".lower(): 0.95,
        f"gpl-2.0-or-later{WITH}".lower(): 0.9,
    }
    # Far below its peer: the text's doing, not the grant's. Near it: chosen.
    assert _chosen_by(later, scores) is False
    assert _chosen_by(later, {**scores, f"gpl-2.0-only{WITH}".lower(): 0.91}) is True
    results: list[RawMatch | InternalMatch] = [only, later]
    _prefer_or_later(results)  # ``--variant or-later``, nothing stated
    assert [r["license_id"] for r in results] == [
        f"GPL-2.0-or-later{WITH}",
        f"GPL-2.0-only{WITH}",
    ]


def test_a_grant_beside_an_only_elsewhere_chooses_only_the_grant() -> None:
    """``signal`` (a grant) and ``only`` ("Python 3 only") both hold: the
    grant chose its ``-or-later`` result, and states no ``-only`` one."""
    out = settle_text(
        [_hit("GPL-2.0-or-later", 0.95), _hit("LGPL-3.0-only", 0.9)],
        True,
        "only",
        only=True,
    )
    states = {r["license_id"]: r["evidence"] for r in out}
    assert states["GPL-2.0-or-later"].get("later") is True
    assert states["LGPL-3.0-only"].get("only") is False


def test_a_stated_only_is_not_swapped_for_or_later() -> None:
    """``--variant or-later`` prefers ``-or-later`` only where nothing is
    stated: "version 2 only" stays first."""
    out = settle_text(
        [_hit("GPL-2.0-only", 0.95), _hit("GPL-2.0-or-later", 0.94)],
        False,
        "or-later",
        only=True,
    )
    assert out[0]["license_id"] == "GPL-2.0-only"


@pytest.mark.parametrize(
    ("expression", "value", "decided", "stated"),
    [
        # An operand licenseid decided is never stated by another operand's
        # words, nor by the same form written elsewhere (it is merged).
        (
            "GPL-2.0-only AND GPL-2.0-only WITH Classpath-exception-2.0",
            "GPL-2.0-only AND GPL-2.0 WITH Classpath-exception-2.0",
            ["gpl-2.0-only"],
            False,
        ),
        (
            "GPL-2.0-or-later AND GPL-2.0-or-later WITH Classpath-exception-2.0",
            "GPL-2.0+ AND GPL-2.0-with-classpath-exception",
            ["gpl-2.0-or-later"],
            False,
        ),
        ("GPL-2.0-only OR MIT", "GPL-2.0-only OR GPL-2.0", ["gpl-2.0-only"], False),
        # Nothing decided: the words of the value state it, re-spelt too.
        (
            "GPL-2.0-only AND GPL-2.0-only WITH Classpath-exception-2.0",
            "GPL-2.0-only AND GPL-2.0-only WITH Classpath-exception-2.0",
            [],
            True,
        ),
        ("GPL-2.0-only OR GPL-2.0-or-later", "GPL-2.0-only OR GPLv2+", [], True),
        (
            "GPL-2.0-only OR GPL-2.0-or-later",
            "GPL-2.0-only OR GPL-2 or later",
            [],
            True,
        ),
        ("GPL-2.0-or-later AND LGPL-2.0-or-later", "GPLv2+ and LGPLv2+", [], True),
        ("GPL-2.0-or-later OR LGPL-2.1-or-later", "GPLv2+ or LGPLv2.1+", [], True),
        ("GPL-2.0-or-later OR LGPL-2.1-or-later", "GPLv2+ or LGPL-2.1", [], False),
        # A reference is no place for a family name.
        (
            "GPL-2.0-only OR LicenseRef-a.GPLv2-only",
            "LicenseRef-a.GPLv2-only OR GPL-2.0",
            ["gpl-2.0-only"],
            False,
        ),
    ],
)
def test_an_operand_the_option_decided_is_not_stated_by_another(
    expression: str, value: str, decided: list[str], stated: bool
) -> None:
    evidence = Evidence(value=value, decided=decided)
    assert stated_of(expression, evidence) is stated


@pytest.mark.parametrize(
    ("resolved", "written", "family"),
    [
        ("GPL-2.0-or-later OR LGPL-2.1-or-later", "GPL-2.0+ OR LGPL-2.1", "LGPL-2.1"),
        ("LGPL-2.1-or-later OR GPL-2.0-only", "LGPL-2.1+ OR GPL-2.0", "GPL-2.0"),
        ("GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0-only OR LGPL-2.1", "LGPL-2.1"),
    ],
)
def test_the_warning_names_the_licence_the_option_decided(
    resolved: str, written: str, family: str
) -> None:
    """A "+" states its licence: the warning names the other one."""
    assert family_of(resolved, written) == family


@pytest.mark.parametrize(
    ("variant", "first"),
    [("auto", "GPL-3.0"), ("only", "GPL-3.0-only"), ("or-later", "GPL-3.0-or-later")],
)
def test_a_heading_id_is_decided_whatever_a_retrieved_twin_scored(
    variant: Variant, first: str
) -> None:
    """A marker found ``GPL-3.0`` in the heading: a declared ID (kept under
    ``auto``) even where Tier 1 retrieved its ``-only`` twin as noise."""
    found: list[RawMatch | InternalMatch] = [
        _hit("GPL-3.0", 0.855),
        _hit("GPL-3.0-only", 0.486),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the guess is said, tested elsewhere
        out = settle_text(found, False, variant, written="## License\n\nGPL-3.0\n")
    assert out[0]["license_id"] == first


@pytest.mark.parametrize(
    ("variant", "first"),
    [
        ("auto", "GPL-2.0-only"),
        ("only", "GPL-2.0-only"),
        ("or-later", "GPL-2.0-or-later"),
    ],
)
def test_the_option_decides_an_only_form_with_no_peer_retrieved(
    variant: Variant, first: str
) -> None:
    """A heading ``GPL v2`` names the ``-only`` form alone (no ``-or-later``
    row was retrieved): ``or-later`` still decides what the input leaves."""
    found: list[RawMatch | InternalMatch] = [_hit("GPL-2.0-only", 0.855)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = settle_text(found, False, variant, written="## License\\n\\nGPL v2\\n")
    assert out[0]["license_id"] == first


def test_an_only_the_input_writes_out_is_not_moved_by_the_option() -> None:
    """A heading ``GPL-2.0-only`` states it: ``or-later`` leaves it (and
    says so), neither swapped for a peer nor renamed."""
    found: list[RawMatch | InternalMatch] = [
        _hit("GPL-2.0-only", 0.855),
        _hit("GPL-2.0-or-later", 0.85),
    ]
    out = settle_text(found, False, "or-later", written="## License\n\nGPL-2.0-only\n")
    assert out[0]["license_id"] == "GPL-2.0-only"
    lone: list[RawMatch | InternalMatch] = [_hit("GPL-2.0-only", 0.855)]
    out = settle_text(lone, False, "or-later", written="## License\n\nGPL-2.0-only\n")
    assert out[0]["license_id"] == "GPL-2.0-only"


def test_the_option_does_not_rename_to_an_excluded_form() -> None:
    """``or-later`` would rename a guessed ``-only`` to ``-or-later``, which
    the caller excluded: the ``-only`` stays (a bare ID is dropped)."""
    found: list[RawMatch | InternalMatch] = [_hit("GPL-2.0-only", 0.855)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = settle_free_text(
            found,
            "## License\n\nGPL v2\n",
            False,
            {"variant": "or-later", "exclude": ["GPL-2.0-or-later"]},
        )
    assert [r["license_id"] for r in out] == ["GPL-2.0-only"]


def test_the_only_kept_for_an_excluded_twin_is_said_to_be_a_guess() -> None:
    """The rename's warning named the excluded form and was dropped: the
    ``-only`` that stays is the guess."""
    found: list[RawMatch | InternalMatch] = [_hit("GPL-2.0-only", 0.855)]
    held: list[tuple[str, str]] = []
    token = _PENDING.set(held)
    try:
        settle_free_text(
            found,
            "## License\n\nGPL v2\n",
            False,
            {"variant": "or-later", "exclude": ["GPL-2.0-or-later"]},
        )
    finally:
        _PENDING.reset(token)
    assert ("GPL-2.0", "GPL-2.0-only") in held


def test_a_grant_the_marker_did_not_read_leaves_the_only_form() -> None:
    """BUG: a README "licensed under the GNU GPL v2 or (at your option) any
    later version" is read by the heading marker as ``GPL-2.0-only``: the
    input grants later versions (the signal), but the ``-or-later`` row the
    text matches far worse is no peer to swap with (``_chosen_by``), so the
    answer stays ``-only`` with a "not stated" warning. Main gave the same
    expression; a rule of the signal that finds the marker's own grant
    would end it (decision 48)."""
    found: list[RawMatch | InternalMatch] = [
        _hit("GPL-2.0-only", 0.855),
        _hit("GPL-2.0-or-later", 0.3),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = settle_text(found, True, "auto", written="GPL v2 or later")
    assert out[0]["license_id"] == "GPL-2.0-only"
