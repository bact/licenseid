# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""An ID written without its ".0" or its dashes ("Apache2", "GPLv3",
"Apache_2.0", "CC by 3 nl") is that ID (licenseid.versionkey.version_key)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import time
from collections.abc import Generator
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.shorttext import match_short_text, match_version_key
from licenseid.versionkey import MAX_KEY_INPUT, version_key

# Real IDs that are hard for the key: a zero version beside a longer one
# (OLDAP-2.0, OLDAP-2.0.1), a letter after the version (LPPL-1.3a), digits
# inside the name (bzip2, 0BSD, X11), a "v" (FSL-1.1-ALv2, Vim), country
# codes (CC-BY-3.0-NL) and the deprecated "+" forms beside their successors.
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
    Lic("MPL-2.0", "Mozilla Public License 2.0"),
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
NARROWED = "WARNING: match: variant not stated: {}; using {}\n"


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_version_key", ROWS):
        yield LicenseDatabase(path)


@pytest.fixture
def matcher() -> Generator[LicenseDetector, None, None]:
    for path in seeded_db("test_version_key_match", ROWS):
        yield LicenseDetector(path)


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
        # "_" and "." separate as "-" does.
        ("Apache_2.0", "apache 2"),
        ("Apache.2.0", "apache 2"),
        ("MPL_2_0", "mpl 2 0"),  # an underscore is no full stop
        ("GPLv3", "gpl 3"),
        ("GPL V3", "gpl 3"),
        ("GPL.v3", "gpl 3"),
        # A "v" is a prefix only before a digit.
        ("Vim", "vim"),
        ("Vixie-Cron", "vixie cron"),
        ("GPLvx", "gplvx"),
        ("CC by 3 nl", "cc by 3 nl"),
        ("CC-BY-3.0-NL", "cc by 3 nl"),
        ("0BSD", "0 bsd"),
        ("LPPL-1.3c", "lppl 1 3 c"),
        # Only a version whose every part after the major is 0 is folded,
        # and only a whole number.
        ("Python-2.0.1", "python 2 0 1"),
        ("LGPL-2.1", "lgpl 2 1"),
        ("X-1.2.0", "x 1 2 0"),
        ("X_1.2.0", "x 1 2 0"),
        ("X-10.0", "x 10"),
        ("X-2.00", "x 2 00"),
        ("X-2.0.0.1", "x 2 0 0 1"),
        ("X-2.0.0.0", "x 2 0 0 0"),
        # The "+" operator, as identifiers reads it: right after an ID.
        ("GPL-2.0+", "gpl 2 or later"),
        ("GPL2+", "gpl 2 or later"),
        ("GPL 2.0+", "gpl 2 or later"),
        ("GPL-2.0 +", "gpl 2"),  # apart from its ID
        ("C++", "c"),  # after a "+"
        ("GPL+2", "gpl 2"),  # inside a word
        ("LicenseRef-x+", "licenseref x"),  # a LicenseRef takes none
        ("A WITH B+", "a with b"),  # nor an exception
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
        ("Apache_2.0", "Apache-2.0"),
        ("apache.2.0", "Apache-2.0"),
        ("Apache1", "Apache-1.0"),
        ("MPL_2.0", "MPL-2.0"),
        ("CC by 3 nl", "CC-BY-3.0-NL"),
        ("CC BY 3", "CC-BY-3.0"),
        ("GPL2+", "GPL-2.0-or-later"),
        ("GPLv2-only", "GPL-2.0-only"),
        ("OLDAP 2", "OLDAP-2.0"),
        ("OLDAP 2.0.1", "OLDAP-2.0.1"),
        ("Python 2.0.1", "Python-2.0.1"),
        ("LPPL 1.3c", "LPPL-1.3c"),
        ("FSL 1.1 AL 2", "FSL-1.1-ALv2"),
        ("x 11", "X11"),
        ("VIM", "Vim"),
        ("Dup 1", "Dup-1"),
        ("Dup-1.0", "Dup-1"),
        # A deprecated ID written as is: -only by the License List's own
        # definition, not a guess.
        ("GPL-2.0", "GPL-2.0-only"),
        ("gpl-2.0", "GPL-2.0-only"),
        # No answer: no ID has the key, or two rows in use share it.
        ("Apache 2.0.1", None),
        ("Apache_2_0", None),
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
    db: LicenseDatabase,
    capsys: pytest.CaptureFixture[str],
    text: str,
    license_id: str | None,
) -> None:
    results = match_version_key(db, text)
    assert [(m["license_id"], m["method"], m["exact"]) for m in results] == (
        [] if license_id is None else [(license_id, "id", True)]
    )
    assert all(m["score"] > 1.0 for m in results)
    assert not capsys.readouterr().err


@pytest.mark.parametrize(
    ("text", "license_id"),
    [
        ("GPL2", "GPL-2.0-only"),
        ("GPLv2", "GPL-2.0-only"),
        ("GPL_2.0", "GPL-2.0-only"),
        ("GPL-2.0 +", "GPL-2.0-only"),  # a "+" apart from its ID is no grant
        (" gpl  2\n", "GPL-2.0-only"),
    ],
)
def test_a_family_alone_is_narrowed_to_only_with_a_warning(
    db: LicenseDatabase,
    capsys: pytest.CaptureFixture[str],
    text: str,
    license_id: str,
) -> None:
    """Neither -only nor -or-later stated: the narrower grant is taken, not
    as exact, and said on standard error."""
    [match] = match_version_key(db, text)
    assert (match["license_id"], match["exact"], match["score"]) == (
        license_id,
        False,
        1.02,
    )
    detail = " ".join(text.split())
    assert capsys.readouterr().err == NARROWED.format(detail, license_id)


