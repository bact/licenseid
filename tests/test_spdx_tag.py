# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What an ``SPDX-License-Identifier`` tag in a source file makes of a match.

A tag is evidence only when it holds a license this database has, or a valid
SPDX expression (or LicenseRef-*) with at least one recognised ID; it is
flagged as not SPDX if any part is unknown. The `license` field of JSON, TOML
and INI files goes through the same function (pinned in
`test_markers_structured.py`). The same file must get the same answer from
the API (`match`, `is_spdx`, `is_osi`) and from the CLI (`match`, `is-spdx`).
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from matcher_db import PROSE, Lic, seeded_db
from spdx_tag_helpers import Answers, answers, cli_match_id, source_with, tag_db

from licenseid.cli import cli
from licenseid.identifiers import strip_plus_operator
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.types import LicenseMatch


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_spdx_tag")


# Tags that name licenses this database has, or valid expressions of known
# parts (or LicenseRef-*): a certain match on every path.
KNOWN = {
    "MIT": "MIT",
    "mit": "MIT",
    "GPL-2.0+": "GPL-2.0-or-later",
    "GPL-2.0": "GPL-2.0-only",
    "MIT AND Apache-2.0": "Apache-2.0 AND MIT",
    "Apache-2.0+": "Apache-2.0+",
    "GPL-2.0-only WITH Classpath-exception-2.0": (
        "GPL-2.0-only WITH Classpath-exception-2.0"
    ),
    # A LicenseRef-* is a valid SPDX ID, so it counts as known (as it does for
    # the `license` field of JSON, TOML and INI).
    "LicenseRef-Foo": "LicenseRef-Foo",
    "LicenseRef-Foo WITH Classpath-exception-2.0": (
        "LicenseRef-Foo WITH Classpath-exception-2.0"
    ),
}
# A valid expression with one part nobody knows: still a match, but not SPDX.
PARTLY_KNOWN = {"MIT OR NoSuch-1.0": "MIT OR NoSuch-1.0"}
# No recognised ID at all: no evidence of a license.
UNKNOWN = [
    "NoSuchLicense-9.9",
    "Apache-2.O",
    "Apache-2",
    "Copyright",
    "Proprietary",
    "NONE",
    "NOASSERTION",
    "GPL-2.0-only WITH NoSuch-exception",
    "MIT++",  # not the "+" operator: no ID to fabricate from it
    "Apache-2.0 WITH Classpath-exception-2.0+",  # an exception has no "+"
]


@pytest.mark.parametrize("tag", KNOWN)
def test_a_known_tag_is_a_certain_match_everywhere(
    db: str, tmp_path: Path, tag: str
) -> None:
    expected = KNOWN[tag]
    assert answers(db, tag, tmp_path) == Answers(expected, True, expected, True)


@pytest.mark.parametrize("tag", PARTLY_KNOWN)
def test_a_partly_known_tag_is_a_match_that_is_not_spdx(
    db: str, tmp_path: Path, tag: str
) -> None:
    expected = PARTLY_KNOWN[tag]
    assert answers(db, tag, tmp_path) == Answers(expected, False, expected, False)


@pytest.mark.parametrize("tag", UNKNOWN)
def test_an_unknown_tag_is_no_evidence_anywhere(
    db: str, tmp_path: Path, tag: str
) -> None:
    """It used to be reported verbatim as a certain, SPDX-flagged match, and
    the CLI's is-spdx disagreed. Now matching falls through to the text tiers,
    as it does for an unresolved `License:` field, and all four agree."""
    assert answers(db, tag, tmp_path) == Answers(None, False, None, False)


def test_an_unknown_tag_does_not_hide_a_known_one(db: str) -> None:
    text = source_with("NoSuchLicense-9.9") + source_with("Apache-2.0")
    results = AggregatedLicenseMatcher(db).match(text=text)
    assert [r["license_id"] for r in results] == ["Apache-2.0"]


WITH_EXPRESSION = "GPL-2.0-only WITH Classpath-exception-2.0"


def test_a_with_tag_has_the_flags_of_its_license(db: str, tmp_path: Path) -> None:
    """The same expression gives the same OSI and FSF answers as a tag, as
    text and as an ID, through the API and the CLI."""
    matcher = AggregatedLicenseMatcher(db)
    path = tmp_path / "source.c"
    path.write_text(source_with(WITH_EXPRESSION), encoding="utf-8")
    assert matcher.is_osi(text=source_with(WITH_EXPRESSION))
    assert matcher.is_fsf(text=source_with(WITH_EXPRESSION))
    assert matcher.is_osi(license_id=WITH_EXPRESSION)
    assert matcher.is_fsf(license_id=WITH_EXPRESSION)
    for command in ("is-osi", "is-fsf"):
        for args in ([str(path)], [WITH_EXPRESSION], ["--id", WITH_EXPRESSION]):
            result = CliRunner().invoke(cli, ["--db", db, command, *args])
            assert result.exit_code == 0, (command, args)


