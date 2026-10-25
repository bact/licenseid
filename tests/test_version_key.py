# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An ID written without its ".0" or its dashes ("Apache2", "GPLv3",
"CC by 3 nl") is that ID (licenseid.shorttext.version_key)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
import time
from collections import Counter
from collections.abc import Generator
from pathlib import Path

import pytest
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.shorttext import match_version_key, version_key

# Real IDs that are hard for the key: a zero version beside a longer one
# (OLDAP-2.0, OLDAP-2.0.1), a letter after the version (LPPL-1.3a), digits
# inside the name (bzip2, 0BSD, X11), a "v" (FSL-1.1-ALv2), country codes
# (CC-BY-3.0-NL) and the deprecated "+" forms beside their successors.
ROWS = [
    Lic("0BSD", "BSD Zero Clause License"),
    Lic("Apache-1.0", "Apache License 1.0"),
    Lic("Apache-2.0", "Apache License 2.0"),
    Lic("bzip2-1.0.6", "bzip2 and libbzip2 License v1.0.6"),
    Lic("CC-BY-3.0", "Creative Commons Attribution 3.0 Unported"),
    Lic("CC-BY-3.0-NL", "Creative Commons Attribution 3.0 Netherlands"),
    Lic("FSL-1.1-ALv2", "Functional Source License, Version 1.1, ALv2"),
    Lic("GPL-2.0", "GNU General Public License v2.0 only", is_deprecated=True),
    Lic("GPL-2.0+", "GNU General Public License v2.0 or later", is_deprecated=True),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("LPPL-1.3a", "LaTeX Project Public License v1.3a"),
    Lic("LPPL-1.3c", "LaTeX Project Public License v1.3c"),
    Lic("OLDAP-2.0", "Open LDAP Public License v2.0"),
    Lic("OLDAP-2.0.1", "Open LDAP Public License v2.0.1"),
    Lic("Python-2.0", "Python License 2.0"),
    Lic("Python-2.0.1", "Python License 2.0.1"),
    Lic("Vim", "Vim License"),
    Lic("X11", "X11 License"),
    # Not real: two rows in use with one key, and a deprecated row with no
    # successor beside the row in use of its key.
    Lic("Twin-1", "Twin Two"),
    Lic("Twin-1.0", "Twin One"),
    Lic("Dup-1", "Dup New"),
    Lic("Dup-1.0", "Dup Old", is_deprecated=True),
]
SYNTHETIC = ("Twin-", "Dup-")
# Where a deprecated ID is redirected, as on the license_id= path.
SUCCESSOR = {"GPL-2.0": "GPL-2.0-only", "GPL-2.0+": "GPL-2.0-or-later"}

# The License List of the developer's cache, read only; absent on CI.
REAL_DB = Path.home() / ".local" / "share" / "licenseid" / "licenses.db"


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_version_key", ROWS):
        yield LicenseDatabase(path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Apache2", "apache 2"),
        ("apache 2", "apache 2"),
        ("Apache-2.0", "apache 2"),
        ("Apache-2.0.0", "apache 2"),
        ("Apache2.0", "apache 2"),
        ("Apache 2.0.", "apache 2"),
        ("  APACHE\t2.0\n", "apache 2"),
        ("GPLv3", "gpl 3"),
        ("GPL V3", "gpl 3"),
        ("GPL-2.0+", "gpl 2 or later"),
        ("GPL-2.0 +", "gpl 2 or later"),
        ("CC by 3 nl", "cc by 3 nl"),
        ("CC-BY-3.0-NL", "cc by 3 nl"),
        ("0BSD", "0 bsd"),
        ("LPPL-1.3c", "lppl 1 3 c"),
        # A "v" is a prefix only before a digit.
        ("Vim", "vim"),
        ("Vixie-Cron", "vixie cron"),
        ("GPLvx", "gplvx"),
        # Only a version whose every part after the major is 0 is folded,
        # and only a whole number.
        ("Python-2.0.1", "python 2 0 1"),
        ("LGPL-2.1", "lgpl 2 1"),
        ("X-1.2.0", "x 1 2 0"),
        ("X-10.0", "x 10"),
        ("X-2.00", "x 2 00"),
        ("X-2.0.0.1", "x 2 0 0 1"),
        ("X-2.0.0.0", "x 2 0 0 0"),
        ("X-.2.0", "x 2 0"),
        ("C++", "c or later or later"),
        ("", ""),
        ("...", ""),
    ],
)
def test_version_key(text: str, key: str) -> None:
    assert version_key(text) == key


