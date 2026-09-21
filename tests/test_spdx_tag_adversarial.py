# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tag values built to break the reader: parentheses, colons, prose after the
expression, comment closers, line breaks and a very long value.

The plain cases live in `test_spdx_tag.py`; this file only holds the ones
written to catch a wrong reading or a drift back to one.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import time
from collections.abc import Generator

import pytest
from matcher_db import PROSE
from spdx_tag_helpers import source_with, tag_db

from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_spdx_tag_adversarial")


def certain(db: str, text: str) -> str | None:
    """The ID of a certain (score 1.0) match for *text*, or None."""
    results = AggregatedLicenseMatcher(db).match(text=text)
    if results and results[0]["score"] == 1.0:
        return results[0]["license_id"]
    return None


# A parenthesised value, a nested one and an ID with a colon are all read
# whole; a value that cannot be one expression is no evidence at all.
@pytest.mark.parametrize(
    ("tag", "certain_id"),
    [
        ("(MIT)", "MIT"),
        ("((MIT))", "MIT"),
        ("(MIT OR Apache-2.0)", "Apache-2.0 OR MIT"),
        (
            "(MIT OR Apache-2.0) AND BSD-3-Clause",
            "BSD-3-Clause AND (Apache-2.0 OR MIT)",
        ),
        ("MIT OR (Apache-2.0 AND BSD-3-Clause)", "Apache-2.0 AND BSD-3-Clause OR MIT"),
        (
            "MIT OR (Apache-2.0 WITH Classpath-exception-2.0)",
            "MIT OR Apache-2.0 WITH Classpath-exception-2.0",
        ),
        ("DocumentRef-x:LicenseRef-y", "DocumentRef-x:LicenseRef-y"),
        ("MIT OR DocumentRef-x:LicenseRef-y", "MIT OR DocumentRef-x:LicenseRef-y"),
        ("LicenseRef-a:b", None),  # a colon outside a DocumentRef is no ID
        ("MIT OR (Apache-2.0 AND BSD-3-Clause", None),  # unbalanced
        ("(MIT", None),
        ("MIT OR", None),  # dangling
        ("(+ MIT)", None),
    ],
)
def test_parentheses_and_colons(db: str, tag: str, certain_id: str | None) -> None:
    assert certain(db, source_with(tag)) == certain_id


# The value runs to the end of the line, so it can trail off into prose:
# only the expression it starts with is read.
@pytest.mark.parametrize(
    ("tag", "certain_id"),
    [
        ("CAL-1.0 Licensed under the Cryptographic Autonomy License", "CAL-1.0"),
        ("MIT license text follows", "MIT"),
        ("MIT (see LICENSE)", "MIT"),
        ("MIT, Apache-2.0", "MIT"),
        (
            "Apache-2.0 WITH Classpath-exception-2.0 as published",
            "Apache-2.0 WITH Classpath-exception-2.0",
        ),
        ("See the LICENSE file", None),  # no ID to take from prose
        # Prose is never normalized: a deprecated ID mentioned in it used to
        # decide the answer.
        ("MIT; see COPYING for GPL-2.0 or later parts", "MIT"),
        ("Apache-2.0 - GPL-2.0 users only", "Apache-2.0"),
    ],
)
def test_prose_after_the_expression(db: str, tag: str, certain_id: str | None) -> None:
    assert certain(db, source_with(tag)) == certain_id


def test_a_value_on_the_next_line_is_not_the_tag(db: str) -> None:
    """A tag and its value are one line: "[ \\t]", never "\\s"."""
    assert certain(db, f"SPDX-License-Identifier:\nMIT\n{PROSE}") is None


@pytest.mark.parametrize(
    "line",
    [
        "/* SPDX-License-Identifier: MIT */",
        "<!-- SPDX-License-Identifier: MIT -->",
        "# SPDX-License-Identifier: MIT",
        "; SPDX-License-Identifier: MIT",
        "-- SPDX-License-Identifier: MIT",
        "// SPDX-License-Identifier: MIT\r",
        "\t//\tSPDX-License-Identifier:\tMIT",
        "' SPDX-License-Identifier: MIT '",
        '"SPDX-License-Identifier: MIT",',
        "(* SPDX-License-Identifier: MIT *)",
        "{# SPDX-License-Identifier: MIT #}",
    ],
)
def test_a_comment_closer_never_joins_the_expression(db: str, line: str) -> None:
    """Every comment style ends the value where the expression ends."""
    assert certain(db, f"{line}\n{PROSE}") == "MIT"


def test_both_tags_on_one_line_are_read(db: str) -> None:
    line = "# SPDX-License-Identifier: MIT SPDX-License-Identifier: Apache-2.0"
    results = AggregatedLicenseMatcher(db).match(text=line + PROSE)
    assert [r["license_id"] for r in results] == ["MIT", "Apache-2.0"]


def test_a_very_long_value_is_read_quickly(db: str) -> None:
    """A minified line must not make the reader quadratic."""
    tag = "MIT OR " + "a" * 40000
    start = time.monotonic()
    AggregatedLicenseMatcher(db).match(text=source_with(tag))
    assert time.monotonic() - start < 5.0


