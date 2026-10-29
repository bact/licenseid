# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` refuses a value whose reading needs a word or a mark to be
dropped (task T8, R7 item 3; decisions P71 to P73)."""
# pylint: disable=missing-function-docstring

import json
import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship
from resolver_corpus import EXCEPTION_LIST, LICENSE_LIST

from licenseid import LicenseDatabase, resolve
from licenseid.dropguard import dropped, dropped_words

#: Value, the reading stopped, the reason.
REFUSED = [
    ("REM MIT", "MIT", "word dropped: rem"),
    ("1. MIT", "MIT", "word dropped: 1"),
    ("12. MIT", "MIT", "word dropped: 12"),
    ("x. MIT", "MIT", "word dropped: x"),
    ("iv. MIT", "MIT", "word dropped: iv"),
    ("- MIT", "MIT", "character dropped: U+002D"),
    ("-- MIT", "MIT", "character dropped: U+002D"),
    ("MIT -", "MIT", "character dropped: U+002D"),
    ("MIT –", "MIT", "character dropped: U+2013"),
    ("Apache 2.0 -", "Apache-2.0", "character dropped: U+002D"),
    ("MIT ...", "MIT", "character dropped: U+002E"),
    ("MIT...", "MIT", "character dropped: U+002E"),
    ("; MIT", "MIT", "character dropped: U+003B"),
    ("... MIT", "MIT", "character dropped: U+002E"),
    ("-MIT", "MIT", "character dropped: U+002D"),
    (".GPL-3.0-only", "GPL-3.0-only", "character dropped: U+002E"),
    ("...GPL-3.0-only", "GPL-3.0-only", "character dropped: U+002E"),
    ("MIT;;", "MIT", "character dropped: U+003B"),
    ("MIT.;", "MIT", "character dropped: U+003B U+002E"),
    ("MIT\u2026", "MIT", "character dropped: U+2026"),
    (". MIT", "MIT", "character dropped: U+002E"),
    ("1. MIT License", "MIT", "word dropped: 1"),
    ("- BSD 3-Clause License", "BSD-3-Clause", "character dropped: U+002D"),
    ("The 1. MIT License", "MIT", "word dropped: 1"),
]
#: Read as before: spelling, not content.
READ = [
    ("MIT.", "MIT"),
    ("MIT .", "MIT"),
    ("MIT ;", "MIT"),
    ("MIT,", "MIT"),
    ("MIT License.", "MIT"),
    ("Apache 2.0.", "Apache-2.0"),
    ("GPLv3", "GPL-3.0"),
    ("GPL v3", "GPL-3.0"),
    ("GPL-3.0", "GPL-3.0"),
    ("mit", "MIT"),
    ("Apache_2.0", "Apache-2.0"),
    ("Apache  2.0", "Apache-2.0"),
    ("Apache - 2.0", "Apache-2.0"),
    ("BSD - 3 - Clause", "BSD-3-Clause"),
    ("Apache2", "Apache-2.0"),
    ("MIT– ", "MIT"),
]
#: A negation or a qualifier is no marker: not read, and not a refusal.
STAYS = [
    "not MIT",
    "no MIT",
    "except MIT",
    "MIT modified",
    "MIT-like",
    "MIT style",
    "MIT draft",
    "MIT v2",
    "copyright MIT",
    "x MIT",
    "MIT.txt",
    "rem MIT",  # the comment marker is REM in capitals only
]


@pytest.mark.parametrize(("value", "stopped", "reason"), REFUSED, ids=lambda v: v[:20])
def test_a_dropped_word_or_mark_refuses_the_value(
    corpus_db: LicenseDatabase, value: str, stopped: str, reason: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["reason"] == reason
    assert got["expression"] is None
    assert got["category"] == "unresolved"
    (drop,) = got["steps"]
    assert (drop["kind"], drop["applied"], drop["to"]) == ("drop", False, stopped)
    assert drop["detail"] == reason.split(": ", 1)[1]


@pytest.mark.parametrize(("value", "expression"), READ, ids=lambda v: v[:20])
def test_spelling_is_not_a_dropped_word(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == expression
    assert got["reason"] is None


@pytest.mark.parametrize("value", STAYS, ids=lambda v: v[:20])
def test_a_negation_or_qualifier_is_not_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"], got["steps"]) == (None, None, [])


def test_several_words_are_listed(corpus_db: LicenseDatabase) -> None:
    got = resolve("REM 1. MIT", corpus_db)
    assert got["reason"] == "word dropped: rem 1"
    assert dropped_words("a. b. 1. MIT") == "a"  # the rules read a line start


@pytest.mark.parametrize(
    ("value", "stopped", "reason"),
    [
        ("1. MIT OR ISC", "MIT", "word dropped: 1"),
        ("MIT AND REM ISC", "ISC", "word dropped: rem"),
        ("MIT OR 1. ISC", "ISC", "word dropped: 1"),
        ("MIT OR ISC -", "ISC", "character dropped: U+002D"),
        ("MIT OR - ISC", "ISC", "character dropped: U+002D"),
    ],
    ids=lambda v: v[:20],
)
def test_an_operand_is_judged_as_it_would_be_alone(
    corpus_db: LicenseDatabase, value: str, stopped: str, reason: str
) -> None:
    """The operand's own refusal is the reason, with its ``drop`` step."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, reason)
    assert [(s["kind"], s["to"]) for s in got["steps"]] == [("drop", stopped)]


@pytest.mark.usefixtures("shipped")
@pytest.mark.parametrize(
    "value",
    [r[0] for r in REFUSED] + [r[0] for r in READ] + STAYS,
    ids=lambda v: v[:20],
)
def test_the_packaged_list_gives_the_same_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    from_db, from_bundle = resolve(value, corpus_db), resolve(value, source="packaged")
    for key in ("expression", "category", "steps", "reason"):
        assert from_bundle[key] == from_db[key], key


@pytest.fixture(name="shipped")
def _shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, fixture_bundle())


def test_no_id_or_name_of_the_list_drops_a_word() -> None:
    """The guard reads the List itself: no ID or name, in any of the spellings
    a loose reading accepts, has a word a line rule takes off."""
    rows: list[list[object]] = []
    for path, key in ((LICENSE_LIST, "licenses"), (EXCEPTION_LIST, "exceptions")):
        rows += json.loads(path.read_text(encoding="utf-8"))[key]
    for row in rows:
        for text in (str(row[0]), str(row[1])):
            for value in (
                text,
                text.lower(),
                text.replace("-", " "),
                text.replace("-", "_"),
                text.replace(".", ""),
            ):
                assert dropped_words(value) == "", value


def test_the_words_guard_is_fast() -> None:
    start = time.monotonic()
    for _ in range(300):
        dropped_words("Apache License Version 2.0 " * 4)
        dropped("- " * 50 + "MIT" + " ." * 50)
    assert time.monotonic() - start < 2
