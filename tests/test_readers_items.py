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

from licenseid import LicenseDatabase, classify, looseid, match
from licenseid.classify import grant_at, grant_end, grant_spans, is_pure_license_text
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.resolverinfo import trove_list_info
from licenseid.trovenames import TROVE_CLASSIFIERS_VERSION


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
    """The release the table was decided from (it had none: ``null`` for a
    list licenseid ships), the lower bound of the test dependency that
    test_trovenames checks every classifier against."""
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text("utf-8")
    pinned = re.findall(r'"trove-classifiers>=([0-9.]+)"', pyproject)
    assert pinned == [TROVE_CLASSIFIERS_VERSION]
    assert trove_list_info()["version"] == TROVE_CLASSIFIERS_VERSION


def test_a_trove_answer_names_the_version(corpus_db: LicenseDatabase) -> None:
    lists = match("License :: OSI Approved :: MIT License", corpus_db)["lists"]
    assert [(e["id"], e["version"]) for e in lists] == [
        ("spdx-license-list", "3.29.0"),
        ("pypi-trove-classifiers", "2026.9.21.13"),
    ]


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


def test_one_probe_reads_a_grant_after_an_id() -> None:
    """``looseid`` (``match()``) reads with the probe the tag reads with."""
    assert looseid.grant_end is classify.grant_end


@pytest.mark.parametrize(
    ("text", "grant"),
    [
        ("GPL-2.0-only not or later", False),  # the tag's own probe read one
        ("GPL-2.0-only No or later", False),
        ("GPL-2.0-only or later", True),
        ("GPL-2.0-only cannot or later", True),  # a word that ends in "not"
        ("GPL-2.0-only OR not later", False),
    ],
)
def test_the_tag_and_match_agree_on_a_negated_grant(text: str, grant: bool) -> None:
    operator = re.compile("or", re.IGNORECASE).search(text, 13)
    assert operator is not None
    tag = grant_at(text, operator, grant_spans(text), True)
    assert tag == grant_end(text, operator.start())
    assert tag == (len(text) if grant else None)


# --- item 5: numbered sections after blank lines ------------------------------

_WORDS = " ".join(f"word{n}" for n in range(40))


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_numbered_sections_are_counted_as_before(line_break: str) -> None:
    sections = line_break.join(f"  {n}. Section {n}" for n in range(1, 6))
    text = _WORDS + line_break * 3 + sections
    assert is_pure_license_text(None, text)
    assert not is_pure_license_text(None, text.replace("5. Section", "5 Section"))


@pytest.mark.parametrize(
    "line_break", ["\n", "\r\n", " \n"], ids=["LF", "CRLF", "space LF"]
)
def test_a_run_of_blank_lines_is_read_in_linear_time(line_break: str) -> None:
    # 20,000 blank lines took 6 s (13 s with CRLF) when the indent was `\s*`.
    payload = _WORDS + line_break * 20_000 + "x"
    start = time.monotonic()
    assert not is_pure_license_text(None, payload)
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"took {elapsed:.3f}s"


@pytest.mark.benchmark
def test_detect_reads_a_run_of_blank_lines_quickly(corpus_db: LicenseDatabase) -> None:
    payload = _WORDS + "\n" * 20_000 + "x"
    start = time.monotonic()
    LicenseDetector(corpus_db.location).detect(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 2, f"took {elapsed:.3f}s"  # 7 s before


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
