# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The 0.7.0 resolver corpus: a database of the whole 3.29.0 List, the
fixtures that pin what ``resolve()`` 0.6.0 answers, and the guard that says
which answers a change moved.

Import as ``from resolver_corpus import ...`` (tests have no ``__init__.py``).
The fixtures are ``fixtures/resolver_parity.tsv`` and
``fixtures/pypi_values_2026-10*.tsv`` (see ``fixtures/README.md``).

``EXPECTED_CHANGES`` is the one place that lists the values whose answer a
later rule is allowed to move.
"""

import json
import sqlite3
from collections.abc import Callable, Generator, Iterable
from pathlib import Path

from licenseid import LicenseDatabase, resolve
from licenseid.normalize import normalize_text
from tools.pypi_licence_sample.answer import (
    Answer,
    answer_from_row,
    answer_of,
    escape_field,
    unescape_field,
)

FIXTURES = Path(__file__).parent / "fixtures"
LICENSE_LIST = FIXTURES / "license-list" / "spdx-license-ids.json"
EXCEPTION_LIST = FIXTURES / "license-list" / "spdx-exception-ids.json"
LICENSE_TEXTS = FIXTURES / "license-text-long"
PARITY_FILE = FIXTURES / "resolver_parity.tsv"
SAMPLE_GLOB = "pypi_values_2026-10*.tsv"

#: Licences that get a search text: the near neighbours of the corpus values.
#: MPL-2.0 itself has no long-text fixture; its two neighbours stand in. A test
#: that expects "no licence" on this database is then not trivially
#: true (Tiers 1 and 2 have something to retrieve).
NEIGHBOURS = (
    "0BSD",
    "Apache-1.1",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "ISC",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MIT",
    "MPL-1.1",
    "MPL-2.0-no-copyleft-exception",
    "Unlicense",
    "Zlib",
)

#: The values whose answer a rule may move, each with the answer it must give
#: and the reason: ``{value: (answer, reason)}``. A later rule pull request
#: adds every value it changes here, and no other; the guard fails on a value
#: that moves without being listed, on a listed value that does not move, and
#: on a listed value that answers anything but the listed answer. Before
#: T4b it was empty: 0.6.0's answers are the fixtures'.
EXPECTED_CHANGES: dict[str, tuple[Answer, str]] = {
    "MIT\udcff": (
        Answer(None, "unresolved", (), (), (), "none", True),
        "G1 (T4b): a lone surrogate is refused before any rule reads the"
        " value (reason `lone surrogate` from T6); 0.6.0 dropped it as a"
        " separator",
    ),
}

_INSERT_LICENSE = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved,"
    " is_fsf_libre, is_deprecated, superseded_by) VALUES (?, ?, 1, 0, 0, ?, ?)"
)
_INSERT_INDEX = "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)"
_INSERT_EXCEPTION = (
    "INSERT INTO exceptions (exception_id, name, is_deprecated, superseded_by)"
    " VALUES (?, ?, ?, ?)"
)
_SET_METADATA = "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)"


def list_meta(path: Path) -> tuple[str, str]:
    """``(license_list_version, release_date)`` of a List fixture."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data["license_list_version"]), str(data["release_date"])


