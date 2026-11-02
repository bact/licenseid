# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, third round: a declared value read the same way by the
tag, a manifest field, a short text, the ``is-*`` answers and ``match()``,
on the whole 3.29.0 List.

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.errors import invalid_id_error
from licenseid.types import Detection

Answer = tuple[str, bool] | None


def _top(found: list[Detection]) -> Answer:
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _tag(corpus_db: LicenseDatabase, value: str) -> Answer:
    detector = LicenseDetector(corpus_db.location)
    return _top(detector.detect(f"SPDX-License-Identifier: {value}"))


def _text(corpus_db: LicenseDatabase, value: str) -> Answer:
    return _top(LicenseDetector(corpus_db.location).detect(text=value))


def _field(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> Answer:
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"name": "x", "license": value}), "utf-8")
    detector = LicenseDetector(corpus_db.location)
    return _top(detector.detect(file_path=str(manifest)))


def _pyproject(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> Answer:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(f"[project]\nlicense = {json.dumps(value)}\n", "utf-8")
    detector = LicenseDetector(corpus_db.location)
    return _top(detector.detect(file_path=str(manifest)))


# --- 1: a "+" apart from its ID, on every path --------------------------------

# Each was read without its "+" (MIT, exact; GPL-2.0 +: GPL-2.0-only with
# "variant not stated") by the text, a package.json and a pyproject.toml
# field, and is-spdx said yes. match() and the tag refuse them (malformed):
# so does every path now (identifiers.is_stray_plus, plusoperator.plus_apart).
SPACED_PLUS = [
    "MIT +",
    "MIT ++",
    "MIT+ +",
    "Apache-2.0 +",
    "(MIT) +",
    "(MIT)+",
    "GPL-2.0-only +",
    "MIT +,",
    "GPL-2.0 +",
]


@pytest.mark.parametrize("value", SPACED_PLUS)
def test_a_spaced_plus_on_every_path(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    got = (
        _text(corpus_db, value),
        _field(corpus_db, tmp_path, value),
        _pyproject(corpus_db, tmp_path, value),
        _tag(corpus_db, value),
    )
    assert got == (None, None, None, None)
    assert match(value, corpus_db)["category"] == "malformed"


@pytest.mark.parametrize("value", ["MIT+", "(MIT+)", "MIT+,", "GPL-2.0+"])
def test_a_plus_that_touches_its_id_still_answers(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    expression = match(value, corpus_db)["expression"]
    assert expression is not None
    got = (_text(corpus_db, value), _field(corpus_db, tmp_path, value))
    assert got == ((expression, True), (expression, True))


@pytest.mark.parametrize(
    ("value", "code"),
    [("MIT +", 1), ("(MIT)+", 1), ("MIT ++", 1), ("MIT+", 0)],
)
def test_a_spaced_plus_is_no_spdx_licence(
    corpus_db: LicenseDatabase, value: str, code: int
) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "is-spdx", "--text", value]
    )
    assert (result.exit_code, result.stderr) == (code, "")


# --- 2: what stands between an ID and its "or later" --------------------------

# match() refuses each ("character dropped: U+003B", "not found"). The tag
# and the field gave MIT+ for the marks a grant crossed (";", ":", ")"...),
# and MIT for the ones that stopped it ("-", "/", "*", "#"): the grant
# dropped. Every reader now refuses them (classify.grant_follows).
REFUSED_GAPS = [
    "MIT; or later",
    "MIT: or later",
    "MIT) or later",
    "MIT] or later",
    "MIT,, or later",
    "MIT ;, or later",
    "MIT,or later",
    "MIT - or later",
    "MIT / or later",
    "MIT * or later",
    "MIT # or later",
    "GPL-2.0; or later",
    "GPL-2.0: or later",
    "GPL-2.0) or later",
    "GPL-2.0,, or later",
    "GPL-2.0 - or later",
    "GPL-2.0 / or later",
    # A grant after an ID that takes none is refused anyway; after a mark
    # too, not read as the ID alone (identifiers._granted_twice).
    "GPL-2.0-only; or later",
    "LicenseRef-a: or later",
]


@pytest.mark.parametrize("value", REFUSED_GAPS)
def test_a_mark_before_a_grant_is_refused(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    assert match(value, corpus_db)["expression"] is None
    assert (_tag(corpus_db, value), _field(corpus_db, tmp_path, value)) == (
        None,
        None,
    )


# match() reads these, and so does everything else. "MIT. or later" was MIT
# in the tag and nothing in the field; "GPL-2.0. or later" was GPL-2.0-only
# in the tag ("variant not stated").
READ_GAPS = [
    "MIT or later",
    "MIT. or later",
    "MIT, or later",
    "MIT , or later",
    "MIT (or later)",
    "MIT [or later]",
    "MIT, (or later)",
    "GPL-2.0. or later",
    "GPL-2.0, or later",
    "GPL-2.0 (or later)",
]


@pytest.mark.parametrize("value", READ_GAPS)
def test_a_grant_match_reads_is_read_everywhere(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    expression = match(value, corpus_db)["expression"]
    assert expression is not None
    got = (_tag(corpus_db, value), _field(corpus_db, tmp_path, value))
    assert got == ((expression, True), (expression, True))


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        # The brackets of the expression are no mark (tag only: match()
        # refuses both, "not found").
        ("(MIT) or later", ("MIT+", True)),
        ("(GPL-2.0) or later", ("GPL-2.0-or-later", True)),
        ("((MIT)) or later", ("MIT+", True)),
        ("(MIT)) or later", None),  # one bracket more than it opened
    ],
)
def test_the_brackets_of_the_tag_before_a_grant(
    corpus_db: LicenseDatabase, value: str, answer: Answer
) -> None:
    assert _tag(corpus_db, value) == answer


# --- 3: a grant after a deprecated ID ------------------------------------------

DEPRECATED = {
    # Each was StandardML-NJ+: the rename is followed, then the "+", as in
    # match() (deprecated_equal_successor).
    "StandardML-NJ, or any later version": ("SMLNJ+", True),
    "StandardML-NJ or later": ("SMLNJ+", True),
    "StandardML-NJ+": ("SMLNJ+", True),
    "standardml-nj+": ("SMLNJ+", True),
    "MIT OR StandardML-NJ or later": ("MIT OR SMLNJ+", True),
    # It was exact; match() calls it ambiguous (deprecated_ambiguous).
    "GPL-2.0-with-classpath-exception or later": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0",
        False,
    ),
    "GPL-2.0-with-classpath-exception+": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0",
        False,
    ),
    "MIT OR GPL-2.0-with-GCC-exception+": (
        "MIT OR GPL-2.0-or-later WITH GCC-exception-2.0",
        False,
    ),
}


