# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``VARIANT_STATED`` of a compound judges each operand (roadmap item 52): an
operand the option decided (``GPL-2.0`` read ``GPL-2.0-only``) is never stated
by another operand, even one of the same form that the expression merges
with it, in the argument, a tag and a JSON field."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import warnings
from collections.abc import Callable, Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from test_variant_invariants import ROWS as FAMILY_ROWS

from licenseid import variants
from licenseid.detector import LicenseDetector
from licenseid.exprtokens import RE_TOKEN
from licenseid.types import Variant

WITH_ROWS = (
    Lic("GPL-2.0-with-classpath-exception", "GPL v2 w/ Classpath", False, True),
    Lic("GPL-2.0-with-GCC-exception", "GPL v2 w/ GCC", False, True),
)
ROWS = (
    *FAMILY_ROWS,
    Lic("LGPL-2.1-only", "GNU Lesser General Public License v2.1 only", True),
    Lic("LGPL-2.1-or-later", "GNU Lesser General Public License v2.1 or later"),
    Lic("LGPL-2.1", "GNU Lesser General Public License v2.1", is_deprecated=True),
    *WITH_ROWS,
)
EXCEPTIONS = ["Classpath-exception-2.0", "GCC-exception-2.0"]
STATED, GUESSED = True, False
CP = "Classpath-exception-2.0"
CASES = [
    # Another operand of the same form merges with the decided one.
    ("GPL-2.0 OR GPL-2.0-only", GUESSED),
    ("GPL-2.0-only OR GPL-2.0", GUESSED),
    ("GPL-2.0-only AND gpl-2.0", GUESSED),
    ("GPL-2.0-only AND GPL-2.0-only AND GPL-2.0", GUESSED),
    ("Apache-2.0 AND GPL-3.0-only AND GPL-3.0", GUESSED),
    ("GPL-3.0-only AND GPLv3", GUESSED),
    ("GPLv2 AND GPL-2.0-only", GUESSED),
    ("GPL-2.0-or-later OR GPL-2.0", GUESSED),
    ("GPL-2.0+ AND GPL-2.0", GUESSED),
    ("GPL-2.0 OR GPL-2.0+", GUESSED),
    ("LGPL-2.0+ AND LGPL-2.0", GUESSED),
    (f"GPL-2.0-only WITH {CP} AND GPL-2.0 WITH {CP}", GUESSED),
    (f"GPL-2.0-with-classpath-exception AND GPL-2.0-only WITH {CP}", GUESSED),
    (f"GPL-2.0-or-later WITH {CP} OR GPL-2.0 WITH {CP}", GUESSED),
    ("GPL-2.0-only AND GPL-2.0 WITH GCC-exception-2.0", GUESSED),
    ("GPL-2.0-only OR LGPL-2.1", GUESSED),
    ("LGPL-2.1+ OR GPL-2.0", GUESSED),
    ("GPL-2.0 OR MIT+", GUESSED),
    # Every operand states its variant.
    ("GPL-2.0-only OR GPL-2.0+", STATED),
    ("(GPL-2.0-only OR MIT) AND (GPLv2-only OR Apache-2.0)", STATED),
    ("GPL-2.0-only AND GPL-2.0-only", STATED),
    ("gpl-2.0-only AND GPL-2.0-ONLY", STATED),
    ("GPLv2-only AND GPL-2.0-only", STATED),
    ("AGPL-3.0-only AND GPL-2.0-only", STATED),
    ("GPL-2.0-only WITH Classpath-exception-2.0 AND GPL-2.0-only", STATED),
    ("GPL-2.0-only OR GPL-2.0-or-later", STATED),
    ("MIT AND GPL-2.0-only", STATED),
    ("GPL-2.0-or-later OR MIT+", STATED),
    ("MIT OR GPL-2.0+", STATED),
]
CHANNELS: dict[str, Callable[[str], str]] = {
    "argument": lambda v: v,
    "tag": lambda v: f"# SPDX-License-Identifier: {v}\n",
    "json": lambda v: json.dumps({"license": v}),
}
OPTIONS: list[Variant] = ["only", "or-later"]


@pytest.fixture(scope="module")
def detector() -> Generator[LicenseDetector, None, None]:
    for path in seeded_db("test_variant_operands", ROWS, EXCEPTIONS):
        yield LicenseDetector(path)


@pytest.mark.parametrize("variant", OPTIONS)
@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize(("value", "stated"), CASES)
def test_an_operand_is_stated_by_its_own_words_only(
    detector: LicenseDetector, value: str, stated: bool, channel: str, variant: Variant
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = detector.detect(text=CHANNELS[channel](value), variant=variant)
    if not found:
        pytest.skip("this channel gives no answer (a tag takes List IDs only)")
    assert found[0]["variant_stated"] is stated, found[0]["expression"]
    if not stated:
        assert found[0]["exact"] is False


@pytest.mark.parametrize("variant", OPTIONS)
@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("value", [value for value, _ in CASES])
def test_every_form_the_option_decided_is_marked(
    detector: LicenseDetector,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    channel: str,
    variant: Variant,
) -> None:
    """The guard: a form ``variants._decide`` chose and the answer holds has a
    mark in ``evidence.decided`` (a reader that decides without marking would
    let another operand of the value state it)."""
    chosen: set[str] = set()
    real = variants._decide  # pylint: disable=protected-access

    def spy(lic_id: str, option: Variant) -> str | None:
        out = real(lic_id, option)
        if out:
            chosen.add(RE_TOKEN.findall(out)[0].casefold())
        return out

    monkeypatch.setattr(variants, "_decide", spy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = detector._match_raw(  # pylint: disable=protected-access
            text=CHANNELS[channel](value), variant=variant
        )
    if not raw:
        pytest.skip("no answer")
    held = {token.casefold() for token in RE_TOKEN.findall(raw[0]["license_id"])}
    marked = {form.casefold() for form in raw[0].get("evidence", {}).get("decided", [])}
    assert (chosen & held) <= marked, (chosen & held, marked)


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("MIT OR GPL-2.0 only", None),
        ("MIT AND GPL-2.0 only", None),
        ("LGPL-2.0 AND GPL-2.0 only", None),
        ("GPL-2.0 only OR MIT", None),
        ("GPL-2.0 only", "GPL-2.0-only"),  # one licence: its "only" is stated
    ],
)
def test_a_tag_refuses_an_only_after_an_operand_of_a_list(
    detector: LicenseDetector, value: str, expression: str | None
) -> None:
    """The argument and a field refuse these (a word of several words in one
    operand), and a tag does now: the "only" of one operand is no reading of
    the list, and an answer would state a variant the other operand did not
    (roadmap item 52, flipped from a pin of main)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = detector.detect(text=CHANNELS["tag"](value), variant="auto")
    assert [r["expression"] for r in found[:1]] == ([expression] if expression else [])


@pytest.mark.parametrize(
    ("value", "exact"),
    [
        ("GPL-2.0-with-classpath-exception", True),
        ("GPL v2 with classpath exception", False),  # a rule re-spelt the ID
        ("GPL-2.0-with-classpath-exception/MIT", True),  # a slash pair is exact
    ],
)
def test_a_with_id_a_rule_re_spelt_is_not_exact(
    detector: LicenseDetector, value: str, exact: bool
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = detector.detect(text=value, variant="auto")
    assert found[0]["exact"] is exact
