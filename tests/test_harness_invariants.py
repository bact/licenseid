# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Invariants over the resolver corpus and the adversarial generator
(``harness_gen``, seed ``harness_checks.SEED``): about 2,000 generated
values on every commit, 20,000 with ``--run-benchmark``. A breaker is a
finding: mark its test ``xfail(strict=True, reason="BUG: ...")`` with a
minimal reproducer, do not weaken the check."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Callable, Iterator

import harness_checks as hc
import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_db import harness_detector
from harness_gen import generate
from packaged_list import fixture_bundle, masked
from release_fakes import ship

from licenseid import InvalidInputError, LicenseDatabase, match
from licenseid.types import Detection

# A warning is not a failure here: the checks ask what a call returns.
pytestmark = pytest.mark.filterwarnings("ignore::licenseid.LicenseIdWarning")

COUNT = 2000
DETECT_STEP = 14  # detect() costs about 20 ms a value: one value in 14
BENCHMARK_COUNT = 20000


def values(count: int) -> list[str]:
    """The corpus, then *count* generated values."""
    return [*hc.corpus_values(), *generate(hc.SEED, count)]


@pytest.fixture(scope="module")
def sample() -> list[str]:
    return values(COUNT)


@pytest.fixture(autouse=True)
def packaged(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The List of the fixtures as the bundle the wheel ships."""
    ship(monkeypatch, fixture_bundle())
    yield


def assert_none_break(batch: list[str], check: Callable[[str], str | None]) -> None:
    broken = hc.failures(batch, check)
    assert not broken, "\n" + "\n".join(broken)


def test_match_never_raises(sample: list[str]) -> None:
    assert_none_break(sample, hc.never_raises_match)


@pytest.fixture(scope="module")
def detected(sample: list[str]) -> dict[str, list[Detection] | Exception]:
    """``detect(text=...)`` of every ``DETECT_STEP``-th value, once."""
    return hc.detect_all(harness_detector(), sample[::DETECT_STEP])


def assert_none_break_outcomes(
    detected: dict[str, list[Detection] | Exception],
    check: Callable[[list[Detection] | Exception], str | None],
) -> None:
    broken = hc.failures(detected, lambda value: check(detected[value]))
    assert not broken, "\n" + "\n".join(broken)


def test_detect_never_raises(
    detected: dict[str, list[Detection] | Exception],
) -> None:
    assert_none_break_outcomes(detected, hc.detect_never_raises)


def test_detect_text_json_and_canonical_form_agree(
    detected: dict[str, list[Detection] | Exception],
) -> None:
    assert_none_break_outcomes(detected, hc.detect_output_agrees)


def test_an_answer_read_again_gives_itself(sample: list[str]) -> None:
    assert_none_break(sample, hc.answer_is_stable)


def test_match_text_json_and_canonical_form_agree(sample: list[str]) -> None:
    assert_none_break(sample, hc.match_output_agrees)


def test_the_packaged_list_and_the_database_agree(
    sample: list[str], bundle_db: LicenseDatabase
) -> None:
    def check(value: str) -> str | None:
        try:
            packaged = match(value, source="packaged")
        except InvalidInputError:
            packaged = None
        try:
            stored = match(value, bundle_db)
        except InvalidInputError:
            stored = None
        if (packaged is None) != (stored is None):
            return "one refuses the input, the other does not"
        if (
            packaged is not None
            and stored is not None
            and masked(packaged) != masked(stored)
        ):
            return f"{packaged['expression']!r} / {stored['expression']!r}"
        return None

    assert_none_break(sample, check)


@pytest.mark.parametrize(
    "check",
    [hc.never_raises_match, hc.answer_is_stable, hc.match_output_agrees],
    ids=lambda check: check.__name__,
)
def test_a_breaker_is_named(check: Callable[[str], str | None]) -> None:
    """The report of a failing check names the value (mutation check of the
    harness itself)."""
    report = hc.failures(["MIT", "x"], lambda value: "bad" if value == "x" else None)
    assert report == ["'x': bad", "(1 in all)"]
    assert check("MIT") is None


@pytest.mark.benchmark
def test_a_long_run_breaks_nothing() -> None:
    """The stream of the every-commit run, ten times longer."""
    batch = values(BENCHMARK_COUNT)
    for check in (hc.never_raises_match, hc.answer_is_stable, hc.match_output_agrees):
        assert_none_break(batch, check)
    outcomes = hc.detect_all(harness_detector(), batch[::40])
    for outcome_check in (hc.detect_never_raises, hc.detect_output_agrees):
        assert_none_break_outcomes(outcomes, outcome_check)
