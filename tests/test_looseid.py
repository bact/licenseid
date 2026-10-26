# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules around a loose ID (licenseid.looseid): a grant after it, a WITH
after it, the -only guess on every path, the warning's DETAIL, the key index,
and the key over a whole License List."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import json
import sqlite3
import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.identifiers import normalize_identifier
from licenseid.looseid import MAX_KEY_INPUT, loose_id, loose_with, shown, version_key
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.shorttext import match_short_text

# The "+" row first: the exact-ID match must not depend on row order.
ROWS = [
    Lic("Apache-2.0", "Apache License 2.0"),
    Lic("GPL-2.0+", "GNU General Public License v2.0 or later", is_deprecated=True),
    Lic("GPL-2.0", "GNU General Public License v2.0 only", is_deprecated=True),
    Lic("GPL-2.0-only", "GNU General Public License v2.0 only"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    Lic("LGPL-2.1", "GNU Lesser General Public License v2.1 only", is_deprecated=True),
    Lic("LGPL-2.1-only", "GNU Lesser General Public License v2.1 only"),
    Lic("LGPL-2.1-or-later", "GNU Lesser General Public License v2.1 or later"),
    Lic("MIT", "MIT License"),
    Lic("GPL-2.0-with-classpath-exception", "GPL-2.0 w/Classpath", is_deprecated=True),
]
EXCEPTIONS = ("Classpath-exception-2.0", "LLVM-exception")
NARROWED = "WARNING: match: variant not stated: {}; using {}\n"

SNAPSHOT = Path(__file__).parent / "fixtures" / "license-list" / "spdx-license-ids.json"
# The License List of the developer's cache, read only; absent on CI.
REAL_DB = Path.home() / ".local" / "share" / "licenseid" / "licenses.db"


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_looseid", ROWS, EXCEPTIONS):
        yield LicenseDatabase(path)


@pytest.fixture
def matcher() -> Generator[AggregatedLicenseMatcher, None, None]:
    for path in seeded_db("test_looseid_match", ROWS, EXCEPTIONS):
        yield AggregatedLicenseMatcher(path)


@pytest.mark.parametrize(
    ("text", "license_id"),
    [
        ("GPLv2 or any later version", "GPL-2.0-or-later"),
        ("GPL2 or later", "GPL-2.0-or-later"),
        ("GPL 2 or newer", "GPL-2.0-or-later"),
        ("GPL-2.0 or any later version.", "GPL-2.0-or-later"),
        ("GPLv2 or any later version of the License", "GPL-2.0-or-later"),
        ("LGPL v2.1 or (at your option) any later version.", "LGPL-2.1-or-later"),
        # "or later" starts the phrase at the version: the whole version is
        # the ID's, not cut at its last part.
        ("LGPL v2.1 or later of the License", "LGPL-2.1-or-later"),
        ("LGPL 2.1, or later", "LGPL-2.1-or-later"),
        ("GPLv2.1 or later", None),  # no GPL-2.1, not GPL-2.0
        # The grant is not dropped in silence: no answer.
        ("Apache2 or any later version", None),
        ("MIT or later", None),
        ("GPL-2.0-only or any later version", None),
        # Not a grant that ends the text, or no grant at all.
        ("GPLv2 not any later version", None),
        ("GPLv2 or any later version, and MIT", None),
        ("GPLv2 or any later version of MIT", None),
        ("or any later version", None),
        ("sooner or later", None),
    ],
)
def test_a_grant_after_a_loose_id(
    db: LicenseDatabase,
    capsys: pytest.CaptureFixture[str],
    text: str,
    license_id: str | None,
) -> None:
    found = loose_id(db, text)
    assert (None if found is None else found[1]) == license_id
    assert not capsys.readouterr().err


@pytest.mark.parametrize(
    ("raw", "license_id", "warned"),
    [
        ("GPL 2 0", "GPL-2.0-only", True),  # spaces for the dots: a guess
        ("gpl  2 0", "GPL-2.0-only", True),
        ("GPL 2 0 +", "GPL-2.0-only", True),  # a "+" apart is no operator
        ("GPL 2.0", "GPL-2.0-only", True),  # the key's path
        ("GPL-2.0", "GPL-2.0-only", False),  # the deprecated ID as is
        ("gpl-2.0", "GPL-2.0-only", False),
        (" GPL-2.0 \n", "GPL-2.0-only", False),
    ],
)
def test_every_path_narrows_alike(
    db: LicenseDatabase,
    capsys: pytest.CaptureFixture[str],
    raw: str,
    license_id: str,
    warned: bool,
) -> None:
    """The key and the exact-ID match treat a family alone the same way,
    whatever the row order: -only, not exact, said."""
    [match] = match_short_text(db, "gpl 2 0", raw)
    assert (match["license_id"], match["exact"]) == (license_id, not warned)
    expected = NARROWED.format(" ".join(raw.split()), license_id) if warned else ""
    assert capsys.readouterr().err == expected


def test_the_exact_id_match_keeps_a_plus_operator(db: LicenseDatabase) -> None:
    """With the operator, the normalised ID of GPL-2.0+ answers or-later."""
    [match] = match_short_text(db, "gpl 2 0", "GPL-2-0+")
    assert match["license_id"] == "GPL-2.0-or-later"


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("GPL;2", "GPL?2"),  # ";" starts the ACTION
        ("GPL2\x1b[2J", "GPL2?[2J"),  # no terminal control
        ("GPL2\x07\x9b", "GPL2??"),
        ("\u200bGPL2", "?GPL2"),  # nor an invisible format character
        (" GPL\t 2\n", "GPL 2"),  # one line
        ("GPL: 2", "GPL: 2"),  # a DETAIL may hold a ":"
    ],
)
def test_the_warning_detail_is_one_printable_line(text: str, detail: str) -> None:
    assert shown(text) == detail


