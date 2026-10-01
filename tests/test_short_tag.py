# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An SPDX-License-Identifier tag in an input of any length, a header line
included. Roadmap items 24 and 25."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import time
from collections.abc import Generator

import pytest
from conftest import MIT_SEARCH_TEXT
from matcher_db import GPL2_ROWS, Lic, seeded_db

from licenseid.identifiers import parse_expression
from licenseid.matcher import AggregatedLicenseMatcher

TAG = "SPDX-License-Identifier:"
# Takes a short input past 30 words, where markers were always read.
FILLER = " ".join(["widget"] * 40)


@pytest.fixture(scope="module")
def db() -> Generator[str, None, None]:
    rows = [
        Lic("MIT", "MIT License", True, True, True, search_text=MIT_SEARCH_TEXT),
        Lic("Apache-2.0", "Apache License 2.0", True, True, True, search_text="x"),
        *GPL2_ROWS,
        Lic(
            "GPL-2.0-with-classpath-exception",
            "GNU General Public License v2.0 w/Classpath exception",
            is_deprecated=True,
        ),
    ]
    yield from seeded_db("test_short_tag", rows, ["Classpath-exception-2.0"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Tier 0 read these as a name: Apache-2.0 at 1.01, dropping MIT.
        (f"{TAG} MIT OR Apache-2.0", "Apache-2.0 OR MIT"),
        (
            f"// {TAG} GPL-2.0-or-later WITH Classpath-exception-2.0",
            "GPL-2.0-or-later WITH Classpath-exception-2.0",
        ),
        (f"# {TAG} Apache-2.0\n", "Apache-2.0"),
        (f"/* {TAG} GPL-2.0 */", "GPL-2.0-only"),
        (f"{TAG} GPL-2.0+", "GPL-2.0-or-later"),
        (
            f"{TAG} GPL-2.0-with-classpath-exception",
            "GPL-2.0-only WITH Classpath-exception-2.0",
        ),
    ],
    ids=["or", "with", "hash-comment", "deprecated", "plus", "deprecated-with"],
)
@pytest.mark.parametrize("large", [False, True], ids=["header-line", "long"])
def test_a_tag_answers_at_any_length(
    db: str, text: str, expected: str, large: bool
) -> None:
    results = AggregatedLicenseMatcher(db).match(
        text=f"{FILLER}\n{text}" if large else text
    )
    assert [(r["license_id"], r["score"]) for r in results] == [(expected, 1.0)]
    assert results[0]["is_spdx"]


def test_a_tag_naming_no_license_falls_through(db: str) -> None:
    """A value that is no expression is no answer; Tier 0 goes on as before."""
    results = AggregatedLicenseMatcher(db).match(text=f"{TAG} Proprietary")
    assert all(r["score"] != 1.0 for r in results)


@pytest.mark.parametrize(
    "text",
    [
        # A manifest field and a tag both declare: both answer, as in a
        # large manifest.
        f'# {TAG} Apache-2.0\n[project]\nname = "x"\nlicense = "MIT"\n',
        # A tag in prose reads as it does in a long text.
        f"Add {TAG} MIT to each file",
    ],
    ids=["manifest-and-tag", "prose"],
)
def test_a_short_input_reads_its_tag_as_a_long_one_does(db: str, text: str) -> None:
    matcher = AggregatedLicenseMatcher(db)
    short = matcher.match(text=text)
    long = matcher.match(text=f"{text}\n# {FILLER}")
    assert short and short == long


def test_a_short_input_reads_no_loose_field(db: str) -> None:
    """Only a declaration is certain; "License:" in prose is not one."""
    detector = AggregatedLicenseMatcher(db).detector
    assert not detector.detect_declared("License: MIT", [])


def test_a_long_tag_value_reads_in_linear_time(db: str) -> None:
    """One 1,000,000-character token cost the expression parser 7 s: its
    tokenizer is quadratic in a token's length (roadmap item 26)."""
    detector = AggregatedLicenseMatcher(db).detector
    text = f"{TAG} " + "x" * 1_000_000
    start = time.monotonic()
    assert not detector.detect_declared(text, [])
    assert time.monotonic() - start < 0.5


@pytest.mark.parametrize(
    ("expression", "parsed"),
    [
        ("LicenseRef-" + "a" * 245, True),  # 256 characters
        ("LicenseRef-" + "a" * 246, False),
        ("((LicenseRef-" + "a" * 245 + "))", True),  # brackets do not count
        ("MIT OR LicenseRef-" + "a" * 245, True),
        # The parser's breaks: each beside a token at the limit.
        (
            "\tOR\n".join(["LicenseRef-" + "a" * 245] * 2)
            + "\rOR LicenseRef-"
            + "b" * 245,
            True,
        ),
        # The parser does not break at other white space, so neither may the
        # guard: one token of a million characters to the parser.
        (("x" * 200 + " ") * 5000, False),
        ("x" * 1_000_000, False),
    ],
    ids=["at-limit", "over-limit", "brackets", "with-operator", "tab", "nbsp", "huge"],
)
def test_the_parser_refuses_an_overlong_token(expression: str, parsed: bool) -> None:
    start = time.monotonic()
    assert (parse_expression(expression) is not None) is parsed
    assert time.monotonic() - start < 0.5