@pytest.mark.parametrize(
    "tag",
    [
        "MIT License",  # a name, not an ID
        "https://spdx.org/licenses/MIT",
        "https://spdx.org/licenses/MIT/",
    ],
)
def test_a_tag_resolves_what_a_json_field_resolves(db: str, tag: str) -> None:
    """The tag and the structured fields share one resolver, so a name and an
    SPDX URL now resolve in a tag too."""
    assert certain(db, source_with(tag)) == "MIT"


@pytest.mark.parametrize(
    ("tag", "certain_id"),
    [
        ("Apache-2.0 + MIT", "Apache-2.0"),
        ("Apache-2.0 +", "Apache-2.0"),
        ("Apache-2.0+", "Apache-2.0+"),
    ],
)
def test_a_detached_plus_is_not_the_or_later_operator(
    db: str, tag: str, certain_id: str
) -> None:
    """SPDX allows no space before `+`, so `A + B` must not widen the grant
    to `A+`."""
    assert certain(db, source_with(tag)) == certain_id


@pytest.mark.parametrize(
    ("line", "certain_id"),
    [
        ("/* SPDX-License-Identifier: MIT */ and_mask = 1;", "MIT"),
        ("/* SPDX-License-Identifier: MIT */ or(x);", "MIT"),
        (
            "# SPDX-License-Identifier: BSD-3-Clause, and the patent grant",
            "BSD-3-Clause",
        ),
        ("# SPDX-License-Identifier: MIT, with additions", "MIT"),
        ("# SPDX-License-Identifier: Apache-2.0: see NOTICE", "Apache-2.0"),
    ],
)
def test_only_white_space_joins_the_parts_of_an_expression(
    db: str, line: str, certain_id: str
) -> None:
    """Code or punctuation after the tag must not be read as an operand: a
    comment closer is not white space."""
    assert certain(db, f"{line}\n{PROSE}") == certain_id


@pytest.mark.parametrize(
    ("tag", "certain_id"),
    [
        ("GPL-2.0 or any later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("LGPL-2.1 or, at your option, any later version", "LGPL-2.1-or-later"),
        ("GPL-2.0 only", "GPL-2.0-only"),
        ("GPL-2.0", "GPL-2.0-only"),  # no phrase: the conservative fallback
        # The ID the value starts with wins: prose further along must not
        # decide the answer.
        ("MIT; see COPYING for GPL-2.0 or later parts", "MIT"),
        ("Apache-2.0 - GPL-2.0 users only", "Apache-2.0"),
        # An explicit -only ID says what the author chose; the phrase after
        # it resolves nothing.
        ("GPL-2.0-only or (at your option) any later version", "GPL-2.0-only"),
        # A grant qualifies the ID beside it, not another one on the line.
        ("GPL-2.0 AND LGPL-2.1 or later", "GPL-2.0-only AND LGPL-2.1-or-later"),
        ("MIT OR GPL-2.0 or later", "GPL-2.0-or-later OR MIT"),
        # Three arms: the grant beside GPL-2.0 is its own, not LGPL-2.1's.
        (
            "MPL-1.1 OR GPL-2.0 or later OR LGPL-2.1 or later",
            "GPL-2.0-or-later OR MPL-1.1",
        ),
    ],
)
def test_or_later_prose_is_read_before_the_expression(
    db: str, tag: str, certain_id: str
) -> None:
    """ "or later" is prose, not the OR operator: `classify.OR_LATER_PHRASE`
    stays the one reader of it, on the tag path too."""
    assert certain(db, source_with(tag)) == certain_id


@pytest.mark.parametrize(
    "line",
    [
        "/* SPDX-License-Identifier: MIT No Attribution */",
        "<!-- SPDX-License-Identifier: MIT No Attribution -->",
        "# SPDX-License-Identifier: MIT No Attribution.",
    ],
)
def test_a_name_is_read_inside_a_comment_too(db: str, line: str) -> None:
    """The name lookup must not be defeated by the closer around it."""
    assert certain(db, f"{line}\n{PROSE}") == "MIT-0"


def test_a_name_shared_with_a_deprecated_id_answers_with_the_current_one(
    db: str,
) -> None:
    """A deprecated ID keeps the name of the ID that replaced it."""
    assert certain(db, source_with("GNU GPL v2.0 only")) == "GPL-2.0-only"


def test_a_name_beats_the_expression_it_starts_with(db: str) -> None:
    """ "MIT No Attribution" is the name of MIT-0, not MIT with prose after
    it; the whole value is looked up as a name first."""
    assert certain(db, source_with("MIT No Attribution")) == "MIT-0"


@pytest.mark.parametrize(
    "tag",
    [
        "MIT OR (at your option) Apache-2.0",
        "MIT OR (Apache-2.0 AND BSD-3-Clause",
        "MIT AND",
    ],
)
def test_a_value_left_dangling_is_no_evidence(db: str, tag: str) -> None:
    """An operator with nothing valid after it leaves the author's intent
    unknown, so the head of the value must not answer for the whole. Text
    matching decides these instead."""
    assert certain(db, source_with(tag)) is None