@pytest.mark.parametrize(
    ("text", "expected", "warned"),
    [
        (
            "GPL2 WITH Classpath-exception-2.0",
            ("GPL-2.0-only WITH Classpath-exception-2.0", False),
            True,
        ),
        (
            "Apache2 WITH LLVM-exception",
            ("Apache-2.0 WITH LLVM-exception", True),
            False,
        ),
        (
            "apache 2 with LLVM-exception",
            ("Apache-2.0 WITH LLVM-exception", True),
            False,
        ),
        (
            "GPLv2+ WITH Classpath-exception-2.0",
            ("GPL-2.0-or-later WITH Classpath-exception-2.0", True),
            False,
        ),
        # No answer, and no warning for it: an unknown exception, an
        # unknown license, two WITHs, or a compound expression, which text
        # never declares (the CLI's rule for `Apache-2.0 OR MIT`).
        ("GPL2 WITH Bogus-exception", None, False),
        ("Bogus2 WITH LLVM-exception", None, False),
        ("Apache2 WITH LLVM-exception WITH LLVM-exception", None, False),
        ("Apache2 OR MIT", None, False),
        ("Apache2 AND MIT", None, False),
        # Brackets around the whole are no part of it, at any depth.
        (
            "(GPL2 WITH Classpath-exception-2.0)",
            ("GPL-2.0-only WITH Classpath-exception-2.0", False),
            True,
        ),
        (
            "((Apache2 WITH LLVM-exception))",
            ("Apache-2.0 WITH LLVM-exception", True),
            False,
        ),
        (
            "( Apache2 WITH LLVM-exception )",
            ("Apache-2.0 WITH LLVM-exception", True),
            False,
        ),
    ],
)
def test_a_loose_license_with_an_exception(
    matcher: AggregatedLicenseMatcher,
    capsys: pytest.CaptureFixture[str],
    text: str,
    expected: tuple[str, bool] | None,
    warned: bool,
) -> None:
    results = matcher.match(text=text)
    assert ((results[0]["license_id"], results[0]["exact"]) if results else None) == (
        expected
    )
    err = capsys.readouterr().err
    assert ("WARNING: match: variant not stated: GPL2;" in err) is warned