@pytest.mark.parametrize("value", sorted(DEPRECATED))
def test_a_grant_after_a_deprecated_id(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    answer = DEPRECATED[value]
    assert (_tag(corpus_db, value), _field(corpus_db, tmp_path, value)) == (
        answer,
        answer,
    )


def test_a_plus_on_a_deprecated_with_id_as_text(corpus_db: LicenseDatabase) -> None:
    """Not exact, and nothing said: it is no -only guess."""
    assert _text(corpus_db, "GPL-2.0-with-classpath-exception+") == (
        "GPL-2.0-or-later WITH Classpath-exception-2.0",
        False,
    )


# --- 4: an operand dropped beside a granted deprecated ID ----------------------

# Each was the granted ID alone, exact, as a field and as a text; match()
# refuses them (not found).
DROPPED = [
    "GPL-3.0, LGPL-2.1 or later",
    "GPL-2.0 / LGPL-2.1 or later",
    "GPL-2.0, LGPL-2.0 or later",
    "LGPL-2.1 or later, GPL-3.0",
    "MIT, GPL-2.0 or later",
]


@pytest.mark.parametrize("value", DROPPED)
def test_no_operand_dropped_beside_a_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    assert match(value, corpus_db)["expression"] is None
    got = (_field(corpus_db, tmp_path, value), _text(corpus_db, value))
    assert got == (None, None)


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 or later",
        "GPL-2.0 or later (GPL-2.0-or-later)",  # its own ID again
        "Licensed under GPL-2.0 or any later version",
    ],
)
def test_a_granted_deprecated_id_alone_still_answers(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _text(corpus_db, value) == ("GPL-2.0-or-later", True)


# --- 5: an "or later" after an ID that has no -or-later form, in match() -------


def test_a_grant_after_an_ambiguous_deprecated_id(corpus_db: LicenseDatabase) -> None:
    """The grant is given after the deprecation: looseid._granted declines an
    ID with no -or-later form, "+" included."""
    got = match("eCos-2.0 or later", corpus_db)
    kinds = [s["kind"] for s in got["steps"] + got["expansions"]]
    assert (got["expression"], got["category"], kinds) == (
        "eCos-2.0+",
        "deprecated_ambiguous",
        ["deprecated_ambiguous", "stated_qualifier"],
    )


# --- 6: "or" is a word -----------------------------------------------------------

ORA = {
    # They were grants on every path, match() included (MIT+,
    # GPL-2.0-or-later): "or" ran into the next word. Now match() refuses
    # them, the field too, and the tag reads its leading ID and no grant.
    "MIT ora later": ("MIT", True),
    "MIT orany later": ("MIT", True),
    "GPL-2.0 ora later": ("GPL-2.0-only", False),
    "GPL-2.0 orany later version": ("GPL-2.0-only", False),
}


@pytest.mark.parametrize("value", sorted(ORA))
def test_or_is_a_word(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, given: GivenWarnings
) -> None:
    got = (
        match(value, corpus_db)["expression"],
        _tag(corpus_db, value),
        _field(corpus_db, tmp_path, value),
    )
    assert got == (None, ORA[value], None)
    assert given.conditions() <= {"variant not stated"}


# --- 7: a refused --id with no visible character --------------------------------


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        # It was the value itself, which shows nothing.
        ("\u200b", "U+200B"),
        ("\ufeff", "U+FEFF"),
        ("\u200b\ufeff\u200b", "U+200B U+FEFF"),
        ("\u00a0\u200b", "U+00A0 U+200B"),
        ("\u200b \u200b", "U+200B U+0020"),  # a space shows nothing either
        ("a\u200b", "a\u200b"),  # a visible character: the value as written
    ],
    ids=["zwsp", "bom", "several", "nbsp", "space", "visible"],
)
def test_an_invisible_id_is_named(value: str, detail: str) -> None:
    assert str(invalid_id_error("--id", value)) == (
        f"option: invalid: --id: {detail}; pass one license ID"
    )


def test_an_invisible_id_on_the_command_line(corpus_db: LicenseDatabase) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "detect", "--id", "\ufeff"]
    )
    assert (result.exit_code, result.stderr) == (
        2,
        "ERROR: option: invalid: --id: U+FEFF; pass one license ID\n",
    )
