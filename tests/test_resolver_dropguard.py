# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``resolve()`` does with a character the loose reading drops (task T6).

A loose ID ("Apache 2.0", "Apache_2.0") is read by dropping the characters
that are neither letters nor digits. Some of those carry the author's doubt
("Apache 2.0?") or a decoding error (U+FFFD): reading past them asserts what
the author did not write. These cases pin the answers of 0.6.0 for every
class of dropped character, so the change that refuses them shows exactly
what it moved.
"""

# pylint: disable=missing-function-docstring

import time
from collections.abc import Sequence

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship

from licenseid import LicenseDatabase, resolve

#: Characters the loose reading may drop silently: white space, "-", "_",
#: ".", a Unicode dash (Pd) and one trailing ",".
KEPT = [
    ("Apache 2.0", "Apache-2.0", "separator"),
    ("Apache_2.0", "Apache-2.0", "separator"),
    ("Apache  2.0", "Apache-2.0", "separator"),
    ("Apache–2.0", "Apache-2.0", "separator"),  # en dash
    ("Apache—2.0", "Apache-2.0", "separator"),  # em dash
    ("Apache‐2.0", "Apache-2.0", "separator"),  # hyphen U+2010
    ("Apache 2.0.", "Apache-2.0", "separator"),
    ("MIT,", "MIT", "separator"),
    ("Apache 2.0,", "Apache-2.0", "separator"),
]

#: Not read through the loose path: a listed name keeps its "!", a grant
#: reads its own tail.
UNTOUCHED = [
    ("Yahoo! Public License v1.0", "YPL-1.0", "listed_name"),
    ("MIT License", "MIT", "listed_name"),
    ("GPLv2 or later.", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later;", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later:", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later,", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later)", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or later]", "GPL-2.0-or-later", "version_spelling"),
    ("GPLv2 or any later version;", "GPL-2.0-or-later", "version_spelling"),
    ("GPL-3.0 (or later)", "GPL-3.0-or-later", "stated_qualifier"),
]

#: Characters that are dropped today and carry no separator. One per class:
#: punctuation, symbols, a second comma, the replacement character. Quotes
#: that delimit the whole value are read before the guard (T6b,
#: ``test_resolver_quotes.py``); the ones inside a value are refused there.
DROPPED = [
    ("Apache 2.0?", "Apache-2.0", "?"),
    ("Apache 2.0!", "Apache-2.0", "!"),
    ("Apache2?", "Apache-2.0", "?"),
    ("MIT?", "MIT", "?"),
    ("mit?", "MIT", "?"),
    ("MIT*", "MIT", "*"),
    ("#MIT", "MIT", "#"),
    ("MIT,,", "MIT", ","),
    ("MIT;;", "MIT", ";"),
    ("MIT..", "MIT", "."),
    ("MIT.;", "MIT", ";."),
    ("MIT/", "MIT", "/"),
    ("MIT\\", "MIT", "\\"),
    ("MIT|", "MIT", "|"),
    ("MIT~", "MIT", "~"),
    ("MIT@", "MIT", "@"),
    ("MIT$", "MIT", "$"),
    ("MIT%", "MIT", "%"),
    ("MIT^", "MIT", "^"),
    ("MIT&", "MIT", "&"),
    ("MIT=", "MIT", "="),
    ("MIT<", "MIT", "<"),
    ("MIT>", "MIT", ">"),
    ("MIT™", "MIT", "™"),  # trade mark sign
    ("MIT★", "MIT", "★"),  # black star
    ("MIT·", "MIT", "·"),  # middle dot
    ("MIT�", "MIT", "�"),
    ("BSD 3-Clause!", "BSD-3-Clause", "!"),
]


def _ids(rows: Sequence[tuple[str, ...]]) -> list[str]:
    return [ascii(row[0])[:36] for row in rows]


@pytest.mark.parametrize(("value", "expression", "category"), KEPT, ids=_ids(KEPT))
def test_an_allowed_dropped_character_is_read(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    """White space, "-", "_", ".", a dash and a trailing comma are dropped."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)


@pytest.mark.parametrize(
    ("value", "expression", "category"), UNTOUCHED, ids=_ids(UNTOUCHED)
)
def test_a_name_and_a_grant_are_not_read_by_dropping(
    corpus_db: LicenseDatabase, value: str, expression: str, category: str
) -> None:
    """A listed name and the tail of a grant never reach the loose reading's
    dropped characters."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expression, category)


# Fixed by T6 (dropguard): 0.6.0 read the licence past the dropped character
# (category `separator` or `version_spelling`); 0.7.0 refuses the value.
@pytest.mark.parametrize(("value", "stopped", "lost"), DROPPED, ids=_ids(DROPPED))
def test_a_dropped_character_refuses_the_value(
    corpus_db: LicenseDatabase, value: str, stopped: str, lost: str
) -> None:
    """Unresolved with the reading it stopped, a step that did not apply and
    a reason that names the character; the input is kept."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        None,
        "unresolved",
        "none",
    )
    (only,) = got["steps"]
    assert (only["kind"], only["applied"], only["from"], only["to"]) == (
        "drop",
        False,
        value,
        stopped,
    )
    points = " ".join(f"U+{ord(c):04X}" for c in lost)
    assert only["detail"] == points
    assert got["reason"] == f"character dropped: {points}"
    assert got["expansions"] == [] and got["candidates"] == []
    assert got["input"] == value


@pytest.mark.parametrize("value", [v for v, *_ in KEPT], ids=_ids(KEPT))
def test_an_allowed_character_has_no_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """An answer has ``reason`` None, and a ``separator`` step that applied."""
    got = resolve(value, corpus_db)
    assert got["reason"] is None
    assert all(s["applied"] for s in got["steps"])


