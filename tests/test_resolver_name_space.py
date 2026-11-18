# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` reads a List name written with a run of white space inside
(``MIT  License``, a tab, a no-break space) as the name spaced once, as the
SPDX matching guidelines read white space: ``listed_name``, exact, as in
0.8.4 (A1)."""
# pylint: disable=missing-function-docstring

import warnings
from collections.abc import Generator

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from matcher_db import Lic, seeded_db
from resolver_corpus import LICENSE_LIST, list_rows

from licenseid import LicenseDatabase, LicenseIdWarning, resolve
from licenseid.detector import LicenseDetector
from licenseid.resolvertypes import Resolution

#: Real List names, a deprecated licence's too (``GNU General Public License
#: v2.0 only`` is the name of GPL-2.0 and of GPL-2.0-only), and the ID each
#: names alone.
NAMES = [
    ("MIT License", "MIT"),
    ("Apache License 2.0", "Apache-2.0"),
    ("Apache License 1.1", "Apache-1.1"),
    ("GNU General Public License v2.0 only", "GPL-2.0-only"),
    ("GNU General Public License v2.0 or later", "GPL-2.0-or-later"),
    ("GNU General Public License v3.0 only", "GPL-3.0-only"),
    ("GNU Lesser General Public License v2.1 only", "LGPL-2.1-only"),
    ("GNU Lesser General Public License v3.0 or later", "LGPL-3.0-or-later"),
    ("GNU Affero General Public License v3.0 only", "AGPL-3.0-only"),
    ("Mozilla Public License 2.0", "MPL-2.0"),
    ('BSD 3-Clause "New" or "Revised" License', "BSD-3-Clause"),
    ('BSD 2-Clause "Simplified" License', "BSD-2-Clause"),
    ("BSD 4 Clause Shortened", "BSD-4-Clause-Shortened"),
    ("BSD 4.3 TAHOE License", "BSD-4.3TAHOE"),
    ("ISC License", "ISC"),
    ("zlib License", "Zlib"),
    ("The Unlicense", "Unlicense"),
    ("Academic Free License v1.2", "AFL-1.2"),
    ("Academic Free License v3.0", "AFL-3.0"),
    ("Eclipse Public License 2.0", "EPL-2.0"),
    ("Common Development and Distribution License 1.0", "CDDL-1.0"),
    ("European Union Public License 1.2", "EUPL-1.2"),
    ("Creative Commons Zero v1.0 Universal", "CC0-1.0"),
    ("Creative Commons Attribution 4.0 International", "CC-BY-4.0"),
    ("Boost Software License 1.0", "BSL-1.0"),
    ("Artistic License 2.0", "Artistic-2.0"),
    ("ImageMagick License", "ImageMagick"),
    ("MIT-STK License", "MIT-STK"),
    ("ssh-keyscan License", "ssh-keyscan"),
    ("psfrag License", "psfrag"),
]

#: Runs of white space that read as one space.
RUNS = ["  ", "\t", " \t ", "  ", "   "]


def _spaced(name: str, run: str) -> str:
    """*name* with each space a *run*."""
    return name.replace(" ", run)


def _reading(got: Resolution) -> tuple[object, ...]:
    """What a resolution answers, leaving out the text its steps quote."""
    return (
        got["expression"],
        got["category"],
        [s["kind"] for s in got["steps"]],
        [s["kind"] for s in got["expansions"]],
        got["reason"],
    )


def test_the_names_are_the_lists() -> None:
    listed = {str(row[1]): str(row[0]) for row in list_rows(LICENSE_LIST, "licenses")}
    assert all(listed.get(name) for name, _ in NAMES)


@pytest.mark.parametrize("run", RUNS, ids=repr)
@pytest.mark.parametrize(("name", "license_id"), NAMES)
def test_a_run_of_white_space_reads_as_one_space(
    corpus_db: LicenseDatabase, name: str, license_id: str, run: str
) -> None:
    value = _spaced(name, run)
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (license_id, "listed_name")
    assert [(s["kind"], s["from"], s["to"]) for s in got["steps"]] == [
        ("listed_name", value, license_id)
    ]
    assert _reading(got) == _reading(resolve(name, corpus_db))


def test_every_list_name_doubled_reads_as_written_once(
    corpus_db: LicenseDatabase,
) -> None:
    """Every licence name of the List (740), each space doubled, answers as
    the name as the List writes it, but the few the List writes with a run of
    their own (below)."""
    names = [str(row[1]) for row in list_rows(LICENSE_LIST, "licenses")]
    assert len(names) > 700
    moved = [
        name
        for name in names
        if " " in name
        and name not in LIST_RUNS
        and _reading(resolve(_spaced(name, "  "), corpus_db))
        != _reading(resolve(name, corpus_db))
    ]
    assert not moved


def test_the_span_indexes_the_value_as_written(corpus_db: LicenseDatabase) -> None:
    value = "  MIT  License "
    (operand,) = resolve(value, corpus_db)["operands"]
    start, end = operand["span"]
    assert value[start:end] == "MIT  License"
    assert operand["category"] == "listed_name"


#: The names the List (3.29.0) writes with a run of white space of its own.
LIST_RUNS = [
    "Common Attack    Pattern Enumeration and Classification License",
    "Creative    Commons Public Domain Mark 1.0 Universal",
    "CMU    Mach - no notices-in-documentation variant",
    "Historical Permission Notice and Disclaimer    - INRIA-IMAG variant",
    "IEC    Code Components End-user licence agreement",
    "NIST    Public Domain Notice TNT variant",
    "United    Kingdom Open Parliament Licence v3.0",
]


def test_the_list_runs_are_the_lists() -> None:
    names = [str(row[1]) for row in list_rows(LICENSE_LIST, "licenses")]
    assert [name for name in names if " ".join(name.split()) != name] == LIST_RUNS


@pytest.mark.parametrize("name", LIST_RUNS)
def test_a_name_with_a_run_of_its_own_reads_only_as_the_list_writes_it(
    corpus_db: LicenseDatabase, name: str
) -> None:
    """Only a run in the value is read as one space, not one in the List:
    ``resolve()`` reads the name spaced once as no List name (``detect()``
    answers it by the name tier, exact)."""
    assert resolve(name, corpus_db)["category"] == "listed_name"
    assert resolve(" ".join(name.split()), corpus_db)["expression"] is None


def test_a_name_the_list_spaces_so_still_reads() -> None:
    """A List name with a run of its own (``Creative    Commons Public Domain
    Mark 1.0 Universal`` in 3.29.0) reads as the List writes it."""
    name = "Creative    Commons Public Domain Mark 1.0 Universal"
    for path in seeded_db("listrun", [Lic("CC-PDM-1.0", name), Lic("MIT", "MIT")]):
        got = resolve(name, LicenseDatabase(path, create=False))
        assert (got["expression"], got["category"]) == ("CC-PDM-1.0", "listed_name")


@pytest.mark.parametrize(
    ("value", "expression", "category"),
    [
        ("MIT  License+", "MIT+", "listed_name"),
        ("MIT  License or later", "MIT+", "stated_qualifier"),
        ("GNU  General Public License v2.0 or later", "GPL-2.0-or-later", None),
        ("The  MIT  License", "MIT", "prose_form"),
        ("MIT  License WITH Classpath-exception-2.0", None, "listed_name"),
        ("MIT \n License", "MIT", "listed_name"),
        ("Eclipse  Public License, Version 2.0", "EPL-2.0", "prose_form"),
    ],
)
def test_a_spaced_name_reads_as_the_name_does(
    corpus_db: LicenseDatabase,
    value: str,
    expression: str | None,
    category: str | None,
) -> None:
    got = resolve(value, corpus_db)
    once = resolve(" ".join(value.split()), corpus_db)
    assert _reading(got) == _reading(once)
    if expression is not None:
        assert got["expression"] == expression
    if category is not None:
        assert got["category"] == category


@pytest.mark.parametrize(
    "value",
    [
        "MIT  License OR Apache  License 2.0",
        "MIT  License AND ISC",
        "MIT; Apache  License 2.0",
        "MIT, Apache  License 2.0",
        "*MIT  License*",
        "GPL  2.0",
        "Nunit  License",
        "New  BSD",
        "GNU  Affero General Public License v3.0",
    ],
)
def test_a_spaced_value_answers_as_spaced_once(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A compound of names stays refused (an operand of several words), as
    with one space; what is refused or read by another rule today stays so."""
    got = resolve(value, corpus_db)
    assert _reading(got) == _reading(resolve(" ".join(value.split()), corpus_db))