@pytest.mark.parametrize(
    ("tag", "osi", "fsf"),
    [
        ("Artistic-1.0", True, False),
        ("Artistic-1.0+", True, False),
        ("Artistic-1.0 WITH Classpath-exception-2.0", True, False),
        ("BSD-4-Clause", False, True),
        ("BSD-4-Clause+", False, True),
        ("BSD-4-Clause WITH Classpath-exception-2.0", False, True),
    ],
)
def test_the_flags_come_from_the_license_not_the_other_flag(
    db: str, tmp_path: Path, tag: str, osi: bool, fsf: bool
) -> None:
    """A license approved by only one body shows that in every entry point."""
    matcher = AggregatedLicenseMatcher(db)
    path = tmp_path / "source.c"
    path.write_text(source_with(tag), encoding="utf-8")
    assert matcher.is_osi(text=source_with(tag)) is osi
    assert matcher.is_fsf(text=source_with(tag)) is fsf
    for command, expected in (("is-osi", osi), ("is-fsf", fsf)):
        result = CliRunner().invoke(cli, ["--db", db, command, str(path)])
        assert (result.exit_code == 0) is expected, (command, tag)


PLUS_WITH = "Apache-2.0+ WITH Classpath-exception-2.0"


def test_a_plus_before_with_is_kept_on_every_path(db: str, tmp_path: Path) -> None:
    """`Apache-2.0+ WITH X` is one expression whether it is a tag or an ID."""
    by_tag = AggregatedLicenseMatcher(db).match(text=source_with(PLUS_WITH))
    by_id = AggregatedLicenseMatcher(db).match(license_id=PLUS_WITH)
    assert [r["license_id"] for r in by_tag] == [PLUS_WITH]
    assert [r["license_id"] for r in by_id] == [PLUS_WITH]
    exception_plus = "Apache-2.0 WITH Classpath-exception-2.0+"
    assert not AggregatedLicenseMatcher(db).match(license_id=exception_plus)
    with_plus = "Apache-2.0 with+ Classpath-exception-2.0"  # nor is the keyword's
    assert not AggregatedLicenseMatcher(db).match(license_id=with_plus)
    assert answers(db, PLUS_WITH, tmp_path) == Answers(PLUS_WITH, True, PLUS_WITH, True)


def test_a_plus_id_has_the_flags_of_its_license(db: str) -> None:
    matcher = AggregatedLicenseMatcher(db)
    assert matcher.is_osi(text=source_with("Apache-2.0"))
    assert matcher.is_osi(text=source_with("Apache-2.0+"))
    assert matcher.is_fsf(text=source_with("Apache-2.0+"))


@pytest.mark.parametrize("command", ["match", "is-spdx"])
@pytest.mark.parametrize(
    "args",
    [
        [WITH_EXPRESSION],
        ["--id", WITH_EXPRESSION],
        [PLUS_WITH],
        ["--id", PLUS_WITH],
    ],
)
def test_an_expression_given_as_an_id_is_known_to_every_command(
    db: str, command: str, args: list[str]
) -> None:
    """`match` resolves an expression that is not a database row; the is-*
    commands answer from the same code and must not say false."""
    result = CliRunner().invoke(cli, ["--db", db, command, *args])
    assert result.exit_code == 0


# The same value must get the same answer wherever it reaches the matcher.
SHARED_VALUES = [
    "MIT",
    "MIT OR Apache-2.0",
    "MIT AND Apache-2.0",
    "LicenseRef-Foo",
    "Apache-2.0+",
    WITH_EXPRESSION,
    PLUS_WITH,
    "MIT OR NoSuch-1.0",
    "MIT OR GPL-2.0 or later",  # a grant, not the OR operator
    "Apache-2.0.",  # a full stop is punctuation
    "MIT No Attribution",  # a name, not MIT with prose after it
]


def flags(result: LicenseMatch) -> tuple[object, ...]:
    """What every source of a value must agree on."""
    return (
        result["license_id"],
        result["is_spdx"],
        result["is_osi_approved"],
        result["is_fsf_libre"],
    )