def test_the_reason_names_each_character_once(corpus_db: LicenseDatabase) -> None:
    got = resolve("Apache??2.0!?", corpus_db)
    assert got["reason"] == "character dropped: U+003F U+0021"


def test_a_comma_in_the_middle_is_refused(corpus_db: LicenseDatabase) -> None:
    got = resolve("Apache, 2.0", corpus_db)
    assert got["expression"] is None
    assert got["reason"] == "character dropped: U+002C"


# P13: a mark before a qualifier or an exception refuses the whole value; the
# `drop` step is the one of the leaf the mark is in.
@pytest.mark.parametrize(
    ("value", "seen", "stopped"),
    [
        ("Apache 2.0?+", "Apache 2.0?", "Apache-2.0"),
        ("Apache2? or later", "Apache2?", "Apache-2.0"),
        ("GPLv2? or later", "GPLv2?", "GPL-2.0"),
        ("MIT? WITH Classpath-exception-2.0", "MIT?", "MIT"),
        ("GPL-2.0? WITH Classpath-exception-2.0", "GPL-2.0?", "GPL-2.0"),
    ],
    ids=["plus", "or-later", "grant-v2", "with", "with-id"],
)
def test_a_mark_before_a_qualifier_or_exception_refuses_the_value(
    corpus_db: LicenseDatabase, value: str, seen: str, stopped: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["trust"]) == (
        None,
        "unresolved",
        "none",
    )
    assert got["reason"] == "character dropped: U+003F"
    assert got["steps"] == [
        {
            "kind": "drop",
            "applied": False,
            "from": seen,
            "to": stopped,
            "list": "",
            "detail": "U+003F",
            "by": "",
        }
    ]
    assert got["expansions"] == [] and got["candidates"] == []


def test_the_step_names_the_listed_id_the_reading_named(
    corpus_db: LicenseDatabase,
) -> None:
    """A renamed ID is not followed: the step shows the listed ID read."""
    got = resolve("StandardML NJ?", corpus_db)
    assert got["steps"][0]["to"] == "StandardML-NJ"


# The characters are those of normalize_text (RE_DASHES, RE_QUOTES), not a
# Unicode category: the minus sign is a dash (SPDX guideline 4), and a wave
# dash or katakana hyphen (Pd) is neither. (The modifier letters that
# normalize_text reads as quotes are quote marks: test_resolver_quotes.py.)
@pytest.mark.parametrize("char", ["\u2212", "\ufe63", "\uff0d", "\u2013", "\u2010"])
def test_a_dash_of_normalize_is_dropped(corpus_db: LicenseDatabase, char: str) -> None:
    got = resolve(f"Apache{char}2.0", corpus_db)
    assert (got["expression"], got["reason"]) == ("Apache-2.0", None)


@pytest.mark.parametrize(
    ("value", "point"),
    [("Apache\u301c2.0", "U+301C"), ("Apache\u30a02.0", "U+30A0")],
    ids=["wave", "kana"],
)
def test_a_non_normalize_dash_is_refused(
    corpus_db: LicenseDatabase, value: str, point: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == f"character dropped: {point}"


@pytest.mark.parametrize(
    ("value", "lost"),
    [("GPLv2 or later!", "!"), ("GPLv2 or later?", "?"), ("GPLv2? or later", "?")],
)
def test_a_mark_that_is_no_grant_tail_is_refused(
    corpus_db: LicenseDatabase, value: str, lost: str
) -> None:
    """The tail of a grant may end in ``. , ; : ) ]``; a ``!`` or ``?`` is
    no tail, and the loose reading would drop it."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == f"character dropped: U+{ord(lost):04X}"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]


@pytest.mark.parametrize("value", [v for v, *_ in UNTOUCHED], ids=_ids(UNTOUCHED))
def test_a_name_and_a_grant_have_no_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["reason"] is None


def test_the_trim_step_is_not_kept_with_a_refusal(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve("  Apache 2.0?  ", corpus_db)
    assert [s["kind"] for s in got["steps"]] == ["drop"]
    assert got["steps"][0]["from"] == "Apache 2.0?"
    assert got["input"] == "  Apache 2.0?  "


def test_brackets_around_a_refused_value_leave_only_the_drop_step(
    corpus_db: LicenseDatabase,
) -> None:
    got = resolve("(Apache 2.0?)", corpus_db)
    assert got["expression"] is None
    assert [s["kind"] for s in got["steps"]] == ["drop"]


@pytest.mark.parametrize("size", [1_000, 100_000])
def test_a_long_run_of_spaces_or_marks_is_fast(
    corpus_db: LicenseDatabase, size: int
) -> None:
    """The guard is linear; a value over MAX_KEY_INPUT never reaches it."""
    start = time.monotonic()
    for value in ("x" + " " * size, "MIT" + "?" * size, "Apache" + " 2" * size):
        assert resolve(value, corpus_db)["expression"] is None
    assert time.monotonic() - start < 5


def test_the_same_answer_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    """The packaged list gives the whole answer, reason and step included,
    for every value of the tables above."""
    ship(monkeypatch, fixture_bundle())
    values = [v for v, *_ in KEPT + UNTOUCHED + DROPPED]
    values += ["Apache 2.0?+", "Apache, 2.0", "  MIT?  ", "(MIT!)", "MIT\ud800"]
    for value in values:
        assert masked(resolve(value, bundle_db)) == masked(
            resolve(value, source="packaged")
        ), value
