# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A "+" that is no operator, on the paths of ``detect()`` that read a
value as a text (tech-debt roadmap, item 44).

``normalize_text`` drops a "+", so a text match answered the licence round
it, exact, for a value ``resolve()`` refuses: quoted or bracketed text
(``"MIT++"``), a name (``MIT License++``), a quoted manifest value read by
the CLI with no extension. A short value ``resolve()`` refuses for a "+"
reason (``resolvereason.is_plus_refusal``) now gets no text match.

A database of the whole List (``corpus_db``): a negative test on a seeded
database with no text passes whatever the code does."""
# pylint: disable=missing-function-docstring

import json
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from timing import slack

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.resolvereason import is_plus_refusal
from licenseid.types import Detection

TOO_FEW = "too few words for text"

# Each answered a licence, exact (or near), while resolve() refuses it.
QUOTED_OR_NAMED = [
    '"MIT++"',
    "[MIT++]",
    "'MIT++'",
    '"GPL-2.0-only+"',
    "[GPL-2.0-only+]",
    '"MIT +"',
    '"Apache-2.0 +"',
    "MIT License++",
    "Apache License 2.0++",
    "The MIT License++",
    "GPL-2.0 or later+",
    "Apache 2.0 +",
    "Apache 2.0 ++",
    "BSD 3-Clause License++",
    "MIT License +",
    "GNU General Public License v2.0 only+",
]


def _top(found: list[Detection]) -> tuple[str, bool] | None:
    return (found[0]["expression"], found[0]["exact"]) if found else None


@pytest.mark.parametrize("value", QUOTED_OR_NAMED)
def test_a_text_with_a_plus_that_is_no_operator_answers_no_licence(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    reason = resolve(value, corpus_db)["reason"]
    assert is_plus_refusal(reason), reason  # the premise: resolve() refuses it
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=value) == []
    assert TOO_FEW in given.conditions()


@pytest.mark.parametrize("command", ["detect", "is-spdx", "is-osi"])
@pytest.mark.parametrize(
    "value", ['"MIT++"', "[MIT++]", "MIT License++", "Apache 2.0 +"]
)
def test_the_cli_answers_no_for_such_a_text(
    corpus_db: LicenseDatabase, command: str, value: str
) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, command, "--text", value]
    )
    assert result.exit_code == 1
    assert "MIT" not in result.stdout.replace("EXPRESSION=", "")


# A quoted value that is a field of a manifest, whatever brings it.
FIELD_VALUES = ["MIT++", "GPL-2.0-only+", "MIT +", "Apache-2.0 +", "(MIT)+"]


def _toml_text(value: str) -> str:
    return f"[project]\nlicense = {json.dumps(value)}\n"


def _ini_text(value: str) -> str:
    return f'[metadata]\nlicense = "{value}"\n'


def _json_text(value: str) -> str:
    return json.dumps({"name": "x", "license": value})


def _text_route(make: Callable[[str], str]) -> Callable[..., list[Detection]]:
    def route(detector: LicenseDetector, _: Path, value: str) -> list[Detection]:
        return detector.detect(text=make(value))

    return route


def _file_route(
    name: str, make: Callable[[str], str]
) -> Callable[..., list[Detection]]:
    def route(detector: LicenseDetector, tmp: Path, value: str) -> list[Detection]:
        path = tmp / name
        path.write_text(make(value), encoding="utf-8")
        return detector.detect(file_path=str(path))

    return route


def _tag_route(detector: LicenseDetector, _: Path, value: str) -> list[Detection]:
    return detector.detect(text=f"SPDX-License-Identifier: {value}")


ROUTES = {
    "toml text": _text_route(_toml_text),
    "ini text": _text_route(_ini_text),
    "json text": _text_route(_json_text),
    "toml file": _file_route("pyproject.toml", _toml_text),
    "json file": _file_route("package.json", _json_text),
    "extensionless file": _file_route("manifest", _toml_text),
    "tag": _tag_route,
}


@pytest.mark.parametrize("route", sorted(ROUTES))
@pytest.mark.parametrize("value", FIELD_VALUES)
def test_a_manifest_field_with_such_a_plus_answers_no_licence(
    corpus_db: LicenseDatabase,
    given: GivenWarnings,
    tmp_path: Path,
    route: str,
    value: str,
) -> None:
    detector = LicenseDetector(corpus_db.location)
    assert ROUTES[route](detector, tmp_path, value) == []
    assert not given.take()  # a field read and refused: nothing to warn of


@pytest.mark.parametrize("value", ["MIT++", "MIT +"])
def test_the_cli_reads_an_extensionless_manifest_as_no_licence(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    path = tmp_path / "manifest"
    path.write_text(_toml_text(value), encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", corpus_db.location, "detect", str(path)])
    assert result.exit_code == 1
    assert "MIT" not in result.stdout.replace("EXPRESSION=", "")


# What a "+" that is an operator, or a value with none, still answers.
STILL_ANSWERS = [
    ("MIT+", "MIT+"),
    ('"MIT+"', "MIT+"),
    ("MIT+,", "MIT+"),
    ("GPL-2.0+", "GPL-2.0-or-later"),
    ("MIT License+", "MIT+"),
    ("Apache License 2.0+", "Apache-2.0+"),
    ('"MIT"', "MIT"),
    ("[MIT]", "MIT"),
    ("MIT License", "MIT"),
]


@pytest.mark.parametrize(("value", "expression"), STILL_ANSWERS)
def test_a_plus_that_is_an_operator_still_answers(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str, expression: str
) -> None:
    found = LicenseDetector(corpus_db.location).detect(text=value)
    assert found
    assert resolve(value, corpus_db)["expression"] == expression
    assert _top(found) == (expression, True)
    assert not given.take()


@pytest.mark.parametrize("value", ["MIT", "MIT+", "Apache-2.0", "Apache-2.0+"])
def test_a_field_with_an_operator_still_answers(
    corpus_db: LicenseDatabase, given: GivenWarnings, tmp_path: Path, value: str
) -> None:
    detector = LicenseDetector(corpus_db.location)
    for route in ROUTES.values():
        assert route(detector, tmp_path, value), route
    assert not given.take()


def test_a_long_text_with_a_c_plus_plus_line_is_matched_as_text(
    corpus_db: LicenseDatabase,
) -> None:
    """30 words or more never reach the check: the "+" of a prose line is no
    operator to refuse."""
    text = (
        "Permission is hereby granted, free of charge, to any person obtaining "
        "a copy of this software and associated documentation files (the "
        '"Software"), to deal in the Software without restriction, including '
        "without limitation the rights to use, copy, modify, merge, publish, "
        "distribute, sublicense, and/or sell copies of the Software.\n"
        "Written in C++\n"
    )
    plain = text.replace("Written in C++\n", "")
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=text)
    assert (
        detector.detect(text=text)[0]["expression"]
        == (detector.detect(text=plain)[0]["expression"])
    )


def test_a_name_in_a_sentence_with_a_plus_answers_no_licence(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    """A "+" left in a short value ``resolve()`` refuses is not dropped to
    match the name (was: ``MIT``, inexact; roadmap item 47, fixed by item
    48)."""
    found = LicenseDetector(corpus_db.location).detect(
        text="Licensed under the MIT++ license"
    )
    assert found == []
    assert TOO_FEW in given.conditions()


@pytest.mark.parametrize(
    "make",
    [
        lambda n: '"' + "MIT" + "+" * n + '"',
        lambda n: "MIT License" + "+" * n,
        lambda n: "MIT" + " +" * n,
    ],
    ids=["quoted", "name", "spaced"],
)
def test_a_long_run_of_pluses_is_read_in_linear_time(
    corpus_db: LicenseDatabase, given: GivenWarnings, make: Callable[[int], str]
) -> None:
    detector = LicenseDetector(corpus_db.location)
    value = make(20_000)
    start = time.monotonic()
    detector.detect(text=value)
    assert time.monotonic() - start < slack(3)
    given.take()  # a refused value says why
