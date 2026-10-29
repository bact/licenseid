# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``resolve()`` does with a quoted value (task T6b).

Characterisation: since T6 the drop guard refuses every quote mark (Q12:
"MIT" with quotes), whatever shape the quotes have. These cases pin that, so
the change that reads quoted values shows exactly what it moved.
"""

# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve

#: ``(value, reason)``: refused with a ``drop`` step of the quote marks.
DROPPED_QUOTES = [
    ('"MIT"', "U+0022"),
    ("'MIT'", "U+0027"),
    ("`MIT`", "U+0060"),
    ("“MIT”", "U+201C U+201D"),
    ("‘MIT’", "U+2018 U+2019"),
    ("«MIT»", "U+00AB U+00BB"),
    ("„MIT“", "U+201E U+201C"),
    ('"MIT', "U+0022"),
    ('MIT"', "U+0022"),
    ("'MIT", "U+0027"),
    ("MIT'", "U+0027"),
    ("\"MIT'", "U+0022 U+0027"),
    ('""MIT""', "U+0022"),
    ("'\"MIT\"'", "U+0027 U+0022"),
    ('" MIT "', "U+0022"),
    ('"MIT?"', "U+0022 U+003F"),
    ('"GPLv2 or later"', "U+0022"),
    ('"Apache 2.0"', "U+0022"),
    ('"mit"', "U+0022"),
    ('"GPL-3.0"', "U+0022"),
    ('("MIT")', "U+0022"),
    ('  "MIT"  ', "U+0022"),
    ('GPL "2.0"', "U+0022"),
    ('Apache "2.0"', "U+0022"),
]

#: Refused with no reason: the loose reading never saw them (a quote inside a
#: listed ID or name, a compound, an empty value).
NO_REASON = [
    '""',
    '"',
    '"""',
    '"GPL-2.0+"',
    '"GPL-2.0 WITH Classpath-exception-2.0"',
    '"(MIT)"',
    '"MIT License"',
    '"AMD\'s plpa_map.c License"',
    "'BSD'",
    'MIT "or" Apache-2.0',
    '"BSD 3-Clause "New" or "Revised" License"',
]


@pytest.mark.parametrize(
    ("value", "points"), DROPPED_QUOTES, ids=[ascii(v)[:30] for v, _ in DROPPED_QUOTES]
)
def test_a_quote_is_refused_by_the_drop_guard(
    corpus_db: LicenseDatabase, value: str, points: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"character dropped: {points}"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]


@pytest.mark.parametrize("value", NO_REASON, ids=[ascii(v)[:30] for v in NO_REASON])
def test_a_quoted_value_the_guard_never_sees_has_no_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        None,
    )


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ('BSD 3-Clause "New" or "Revised" License', "BSD-3-Clause"),
        ("AMD's plpa_map.c License", "AMDPLPA"),
        (
            "Do What The F*ck You Want To But It's Not My Fault Public License",
            "WTFNMFPL",
        ),
    ],
    ids=["bsd-3", "amd", "wtfnmfpl"],
)
def test_a_listed_name_with_quotes_inside_is_read(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        expression,
        "listed_name",
        None,
    )