@pytest.mark.parametrize(
    "row", [r for r in ROWS if not r.license_id.startswith(SYNTHETIC)]
)
def test_every_id_is_found_by_its_own_spelling(db: LicenseDatabase, row: Lic) -> None:
    """Drift guard: the key of an ID finds that ID (or its successor), never
    a neighbour of it: as is, without a trailing ".0", and with spaces or
    underscores for dashes."""
    lid = row.license_id
    expected = SUCCESSOR.get(lid, lid)
    spellings = (
        lid,
        lid.removesuffix(".0"),
        lid.replace("-", " "),
        lid.replace("-", "_"),
    )
    for spelling in spellings:
        found = match_version_key(db, spelling)
        assert [m["license_id"] for m in found] == [expected], spelling


@pytest.mark.parametrize(("text", "has_flags"), [("Apache2", True), ("GPL2", False)])
def test_a_redirected_id_leaves_its_flags_to_the_caller(
    db: LicenseDatabase, text: str, has_flags: bool
) -> None:
    """The flags of GPL-2.0 are not those of GPL-2.0-only: the matcher looks
    them up (see shorttext._id_hit)."""
    [match] = match_version_key(db, text)
    assert ("is_spdx" in match) is has_flags


def test_a_row_lost_between_the_two_reads_is_no_match(db: LicenseDatabase) -> None:
    """The cached rows can be rebuilt between loose_id and the full row
    (another process's ``update``): the answer is no match, not an error."""
    assert match_version_key(db, "Apache2")
    with mock.patch("licenseid.shorttext._full_row", autospec=True, return_value=None):
        assert not match_version_key(db, "Apache2")


@pytest.mark.parametrize(
    ("padding", "found"),
    [(MAX_KEY_INPUT - len("Apache2"), True), (MAX_KEY_INPUT - len("Apache"), False)],
    ids=["at-the-limit", "past-the-limit"],
)
def test_a_long_input_is_no_loose_id(
    db: LicenseDatabase, padding: int, found: bool
) -> None:
    """A long input is no ID, and is not normalised a second time; white
    space around it does not count."""
    text = "Apache" + " " * padding + "2"
    with mock.patch("licenseid.versionkey.version_key", wraps=version_key) as key:
        assert bool(match_version_key(db, f"\n {text} \n")) is found
    assert key.called is found


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache2", ("Apache-2.0", "id", True)),
        ('{"license": "Apache_2.0"}', ("Apache-2.0", "field", True)),
        ('{"license": "GPLv2"}', ("GPL-2.0-only", "field", False)),
        ("GPL 2.0+", ("GPL-2.0-or-later", "id", True)),
        ("GPL2", ("GPL-2.0-only", "id", False)),
        # A declared ID keeps its own path, not the key's.
        ("GPL-2.0", ("GPL-2.0-only", "id", True)),
        ("GPL-2.0+", ("GPL-2.0-or-later", "id", True)),
        # No key: the fuzzy name match answers, never as an exact ID.
        ("Apache 2+", ("Apache-2.0", "name", False)),
    ],
)
def test_match_answers_with_the_id(
    matcher: LicenseDetector, text: str, expected: tuple[str, str, bool]
) -> None:
    """Through detect(), with the flags of the answer, from text and from a
    manifest's license field."""
    top = matcher.detect(text=text)[0]
    assert (top["license_id"], top["method"], top["exact"]) == expected
    assert top["is_spdx"] is True


def test_a_plus_without_a_key_is_no_exact_answer(
    matcher: LicenseDetector,
) -> None:
    results = matcher.detect(text="C++")
    assert not [r for r in results if r["exact"] or r["method"] == "id"]


@pytest.mark.parametrize(
    ("norm_input", "text", "expected"),
    [
        ("apache 2 0", "Apache.2.0", "Apache-2.0"),
        ("apache2", None, "Apache-2.0"),  # no raw text: the normalised one
        ("apache 2 0", None, "Apache-2.0"),  # the exact ID match after it
    ],
)
def test_match_short_text_reads_the_key_of_the_raw_text(
    db: LicenseDatabase, norm_input: str, text: str | None, expected: str
) -> None:
    [match] = match_short_text(db, norm_input, text)
    assert (match["license_id"], match["exact"]) == (expected, True)


def test_mixed_content_gives_its_sections_raw_to_tier_0(
    matcher: LicenseDetector,
) -> None:
    """Every Tier 0 caller hands over the raw text the key reads. A section
    holds its "licens" word, so it is never a loose ID itself."""
    # pylint: disable=protected-access
    with mock.patch.object(
        matcher, "_match_short_text", wraps=matcher._match_short_text
    ) as tier0:
        matcher._match_mixed_content({}, "Licensed Apache.2.0")
    tier0.assert_called_once_with("licensed apache 2 0", "Licensed Apache.2.0")


@pytest.mark.parametrize(
    "text",
    ["a1" * 50_000, "1.0" * 50_000, ".1.0" * 50_000, "v1" * 50_000]
    + ["1" * 100_000, "+" * 100_000, "a+ " * 50_000, "_1" * 50_000],
    ids=["letter-digit", "zero-versions", "dot-versions", "v-prefix"]
    + ["digits", "plus", "plus-operators", "underscores"],
)
def test_the_key_regexes_do_not_backtrack(text: str) -> None:
    start = time.monotonic()
    version_key(text)
    assert time.monotonic() - start < 2.0