def test_an_information_separator_is_no_white_space(
    corpus_db: LicenseDatabase,
) -> None:
    """U+001C to U+001F, which ``str.split()`` takes as white space, are not
    read as a space: a reader that gets one (here the reason of a refused
    value, whose name keeps the U+001F) reads no name past it."""
    value = "\x1fBoehm-Demers-Weiser GC License WITH x-exception + MIT)"
    got = resolve(value, corpus_db)
    assert str(got["reason"]).startswith("not found: Boehm-Demers-Weiser")
    assert resolve("MIT\x1fLicense", corpus_db)["expression"] is None


@pytest.mark.parametrize(
    "value",
    [
        (
            "*European  Space Agency Public License (ESA-PL) - V2.4 - Strong"
            " Copyleft (Type 1)*"
        ),
        "# Creative  Commons Attribution Share Alike 2.0 England and Wales",
    ],
    ids=lambda v: v[:12],
)
def test_a_long_spaced_name_in_marks_has_no_text_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """A List name in marks is refused, not matched as text, with a run of
    white space as with one space (``resolvereason.wrapped_name``)."""
    assert str(resolve(value, corpus_db)["reason"]).startswith("character dropped")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LicenseIdWarning)
        assert LicenseDetector(corpus_db.location).detect(text=value) == []


@pytest.fixture(name="near_db")
def fixture_near_db() -> Generator[str, None, None]:
    """MIT and Apache-2.0 with their near neighbours and texts, so a text
    tier has something to answer."""
    rows = [
        Lic("MIT", "MIT License", search_text="permission is hereby granted mit"),
        Lic("MIT-0", "MIT No Attribution", search_text="mit no attribution"),
        Lic("X11", "X11 License", search_text="x11 permission is hereby granted"),
        Lic("Apache-2.0", "Apache License 2.0", search_text="apache license 2 0"),
        Lic("Apache-1.1", "Apache License 1.1", search_text="apache license 1 1"),
    ]
    yield from seeded_db("namespace", rows)


@pytest.mark.parametrize(
    ("text", "expression"),
    [
        ("MIT  License", "MIT"),
        ("MIT\tLicense", "MIT"),
        ("Apache  License 2.0", "Apache-2.0"),
        ("  Apache License  2.0 ", "Apache-2.0"),
    ],
)
def test_detect_answers_a_spaced_name_exactly(
    near_db: str, text: str, expression: str
) -> None:
    (found,) = LicenseDetector(near_db).detect(text)
    assert (found["expression"], found["method"], found["exact"]) == (
        expression,
        "name",
        True,
    )
