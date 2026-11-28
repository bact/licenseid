# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A text found whole answers alone: beside it, no look-alike that nothing
names is a result (roadmap items 13 and 68, ``ranking.under_found``).
Through ``detect()`` and the CLI; the rule on made-up tables is in
``test_whole_text_rules``.

The database of the Apache-2.0 family holds the real texts of the
look-alikes (``Pixar`` is Apache-2.0 with another section 6, ``ImageMagick``
and ``ECL-2.0`` are near copies): without them the tests would pass whatever
the code does. The real file is the ``LICENSE`` of rfc8785 0.1.4, the Apache
2.0 text without its appendix, which answered ``Apache-2.0`` 1.0 with
``Pixar`` 0.9947 and ``ImageMagick`` 0.9871 beside it in 0.10.0."""
# pylint: disable=missing-function-docstring

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from long_text_db import long_text_detector
from template_texts import long_text, template_texts_db

from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.retrieval import Candidates, get_candidates
from licenseid.types import DetectOptions
from licenseid.warning import LicenseIdWarning

REAL_FILE = (
    Path(__file__).parent / "fixtures" / "real-files" / "rfc8785-0.1.4-LICENSE.txt"
)
APACHE_FAMILY = ("Apache-2.0", "ECL-2.0", "ImageMagick", "Pixar", "MIT")
LOOK_ALIKES = {"Pixar", "ImageMagick", "ECL-2.0"}


@pytest.fixture(scope="module", name="family_db")
def _family_db(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    yield str(
        template_texts_db(tmp_path_factory.mktemp("apache_family"), APACHE_FAMILY)
    )


@pytest.fixture(name="family")
def _family(family_db: str) -> LicenseDetector:
    return LicenseDetector(family_db)


def _candidates(detector: LicenseDetector, text: str, **options: Any) -> Candidates:
    with detector.db.reading():
        return get_candidates(detector.db, cast(DetectOptions, options), text)


def _ids(results: list[Any]) -> list[str]:
    return [r["expression"] for r in results]


def test_the_look_alikes_are_scored_beside_the_real_file(
    family: LicenseDetector,
) -> None:
    """The guard of the tests below: Tier 2 does score the look-alikes."""
    narrow = _candidates(family, REAL_FILE.read_text(encoding="utf-8")).narrowed
    assert narrow is not None and narrow.group == {"Apache-2.0"}
    assert narrow.runner_ups == LOOK_ALIKES


def test_a_verbatim_apache_file_answers_apache_alone(family: LicenseDetector) -> None:
    results = family.detect(REAL_FILE.read_text(encoding="utf-8"))
    assert _ids(results) == ["Apache-2.0"]
    assert (results[0]["score"], results[0]["exact"]) == (1.0, False)
    assert results[0]["texts"] == ["Apache-2.0"]


@pytest.mark.parametrize("license_id", sorted(LOOK_ALIKES | {"Apache-2.0"}))
def test_each_text_of_the_family_answers_itself_alone(
    family: LicenseDetector, license_id: str
) -> None:
    """A real ``Pixar`` text still answers ``Pixar``, not ``Apache-2.0``."""
    results = family.detect(long_text(license_id))
    assert _ids(results) == [license_id]
    assert results[0]["exact"] is True


def test_a_hinted_licence_that_is_no_runner_up_stays(family: LicenseDetector) -> None:
    results = family.detect(REAL_FILE.read_text(encoding="utf-8"), hint=["MIT"])
    assert _ids(results) == ["Apache-2.0", "MIT"]


def test_a_hinted_runner_up_stays_under_the_text_found(
    family: LicenseDetector,
) -> None:
    """A look-alike the caller names is a candidate in its own right."""
    results = family.detect(REAL_FILE.read_text(encoding="utf-8"), hint=["pixar"])
    assert _ids(results) == ["Apache-2.0", "Pixar"]


@pytest.mark.parametrize("lead", ["License: ECL-2.0", "Licensed under ECL-2.0."])
def test_a_runner_up_the_file_declares_stays(
    family: LicenseDetector, lead: str
) -> None:
    """The file names one of the look-alikes: that one stays, with the score
    0.10.0 gave it; the two that nothing names go."""
    results = family.detect(lead + "\n\n" + REAL_FILE.read_text(encoding="utf-8"))
    assert _ids(results) == ["Apache-2.0", "ECL-2.0"]
    assert 0.9 < results[1]["score"] < 1.0


def test_a_declared_licence_keeps_its_twin(given: GivenWarnings) -> None:
    """``LGPL-3.0-or-later`` declared above the GPL-3.0 text: both twins of
    the LGPL stay (the tie-breaker reads the pair), with the warnings of
    0.10.0."""
    text = "Licensed under LGPL-3.0-or-later.\n\n" + long_text("GPL-3.0-only")
    results = long_text_detector().detect(text)
    assert _ids(results) == [
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "LGPL-3.0-or-later",
        "LGPL-3.0-only",
    ]
    assert [str(w) for w in given.take()] == [
        "input: variant not stated: GPL-3.0; using GPL-3.0-only"
    ]


def test_without_the_text_found_no_look_alike_answers(family: LicenseDetector) -> None:
    """``exclude`` of the text found: no narrowing, and no text of the rest
    shares as much of the file (``gramselect.beyond_bar``)."""
    text = REAL_FILE.read_text(encoding="utf-8")
    assert not family.detect(text, exclude=["Apache-2.0"])
    assert _ids(family.detect(text, exclude=["Pixar"])) == ["Apache-2.0"]


def test_a_fragment_still_lists_its_look_alikes(family: LicenseDetector) -> None:
    """No text found whole, no narrowing: the selection, as before."""
    words = REAL_FILE.read_text(encoding="utf-8").split()
    fragment = " ".join(words[200:500])
    assert _candidates(family, fragment).narrowed is None
    results = family.detect(fragment)
    assert results[0]["texts"] is None
    assert set(_ids(results)) & LOOK_ALIKES


def test_a_twin_of_the_text_found_stays() -> None:
    """``GPL-3.0-only`` and ``GPL-3.0-or-later`` have one text. The text
    names the AGPL (section 13), a runner-up here, so it stays; the LGPL,
    which nothing names, goes."""
    text = long_text("GPL-3.0-only")
    narrow = _candidates(long_text_detector(), text).narrowed
    assert narrow is not None and "LGPL-3.0-only" in narrow.runner_ups
    with pytest.warns(LicenseIdWarning, match="variant not stated"):
        results = long_text_detector().detect(text)
    assert _ids(results) == ["GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0-only"]


def test_a_licence_the_text_names_stays() -> None:
    """The EPL-2.0 text names the GPL as a secondary licence: a marker's
    candidate, no runner-up, so it stays under the text found."""
    text = long_text("EPL-2.0")
    detector = long_text_detector()
    narrow = _candidates(detector, text).narrowed
    assert narrow is not None and narrow.runner_ups
    assert "GPL-2.0-or-later" not in narrow.runner_ups
    results = detector.detect(text)
    assert _ids(results) == ["EPL-2.0", "GPL-2.0-or-later"]
    assert results[1]["score"] < 0.85


@pytest.mark.parametrize("output", ["-v", "--json"])
def test_the_cli_prints_one_record_for_the_real_file(
    family_db: str, output: str
) -> None:
    args = ["--db", family_db, "detect", "--top", "5", output, str(REAL_FILE)]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    if output == "--json":
        assert json.loads(lines[0])["expression"] == "Apache-2.0"
    else:
        assert lines[0].startswith("EXPRESSION=Apache-2.0\t")
        assert "\tTEXTS=Apache-2.0" in lines[0]