@pytest.mark.parametrize("value", SHARED_VALUES)
def test_every_source_of_a_value_gives_the_same_answer(
    db: str, tmp_path: Path, value: str
) -> None:
    """An ID, a tag and a JSON `license` field share one judge, so they cannot
    drift apart."""
    matcher = AggregatedLicenseMatcher(db)
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps({"license": value, "description": PROSE}), encoding="utf-8"
    )
    sources = (
        matcher.match(license_id=value),
        matcher.match(text=source_with(value)),
        matcher.match(file_path=str(package)),
    )
    by_id, by_tag, by_json = (flags(r[0]) for r in sources)
    assert by_id == by_tag == by_json


def test_a_bare_argument_that_names_no_license_is_matched_as_text(db: str) -> None:
    """A bare argument is the CLI guessing between an ID and text, so it takes
    the ID reading only when every part is recognised."""
    assert cli_match_id(db, "MIT or something") is None
    result = CliRunner().invoke(cli, ["--db", db, "is-spdx", "MIT or something"])
    assert result.exit_code == 1


PARTLY_KNOWN_VALUE = "MIT AND Proprietary"


@pytest.fixture
def named_db() -> Generator[str, None, None]:
    """A database holding a license whose NAME is what the text tiers find for
    PARTLY_KNOWN_VALUE, so the two readings of it differ."""
    yield from seeded_db(
        "test_spdx_tag_named",
        [
            Lic("MIT", "MIT License", True, True, True),
            Lic("Weird-1.0", "MIT AND Proprietary Extras", True, False, False),
        ],
    )


def test_only_an_explicit_id_is_trusted_when_a_part_is_unknown(named_db: str) -> None:
    """`--id` is a declaration, so the expression answers even though one part
    is unknown. The same value as a bare argument is only a guess, so it falls
    through to text matching. `match` and `is-spdx` follow the same reading."""
    with_id = ["--id", PARTLY_KNOWN_VALUE]
    assert cli_match_id(named_db, *with_id) == PARTLY_KNOWN_VALUE
    assert cli_match_id(named_db, PARTLY_KNOWN_VALUE) == "Weird-1.0"
    run = CliRunner()
    assert run.invoke(cli, ["--db", named_db, "is-spdx", *with_id]).exit_code == 1
    assert (
        run.invoke(cli, ["--db", named_db, "is-spdx", PARTLY_KNOWN_VALUE]).exit_code
        == 0
    )


@pytest.mark.parametrize(
    ("expression", "stripped"),
    [
        ("Apache-2.0+", "Apache-2.0"),
        ("Apache-2.0+ OR GPL-2.0-only+", "Apache-2.0 OR GPL-2.0-only"),
        ("(Apache-2.0+)", "(Apache-2.0)"),
        ("MIT", "MIT"),
        ("LicenseRef-foo+bar", "LicenseRef-foo+bar"),  # a + inside a name stays
        ("MIT++", "MIT++"),  # a "+" after a "+" is not an operator
        ("MIT+ +", "MIT +"),  # nor one after a space
        ("(+ MIT)", "(+ MIT)"),  # nor one after a "("
        ("Apache-2.0 WITH LLVM-exception+", "Apache-2.0 WITH LLVM-exception+"),
        ("Apache-2.0+ WITH LLVM-exception", "Apache-2.0 WITH LLVM-exception"),
        ("apache-2.0+ with llvm-exception+", "apache-2.0 with llvm-exception+"),
        ("A WITH  B+", "A WITH  B+"),  # any run of spaces after WITH
        ("Apache-2.0 with+ LLVM-exception", "Apache-2.0 with+ LLVM-exception"),
        ("Apache-2.0 WITH+ LLVM-exception", "Apache-2.0 WITH+ LLVM-exception"),
        ("MIT or+ Apache-2.0", "MIT or+ Apache-2.0"),
        ("MIT AND+ Apache-2.0", "MIT AND+ Apache-2.0"),
        ("swith+ or+x", "swith or+x"),  # only a whole word is an operator
    ],
)
def test_strip_plus_operator(expression: str, stripped: str) -> None:
    assert strip_plus_operator(expression) == stripped


@pytest.mark.parametrize(
    "payload",
    [
        "A" * 100000,
        "A+ " * 30000,
        "A+" * 50000,
        "(" * 100000,
        "WITH" + " " * 100000 + ")",
    ],
    ids=["one-token", "plus-runs", "plus-no-space", "open-parens", "with-spaces"],
)
def test_strip_plus_operator_does_not_backtrack(payload: str) -> None:
    start = time.monotonic()
    strip_plus_operator(payload)
    assert time.monotonic() - start < 1.0
