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

from seed_sql import INSERT_EXCEPTION, INSERT_INDEX, INSERT_LICENSE, SET_METADATA

from licenseid import LicenseDatabase, resolve
from licenseid.normalize import normalize_text
from licenseid.resolvertypes import Source
from tools.pypi_licence_sample.answer import (
    Answer,
    answer_diff,
    answer_from_row,
    answer_of,
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

#: The answer to a value that names nothing: no expression, nothing taken.
UNRESOLVED = Answer(
    expression=None,
    category="unresolved",
    candidates=(),
    steps=(),
    step_targets=(),
    expansions=(),
    expansion_targets=(),
    trust="none",
    input_same=True,
    reason=None,
)


def refused(reason: str, stopped: str | None = None) -> Answer:
    """The answer to a value the resolver refuses: nothing resolved, the
    *reason* given and, for the drop guard, one ``drop`` step that did not
    apply and *stopped* the reading of that licence."""
    return UNRESOLVED._replace(
        steps=() if stopped is None else ("drop!",),
        step_targets=() if stopped is None else (stopped,),
        reason=reason,
    )


_DROP = (
    "T6 (dropguard, F6): the {char} is the author's doubt or a corruption;"
    " 0.6.0 dropped it and answered {licence} (`separator`)"
)
_CONTROL = (
    "T6: refused as before (a control or format character is no separator);"
    " the answer now says why"
)

#: The values whose answer a rule may move, each with the answer it must give
#: and the reason: ``{value: (answer, reason)}``. A later rule pull request
#: adds every value it changes here, and no other; the guard fails on a value
#: that moves without being listed, on a listed value that does not move, and
#: on a listed value that answers anything but the listed answer. Before
#: T4b it was empty: 0.6.0's answers are the fixtures'.
EXPECTED_CHANGES: dict[str, tuple[Answer, str]] = {
    "MIT\udcff": (
        refused("lone surrogate"),
        (
            "G1 (T4b): a lone surrogate is refused before any rule reads the"
            " value; 0.6.0 dropped it as a separator. T6 gives the reason"
        ),
    ),
    "MIT\x00": (refused("control or format character: U+0000"), _CONTROL),
    "MIT\u200b": (refused("control or format character: U+200B"), _CONTROL),
    "\u202eMIT": (refused("control or format character: U+202E"), _CONTROL),
    "Apache 2.0?": (
        refused("character dropped: U+003F", "Apache-2.0"),
        _DROP.format(char="question mark", licence="Apache-2.0"),
    ),
    "Apache 2.0!": (
        refused("character dropped: U+0021", "Apache-2.0"),
        _DROP.format(char="exclamation mark", licence="Apache-2.0"),
    ),
    "MIT*": (
        refused("character dropped: U+002A", "MIT"),
        _DROP.format(char="asterisk", licence="MIT"),
    ),
    "#MIT": (
        refused("character dropped: U+0023", "MIT"),
        _DROP.format(char="hash", licence="MIT"),
    ),
    "MIT" + chr(0xFFFD): (  # not a literal: ruff reads it as the surrogate key
        refused("character dropped: U+FFFD", "MIT"),
        _DROP.format(char="replacement character U+FFFD", licence="MIT"),
    ),
    '"MIT"': (
        refused("character dropped: U+0022", "MIT"),
        _DROP.format(char="quote", licence="MIT")
        + "; Q12: quotes are refused here, a later task (T6b) reads them",
    ),
}


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
            INSERT_LICENSE,
            [
                (row[0], row[1], 1, 0, 0, row[2], row[3])
                for row in list_rows(LICENSE_LIST, "licenses")
            ],
        )
        conn.executemany(
            INSERT_EXCEPTION,
            list_rows(EXCEPTION_LIST, "exceptions"),
        )
        conn.executemany(INSERT_INDEX, [(lid, _search_text(lid)) for lid in NEIGHBOURS])
        conn.executemany(
            SET_METADATA,
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
    rows = []
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != len(header):
            raise ValueError(
                f"{path.name}: row {number} has {len(fields)} fields,"
                f" the header {len(header)}"
            )
        rows.append(dict(zip(header, fields)))
    return rows


def sample_files() -> list[Path]:
    """The PyPI sample files, in name order."""
    return sorted(FIXTURES.glob(SAMPLE_GLOB))


def parity_rows() -> list[dict[str, str]]:
    """The parity corpus."""
    return read_rows(PARITY_FILE)


def sample_rows() -> list[dict[str, str]]:
    """Every row of the PyPI sample files."""
    return [row for path in sample_files() for row in read_rows(path)]


def corpus_rows() -> list[dict[str, str]]:
    """The rows the guard reads: the parity corpus, then the PyPI sample."""
    return [*parity_rows(), *sample_rows()]


def pinned(row: dict[str, str]) -> Answer:
    """The 0.6.0 answer a fixture row records."""
    return answer_from_row(row)


def changed_answers(
    db: LicenseDatabase | None,
    rows: Iterable[dict[str, str]] | None = None,
    *,
    source: Source = "auto",
) -> dict[str, tuple[Answer, Answer]]:
    """The values whose answer differs from the pinned one, over the parity
    corpus and the PyPI sample (or *rows*): ``{value: (pinned, current)}``.
    The list is *db*, else the one *source* names (``packaged``: the bundle
    the test ships, ``release_fakes.ship``)."""
    if rows is None:
        rows = corpus_rows()
    changed: dict[str, tuple[Answer, Answer]] = {}
    for row in rows:
        value = unescape_field(row["value"])
        old, new = pinned(row), answer_of(value, resolve(value, db, source=source))
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
        if value not in expected:
            lines.append(
                f"changed, not in EXPECTED_CHANGES: {value!r}: {answer_diff(old, new)}"
            )
        elif new != expected[value][0]:
            lines.append(
                f"in EXPECTED_CHANGES, wrong answer: {value!r}: "
                f"{answer_diff(expected[value][0], new)} (expected -> got)"
            )
    lines += [
        f"in EXPECTED_CHANGES, answer unchanged: {value!r} ({why})"
        for value, (_, why) in expected.items()
        if value not in changed
    ]
    return "\n".join(lines)
