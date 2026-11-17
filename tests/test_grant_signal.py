# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An "or later" grant counts for the licence it names (roadmap items 52, 54).

``Requires Python 3.8 or later`` beside a GNU name grants nothing of the GNU
licence: the answer is ``-only``, with a warning, and ``VARIANT_STATED`` is
false. The unit rows run :func:`licenseid.variants.settle_text` with a signal
per licence; the detect rows run the whole pipeline on a small database.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from typing import Any

import pytest
from conftest import GivenWarnings
from matcher_db import Lic, seeded_db
from ordering_helpers import ids, im
from test_variant import GPL_TEXT, _hit
from test_variant import ROWS as VARIANT_ROWS

from licenseid.detector import LicenseDetector
from licenseid.grantsubject import GrantSignal, Signals, constant
from licenseid.ranking import apply_version_suffix_tiebreaker
from licenseid.types import InternalMatch, RawMatch, Variant
from licenseid.variants import settle_free_text, settle_text

ROWS = (
    *VARIANT_ROWS,
    Lic(
        "LGPL-2.1-only", "GNU Lesser General Public License v2.1 only", True, True, True
    ),
    Lic(
        "LGPL-2.1-or-later",
        "GNU Lesser General Public License v2.1 or later",
        True,
        True,
        True,
    ),
    Lic(
        "LGPL-2.1", "GNU Lesser General Public License v2.1", False, is_deprecated=True
    ),
)
NAME = "GNU General Public License v2.0"
NOT_STATED = "input: variant not stated: GPL-2.0; using GPL-2.0-only"
GPL_GRANT = "either version 2 of the License, or (at your option) any later version."


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    yield from seeded_db("test_grant_signal", ROWS)


def _answer(
    db: str, given: GivenWarnings, text: str, variant: Variant = "auto"
) -> tuple[str, bool | None, list[str]]:
    top = LicenseDetector(db).detect(text=text, variant=variant)[0]
    return top["expression"], top["variant_stated"], [str(w) for w in given.take()]


@pytest.mark.parametrize(
    ("text", "variant", "expected"),
    [
        # A tool's "or later" is no grant of the licence.
        (
            f"{NAME}\nRequires Python 3.8 or later.",
            "auto",
            ("GPL-2.0-only", False, [NOT_STATED]),
        ),
        # ... so --variant only is not overridden by it.
        (
            f"{NAME}\nRequires Python 3.8 or later.",
            "only",
            ("GPL-2.0-only", False, [NOT_STATED]),
        ),
        (
            f"{NAME}\nRequires Python 3.8 or later.",
            "or-later",
            (
                "GPL-2.0-or-later",
                False,
                ["input: variant not stated: GPL-2.0; using GPL-2.0-or-later"],
            ),
        ),
        # A tool's "only" states nothing of the licence either.
        (
            f"{NAME}\nSupports Python 3 only.",
            "auto",
            ("GPL-2.0-only", False, [NOT_STATED]),
        ),
        # The licence's own words stay stated.
        (f"{NAME} or later", "auto", ("GPL-2.0-or-later", True, [])),
        (f"{NAME}, version 2 or later", "auto", ("GPL-2.0-or-later", True, [])),
        (f"{NAME}\nLicensed under version 2 only.", "auto", ("GPL-2.0-only", True, [])),
        (
            f"{NAME}\nRequires Python 3.8 or later. {NAME} or later.",
            "auto",
            ("GPL-2.0-or-later", True, []),
        ),
        # Another licence's grant beside it is that licence's.
        (
            (
                "# Project\n\nWorks with Python 3.8 or any later version.\n\n"
                "## License\n\nGNU Lesser General Public License v2.1"
            ),
            "auto",
            (
                "LGPL-2.1-only",
                False,
                ["input: variant not stated: LGPL-2.1; using LGPL-2.1-only"],
            ),
        ),
    ],
)
def test_a_name_is_settled_by_the_grant_of_its_own_licence(
    db: str,
    given: GivenWarnings,
    text: str,
    variant: Variant,
    expected: tuple[str, bool | None, list[str]],
) -> None:
    assert _answer(db, given, text, variant) == expected


