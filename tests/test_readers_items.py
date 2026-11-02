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
from licenseid.identifiers import qualify_trailing_grant
from licenseid.resolverinfo import trove_list_info
from licenseid.trovenames import TROVE_CLASSIFIERS_VERSION


def _tag(corpus_db: LicenseDatabase, value: str) -> tuple[str, bool] | None:
    """The top answer of ``detect()`` for an SPDX tag of *value*."""
    found = LicenseDetector(corpus_db.location).detect(
        f"SPDX-License-Identifier: {value}"
    )
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _field(corpus_db: LicenseDatabase, tmp_path: Path, value: str) -> str | None:
    """The answer of ``detect()`` for a package.json ``license`` field, when
    it is exact (the field declares it)."""
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"name": "x", "license": value}), "utf-8")
    top = LicenseDetector(corpus_db.location).detect(file_path=str(manifest))[:1]
    return next((r["expression"] for r in top if r["exact"]), None)


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
    ("value", "reason"),
    [
        ("GPL-2.0 +", "plus after a space: GPL-2.0 +"),
        ("GPL-2.0  +", "plus after a space: GPL-2.0 +"),
        ("GPL-2.0\t+", "plus after a space: GPL-2.0 +"),
        ("MIT +", "plus after a space: MIT +"),
        ("Apache 2.0 +", "plus after a space: Apache 2.0 +"),
        ("GPL-2.0 +,", "plus after a space: GPL-2.0 +"),  # the core's reason
        ("GPL-2.0 + OR MIT", "plus after a space: GPL-2.0 +"),
        ("MIT OR GPL-2.0 +", "plus after a space: GPL-2.0 +"),
        ("GPL-2.0 + WITH Classpath-exception-2.0", "plus after a space: GPL-2.0 +"),
        # Unchanged: a "+" after a bracket, and two "+".
        ("(MIT) +", "plus after a bracket: (MIT) +"),
        ("GPL-2.0 + +", "qualifier stated twice: GPL-2.0 + +"),
        ("MIT+ +", "qualifier stated twice: MIT+ +"),
    ],
)
def test_a_spaced_plus_in_match(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    """A "+" after a space is no operator (plusoperator.PLUS_OPERATOR; it
    may say "and" too): refused where it qualifies a licence. It was read
    as the operator, with a ``whitespace`` step (P34)."""
    got = match(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "malformed",
        reason,
    )


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("GPL-2.0+", "GPL-2.0-or-later"),
        ("MIT+", "MIT+"),
        ("GPL-2.0+ OR MIT", "GPL-2.0-or-later OR MIT"),
    ],
)
def test_a_plus_that_touches_its_id_reads(
    corpus_db: LicenseDatabase, value: str, expression: str
) -> None:
    assert _answer(corpus_db, value) == (expression, None)


def test_a_spaced_plus_after_nothing_is_not_found(corpus_db: LicenseDatabase) -> None:
    assert _answer(corpus_db, "Foo +") == (None, "not found: Foo +")


@pytest.mark.parametrize(
    "value",
    ["GPL-2.0 + OR MIT", "Apache-2.0 +", "Apache-2.0 + MIT", "MIT+ +", "(MIT) +"],
)
def test_a_spaced_plus_in_a_tag(corpus_db: LicenseDatabase, value: str) -> None:
    """The tag read the licence before the "+" and dropped the rest:
    GPL-2.0-only (narrowed) for "GPL-2.0 + OR MIT", Apache-2.0 exact for
    "Apache-2.0 + MIT". Now no expression, as ``match()`` refuses it."""
    assert _tag(corpus_db, value) is None


