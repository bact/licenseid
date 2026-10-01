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


def _ref(length: int, letter: str = "a") -> str:
    """A LicenseRef ID of *length* characters."""
    return "LicenseRef-" + letter * (length - len("LicenseRef-"))


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
        # SPDX sets no length on a LicenseRef: none may be dropped (and an
        # expression this long keeps its order).
        (f"{TAG} MIT OR {_ref(300)}", f"MIT OR {_ref(300)}"),
    ],
    ids=[
        "or",
        "with",
        "hash-comment",
        "deprecated",
        "plus",
        "deprecated-with",
        "long-ref",
    ],
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


def test_a_long_license_ref_is_one_license(db: str) -> None:
    results = AggregatedLicenseMatcher(db).match(license_id=_ref(300))
    assert [r["license_id"] for r in results] == [_ref(300)]


@pytest.mark.parametrize(
    "value",
    [
        "Proprietary",
        # The name match read the license inside them: MIT at 1.01.
        "LicenseRef-MIT+",  # SPDX gives "+" to a license ID only
        "MIT OR",  # a dangling operator
        "(MIT",
        "",
    ],
)
def test_a_tag_naming_no_license_is_no_name_to_match(db: str, value: str) -> None:
    """The tag was read and named no license, and there is nothing else."""
    assert not AggregatedLicenseMatcher(db).match(text=f"// {TAG} {value}")


def test_a_name_beside_a_refused_tag_still_answers(db: str) -> None:
    results = AggregatedLicenseMatcher(db).match(text=f"{TAG} Proprietary\nMIT")
    assert [r["license_id"] for r in results][:1] == ["MIT"]
    assert results[0]["score"] >= 1.0


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
        # SPDX sets no length on a LicenseRef; 256 characters used to be
        # refused, and a tag lost the license.
        (_ref(300), True),
        # The parse budget is the sum of squared token lengths, 10**9.
        # Exactly the budget: 31,598^2 + 1,108^2 + 582^2 + 2 * 2^2 ("OR").
        (f"{_ref(31_598)} OR {_ref(1_108, 'b')} OR {_ref(582, 'c')}", True),
        (_ref(31_623), False),  # 1,000,014,129
        ("((" + _ref(31_622) + "))", True),  # brackets break a token
        # The sum, not the longest: two tokens each within the budget.
        (f"{_ref(22_360)} OR {_ref(22_360, 'b')}", True),
        (f"{_ref(22_361)} OR {_ref(22_361, 'b')}", False),
        # The parser's breaks, each between two long tokens: a pair joined
        # into one token would cost more than the budget.
        (
            (
                f"{_ref(12_000)}\tOR\t{_ref(12_000, 'b')} OR "
                f"{_ref(12_000, 'c')}\nOR\n{_ref(12_000, 'd')} OR "
                f"{_ref(12_000, 'e')}\rOR\r{_ref(12_000, 'f')}"
            ),
            True,
        ),
        # The parser does not break at other white space, so neither may the
        # guard: one token of a million characters to the parser.
        (("x" * 200 + "\u00a0") * 5000, False),
        ("x" * 1_000_000, False),
    ],
    ids=[
        "long-ref",
        "at-budget",
        "over-budget",
        "brackets",
        "sum-within",
        "sum-over",
        "breaks",
        "nbsp",
        "huge",
    ],
)
def test_the_parser_refuses_an_overlong_token(expression: str, parsed: bool) -> None:
    start = time.monotonic()
    assert (parse_expression(expression) is not None) is parsed
    assert time.monotonic() - start < 0.5
