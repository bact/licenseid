# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A deprecated ID of a name or text match whose replacement was dropped
(``exclude``, or a rule of :mod:`licenseid.namehits`) goes with it; the
warning of a decided variant names the licence; a kept deprecated row is
judged by its ``-only`` twin (roadmap item 52, 0.9.0 review)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import itertools
import warnings
from collections.abc import Generator

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_db import value_detector
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.deprecatedids import (
    DEPRECATED_BARE_LICENSE_IDS,
    DEPRECATED_SPDX_LICENSE_IDS,
)
from licenseid.detector import LicenseDetector
from licenseid.grantsubject import Signals, constant
from licenseid.listlookup import fold_case
from licenseid.normalize import normalize_text
from licenseid.shorttext import match_short_text
from licenseid.types import Method, RawMatch, Variant
from licenseid.variants import family_of, reading, settle_text
from licenseid.warning import LicenseIdWarning

#: The deprecated IDs a text match never answers (``variants._REPLACED_BY``).
DEPRECATED = {
    fold_case(lid)
    for lid in (*DEPRECATED_BARE_LICENSE_IDS, *DEPRECATED_SPDX_LICENSE_IDS)
}
DECIDING: tuple[Variant, ...] = ("auto", "only", "or-later")
GPL2 = "GNU General Public License v2.0"

# --- A deprecated ID goes with its dropped replacement ---

NAMES = (
    "GNU Affero General Public License v3.0",
    "GNU Lesser General Public License v2.1",
    "GNU Lesser General Public License v3.0",
    "GNU Library General Public License v2",
)
HEADS = ("", "Distributed under the ")
TAILS = (" or later", " only")


@pytest.mark.parametrize("variant", DECIDING)
@pytest.mark.parametrize(
    "text",
    [h + n + t for h, n, t in itertools.product(HEADS, NAMES, TAILS)],
)
def test_a_name_rule_takes_the_deprecated_id_with_its_replacement(
    text: str, variant: Variant
) -> None:
    """An AGPL or LGPL name loses the GPL hit it holds (``namehits``): the
    deprecated GPL ID of that hit is no answer either, at any rank."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        found = value_detector().detect(text=text, variant=variant)
    assert found
    assert not [
        r["expression"] for r in found if fold_case(r["expression"]) in DEPRECATED
    ]


@pytest.mark.parametrize("variant", DECIDING)
@pytest.mark.parametrize(
    "text", [GPL2, f"{GPL2}. Requires Python 3.8 or later"], ids=["name", "python"]
)
def test_an_excluded_twin_takes_the_bare_id_with_it(
    given: GivenWarnings, text: str, variant: Variant
) -> None:
    """``-only`` excluded: the ``-or-later`` twin answers whole, a guess said
    once, whatever the option."""
    found = value_detector().detect(
        text=text, variant=variant, exclude=["GPL-2.0-only"]
    )
    assert (found[0]["expression"], found[0]["score"]) == ("GPL-2.0-or-later", 1.0)
    assert not [r for r in found if fold_case(r["expression"]) in DEPRECATED]
    assert given.lines() == (
        "WARNING: input: variant not stated: GPL-2.0; using GPL-2.0-or-later\n"
    )


@pytest.mark.parametrize("variant", DECIDING)
def test_an_excluded_stated_twin_is_not_answered_as_the_bare_id(
    variant: Variant,
) -> None:
    text = f"licensed under the {GPL2} only"
    with pytest.warns(LicenseIdWarning, match="variant not stated"):
        found = value_detector().detect(
            text=text, variant=variant, exclude=["GPL-2.0-only"]
        )
    assert found
    assert not [r for r in found if fold_case(r["expression"]) in DEPRECATED]
    assert "GPL-2.0-only" not in [r["expression"] for r in found]


@pytest.mark.parametrize("method", ["id", "tag"])
def test_a_declared_deprecated_id_stays_without_its_twin(method: Method) -> None:
    """Only a text or name match loses the deprecated ID: one a reader
    declared is kept as written under ``auto``."""
    hit = RawMatch(
        license_id="GPL-2.0",
        method=method,
        exact=True,
        score=1.0,
        similarity=None,
        coverage=None,
    )
    (kept,) = settle_text([hit], Signals(constant(False)), "auto")
    assert kept["license_id"] == "GPL-2.0"


def test_as_written_still_keeps_the_bare_id() -> None:
    """``as-written`` never drops a deprecated ID of a text."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        found = value_detector().detect(
            text=GPL2, variant="as-written", exclude=["GPL-2.0-only"]
        )
    assert "GPL-2.0" in [r["expression"] for r in found]