def test_a_spaced_plus_as_an_argument(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    """Not changed: the loose reading of Tier 0 (versionkey, detector) drops a
    "+" apart from its ID and guesses the narrow grant, not exact, with a
    warning (F3)."""
    found = LicenseDetector(corpus_db.location).detect("GPL-2.0 +")
    assert (found[0]["expression"], found[0]["exact"]) == ("GPL-2.0-only", False)
    assert given.conditions() == {"variant not stated"}


# --- item 3: a keyword ignores case in ASCII only -----------------------------


def test_a_dotted_capital_i_in_with(corpus_db: LicenseDatabase) -> None:
    """U+0130 folded to "i", so "W\u0130TH" was the operator; it is no
    word of an expression (tests/test_readers_case.py)."""
    assert _answer(corpus_db, "MIT W\u0130TH Classpath-exception-2.0") == (
        None,
        "not found: MIT W\u0130TH Classpath-exception-2.0",
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
        # A reference in another case answered nothing alone, and stayed in
        # its case in an expression. Its prefix is SPDX's case now, its
        # idstring the author's; exact, as a case-folded ID is ("mit").
        ("licenseref-foo", ("LicenseRef-foo", True)),
        ("LICENSEREF-Foo", ("LicenseRef-Foo", True)),
        ("MIT OR licenseref-foo", ("MIT OR LicenseRef-foo", True)),
        ("mit OR licenseref-foo", ("MIT OR LicenseRef-foo", True)),
        ("documentref-x:licenseref-foo", ("DocumentRef-x:LicenseRef-foo", True)),
        (
            "MIT AND documentref-x:licenseref-foo",
            ("MIT AND DocumentRef-x:LicenseRef-foo", True),
        ),
        ("LicenseRef-foo", ("LicenseRef-foo", True)),
        ("mit", ("MIT", True)),
        # Still no reference: a "+" is none's.
        ("licenseref-foo+", None),
    ],
)
def test_a_reference_in_another_case_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool] | None
) -> None:
    assert _tag(corpus_db, value) == answer


def test_a_reference_in_another_case_in_a_field(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    assert _field(corpus_db, tmp_path, "licenseref-foo") == "LicenseRef-foo"
    assert _field(corpus_db, tmp_path, "MIT OR licenseref-foo") == (
        "MIT OR LicenseRef-foo"
    )


# --- item 7: whose grant ------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0, version 3 or later",
        "GPL-2.0, 3 or later",
        "GPL-2.0 version 3.0 or later",
        "GPL-2.0 (version 3 or later)",
        "GPL-2.0, LGPL-2.0 or later",  # a number joined to another word
        "GPL-2.0, v2 or later",
    ],
)
def test_a_grant_after_another_version_is_not_the_ids(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    """The grant is version 3's (the number between the ID and the phrase is
    another licence's), not GPL-2.0's: GPL-2.0 alone is read, as the narrow
    guess with a warning. It was GPL-2.0-or-later, exact."""
    assert _tag(corpus_db, value) == ("GPL-2.0-only", False)
    assert given.conditions() == {"variant not stated"}


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        # The grant was dropped in silence: MIT, exact. match() reads it as
        # the "+" of an ID with no -or-later form (P35).
        ("MIT, or any later version", "MIT+"),
        ("MIT or any later version", "MIT+"),
        ("Apache-2.0 or later", "Apache-2.0+"),
        ("MPL-2.0 (or later)", "MPL-2.0+"),
        ("MIT OR Apache-2.0 or later", "MIT OR Apache-2.0+"),
        (
            "MIT WITH Classpath-exception-2.0 or later",
            "MIT+ WITH Classpath-exception-2.0",
        ),
        # Unchanged: the -or-later form where the List has one.
        ("GPL-2.0, or any later version", "GPL-2.0-or-later"),
        ("GPL-2.0 or later", "GPL-2.0-or-later"),
        ("GPL-2 or later", "GPL-2.0-or-later"),
        ("(GPL-2.0) or later", "GPL-2.0-or-later"),
    ],
)
def test_a_grant_is_kept_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: str
) -> None:
    assert _tag(corpus_db, value) == (answer, True)


@pytest.mark.parametrize(
    "value",
    [
        "MIT, or any later version",
        "Apache-2.0 or later",
        "MPL-2.0 (or later)",
        "MIT WITH Classpath-exception-2.0 or later",
        "GPL-2.0, or any later version",
    ],
)
def test_the_tag_reads_a_grant_as_match_does(
    corpus_db: LicenseDatabase, value: str
) -> None:
    tag = _tag(corpus_db, value)
    assert tag is not None
    assert tag[0] == match(value, corpus_db)["expression"]


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0-only, or any later version",  # stated twice
        "LicenseRef-a or later",  # a reference takes none
        "GPL-2.0+ or later",  # stated twice
    ],
)
def test_a_grant_no_licence_takes_is_refused_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _tag(corpus_db, value) is None


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0, version 2 or later",  # its own version, restated
        "GPL-2.0, version 2.0 or later",
        "GPL-2.0 (version 2.0 or later)",
    ],
)
def test_a_grant_after_the_ids_own_version_is_the_ids(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _tag(corpus_db, value) == ("GPL-2.0-or-later", True)


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("GPL-2.0-only", "GPL-2.0-only or later"),
        ("LicenseRef-a", "LicenseRef-a or later"),
        ("GPL-2.0-only WITH Classpath-exception-2.0", "GPL-2.0-only WITH x or later"),
    ],
)
def test_no_qualifier_is_added_to_one_that_takes_none(
    expression: str, value: str
) -> None:
    """A tag refuses these before (leading_expression); the reader of the
    grant itself adds no "+" either."""
    assert qualify_trailing_grant(expression, value) == expression


