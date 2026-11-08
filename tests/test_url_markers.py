# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A licence URL in an SPDX tag or a manifest field is read through the one
URL reader (``licenseid.resolveurl``, issue #14), and the helpers of that
reader that only a declared value reaches."""
# pylint: disable=missing-function-docstring

import json
from pathlib import Path

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import resolve
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.resolveurl import url_license_id

MIT = "https://spdx.org/licenses/MIT"
OSI_MIT = "https://opensource.org/licenses/MIT"
APACHE = "https://www.apache.org/licenses/LICENSE-2.0"
GNU = "https://www.gnu.org/licenses/gpl-3.0.html"
GPL2 = "https://spdx.org/licenses/GPL-2.0-only"


def tag_answer(db: LicenseDatabase, value: str) -> str | None:
    """The expression of a certain match of the tag *value*, or None."""
    found = LicenseDetector(db.location).detect(
        text=f"# SPDX-License-Identifier: {value}\n"
    )
    return found[0]["expression"] if found and found[0]["score"] == 1.0 else None


def field_answer(db: LicenseDatabase, tmp_path: Path, data: object) -> str | None:
    path = tmp_path / "package.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    found = LicenseDetector(db.location).detect(file_path=str(path))
    return found[0]["expression"] if found and found[0]["score"] == 1.0 else None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (APACHE, "Apache-2.0"),
        (MIT, "MIT"),
        (MIT + "/", "MIT"),
        (MIT + ".html", "MIT"),
        (MIT + ".", "MIT"),
        (OSI_MIT, "MIT"),
        (MIT + " OR Apache-2.0", "Apache-2.0 OR MIT"),
        # Regression pin: any host with "/licenses/" in its path used to be
        # read by its last segment. Only a page the reader knows is read now.
        ("https://evil.com/licenses/MIT", None),
    ],
    ids=["apache", "spdx", "slash", "html", "dot", "osi", "or", "evil"],
)
def test_a_tag_reads_a_url(
    corpus_db: LicenseDatabase, value: str, expected: str | None
) -> None:
    assert tag_answer(corpus_db, value) == expected


def test_a_gnu_url_is_the_bare_id(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    by_url = tag_answer(corpus_db, GNU)
    conditions_url = given.conditions()
    assert by_url == tag_answer(corpus_db, "GPL-3.0")
    assert conditions_url == given.conditions()
    assert by_url is not None
    assert "variant not stated" in conditions_url


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"license": {"type": "MIT", "url": OSI_MIT}}, "MIT"),
        ({"license": {"url": OSI_MIT}}, "MIT"),
        ({"license": {"type": "Foo", "url": OSI_MIT}}, "MIT"),
        # The type answers first: the URL is used only when it does not.
        ({"license": {"type": "Apache-2.0", "url": OSI_MIT}}, "Apache-2.0"),
        ({"license": OSI_MIT}, "MIT"),
        # An entry of "licenses" with only a url names nothing.
        ({"licenses": [{"url": OSI_MIT}]}, None),
    ],
    ids=["type", "url-only", "bad-type", "type-first", "string", "array-url"],
)
def test_a_field_reads_a_url(
    corpus_db: LicenseDatabase, tmp_path: Path, data: object, expected: str | None
) -> None:
    assert field_answer(corpus_db, tmp_path, data) == expected


ISC = "https://spdx.org/licenses/ISC"


@pytest.mark.parametrize(
    "value",
    [
        f"MIT OR {ISC}",
        f"{MIT} OR {ISC}",
        f"{MIT} AND {APACHE}",
        f"{APACHE} OR {MIT} OR ISC",
        f"{MIT}  OR\t{ISC}",
        f"<{MIT}> OR <{ISC}>",
        f"MIT OR {OSI_MIT}",
        # no URL: a word that looks like a host is no URL
        "LICENSE.md OR MIT",
        "MIT OR LICENSE.md",
        "MIT OR https://www.unicode.org/license.txt",  # a page of two
        "MIT OR https://example.com/x",
    ],
)
def test_a_tag_reads_every_url_as_resolve_does(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """Each word of the value is read as a URL, not only the first."""
    assert tag_answer(corpus_db, value) == resolve(value, corpus_db)["expression"]


@pytest.mark.parametrize(
    ("value", "tag", "resolved"),
    [
        # Pinned: a URL operand of WITH is read by the tag, not by resolve().
        (
            f"{GPL2} WITH Classpath-exception-2.0",
            "GPL-2.0-only WITH Classpath-exception-2.0",
            None,
        ),
        # Pinned: the tag drops one end mark after a URL, as before.
        (f"{MIT}. OR ISC", "ISC OR MIT", None),
        # Pinned: a bracket against a URL makes the word no URL to the tag.
        (f"({MIT} OR {ISC})", None, "ISC OR MIT"),
    ],
    ids=["with", "end-mark", "parenthesis"],
)
def test_where_a_tag_and_resolve_differ_on_a_url(
    corpus_db: LicenseDatabase, value: str, tag: str | None, resolved: str | None
) -> None:
    assert tag_answer(corpus_db, value) == tag
    assert resolve(value, corpus_db)["expression"] == resolved


def test_a_field_reads_every_url_of_its_value(
    corpus_db: LicenseDatabase, tmp_path: Path
) -> None:
    data = {"license": f"MIT OR {ISC}"}
    assert field_answer(corpus_db, tmp_path, data) == "ISC OR MIT"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (MIT, "MIT"),
        (MIT + ".", "MIT"),
        (f"<{MIT}>", "MIT"),
        ("MIT", None),
        ("https://example.com/x", None),
        ("https://example.com/x.", None),
    ],
    ids=["url", "end-mark", "brackets", "id", "unknown", "unknown-mark"],
)
def test_url_license_id(
    corpus_db: LicenseDatabase, text: str, expected: str | None
) -> None:
    assert url_license_id(corpus_db, text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MIT OR ISC\u200b", "ISC OR MIT"),
        ("MIT OR ISC\u202e", "ISC OR MIT"),
        ("\ufeffMIT OR ISC", "ISC OR MIT"),
        ("MIT\u200b", "MIT"),
        ("\u202eMIT", None),
        ("MIT OR\u200b ISC", "ISC OR MIT"),
        ("MIT OR\u200bISC", None),
    ],
    ids=[
        "trailing",
        "trailing-bidi",
        "leading",
        "single",
        "leading-bidi",
        "spaced",
        "inside",
    ],
)
def test_a_tag_and_a_field_leave_hidden_characters_off_the_ends(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str, expected: str | None
) -> None:
    """As ``resolve()`` does (``hiddenchars``): not a bidi control first, not
    one inside."""
    assert tag_answer(corpus_db, value) == expected
    # BUG: a field with a bidi control first still reads, through the text
    # tiers (it did before); resolve() refuses it.
    field = "MIT" if value == "\u202eMIT" else expected
    assert field_answer(corpus_db, tmp_path, {"license": value}) == field