@pytest.mark.parametrize(
    ("text", "variant", "expected"),
    [
        (f"{GPL_TEXT} {GPL_GRANT}", "auto", ("GPL-2.0-or-later", True)),
        (f"{GPL_TEXT} Requires Python 3.8 or newer.", "auto", ("GPL-2.0-only", False)),
        (f"{GPL_TEXT} Requires Python 3.8 or newer.", "only", ("GPL-2.0-only", False)),
        (
            f"{GPL_TEXT} Requires Python 3.8 or any later version.",
            "auto",
            ("GPL-2.0-only", False),  # a tool's own "any later version"
        ),
        # The grant of the LGPL beside it is not the GPL's.
        (
            f"{GPL_TEXT} The docs are under LGPL-2.1 or later.",
            "auto",
            ("GPL-2.0-only", False),
        ),
        (
            f"{GPL_TEXT} {GPL_GRANT} Requires Python 3.8 or later.",
            "only",
            ("GPL-2.0-or-later", True),
        ),
    ],
)
def test_a_text_is_settled_by_the_grant_of_its_own_licence(
    db: str,
    given: GivenWarnings,
    text: str,
    variant: Variant,
    expected: tuple[str, bool | None],
) -> None:
    found, stated, _ = _answer(db, given, text, variant)
    assert (found, stated) == expected


def test_a_grant_of_the_text_overrides_the_option_with_a_warning(
    db: str, given: GivenWarnings
) -> None:
    text = f"{GPL_TEXT} {GPL_GRANT} Requires Python 3.8 or later."
    _, _, warned = _answer(db, given, text, "only")
    assert any("overridden by input" in w for w in warned)


def _granted(*ids: str) -> GrantSignal:
    """A signal that grants the licences *ids* only."""
    return lambda license_id: license_id in ids


def _settle(
    hits: list[Any],
    signal: GrantSignal,
    variant: Variant,
    given: GivenWarnings,
    **kw: Any,
) -> tuple[list[tuple[str, float]], list[str]]:
    unowned = kw.pop("unowned", lambda: False)
    out: list[RawMatch | InternalMatch] = settle_text(
        hits, Signals(signal, unowned=unowned), variant, **kw
    )
    return [(r["license_id"], r["score"]) for r in out], [str(w) for w in given.take()]


def test_an_or_later_name_without_its_grant_settles_to_its_twin(
    given: GivenWarnings,
) -> None:
    """Of two licences, the grant of one chose its ``-or-later`` only (what a
    signal of the whole input could not tell)."""
    hits = [_hit("LGPL-2.1-or-later", 1.0), _hit("LGPL-2.1-only", 1.0)]
    out, warned = _settle(hits, _granted("GPL-2.0-or-later"), "auto", given)
    assert [i for i, _ in out] == ["LGPL-2.1-only", "LGPL-2.1-or-later"]
    assert warned == ["input: variant not stated: LGPL-2.1; using LGPL-2.1-only"]


def test_a_twin_that_is_not_there_is_named_by_the_rule(given: GivenWarnings) -> None:
    out, _ = _settle([_hit("GPL-3.0-or-later", 1.0)], constant(False), "auto", given)
    assert out == [("GPL-3.0-only", 1.0)]


def test_an_exception_stays_when_the_twin_is_named(given: GivenWarnings) -> None:
    hit = _hit("GPL-2.0-or-later WITH Classpath-exception-2.0", 1.0)
    out, _ = _settle([hit], constant(False), "only", given)
    assert out == [("GPL-2.0-only WITH Classpath-exception-2.0", 1.0)]


@pytest.mark.parametrize("variant", ["auto", "only", "as-written"])
def test_a_granted_licence_is_not_settled(
    given: GivenWarnings, variant: Variant
) -> None:
    out, _ = _settle(
        [_hit("GPL-2.0-or-later", 1.0)], _granted("GPL-2.0-or-later"), variant, given
    )
    assert out == [("GPL-2.0-or-later", 1.0)]


def test_the_or_later_option_keeps_an_or_later_answer(given: GivenWarnings) -> None:
    out, _ = _settle(
        [_hit("GPL-2.0-or-later", 1.0)], constant(False), "or-later", given
    )
    assert out == [("GPL-2.0-or-later", 1.0)]