def test_a_grant_is_kept_in_a_field(corpus_db: LicenseDatabase, tmp_path: Path) -> None:
    assert _field(corpus_db, tmp_path, "MIT, or any later version") == "MIT+"
    assert _field(corpus_db, tmp_path, "GPL-2.0, version 3 or later") is None


# --- item 8: an information separator on the command line ---------------------


@pytest.mark.parametrize(
    ("value", "code"),
    [("\x1f", "U+001F"), (" \x1f ", "U+001F"), ("\x1fMIT", "U+001F")],
    ids=["alone", "in-spaces", "before-an-id"],
)
def test_a_unit_separator_is_a_character_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, value: str, code: str
) -> None:
    """It was blank (``str.strip`` takes U+001C to U+001F), exit 2; match()
    refuses it as a control character, exit 1, as for ``MIT\x1f``."""
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["match", value])
    assert (result.exit_code, result.stderr) == (1, "")
    assert result.stdout == (
        "EXPRESSION=\tCATEGORY=unresolved\tTRUST=none\n"
        f"REASON=control or format character: {code}\n"
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [("\x1c", "U+001C"), (" \x1e ", "U+001E"), ("\x1d", "U+001D")],
    ids=["x1c", "x1e-in-spaces", "x1d"],
)
def test_a_separator_that_breaks_a_line_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, value: str, code: str
) -> None:
    """It was blank; it breaks a line (``str.splitlines``), as in ``MIT\x1c``."""
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["match", value])
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr == (
        f"ERROR: input: invalid: line break {code}; run 'licenseid detect'\n"
    )


@pytest.mark.parametrize("value", ["", " ", "\t \u3000", "\x85"])
def test_white_space_alone_is_still_empty(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    ship(monkeypatch, fixture_bundle())
    result = CliRunner().invoke(cli, ["match", value])
    assert (result.exit_code, result.stdout) == (2, "")
    assert result.stderr == "ERROR: input: empty: argument\n"


def test_a_unit_separator_as_the_argument_of_detect(corpus_db: LicenseDatabase) -> None:
    """It was blank, exit 2; detect reads it as the library does: no
    licence, exit 1 (--text and --id: tests/test_readers_tags.py)."""
    result = CliRunner().invoke(cli, ["--db", corpus_db.location, "detect", "\x1f"])
    assert (result.exit_code, result.stderr) == (1, "")


# --- item 9: quote marks around nothing, a reference before a comma -----------


@pytest.mark.parametrize(
    "value", ['"" OR ""', '"" AND ""', "'' OR ''", "\"\" OR ''"], ids=str
)
def test_empty_quotes_joined_by_an_operator(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The outer marks paired as two layers around the operator, which was
    then the value (``not found: OR``); each pair is an operand's."""
    quotes = value[0] * 2
    assert _answer(corpus_db, value) == (None, f"operand not resolved: {quotes}")


@pytest.mark.parametrize(
    ("value", "expression"),
    [('""MIT""', "MIT"), ('"OR"', None), ('" MIT "', "MIT")],
)
def test_quotes_around_a_value_still_go(
    corpus_db: LicenseDatabase, value: str, expression: str | None
) -> None:
    assert match(value, corpus_db)["expression"] == expression


@pytest.mark.parametrize(
    "value",
    [
        "LicenseRef-a, or any later version",  # was not found, for its comma
        "LicenseRef-a; or any later version",
        "licenseref-a, or later",
        "LicenseRef-a or any later version",
    ],
)
def test_a_reference_and_an_end_mark_before_a_grant(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        f"qualifier on a reference: {value}",
    )
