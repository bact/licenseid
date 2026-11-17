# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A cut ID gets no answer (roadmap item 54).

Two shapes were answered: a bare major with another minor on the List
(``Apache-1`` read as ``Apache-1.0``, ``LGPLv2`` as ``LGPL-2.0``) and an ID
with a dash or ``_`` joined to its end (``MIT-`` read as ``MIT``). Both are
refused now. A bare major no other minor shares (``Apache 2``), an
"or later" grant (``LGPLv2+``) and an ending (``MIT.``) are read as before.
The rows were pinned on ``main`` first (``# BUG: (item 54)``) and flipped.
"""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase, resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.dropguard import trailing_joiners
from licenseid.versionkey import ambiguous_ids, sibling_keys, writes_bare_major

AMBIGUOUS = "version ambiguous: "
DASH = "character dropped: U+002D"

#: ``value: reason``, read before item 54 (``# BUG: (item 54)`` in the
#: git history of this table: ``Apache-1`` was ``Apache-1.0``).
REFUSED: dict[str, str] = {
    "Apache-1": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "Apache 1": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "Apache-1.": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "MPL-1": AMBIGUOUS + "MPL-1.0, MPL-1.1",
    "OFL-1": AMBIGUOUS + "OFL-1.0, OFL-1.1",
    "LGPLv2": AMBIGUOUS + "LGPL-2.0, LGPL-2.1",
    "CC-BY-SA-2": AMBIGUOUS + "CC-BY-SA-2.0, CC-BY-SA-2.5",
    "EUPL-1": AMBIGUOUS + "EUPL-1.0, EUPL-1.1, EUPL-1.2",
    "Python-2": AMBIGUOUS + "Python-2.0, Python-2.0.1",
    "LGPL-2-only": AMBIGUOUS + "LGPL-2.0-only, LGPL-2.1-only",
    "LGPLv2 only": AMBIGUOUS + "LGPL-2.0-only, LGPL-2.1-only",
    "Apache 1 License": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "Apache-1 OR MIT": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "MIT OR Apache-1": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "(Apache-1 OR MIT) AND ISC": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "Apache-1 WITH LLVM-exception": AMBIGUOUS + "Apache-1.0, Apache-1.1",
    "MIT-": DASH,
    "MIT_": "character dropped: U+005F",
    "MIT--": DASH,
    "MIT-.": DASH,
    "MIT-_": "character dropped: U+002D U+005F",
    "MIT–": "character dropped: U+2013",
    "Zlib-": DASH,
    "GPL-2.0-": DASH,
    "LGPL-2.1-": DASH,
    "GPLv2-": DASH,
    "Apache 2.0-": DASH,
    "GPL-2.0 or later-": DASH,
    "BSD-3-Clause-": DASH,
    "MIT- OR ISC": DASH,
    "MIT OR ISC-": DASH,
    "(MIT-)": DASH,
    "MIT-+": DASH,
    "MIT--+": DASH,
    "GPL-2.0-+": DASH,
    "LGPL-2.1_+": "character dropped: U+005F",
    "MIT-+ WITH LLVM-exception": DASH,
}

#: A malformed qualifier on a cut ID keeps its own reason: the grant exempts
#: the ID from ``version ambiguous``, and the qualifier is what is wrong.
MALFORMED: dict[str, str] = {
    "LGPLv2 +": "plus after a space: LGPLv2 +",
    "LGPLv2+ or later": "qualifier stated twice: LGPLv2+ or later",
    "(LGPLv2)+": "plus after a bracket: (LGPLv2)+",
}

#: ``value: expression``, answered before and after: a bare major no other
#: minor of the List shares, a stated grant, an ending, a reference.
STAYS: dict[str, str] = {
    "Apache 2": "Apache-2.0",
    "Apache2": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "GPLv3": "GPL-3.0",
    "GPL-2": "GPL-2.0",
    "GPL2+": "GPL-2.0-or-later",
    "LGPLv2+": "LGPL-2.0-or-later",
    "LGPLv2 or later": "LGPL-2.0-or-later",
    "LGPL-2-or-later": "LGPL-2.0-or-later",
    "LGPL-2.0+": "LGPL-2.0-or-later",
    "LGPLv3": "LGPL-3.0",
    "MPL-2": "MPL-2.0",
    "CC-BY-4": "CC-BY-4.0",
    "CC-BY-3": "CC-BY-3.0",
    "EPL-1": "EPL-1.0",
    "Artistic-1": "Artistic-1.0",
    "Apache-1.0": "Apache-1.0",
    "Apache-1.1": "Apache-1.1",
    "Apache-1+": "Apache-1.0+",
    "Apache 1 or later": "Apache-1.0+",
    "LGPL-2.1": "LGPL-2.1",
    "OLDAP-2.2": "OLDAP-2.2",
    "Python-2.0.1": "Python-2.0.1",
    "MIT.": "MIT",
    "MIT;": "MIT",
    "MIT,": "MIT",
    "MIT.-": "MIT",
    "LicenseRef-a-": "LicenseRef-a-",
}


def _top(detector: LicenseDetector, value: str) -> str | None:
    found = detector.detect(text=value)
    return found[0]["expression"] if found else None


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: v[:30])
def test_a_cut_value_is_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"], got["reason"]) == (
        None,
        "unresolved",
        REFUSED[value],
    )
    assert got["candidates"] == []
    assert got["expansions"] == []
    detector = LicenseDetector(corpus_db.location)
    assert _top(detector, value) is None
    # a refused short value says it is too short for a text match
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("value", sorted(MALFORMED), ids=lambda v: v[:30])
def test_a_malformed_qualifier_keeps_its_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["category"], got["reason"]) == ("malformed", MALFORMED[value])


def test_a_dropped_joiner_is_a_dropped_step(corpus_db: LicenseDatabase) -> None:
    got = resolve("MIT-", corpus_db)
    assert [(s["kind"], s["applied"], s["from"]) for s in got["steps"]] == [
        ("drop", False, "MIT-")
    ]
    assert not resolve("Apache-1", corpus_db)["steps"]


@pytest.mark.parametrize("value", sorted(STAYS), ids=lambda v: v[:30])
def test_an_unambiguous_value_is_read(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == STAYS[value]
    assert _top(LicenseDetector(corpus_db.location), value) == STAYS[value]


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: v[:30])
def test_the_packaged_list_refuses_alike(
    monkeypatch: pytest.MonkeyPatch, corpus_db: LicenseDatabase, value: str
) -> None:
    ship(monkeypatch, fixture_bundle())
    got = resolve(value, source="packaged")
    assert (got["expression"], got["reason"]) == (None, REFUSED[value])
    assert got["lists"][0]["source"] == "packaged"
    assert resolve(value, corpus_db)["reason"] == got["reason"]


@pytest.mark.parametrize("value", ["Apache 2", "LGPLv2+", "MIT."])
def test_the_packaged_list_reads_alike(
    monkeypatch: pytest.MonkeyPatch, corpus_db: LicenseDatabase, value: str
) -> None:
    ship(monkeypatch, fixture_bundle())
    assert (
        resolve(value, source="packaged")["expression"]
        == resolve(value, corpus_db)["expression"]
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache-1", True),
        ("Apache 1.", True),
        ("LGPLv2", True),
        ("CC-BY-3-DE", True),
        ("BSD-3-Clause", True),
        ("Apache2", True),
        ("Apache-1.0", False),
        ("Apache-1.0.1", False),
        ("Python-2.0.1", False),
        ("OLDAP-2.2", False),
        ("CC-BY-3.0-DE", False),
        ("MIT", False),
        ("", False),
        ("Apache-1.", True),
        ("١", False),  # an Arabic-Indic digit: no reading changes
    ],
)
def test_writes_bare_major(text: str, expected: bool) -> None:
    assert writes_bare_major(text) is expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("apache 1", ["apache 1 1"]),
        ("lgpl 2 only", ["lgpl 2 1 only"]),
        ("python 2", ["python 2 0 1"]),
        ("cc by 3", []),  # a port is another word, no sibling
        ("mit", []),
        ("", []),
        ("apache 11", []),  # a longer number is no prefix
    ],
)
def test_sibling_keys(key: str, expected: list[str]) -> None:
    keys = [
        "apache 1",
        "apache 1 1",
        "apache 11",
        "apache 2",
        "lgpl 2 only",
        "lgpl 2 1 only",
        "python 2",
        "python 2 0 1",
        "cc by 3",
        "cc by 3 de",
        "cc by 3 0 de",
        "mit",
    ]
    assert sibling_keys(keys, key) == [k for k in expected if k in keys]


def test_ambiguous_ids(corpus_db: LicenseDatabase) -> None:
    with corpus_db.reading():
        assert ambiguous_ids(corpus_db, "Apache-1") == ["Apache-1.0", "Apache-1.1"]
        assert ambiguous_ids(corpus_db, " LGPLv2 ") == ["LGPL-2.0", "LGPL-2.1"]
        assert ambiguous_ids(corpus_db, "Apache-1.0") == []
        assert ambiguous_ids(corpus_db, "Apache-2") == []
        assert ambiguous_ids(corpus_db, "LGPL-2-or-later") == []
        assert ambiguous_ids(corpus_db, "Nothing-1") == []
        assert ambiguous_ids(corpus_db, "Apache-1" + " x" * 60) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT-", "-"),
        ("MIT_", "_"),
        ("MIT--", "-"),
        ("MIT-_", "-_"),
        ("MIT-.", "-"),
        ("MIT-,", "-"),
        ("MIT-  ", "-"),
        ("MIT–", "–"),
        ("GPL-2.0-", "-"),
        ("MIT", ""),
        ("MIT.", ""),
        ("MIT -", ""),
        ("MIT.-", ""),
        ("MIT+-", ""),  # after a "+": its own reader
        ("-", ""),
        ("", ""),
        ("LicenseRef-a-", ""),
        ("AdditionRef-a-", ""),
        ("MIT-0", ""),
    ],
)
def test_trailing_joiners(text: str, expected: str) -> None:
    assert trailing_joiners(text) == expected


def test_a_cut_id_in_a_manifest_field_gets_no_answer(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"license": "Apache-1"}), encoding="utf-8")
    assert LicenseDetector(corpus_db.location).detect(file_path=str(path)) == []
    path.write_text(json.dumps({"license": "Apache-1.1"}), encoding="utf-8")
    found = LicenseDetector(corpus_db.location).detect(file_path=str(path))
    assert [d["expression"] for d in found] == ["Apache-1.1"]


@pytest.mark.parametrize(
    ("args", "code", "line"),
    [
        (["detect", "--id", "Apache-1"], 1, "EXPRESSION=\t"),
        (["detect", "--id", "Apache-1.1"], 0, "EXPRESSION=Apache-1.1\t"),
        (["is-osi", "--id", "Apache-1"], 1, "EXPRESSION=\t"),
        (["is-osi", "Apache-1"], 1, "EXPRESSION=\t"),
        (["detect", "--variant", "or-later", "LGPLv2"], 1, "EXPRESSION=\t"),
        (["detect", "--variant", "only", "LGPLv2"], 1, "EXPRESSION=\t"),
        (["detect", "--variant", "or-later", "LGPLv2+"], 0, "EXPRESSION=LGPL-2.0-or"),
        (["resolve", "LGPLv2"], 1, ""),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_cli_gives_no_answer_for_a_cut_id(
    corpus_db: LicenseDatabase,
    args: list[str],
    code: int,
    line: str,
) -> None:
    verbose = [] if args[0] == "is-osi" else ["--verbose"]
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, args[0], *verbose, *args[1:]]
    )
    assert result.exit_code == code, result.stderr
    assert result.stdout.startswith(line)


def test_the_trove_classifier_stays_lgpl_2_0(corpus_db: LicenseDatabase) -> None:
    """The classifier names the licence by a table (``trovenames``), not by
    reading an ID: the PyPI classifier ``(LGPLv2)`` stays ``LGPL-2.0``."""
    got = resolve("GNU Lesser General Public License v2 (LGPLv2)", corpus_db)
    assert got["expression"] == "LGPL-2.0"