def test_an_id_the_input_writes_is_not_settled(given: GivenWarnings) -> None:
    """A marker found ``GPL-2.0-or-later`` in the text: a declared ID."""
    out, _ = _settle(
        [_hit("GPL-2.0-or-later", 1.0, "text")],
        constant(False),
        "auto",
        given,
        written="licence: GPL-2.0-or-later",
    )
    assert out == [("GPL-2.0-or-later", 1.0)]


def test_only_the_answer_is_settled_not_the_runners_up(given: GivenWarnings) -> None:
    hits = [_hit("GPL-2.0-only", 1.0), _hit("GPL-3.0-or-later", 0.9)]
    out, _ = _settle(hits, constant(False), "auto", given)
    assert [i for i, _ in out] == ["GPL-2.0-only", "GPL-3.0-or-later"]


def test_an_id_method_answer_is_a_declaration_and_is_not_settled(
    given: GivenWarnings,
) -> None:
    out, _ = _settle(
        [_hit("GPL-2.0-or-later", 1.0, "id")], constant(False), "auto", given
    )
    assert out == [("GPL-2.0-or-later", 1.0)]


def test_as_written_collapses_twins_only_where_nothing_is_granted(
    given: GivenWarnings,
) -> None:
    twins = [
        _hit("GPL-2.0-only", 0.96, "text"),
        _hit("GPL-2.0-or-later", 0.96, "text"),
        _hit("GPL-2.0", 0.96, "text"),
    ]
    out, _ = _settle(list(twins), constant(False), "as-written", given)
    assert [i for i, _ in out] == ["GPL-2.0"]
    out, _ = _settle(
        [dict(t) for t in twins], _granted("GPL-2.0-or-later"), "as-written", given
    )
    assert len(out) == 3


def test_the_tie_breaker_asks_for_each_pair_of_twins() -> None:
    """A grant of the GPL chooses the GPL's ``-or-later``, not the LGPL's."""
    ranked = [
        im("LGPL-2.1-or-later", 0.9),
        im("LGPL-2.1-only", 0.9),
        im("GPL-2.0-or-later", 0.9),
        im("GPL-2.0-only", 0.9),
    ]
    out = ids(apply_version_suffix_tiebreaker(ranked, "GPL-2.0 or later", False))
    assert out.index("GPL-2.0-or-later") < out.index("GPL-2.0-only")
    assert out.index("LGPL-2.1-only") < out.index("LGPL-2.1-or-later")


@pytest.mark.parametrize("unowned", [True, False])
def test_a_phrase_no_subject_owns_leaves_the_or_later_answer(
    given: GivenWarnings, unowned: bool
) -> None:
    """The licence's own grant may be one the subject rule cannot read (``or
    any version later``): the answer stays ``-or-later``, a guess; where every
    phrase has an owner, a tool's, it is settled to ``-only``."""
    out, _ = _settle(
        [_hit("GPL-3.0-or-later", 1.0)],
        constant(False),
        "auto",
        given,
        unowned=lambda: unowned,
    )
    assert out == [("GPL-3.0-or-later" if unowned else "GPL-3.0-only", 1.0)]


@pytest.mark.parametrize(
    ("text", "is_pure", "expected"),
    [
        # "or any version later" is no phrase the reader owns: left alone.
        (
            "licensed under the GPL License version 3.0 or any version later.",
            False,
            "or-later",
        ),
        (
            "licensed under the GPL License version 3.0. Needs Python 3.8 or later.",
            False,
            "only",
        ),
        ("version 3.0. Needs Python 3.8 or any later version.", False, "only"),
        # A pure licence text is never read for a phrase.
        (
            "licensed under the GPL License version 3.0 or any version later.",
            True,
            "only",
        ),
    ],
)
def test_the_free_text_settling_reads_the_unowned_phrase(
    given: GivenWarnings, text: str, is_pure: bool, expected: str
) -> None:
    out = settle_free_text([_hit("GPL-3.0-or-later", 1.0)], text, is_pure, {})
    assert out[0]["license_id"] == f"GPL-3.0-{expected}"
    given.take()