# --- The warning names the licence, not an ID or an expression ---


@pytest.mark.parametrize(
    ("resolved", "written", "family"),
    [
        ("GPL-2.0-only", "GPL-2.0-only OR GPL-2.0", "GPL-2.0"),
        ("GPL-2.0-or-later", "GPL-2.0-or-later OR GPL-2.0", "GPL-2.0"),
        ("MIT OR GPL-2.0-only", "MIT OR GPL-2.0-only", "GPL-2.0"),
        ("GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0-only OR LGPL-2.1-only", "GPL-2.0"),
        ("MIT", "MIT", "MIT"),
    ],
)
def test_every_form_written_still_names_the_licence(
    resolved: str, written: str, family: str
) -> None:
    assert family_of(resolved, written) == family


@pytest.mark.parametrize("variant", ["only", "or-later"])
@pytest.mark.parametrize(
    "value", ["GPL-2.0-only OR GPL-2.0", "GPL-2.0 OR GPL-2.0-only"]
)
def test_the_warning_of_a_merged_operand_names_the_licence(
    given: GivenWarnings, value: str, variant: Variant
) -> None:
    value_detector().detect(text=value, variant=variant)
    details = [w.detail for w in given.take() if w.condition == "variant not stated"]
    assert details == ["GPL-2.0"]


# --- A kept deprecated row has its -only twin's flags ---

AGPL1 = "Affero General Public License v1.0"
GCC3 = "GNU General Public License v3.0 w/GCC Runtime Library exception"
CLASSPATH = "GNU General Public License v2.0 w/Classpath exception"
ROWS = (
    Lic("AGPL-1.0-only", f"{AGPL1} only"),
    Lic("AGPL-1.0-or-later", f"{AGPL1} or later"),
    Lic("AGPL-1.0", AGPL1, is_fsf_libre=True, is_deprecated=True),
    Lic("GPL-3.0-only", "GNU General Public License v3.0 only", True, True, True),
    Lic(
        "GPL-3.0-or-later", "GNU General Public License v3.0 or later", True, True, True
    ),
    Lic("GPL-3.0-with-GCC-exception", GCC3, True, True, is_deprecated=True),
    Lic("GPL-2.0-only", f"{GPL2} only", True, True, True),
    Lic("GPL-2.0-or-later", f"{GPL2} or later", True, True, True),
    Lic("GPL-2.0-with-classpath-exception", CLASSPATH, is_deprecated=True),
    Lic("MIT", "MIT License", True, True, True, search_text="mit"),
)


@pytest.fixture(scope="module")
def flags_db() -> Generator[str, None, None]:
    yield from seeded_db(
        "test_variant_dropped_twin",
        ROWS,
        ["GCC-exception-3.1", "Classpath-exception-2.0"],
    )


def test_a_kept_deprecated_name_answer_is_judged_by_its_twin(flags_db: str) -> None:
    detector = LicenseDetector(flags_db)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        (hit, *_) = detector.detect(text=AGPL1, variant="as-written")
    assert hit["expression"] == "AGPL-1.0"
    assert hit["is_fsf_libre"] is detector.is_fsf("AGPL-1.0") is False


@pytest.mark.parametrize(
    ("text", "lic_id", "judged"),
    [
        (AGPL1, "AGPL-1.0", False),
        (GCC3, "GPL-3.0-with-GCC-exception", True),
        (CLASSPATH, "GPL-2.0-with-classpath-exception", True),
        ("AGPL-1.0", "AGPL-1.0", False),
        ("AGPL1", "AGPL-1.0", False),
    ],
    ids=["agpl_name", "gcc_name", "classpath_name", "id", "loose"],
)
def test_a_kept_deprecated_hit_of_the_name_tier_is_judged_by_its_twin(
    flags_db: str, text: str, lic_id: str, judged: bool
) -> None:
    """The name tier as a section of a mixed text reads it."""
    with reading("as-written"):
        found = match_short_text(
            LicenseDatabase(flags_db, create=False), normalize_text(text), text
        )
    flags = {r["license_id"]: (r["is_osi_approved"], r["is_fsf_libre"]) for r in found}
    assert flags[lic_id] == (judged, judged)
