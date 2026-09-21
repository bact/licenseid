# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What an ``SPDX-License-Identifier`` tag in a source file makes of a match.

A tag is evidence only when it holds a license this database has, or a valid
SPDX expression (or LicenseRef-*) with at least one recognised ID; it is
flagged as not SPDX if any part is unknown. The same rule reads the `license`
field of JSON, TOML and INI files. The same file must get the same answer from
the API (`match`, `is_spdx`, `is_osi`) and from the CLI (`match`, `is-spdx`).
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

import pytest
from click.testing import CliRunner
from matcher_db import PROSE, Lic, seeded_db

from licenseid.cli import cli
from licenseid.identifiers import strip_plus_operator
from licenseid.matcher import AggregatedLicenseMatcher


class Answers(NamedTuple):
    """One file's answer from each entry point. The API's match counts only at
    the score (0.85) the CLI and the predicates use: a weaker top result is
    not an answer."""

    api_match: str | None
    api_is_spdx: bool
    cli_match: str | None
    cli_is_spdx: bool


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from seeded_db(
        "test_spdx_tag",
        [
            Lic("MIT", "MIT License", True, True, True),
            Lic("Apache-2.0", "Apache License 2.0", True, True, True),
            Lic("GPL-2.0-only", "GNU GPL v2.0 only", True, True, True),
            Lic("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, True, True),
        ],
        exception_ids=["Classpath-exception-2.0"],
    )


def source_with(tag: str) -> str:
    return f"/*\n * SPDX-License-Identifier: {tag}\n{PROSE} */\n"


def answers(db: str, tag: str, tmp_path: Path) -> Answers:
    matcher = AggregatedLicenseMatcher(db)
    text = source_with(tag)
    results = matcher.match(text=text)
    path = tmp_path / "source.c"
    path.write_text(text, encoding="utf-8")
    runner = CliRunner()
    matched = runner.invoke(cli, ["--db", db, "match", str(path)])
    cli_match = None
    if matched.exit_code == 0:
        first_line = matched.stdout.splitlines()[0]  # an ID can hold spaces
        cli_match = first_line.removeprefix("LICENSE_ID=").rsplit(" SIMILARITY=")[0]
    is_spdx = runner.invoke(cli, ["--db", db, "is-spdx", str(path)])
    return Answers(
        results[0]["license_id"] if results and results[0]["score"] >= 0.85 else None,
        matcher.is_spdx(text=text),
        cli_match,
        is_spdx.exit_code == 0,
    )


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


PLUS_WITH = "Apache-2.0+ WITH Classpath-exception-2.0"


def test_a_plus_before_with_is_kept_on_every_path(db: str, tmp_path: Path) -> None:
    """`Apache-2.0+ WITH X` is one expression whether it is a tag or an ID."""
    by_tag = AggregatedLicenseMatcher(db).match(text=source_with(PLUS_WITH))
    by_id = AggregatedLicenseMatcher(db).match(license_id=PLUS_WITH)
    assert [r["license_id"] for r in by_tag] == [PLUS_WITH]
    assert [r["license_id"] for r in by_id] == [PLUS_WITH]
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
    ],
)
def test_strip_plus_operator(expression: str, stripped: str) -> None:
    assert strip_plus_operator(expression) == stripped