@pytest.mark.parametrize(
    "text",
    [
        "GPL2 WITH",
        "WITH LLVM-exception",
        # The license carries an exception already.
        "GPL-2.0-with-classpath-exception WITH LLVM-exception",
        # Any other bracket: unbalanced, around the license alone (WITH takes
        # an ID), around the exception, or two pairs side by side.
        "(Apache2 WITH LLVM-exception",
        "Apache2 WITH LLVM-exception)",
        "(Apache2) WITH LLVM-exception",
        "Apache2 WITH (LLVM-exception)",
        "(Apache2) WITH (LLVM-exception)",
        ")Apache2 WITH LLVM-exception(",
    ],
)
def test_no_loose_with_expression(db: LicenseDatabase, text: str) -> None:
    assert loose_with(db, text) is None


def test_a_manifest_value_read_as_a_guess_is_still_a_field(
    matcher: AggregatedLicenseMatcher,
) -> None:
    [result] = matcher.match(text='{"license": "GPLv2"}')
    assert (result["license_id"], result["method"], result["exact"]) == (
        "GPL-2.0-only",
        "field",
        False,
    )


def test_the_key_index_is_built_once_per_table_read(db: LicenseDatabase) -> None:
    key = mock.Mock(wraps=version_key)
    first = db.get_names_by_key(key)
    assert db.get_names_by_key(key) is first
    assert key.call_count == len(ROWS)
    # Another key rebuilds it; a rewritten table drops it.
    assert db.get_names_by_key(str.lower) is not first
    db.get_names_by_key(key)
    db._tables.clear()  # pylint: disable=protected-access
    db.get_names_by_key(key)
    assert key.call_count == 3 * len(ROWS)


def _snapshot_rows() -> list[Lic]:
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return [
        Lic(lid, name, is_deprecated=dep, superseded_by=successor)
        for lid, name, dep, successor in data["licenses"]
    ]


def _cache_rows() -> list[Lic]:
    if not REAL_DB.is_file():
        pytest.skip("no License List in the cache")
    with sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True) as conn:
        return [
            Lic(lid, name or "", is_deprecated=bool(dep), superseded_by=successor)
            for lid, name, dep, successor in conn.execute(
                "SELECT license_id, name, is_deprecated, superseded_by FROM licenses"
            )
        ]


@pytest.mark.parametrize(
    "source", [_snapshot_rows, _cache_rows], ids=["snapshot", "cache"]
)
def test_a_license_list_keeps_the_key_unambiguous(source: object) -> None:
    """Drift guard over a whole License List: the snapshot in
    tests/fixtures/license-list (SPDX 3.29.0, on every run) and the
    developer's cache (read only, when there is one). No key may name two
    IDs in use (neither is reachable by it), a deprecated ID and a row in
    use other than its successor as the database resolves it (the row in
    use would answer for it), or a license's name and another license's ID
    (the key runs before the exact name match). Every ID fits the limit."""
    rows = source()  # type: ignore[operator]
    for path in seeded_db("test_looseid_list", rows):
        lists = LicenseDatabase(path)
        index = lists.get_names_by_key(version_key)
        live = {
            k: [r["license_id"] for r in v if not r["is_deprecated"]]
            for k, v in index.items()
        }
        assert rows
        assert not [ids for ids in live.values() if len(ids) > 1]
        assert not [
            (row.license_id, live[key])
            for row in rows
            if row.is_deprecated
            and live[key := version_key(row.license_id)]
            and live[key] != [normalize_identifier(row.license_id, lists)]
        ]
        assert not [
            (row.license_id, row.name)
            for row in rows
            if [
                r["license_id"]
                for r in index.get(version_key(row.name), [])
                if r["license_id"] != row.license_id
            ]
        ]
        assert max(len(row.license_id) for row in rows) <= MAX_KEY_INPUT


@pytest.mark.parametrize(
    ("text", "answered"),
    [
        ("(" * 100_000 + "Apache2 WITH LLVM-exception" + ")" * 100_000, True),
        ("(" * 100_000 + "Apache2 WITH LLVM-exception" + ")" * 99_999, False),
    ],
    ids=["balanced", "unbalanced"],
)
def test_deep_brackets_are_read_in_one_pass(
    db: LicenseDatabase, text: str, answered: bool
) -> None:
    start = time.monotonic()
    found = loose_with(db, text)
    assert time.monotonic() - start < 2.0
    assert (found is not None) is answered
