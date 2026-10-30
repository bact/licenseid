# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A text that is a "+" after ``-only`` or ``-or-later`` names no licence,
so ``detect`` answers none: not the near name a fuzzy match finds for it.

A database of four rows hid this: the near neighbours below are the ones
the 3.29.0 list gave (``GPL-2.0-only+`` answered LGPL-3.0-only at 0.755,
``GPL-2.0-or-later+`` SimPL-2.0 at 0.84)."""
# pylint: disable=missing-function-docstring

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import predicate_line
from matcher_db import Lic, seeded_db

from licenseid import match
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.identifiers import is_qualified_plus

# Each with a short text to search, as a real row has: the wrong answers
# came from Tiers 1 and 2, which a row with no text never reaches.
NAMES = {
    "MIT": "MIT License",
    "GPL-2.0-only": "GNU General Public License v2.0 only",
    "GPL-2.0-or-later": "GNU General Public License v2.0 or later",
    "LGPL-2.1-only": "GNU Lesser General Public License v2.1 only",
    "LGPL-2.1-or-later": "GNU Lesser General Public License v2.1 or later",
    "LGPL-3.0-only": "GNU Lesser General Public License v3.0 only",
    "LGPL-3.0-or-later": "GNU Lesser General Public License v3.0 or later",
    "AGPL-1.0-only": "Affero General Public License v1.0 only",
    "SimPL-2.0": "Simple Public License 2.0",
    "BUSL-1.1": "Business Source License 1.1",
}
ROWS = tuple(
    Lic(lic_id, name, search_text=f"{lic_id} {name}".lower())
    for lic_id, name in NAMES.items()
)
CP = "Classpath-exception-2.0"


@pytest.fixture(name="db_path")
def _db_path() -> Generator[str, None, None]:
    yield from seeded_db("test_qualified_plus", ROWS, exception_ids=(CP,))


def ids(db_path: str, text: str) -> list[str]:
    return [r["expression"] for r in LicenseDetector(db_path).detect(text=text)]


QUALIFIED_PLUS = [
    "GPL-2.0-only+",
    "GPL-2.0-or-later+",
    "LGPL-2.1-only+",
    "LGPL-3.0-or-later+",
    "gpl-2.0-ONLY+",
    " \tGPL-2.0-only+\n",
    "(GPL-2.0-only+)",
    "((LGPL-2.1-only+))",
    f"GPL-2.0-only+ WITH {CP}",
    "MIT OR GPL-2.0-only+",
    "GPL-2.0-or-later+ AND MIT",
    "(MIT AND (LGPL-2.1-only+ OR MIT))",
    "MIT OR " * 20 + "GPL-2.0-only+",  # over 30 words: Tier 1 never sees it
    "MIT OR " * 151 + "GPL-2.0-only+",  # too large to parse, not to read
    "Foo-only+",  # names nothing either way
    "GPL-2.0-only+ or later",  # no number before it: "or later" is OR later
]


@pytest.mark.parametrize("text", QUALIFIED_PLUS, ids=lambda v: ascii(v)[:40])
def test_a_plus_after_a_qualifier_answers_no_licence(db_path: str, text: str) -> None:
    assert is_qualified_plus(text)
    assert ids(db_path, text) == []


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("GPL-2.0+", ["GPL-2.0-or-later"]),  # an ID that states no qualifier
        ("GPL-2.0-only", ["GPL-2.0-only"]),
        ("GPL-2.0-only +", ["GPL-2.0-only"]),  # a detached "+" is no operator
        ("LicenseRef-x-only+", None),  # a LicenseRef takes no "+": no operator
        ("GPL-2.0-only+ licensed code", None),  # prose: matched as text
        ("MIT OR", None),  # dangling: no expression
        # BUG: a "+" that is no operator is dropped as punctuation, and the
        # answer is exact (as in 0.5.0; tech-debt roadmap, item 44).
        ("GPL-2.0-only++", ["GPL-2.0-only"]),
        ("GPL-2.0-only+,", ["GPL-2.0-only"]),
    ],
)
def test_what_is_not_a_qualified_plus_is_matched(
    db_path: str, text: str, answer: list[str] | None
) -> None:
    assert not is_qualified_plus(text)
    if answer is not None:
        assert ids(db_path, text)[:1] == answer


def test_no_entry_point_answers_a_near_name(db_path: str, tmp_path: Path) -> None:
    """Text, a tag, a manifest field and a file agree: no licence."""
    matcher = LicenseDetector(db_path)
    assert matcher.detect(text="SPDX-License-Identifier: GPL-2.0-only+") == []
    assert matcher.detect(text='{"license": "GPL-2.0-only+"}') == []
    path = tmp_path / "LICENSE"
    path.write_text("LGPL-2.1-only+\n", encoding="utf-8")
    assert matcher.detect(file_path=str(path)) == []
    assert match("GPL-2.0-only+", matcher.db)["category"] == "malformed"


@pytest.mark.parametrize("command", ["detect", "is-osi"])
def test_the_cli_answers_no_with_no_threshold_to_hide_behind(
    db_path: str, command: str
) -> None:
    """Text that names no licence is a "no" (exit 1), as for ``Foo``; only
    ``--id`` is a declaration, refused as a usage error (exit 2)."""
    args = ["--threshold", "0"] if command == "detect" else []
    result = CliRunner().invoke(cli, ["--db", db_path, command, *args, "GPL-2.0-only+"])
    assert result.exit_code == 1
    assert result.stdout == (
        "" if command == "detect" else predicate_line(command, "", False)
    )
