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

SPACED_PLUS = {
    # value: what the text, a package.json and a pyproject.toml field gave
    "MIT +": ("MIT", True),  # BUG: the "+" dropped in silence
    "MIT ++": ("MIT", True),  # BUG
    "Apache-2.0 +": ("Apache-2.0", True),  # BUG
    "(MIT) +": ("MIT", True),  # BUG
    "(MIT)+": ("MIT", True),  # BUG
    "GPL-2.0-only +": ("GPL-2.0-only", True),  # BUG
    "MIT +,": ("MIT", True),  # BUG
    "GPL-2.0 +": ("GPL-2.0-only", False),  # BUG: "variant not stated"
}


@pytest.mark.parametrize("value", sorted(SPACED_PLUS))
def test_a_spaced_plus_on_every_path(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, given: GivenWarnings
) -> None:
    answer = SPACED_PLUS[value]
    got = (
        _text(corpus_db, value),
        _field(corpus_db, tmp_path, value),
        _pyproject(corpus_db, tmp_path, value),
    )
    assert got == (answer, answer, answer)
    assert _tag(corpus_db, value) is None
    assert match(value, corpus_db)["category"] == "malformed"
    assert given.conditions() <= {"variant not stated"}


@pytest.mark.parametrize("value", ["MIT +", "(MIT)+", "MIT ++"])
def test_a_spaced_plus_is_spdx(corpus_db: LicenseDatabase, value: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "is-spdx", "--text", value]
    )
    assert result.exit_code == 0  # BUG: it names no licence


# --- 2: what stands between an ID and its "or later" --------------------------

GAPS = {
    # value: the tag, the package.json field; match() in the comment
    "MIT; or later": (("MIT+", True), ("MIT+", True)),  # BUG: match refuses
    "MIT: or later": (("MIT+", True), ("MIT+", True)),  # BUG
    "MIT) or later": (("MIT+", True), ("MIT+", True)),  # BUG
    "MIT] or later": (("MIT+", True), ("MIT+", True)),  # BUG
    "MIT,, or later": (("MIT+", True), ("MIT+", True)),  # BUG
    "MIT ;, or later": (("MIT+", True), ("MIT+", True)),  # BUG
    "MIT,or later": (("MIT+", True), None),  # BUG: the tag
    "MIT - or later": (("MIT", True), None),  # BUG: the grant dropped
    "MIT / or later": (("MIT", True), None),  # BUG
    "MIT * or later": (("MIT", True), None),  # BUG
    "MIT # or later": (("MIT", True), None),  # BUG
    "MIT. or later": (("MIT", True), None),  # BUG: match gives MIT+
    "GPL-2.0. or later": (  # BUG: the tag; match gives GPL-2.0-or-later
        ("GPL-2.0-only", False),
        ("GPL-2.0-or-later", True),
    ),
    "GPL-2.0; or later": (  # BUG: match refuses
        ("GPL-2.0-or-later", True),
        ("GPL-2.0-or-later", True),
    ),
    "GPL-2.0 - or later": (  # BUG
        ("GPL-2.0-or-later", True),
        ("GPL-2.0-or-later", True),
    ),
    # match() reads these, and so does everything else.
    "MIT or later": (("MIT+", True), ("MIT+", True)),
    "MIT, or later": (("MIT+", True), ("MIT+", True)),
    "MIT , or later": (("MIT+", True), ("MIT+", True)),
    "MIT (or later)": (("MIT+", True), ("MIT+", True)),
    "MIT [or later]": (("MIT+", True), ("MIT+", True)),
    "GPL-2.0, or later": (("GPL-2.0-or-later", True), ("GPL-2.0-or-later", True)),
}


@pytest.mark.parametrize("value", sorted(GAPS))
def test_the_gap_before_a_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, given: GivenWarnings
) -> None:
    tag, field = GAPS[value]
    assert _tag(corpus_db, value) == tag
    assert _field(corpus_db, tmp_path, value) == field
    assert given.conditions() <= {"variant not stated"}


# --- 3: a grant after a deprecated ID ------------------------------------------

DEPRECATED = {
    # value: the tag and the package.json field (match() in the comment)
    "StandardML-NJ, or any later version": ("StandardML-NJ+", True),  # BUG: SMLNJ+
    "StandardML-NJ or later": ("StandardML-NJ+", True),  # BUG
    "StandardML-NJ+": ("StandardML-NJ+", True),  # BUG
    "MIT OR StandardML-NJ or later": ("MIT OR StandardML-NJ+", True),  # BUG
    # BUG: match() calls it ambiguous (deprecated_ambiguous): not exact.
    "GPL-2.0-with-classpath-exception or later": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0",
        True,
    ),
    "GPL-2.0-with-classpath-exception+": (
        "GPL-2.0-or-later WITH Classpath-exception-2.0",
        True,
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


# --- 4: an operand dropped beside a granted deprecated ID ----------------------

DROPPED = {
    "GPL-3.0, LGPL-2.1 or later": ("LGPL-2.1-or-later", True),  # BUG
    "GPL-2.0 / LGPL-2.1 or later": ("LGPL-2.1-or-later", True),  # BUG
    "GPL-2.0, LGPL-2.0 or later": ("LGPL-2.0-or-later", True),  # BUG
    "LGPL-2.1 or later, GPL-3.0": ("LGPL-2.1-or-later", True),  # BUG
    "GPL-2.0 or later": ("GPL-2.0-or-later", True),
}


@pytest.mark.parametrize("value", sorted(DROPPED))
def test_no_operand_dropped_beside_a_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    answer = DROPPED[value]
    got = (_field(corpus_db, tmp_path, value), _text(corpus_db, value))
    assert got == (answer, answer)


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
    # value: match(), the tag, the field
    "MIT ora later": ("MIT+", ("MIT+", True), ("MIT+", True)),  # BUG
    "MIT orany later": ("MIT+", ("MIT+", True), ("MIT+", True)),  # BUG
    "GPL-2.0 ora later": (  # BUG
        "GPL-2.0-or-later",
        ("GPL-2.0-or-later", True),
        ("GPL-2.0-or-later", True),
    ),
    "GPL-2.0 orany later version": (  # BUG
        "GPL-2.0-or-later",
        ("GPL-2.0-or-later", True),
        ("GPL-2.0-or-later", True),
    ),
}


@pytest.mark.parametrize("value", sorted(ORA))
def test_or_is_a_word(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> None:
    answer = ORA[value]
    got = (
        match(value, corpus_db)["expression"],
        _tag(corpus_db, value),
        _field(corpus_db, tmp_path, value),
    )
    assert got == answer


# --- 7: a refused --id with no visible character --------------------------------


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ("\u200b", "\u200b"),  # BUG: invisible
        ("\ufeff", "\ufeff"),  # BUG
        ("\u200b\ufeff\u200b", "\u200b\ufeff\u200b"),  # BUG
    ],
    ids=["zwsp", "bom", "several"],
)
def test_an_invisible_id_is_named(value: str, detail: str) -> None:
    assert str(invalid_id_error("--id", value)) == (
        f"option: invalid: --id: {detail}; pass one license ID"
    )