@pytest.mark.parametrize(
    ("text", "license_id"),
    [
        ("Apache2", "Apache-2.0"),
        ("APACHE-2", "Apache-2.0"),
        ("Apache1", "Apache-1.0"),
        ("CC by 3 nl", "CC-BY-3.0-NL"),
        ("CC BY 3", "CC-BY-3.0"),
        ("GPLv2", "GPL-2.0-only"),
        ("GPL2+", "GPL-2.0-or-later"),
        ("GPL 2.0 +", "GPL-2.0-or-later"),
        ("OLDAP 2", "OLDAP-2.0"),
        ("OLDAP 2.0.1", "OLDAP-2.0.1"),
        ("Python 2.0.1", "Python-2.0.1"),
        ("LPPL 1.3c", "LPPL-1.3c"),
        ("FSL 1.1 AL 2", "FSL-1.1-ALv2"),
        ("x 11", "X11"),
        ("VIM", "Vim"),
        ("Dup 1", "Dup-1"),
        ("Dup-1.0", "Dup-1"),
        # No answer: no ID has the key, or two rows in use share it.
        ("Apache 2.0.1", None),
        ("Apache 2+", None),
        ("Apache 3", None),
        ("Apache", None),
        ("Python 2.1", None),
        ("OLDAP 2.1", None),
        ("LPPL 1.3", None),
        ("bzip2", None),
        ("BSD", None),
        ("CC BY", None),
        ("GPL", None),
        ("C++", None),
        ("2.0", None),
        ("Twin 1", None),
        ("", None),
    ],
)
def test_match_version_key(
    db: LicenseDatabase, text: str, license_id: str | None
) -> None:
    results = match_version_key(db, text)
    if license_id is None:
        assert not results
        return
    [match] = results
    assert (match["license_id"], match["method"], match["exact"]) == (
        license_id,
        "id",
        True,
    )
    assert match["score"] > 1.0


@pytest.mark.parametrize(
    "row", [r for r in ROWS if not r.license_id.startswith(SYNTHETIC)]
)
def test_every_id_is_found_by_its_own_spelling(db: LicenseDatabase, row: Lic) -> None:
    """Drift guard: the key of an ID finds that ID (or its successor), never
    a neighbour of it, spelled as is, without a trailing ".0" or with spaces
    for dashes."""
    lid = row.license_id
    expected = SUCCESSOR.get(lid, lid)
    for spelling in (lid, lid.removesuffix(".0"), lid.replace("-", " ")):
        assert [m["license_id"] for m in match_version_key(db, spelling)] == [
            expected
        ], spelling


@pytest.mark.parametrize(("text", "has_flags"), [("Apache2", True), ("GPL2", False)])
def test_a_redirected_id_leaves_its_flags_to_the_caller(
    db: LicenseDatabase, text: str, has_flags: bool
) -> None:
    """The flags of GPL-2.0 are not those of GPL-2.0-only: the matcher looks
    them up (see shorttext._id_hit)."""
    [match] = match_version_key(db, text)
    assert ("is_spdx" in match) is has_flags


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache2", ("Apache-2.0", "id", True)),
        ('{"license": "Apache2"}', ("Apache-2.0", "field", True)),
        ("GPL 2.0+", ("GPL-2.0-or-later", "id", True)),
        # A declared ID keeps its own path, not the key's.
        ("GPL-2.0", ("GPL-2.0-only", "id", True)),
        ("GPL-2.0+", ("GPL-2.0-or-later", "id", True)),
        # No key: the fuzzy name match answers, never as an exact ID.
        ("Apache 2+", ("Apache-2.0", "name", False)),
    ],
)
def test_match_answers_with_the_id(text: str, expected: tuple[str, str, bool]) -> None:
    """Through match(), with the flags of the answer, from text and from a
    manifest's license field."""
    for path in seeded_db("test_version_key_match", ROWS):
        results = AggregatedLicenseMatcher(path).match(text=text)
        top = results[0]
        assert (top["license_id"], top["method"], top["exact"]) == expected
        assert top["is_spdx"] is True


def test_a_plus_without_a_key_is_no_exact_answer() -> None:
    for path in seeded_db("test_version_key_cpp", ROWS):
        results = AggregatedLicenseMatcher(path).match(text="C++")
        assert not [r for r in results if r["exact"] or r["method"] == "id"]


@pytest.mark.skipif(not REAL_DB.is_file(), reason="no License List in the cache")
def test_no_two_ids_in_use_share_a_key() -> None:
    """Drift guard over a real License List: a new release that gives two
    IDs in use one key makes both unreachable by it. Read only."""
    with sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True) as conn:
        ids = [
            lid
            for (lid,) in conn.execute(
                "SELECT license_id FROM licenses WHERE NOT is_deprecated"
            )
        ]
    keys = Counter(version_key(lid) for lid in ids)
    assert ids
    assert not {lid for lid in ids if keys[version_key(lid)] > 1}


@pytest.mark.parametrize(
    "text",
    ["a1" * 50_000, "1.0" * 50_000, "v1" * 50_000, "1" * 100_000, "+" * 100_000],
    ids=["letter-digit", "zero-versions", "v-prefix", "digits", "plus"],
)
def test_the_key_regexes_do_not_backtrack(text: str) -> None:
    start = time.monotonic()
    version_key(text)
    assert time.monotonic() - start < 2.0