def list_rows(path: Path, key: str) -> list[list[object]]:
    """The rows under *key* of a List fixture."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[list[object]] = data[key]
    return rows


def _search_text(license_id: str) -> str:
    """The normalised text of a licence, from the long-text fixtures."""
    text_file = LICENSE_TEXTS / f"{license_id}.json"
    data = json.loads(text_file.read_text(encoding="utf-8"))
    return normalize_text(str(data["license_text"]))


def corpus_db_path(
    prefix: str, make_path: Callable[[str], tuple[str, sqlite3.Connection]]
) -> Generator[str, None, None]:
    """Yield the path of an in-memory database that holds every licence and
    exception of the List fixtures (ids, names, deprecation, successors, the
    version and release date) and the text of the :data:`NEIGHBOURS`.
    *make_path* is ``conftest.make_memory_db_path``; its keep-alive connection
    is closed after."""
    version, release_date = list_meta(LICENSE_LIST)
    db_path, keep_alive = make_path(prefix)
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.executemany(
            _INSERT_LICENSE,
            [
                (row[0], row[1], row[2], row[3])
                for row in list_rows(LICENSE_LIST, "licenses")
            ],
        )
        conn.executemany(
            _INSERT_EXCEPTION,
            list_rows(EXCEPTION_LIST, "exceptions"),
        )
        conn.executemany(
            _INSERT_INDEX, [(lid, _search_text(lid)) for lid in NEIGHBOURS]
        )
        conn.executemany(
            _SET_METADATA,
            [
                ("license_list_version", version),
                ("release_date", release_date),
                ("last_update_datetime", "2026-10-28T00:00:00+00:00"),
            ],
        )
    yield db_path
    keep_alive.close()


# --- fixture files ---------------------------------------------------------


def _split(path: Path) -> tuple[list[str], list[str]]:
    """``(comment lines, lines from the header row on)`` of a TSV fixture. Only
    the lines before the header row are comments: a value may start with
    ``#``."""
    lines = [line for line in path.read_text(encoding="utf-8").split("\n") if line]
    top = 0
    while top < len(lines) and lines[top].startswith("#"):
        top += 1
    return lines[:top], lines[top:]


def read_comments(path: Path) -> list[str]:
    """The comment lines at the top of a TSV fixture."""
    return _split(path)[0]


def read_rows(path: Path) -> list[dict[str, str]]:
    """The rows of a TSV fixture, by column name. Fields are not stripped: a
    value may start or end with white space."""
    _, lines = _split(path)
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:]]


def sample_files() -> list[Path]:
    """The PyPI sample files, in name order."""
    return sorted(FIXTURES.glob(SAMPLE_GLOB))


def parity_rows() -> list[dict[str, str]]:
    """The parity corpus."""
    return read_rows(PARITY_FILE)


def sample_rows() -> list[dict[str, str]]:
    """Every row of the PyPI sample files."""
    return [row for path in sample_files() for row in read_rows(path)]


def pinned(row: dict[str, str]) -> Answer:
    """The 0.6.0 answer a fixture row records."""
    return answer_from_row(row)


def changed_answers(
    db: LicenseDatabase,
    rows: Iterable[dict[str, str]] | None = None,
) -> dict[str, tuple[Answer, Answer]]:
    """The values whose answer differs from the pinned one, over the parity
    corpus and the PyPI sample (or *rows*): ``{value: (pinned, current)}``."""
    if rows is None:
        rows = [*parity_rows(), *sample_rows()]
    changed: dict[str, tuple[Answer, Answer]] = {}
    for row in rows:
        value = unescape_field(row["value"])
        old, new = pinned(row), answer_of(value, resolve(value, db))
        if old != new:
            changed[value] = (old, new)
    return changed


def changes_report(
    changed: dict[str, tuple[Answer, Answer]],
    expected: dict[str, tuple[Answer, str]] | None = None,
) -> str:
    """Why *changed* is not the expected set, one value per line with the old
    and the new answer; empty when every changed value is listed in
    *expected* (default :data:`EXPECTED_CHANGES`) with the answer it now
    gives, and every listed value changed."""
    if expected is None:
        expected = EXPECTED_CHANGES
    lines = []
    for value, (old, new) in changed.items():
        name = escape_field(value)
        if value not in expected:
            lines.append(f"changed, not in EXPECTED_CHANGES: {name!r}: {old} -> {new}")
        elif new != expected[value][0]:
            lines.append(
                f"in EXPECTED_CHANGES, wrong answer: {name!r}: got {new},"
                f" expected {expected[value][0]}"
            )
    lines += [
        f"in EXPECTED_CHANGES, answer unchanged: {escape_field(value)!r} ({why})"
        for value, (_, why) in expected.items()
        if value not in changed
    ]
    return "\n".join(lines)
