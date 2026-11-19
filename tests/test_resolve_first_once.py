# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect()`` reads a value ``resolve()`` reads once (B3, the 0.9.0 speed
fix).

``resolve()`` is a fixed point of its own answers: no rewrite rule reads an
expression it gave (:func:`ruleread.rule_read` is False), so ``detect()`` need
not ask a second time whether the answer of ``resolve()`` was read by a rule.
The first test holds that, over the corpora and the generator. The call counts
pin how often ``resolve_with`` runs for one call; a value a tag declares is the
user's, not ``resolve()``'s, and is read again on purpose.
"""
# pylint: disable=missing-function-docstring

import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final
from unittest import mock

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_db import value_detector
from harness_gen import generate
from resolver_corpus import FIXTURES, PARITY_FILE, read_rows

from licenseid import resolver
from licenseid.detector import LicenseDetector
from licenseid.ruleread import rule_read
from licenseid.types import Detection
from tools.pypi_licence_sample.answer import unescape_field

pytestmark = pytest.mark.filterwarnings("ignore::licenseid.LicenseIdWarning")

COMPOUNDS_FILE: Final = FIXTURES / "resolver_compounds_generated.tsv"
GENERATED: Final = 2000

#: Fewer values than this read to an expression: the test no longer reaches
#: its check (measured on the corpora: 101 parity, 74 compounds, 621 generated).
MIN_READ: Final = {"parity": 90, "compounds": 50, "generated": 500}


def _column(path: Path) -> list[str]:
    """The ``value`` column of a TSV fixture, unescaped."""
    return [unescape_field(row["value"]) for row in read_rows(path)]


#: Each corpus of the invariant, read at the first use.
CORPORA: Final[dict[str, Callable[[], list[str]]]] = {
    "parity": lambda: _column(PARITY_FILE),
    "compounds": lambda: _column(COMPOUNDS_FILE),
    "generated": lambda: list(generate(1, GENERATED)),
}


@pytest.mark.parametrize("name", CORPORA)
def test_no_rule_reads_an_expression_resolve_gave(name: str) -> None:
    """The invariant behind reading once: for every value ``resolve()`` reads
    to an expression E, ``rule_read(E)`` is False. A rule that read its own
    output would make a tag or a field of E inexact, so the second read of
    ``detect()`` would no longer be a no-op."""
    db = value_detector().db
    read = 0
    broken: list[str] = []
    for value in CORPORA[name]():
        expression = resolver.resolve_with(db, value)["expression"]
        if expression is None:
            continue
        read += 1
        if rule_read(db, expression):
            broken.append(f"{value!r} -> {expression!r}")
    assert read > MIN_READ[name]  # the test reaches the check
    assert not broken, "\n" + "\n".join(broken[:20])


@contextmanager
def _counted() -> Iterator[Callable[[], int]]:
    """Count the calls of ``resolve_with`` made through the two modules that
    read a value for ``detect()``: ``detector`` and ``ruleread``."""
    real = resolver.resolve_with
    with (
        mock.patch(
            "licenseid.detector.resolve_with", autospec=True, side_effect=real
        ) as in_detector,
        mock.patch(
            "licenseid.ruleread.resolve_with", autospec=True, side_effect=real
        ) as in_ruleread,
    ):
        yield lambda: in_detector.call_count + in_ruleread.call_count


def _detect(
    *, text: str | None = None, license_id: str | None = None
) -> tuple[int, list[Detection]]:
    """``detect()`` on the harness database: the number of ``resolve_with``
    calls it makes, and its results."""
    detector: LicenseDetector = value_detector()
    with _counted() as calls, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = detector.detect(text=text, license_id=license_id)
        return calls(), found


@pytest.mark.parametrize(
    ("kwargs", "answer"),
    [
        ({"text": "MIT"}, "MIT"),
        ({"text": "Apache License 2.0"}, "Apache-2.0"),
        ({"license_id": "GPL2"}, "GPL-2.0"),
    ],
    ids=["text-MIT", "text-Apache-name", "id-GPL2"],
)
def test_a_whole_value_is_read_once(kwargs: dict[str, str], answer: str) -> None:
    """``detect()`` asks ``resolve()`` once and takes its expression as
    resolved: ``tag_inexact`` makes no second read (B3). ``--id GPL2`` reaches
    ``resolve()`` last, after the marker reader and the loose ID reader."""
    calls, found = _detect(**kwargs)
    assert found[0]["expression"] == answer
    assert calls == 1


def test_an_id_that_resolve_reads_is_read_once() -> None:
    """``--id MIT``: the marker reader answers it before ``resolve()``."""
    calls, found = _detect(license_id="MIT")
    assert found[0]["expression"] == "MIT"
    assert calls == 1


def test_a_tag_is_read_by_its_rule_check() -> None:
    """The whole value is no expression (resolve() refuses the line); the tag
    reader then judges its own expression, so the second read stays."""
    calls, found = _detect(text="SPDX-License-Identifier: LGPLv2 or later")
    assert found[0]["expression"] == "LGPL-2.0-or-later"
    assert calls == 2


def _first(text: str | None = None, license_id: str | None = None) -> Detection:
    return _detect(text=text, license_id=license_id)[1][0]


def test_a_tag_of_a_cut_version_with_a_grant_stays_inexact() -> None:
    top = _first(text="SPDX-License-Identifier: LGPLv2 or later")
    assert (top["expression"], top["method"], top["exact"]) == (
        "LGPL-2.0-or-later",
        "tag",
        False,
    )


def test_a_tag_with_a_plus_on_a_loose_id_stays_inexact() -> None:
    top = _first(text="SPDX-License-Identifier: GPL2+")
    assert (top["expression"], top["method"], top["exact"]) == (
        "GPL-2.0-or-later",
        "tag",
        False,
    )


def test_an_id_written_loosely_stays_inexact() -> None:
    top = _first(license_id="GPL2")
    assert (top["expression"], top["method"], top["exact"]) == (
        "GPL-2.0",
        "id",
        False,
    )


def test_a_field_of_a_cut_version_with_a_grant_stays_inexact() -> None:
    """A manifest field is the user's value, not an expression ``resolve()``
    gave: its rule check stays."""
    top = _first(text='{"license": "GPLv2 or later"}')
    assert (top["expression"], top["method"], top["exact"]) == (
        "GPL-2.0-or-later",
        "field",
        False,
    )
