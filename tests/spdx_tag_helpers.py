# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shared database and entry points for the SPDX tag tests.

Plain helpers, not fixtures: a fixture imported into a test module and then
used as an argument trips ruff F811.
"""

from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

from click.testing import CliRunner
from db_variants import MIT_TEXT
from matcher_db import PROSE, Lic, seeded_db

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher

LICENSES = [
    # MIT carries its text, so the CLI's text fallback has something to find.
    Lic("MIT", "MIT License", True, True, True, False, None, MIT_TEXT),
    # A name that starts with another row's ID.
    Lic("MIT-0", "MIT No Attribution", True, True, True),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),
    Lic("BSD-3-Clause", "BSD 3-Clause", True, True, True),
    # A deprecated ID shares its name with the ID that replaced it.
    Lic("GPL-2.0", "GNU GPL v2.0 only", True, True, True, True, None),
    Lic("GPL-2.0-only", "GNU GPL v2.0 only", True, True, True),
    Lic("GPL-2.0-or-later", "GNU GPL v2.0 or later", True, True, True),
    Lic("LGPL-2.1-only", "GNU LGPL v2.1 only", True, True, True),
    Lic("LGPL-2.1-or-later", "GNU LGPL v2.1 or later", True, True, True),
    Lic("MPL-1.1", "Mozilla Public License 1.1", True, True, True),
    # A license whose name is its own ID, so the name lookup can shadow it.
    Lic("Artistic-1.0", "Artistic-1.0", True, True, False),
    Lic("BSD-4-Clause", "BSD 4-Clause", True, False, True),
]
EXCEPTIONS = ["Classpath-exception-2.0"]


def tag_db(prefix: str) -> Generator[str, None, None]:
    """The database every SPDX tag test runs against."""
    yield from seeded_db(prefix, LICENSES, exception_ids=EXCEPTIONS)


class Answers(NamedTuple):
    """One file's answer from each entry point. The API's match counts only at
    the score (0.85) the CLI and the predicates use: a weaker top result is
    not an answer."""

    api_match: str | None
    api_is_spdx: bool
    cli_match: str | None
    cli_is_spdx: bool


def source_with(tag: str) -> str:
    """A source file whose only license evidence is *tag*."""
    return f"/*\n * SPDX-License-Identifier: {tag}\n{PROSE} */\n"


def cli_match_id(db: str, *args: str) -> str | None:
    """The top LICENSE_ID the CLI's match prints, or None when it finds none."""
    result = CliRunner().invoke(cli, ["--db", db, "match", *args])
    if result.exit_code != 0:
        return None
    first_line = result.stdout.splitlines()[0]  # an ID can hold spaces
    return first_line.removeprefix("LICENSE_ID=").rsplit(" SIMILARITY=")[0]


def answers(db: str, tag: str, tmp_path: Path) -> Answers:
    """What every entry point makes of a file carrying *tag*."""
    matcher = AggregatedLicenseMatcher(db)
    text = source_with(tag)
    results = matcher.match(text=text)
    path = tmp_path / "source.c"
    path.write_text(text, encoding="utf-8")
    is_spdx = CliRunner().invoke(cli, ["--db", db, "is-spdx", str(path)])
    return Answers(
        results[0]["license_id"] if results and results[0]["score"] >= 0.85 else None,
        matcher.is_spdx(text=text),
        cli_match_id(db, str(path)),
        is_spdx.exit_code == 0,
    )
