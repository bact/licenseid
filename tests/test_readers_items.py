# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers`` of the 0.7.0 review: the readers of a declared value
that ``detect()`` and ``match()`` share, held to one answer, on the whole
3.29.0 List.

Each test was first a pin of what ``main`` did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

import json
import re
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, match
from licenseid.classify import grant_at, grant_spans, is_pure_license_text
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.looseid import grant_end
from licenseid.resolverinfo import trove_list_info


def _tag(corpus_db: LicenseDatabase, value: str) -> tuple[str, bool] | None:
    """The top answer of ``detect()`` for an SPDX tag of *value*."""
    found = LicenseDetector(corpus_db.location).detect(
        f"SPDX-License-Identifier: {value}"
    )
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _field(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> str | None:
    """The exact answer of ``detect()`` for a package.json ``license`` field."""
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"license": value}), encoding="utf-8")
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    return found[0]["expression"] if found and found[0]["exact"] else None


def _answer(corpus_db: LicenseDatabase, value: str) -> tuple[str | None, str | None]:
    got = match(value, corpus_db)
    return got["expression"], got["reason"]


# --- item 1: the trove list we ship has a version -----------------------------


def test_the_trove_list_has_a_version() -> None:
    # BUG: no version for a list licenseid ships.
    assert trove_list_info()["version"] is None


# --- item 2: a "+" after a space ----------------------------------------------


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("GPL-2.0 +", "GPL-2.0-or-later"),
        ("GPL-2.0 + OR MIT", "GPL-2.0-or-later OR MIT"),
        ("MIT +", "MIT+"),
    ],
)
def test_a_spaced_plus_in_match(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    # BUG: read as the operator, which never follows a space.
    assert _answer(corpus_db, value) == (expression, None)


def test_a_spaced_plus_in_a_tag(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    assert _tag(corpus_db, "GPL-2.0 + OR MIT") == ("GPL-2.0-only", False)
    assert given.conditions() == {"variant not stated"}
    assert _tag(corpus_db, "Apache-2.0 +") == ("Apache-2.0", True)


# --- item 3: a keyword ignores case in ASCII only -----------------------------


def test_a_dotted_capital_i_in_with(corpus_db: LicenseDatabase) -> None:
    # BUG: U+0130 folds to "i", so "WİTH" was the operator.
    assert _answer(corpus_db, "MIT WİTH Classpath-exception-2.0") == (
        "MIT WITH Classpath-exception-2.0",
        None,
    )


# --- item 4: one probe of "or later" ------------------------------------------


def test_the_tag_and_match_disagree_on_a_negated_grant() -> None:
    text = "GPL-2.0-only not or later"
    operator = re.compile("or").search(text, 17)
    assert operator is not None
    # BUG: two probes; the tag's took no negation.
    assert grant_at(text, operator, grant_spans(text), True) == len(text)
    assert grant_end(text, operator.start()) is None


# --- item 5: numbered sections after blank lines ------------------------------

_WORDS = " ".join(f"word{n}" for n in range(40))


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_numbered_sections_are_counted_as_before(line_break: str) -> None:
    sections = line_break.join(f"  {n}. Section {n}" for n in range(1, 6))
    text = _WORDS + line_break * 3 + sections
    assert is_pure_license_text(None, text)
    assert not is_pure_license_text(None, text.replace("5. Section", "5 Section"))


def test_a_run_of_blank_lines_before_a_section() -> None:
    payload = _WORDS + "\n" * 2_000 + "x"
    start = time.monotonic()
    assert not is_pure_license_text(None, payload)
    assert time.monotonic() - start < 5


# --- item 6: a reference in another case --------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("licenseref-foo", None),  # BUG: nothing
        ("MIT OR licenseref-foo", ("MIT OR licenseref-foo", True)),  # BUG
        ("LicenseRef-foo", ("LicenseRef-foo", True)),
        ("mit", ("MIT", True)),
    ],
)
def test_a_reference_in_another_case_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool] | None
) -> None:
    assert _tag(corpus_db, value) == answer


def test_a_reference_in_another_case_in_a_field(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    assert _field(corpus_db, tmp_path, "licenseref-foo") is None  # BUG
    assert _field(corpus_db, tmp_path, "MIT OR licenseref-foo") == (
        "MIT OR licenseref-foo"  # BUG
    )


# --- item 7: whose grant ------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        # BUG: the grant is version 3's, not GPL-2.0's.
        ("GPL-2.0, version 3 or later", ("GPL-2.0-or-later", True)),
        ("GPL-2.0, 3 or later", ("GPL-2.0-or-later", True)),
        # BUG: the grant is dropped in silence.
        ("MIT, or any later version", ("MIT", True)),
        ("Apache-2.0 or later", ("Apache-2.0", True)),
        ("GPL-2.0, or any later version", ("GPL-2.0-or-later", True)),
    ],
)
def test_whose_grant_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool] | None
) -> None:
    assert _tag(corpus_db, value) == answer


# --- item 8: an information separator on the command line ---------------------


@pytest.mark.parametrize(
    "value", ["\x1f", "\x1c", " \x1e "], ids=["x1f", "x1c", "x1e-in-spaces"]
)
def test_an_information_separator_alone_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["match", value])
    # BUG: blank, where match() reads a character it refuses.
    assert (result.exit_code, result.stderr) == (2, "ERROR: input: empty: argument\n")


# --- item 9: quote marks around nothing, a reference before a comma -----------


def test_empty_quotes_joined_by_an_operator(corpus_db: LicenseDatabase) -> None:
    # BUG: the outer marks pair as one layer around `" OR "`.
    assert _answer(corpus_db, '"" OR ""') == (None, "not found: OR")


def test_a_reference_and_a_comma_before_a_grant(corpus_db: LicenseDatabase) -> None:
    # BUG: the reference is not found for its comma.
    assert _answer(corpus_db, "LicenseRef-a, or any later version") == (
        None,
        "not found: LicenseRef-a, or any later version",
    )
