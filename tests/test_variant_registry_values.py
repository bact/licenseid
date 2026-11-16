# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Licence field values that package registries declare (npm, crates.io, Maven,
PyPI; only the SPDX IDs and short values are kept), through the argument, a
JSON field and a tag, with the variant options (roadmap item 52)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import warnings
from collections.abc import Callable, Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import seeded_db
from test_variant_operands import EXCEPTIONS, ROWS

from licenseid.detector import LicenseDetector
from licenseid.types import Variant
from licenseid.warning import LicenseIdWarning

CHANNELS: dict[str, Callable[[str], str]] = {
    "argument": lambda v: v,
    "json": lambda v: json.dumps({"license": v}),
    "tag": lambda v: f"# SPDX-License-Identifier: {v}\n",
}


@pytest.fixture(scope="module")
def detector() -> Generator[LicenseDetector, None, None]:
    for path in seeded_db(
        "test_variant_registry_values", ROWS, [*EXCEPTIONS, "LLVM-exception"]
    ):
        yield LicenseDetector(path)


def first(detector: LicenseDetector, text: str, variant: Variant) -> dict[str, object]:
    with warnings.catch_warnings(record=True) as given:
        warnings.simplefilter("always")
        found = detector.detect(text=text, variant=variant)
    # Only licenseid's own warnings: a collection in this block can close an
    # earlier test's database (a ResourceWarning, Python 3.13+).
    given = [w for w in given if isinstance(w.message, LicenseIdWarning)]
    top = found[0]
    return {
        "expression": top["expression"],
        "exact": top["exact"],
        "stated": top["variant_stated"],
        "warned": [str(w.message).split(";", maxsplit=1)[0] for w in given],
    }


@pytest.mark.parametrize("channel", CHANNELS)
def test_a_cargo_licence_expression_reads_alike_in_every_channel(
    detector: LicenseDetector, channel: str
) -> None:
    """A crates.io value (ring, rustls): the operands in one canonical order,
    whatever the channel (the field and the tag kept the written order)."""
    value = "Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT"
    got = first(detector, CHANNELS[channel](value), "auto")
    assert got["expression"] == "Apache-2.0 OR MIT OR Apache-2.0 WITH LLVM-exception"
    assert got["warned"] == []


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize(
    ("variant", "expression", "warned"),
    [
        ("auto", "GPL-3.0", []),  # an npm/PyPI value, kept as declared
        ("as-written", "GPL-3.0", []),
        ("only", "GPL-3.0-only", ["input: variant not stated: GPL-3.0"]),
        ("or-later", "GPL-3.0-or-later", ["input: variant not stated: GPL-3.0"]),
    ],
)
def test_a_bare_gpl_id_is_kept_or_decided_by_the_option(
    detector: LicenseDetector,
    channel: str,
    variant: Variant,
    expression: str,
    warned: list[str],
) -> None:
    got = first(detector, CHANNELS[channel]("GPL-3.0"), variant)
    assert got["expression"] == expression
    assert got["warned"] == warned
    assert got["stated"] is False
    assert got["exact"] is (variant in ("auto", "as-written"))


@pytest.mark.parametrize("channel", ["argument", "json"])
def test_a_maven_name_a_rule_read_is_not_exact(
    detector: LicenseDetector, channel: str
) -> None:
    """``Apache 2.0`` (a Maven licence name) is Apache-2.0 by a rewrite rule."""
    got = first(detector, CHANNELS[channel]("Apache 2.0"), "auto")
    assert (got["expression"], got["exact"]) == ("Apache-2.0", False)
