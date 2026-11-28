# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The public ``coverage`` is capped at 1, as the public score is (roadmap
item 80, finding 3): above 1 the value grew with any prose in a file, not
with licence text, and ``texts`` and ``exact`` say what a file holds. The
ranking, the marker floor and the first-text rule read the raw value."""
# pylint: disable=missing-function-docstring,protected-access

import pytest
from long_text_db import long_text_detector
from several_texts import several_text

from licenseid.result import detect_json, public_result, text_line
from licenseid.types import RawMatch


def _raw(coverage: float | None) -> RawMatch:
    return RawMatch(
        license_id="MIT",
        method="text",
        exact=False,
        score=0.9,
        similarity=0.9,
        coverage=coverage,
    )


@pytest.mark.parametrize(
    ("raw", "public"),
    [
        (263.8, 1.0),  # a README: the highest first row measured
        (2.1059, 1.0),  # a file twice the MIT text
        (1.0179, 1.0),  # a verbatim Apache-2.0 file
        (1.0001, 1.0),
        (1.00004, 1.0),
        (1.0, 1.0),
        (0.99996, 1.0),  # rounded to 4 places, as before
        (0.99994, 0.9999),
        (0.9987, 0.9987),
        (0.0299, 0.0299),
        (0.0, 0.0),
    ],
)
def test_the_coverage_is_capped_at_1_and_rounded(raw: float, public: float) -> None:
    assert public_result(_raw(raw), [])["coverage"] == public


def test_no_coverage_stays_none() -> None:
    """Nothing measured is nothing: never 1, 0 or an empty text."""
    result = public_result(_raw(None), [])
    assert result["coverage"] is None
    assert "\tCOVERAGE=\t" in text_line(result)
    assert '"coverage":null,' in detect_json(result)


def test_the_raw_match_keeps_its_coverage() -> None:
    raw = _raw(1.0179)
    public_result(raw, [])
    assert raw["coverage"] == 1.0179


def test_both_outputs_print_the_capped_value() -> None:
    result = public_result(_raw(2.1059), [])
    assert "\tCOVERAGE=1.0000\t" in text_line(result)
    assert detect_json(result).startswith('{"coverage":1,"exact":false,')


def test_a_file_of_two_texts_has_a_public_coverage_of_1() -> None:
    """The Apache-2.0 text, then the MIT text: the answer's raw coverage is
    about 1.12, above the marker floor's 1.05. The public form reads 1; the
    raw rows keep their values and the order stays Apache-2.0, then MIT."""
    detector = long_text_detector()
    text = several_text("apache-then-mit")
    raw = detector._match_raw(text=text)
    public = detector.detect(text=text)

    top = raw[0]["coverage"]
    assert [r["license_id"] for r in raw[:2]] == ["Apache-2.0", "MIT"]
    assert top is not None and 1.05 < top < 1.2
    assert [r["expression"] for r in public] == [r["license_id"] for r in raw]
    assert public[0]["texts"] == ["Apache-2.0", "MIT"]
    assert "\tCOVERAGE=1.0000\t" in text_line(public[0])
    # Every row: the second (MIT, a fragment of the file) is above 10 raw.
    assert [r["coverage"] for r in public] == [1.0] * len(raw)
    assert all((r["coverage"] or 0.0) > 1.0 for r in raw)


_APACHE_NOTICE = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""


def test_a_notice_in_long_prose_reads_1_and_names_no_text() -> None:
    """300 sentences, then Apache's header: the input is over twice as long
    as the Apache-2.0 text and holds none of it. Raw, the coverage grew with
    the prose; public, it is 1, and ``texts`` says no whole text is there."""
    prose = " ".join(
        f"Chapter {i} tells how the widget number {i} is built and tested."
        for i in range(300)
    )
    detector = long_text_detector()
    text = f"{prose}\n\n{_APACHE_NOTICE}"
    raw = detector._match_raw(text=text)[0]
    public = detector.detect(text=text)[0]
    assert raw["license_id"] == public["expression"] == "Apache-2.0"
    assert raw["coverage"] is not None and 2.0 < raw["coverage"] < 3.0
    assert (public["coverage"], public["texts"]) == (1.0, None)


def test_a_fragment_keeps_its_coverage() -> None:
    """A notice of the MPL-2.0: about 0.03 of the text, raw and public."""
    detector = long_text_detector()
    text = several_text("mpl-header-notice")
    raw = detector._match_raw(text=text)[0]["coverage"]
    public = detector.detect(text=text)[0]["coverage"]
    assert raw is not None and public is not None
    assert 0.02 < public < 0.04
    assert public == round(raw, 4)
