# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The text of ``docs/lists.md``: the tables are read from the list objects
in ``src/licenseid/``, never typed; the prose between them is the only
fixed text. Each table names the object it reads by its import path, and a
row by its key in that object."""

import importlib
import textwrap
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Final

from licenseid.resolvefirst import EXACT_CATEGORIES
from licenseid.resolvertypes import Category
from licenseid.trovenames import TROVE_NAMES, TroveEntry
from tools.lists_page import evidence
from tools.lists_page.measure import Answer, answer_of
from tools.lists_page.rules import RULES

INTRO: Final = """\
---
# Generated from the code by `python -m tools.lists_page`: never edit by hand.
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# The lists that `resolve()` reads

This page is generated from the code by `python -m tools.lists_page`. Do not
edit it by hand: `tests/test_lists_page.py` fails when the page and the code
differ. To change a row, change the list in `src/licenseid/` and run the
command again.

`resolve()` reads a declared licence value (a `License` field, a classifier,
a URL) as an SPDX expression. Besides the SPDX License List it reads the
lists on this page, which licenseid keeps. Each is decided once, as data: a
value is read only if a list holds it, never by a looser match. A table names
the object it comes from by its import path, and each row by its key in that
object.

Each list gives one `category` (see [the table of
categories](resolve.md#steps-and-categories)) and so one `EXACT` value.
`EXACT` is yes when an authoritative list defines the reading, which is the
SPDX License List and the lists below, and no when a rewrite rule made it
(`separator`, `prose_form`, `version_spelling`). A compound is exact when
every operand is.

A row is added only with a measured count of the packages that declare it.
The counts of the PyPI tables are projects of a sample of the 10,000 most
downloaded PyPI projects of October 2026
(`tests/fixtures/pypi_values_2026-10.tsv`), counted by the generator. The
counts of the URL table are packages of a survey of 2026-11-07 (issue #14:
the 1,000 Maven Central packages with most dependants and the 300 most
downloaded NuGet, npm, PyPI and crates.io packages). A dash is no count
recorded.
"""

RULES_INTRO: Final = """\
## Named rules

Some rules are named in the code and the tests: T1 to T3 read a trove
classifier or a name with its abbreviation (`licenseid.resolvetrove`), and P1
to P3 read the prose form of an ID (`licenseid.resolveprose`). Each row names
the function that is the rule. The answer, the category and `EXACT` are what
`resolve()` gives for the example.

A rule that hands a value to a list or to the SPDX List reads as that list
does, so it is exact when the list is. A rule that rewrites a value is no
list: `prose_form` and `version_spelling` are not exact. When a prose form
reduces to a name of a table below, the category is the table's, as the
weakest of the steps (`New BSD License` is `alias_name`).
"""


def _object(path: str) -> Any:
    """The object at the import path *path* (``module.NAME``)."""
    module, _, name = path.rpartition(".")
    return getattr(importlib.import_module(module), name)


def _wrapped(page: str) -> str:
    """*page* with each prose paragraph over 80 columns filled to 80; tables,
    headings and the front matter are left as they are."""
    blocks = []
    for block in page.split("\n\n"):
        lines = block.split("\n")
        if not block.startswith(("|", "#", "---")) and any(len(x) > 80 for x in lines):
            block = textwrap.fill(
                " ".join(lines), 80, break_long_words=False, break_on_hyphens=False
            )
        blocks.append(block)
    return "\n\n".join(blocks)


def _cell(text: object) -> str:
    """*text* for a table cell: a pipe is escaped."""
    return str(text).replace("|", "\\|")


def _code(text: object) -> str:
    """*text* as a code span in a table cell."""
    return f"`{_cell(text)}`"


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """A Markdown table, ending in a blank line."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _exact(category: Category | str) -> str:
    """``yes`` or ``no``: whether a category of a declared value is exact."""
    return "yes" if category in EXACT_CATEGORIES else "no"


def _count(counts: Counter[str] | dict[str, int], key: str) -> str:
    return str(counts[key]) if counts.get(key) else "—"


def _id(function: Any) -> str:
    return f"{function.__module__}.{function.__qualname__}"


def _glance() -> str:
    rows = [
        ("resolvealias.ALIASES", "alias_name", "BSD names"),
        ("resolvetitle.TITLES", "text_title", "titles of licence texts"),
        ("trovenames.TROVE_NAMES", "trove_name", "classifier names"),
        ("resolveurl.URL_ALIASES", "license_url", "pages read as a licence"),
        ("resolveurl.ID_PAGES", "license_url", "hosts with an ID in the path"),
        ("resolveurl.DUAL_PAGES", "unresolved", "pages refused: a choice"),
        ("resolveurl.SCANCODE_NOT_SPDX", "unresolved", "ScanCode keys not read"),
        ("resolveslash.REFUSED_PAIRS", "unresolved", "pairs refused in a slash"),
        ("resolveprose.VERSIONED_NAMES", "prose_form", "names with a version"),
    ]
    out = [
        (
            _code("licenseid." + path),
            _code(category),
            _exact(category) if category != "unresolved" else "—",
            len(_object("licenseid." + path)),
            what,
        )
        for path, category, what in rows
    ]
    return "## The lists at a glance\n\n" + table(
        ["Object", "Category", "`EXACT`", "Rows", "Holds"], out
    )


def _rules(db: Any) -> str:
    rows = []
    for rule in RULES:
        answer = answer_of(db, rule.example)
        rows.append(
            (
                rule.name,
                _code(_id(rule.code)),
                _cell(rule.reads),
                _code(rule.example),
                _code(answer.expression),
                _code(answer.category),
                "yes" if answer.exact else "no",
                _cell(rule.note),
            )
        )
    headers = [
        "Rule",
        "Function",
        "Reads",
        "Example",
        "Answer",
        "Category",
        "`EXACT`",
        "Decided by",
    ]
    return RULES_INTRO + "\n" + table(headers, rows)


def _sourced_table(
    heading: str,
    text: str,
    path: str,
    sources: dict[str, str],
    counts: Counter[str],
) -> str:
    rows = [
        (_code(key), _code(license_id), sources[key], _count(counts, key))
        for key, license_id in sorted(_object(path).items())
    ]
    headers = ["Name (folded)", "ID", "Source", "Projects"]
    return f"## {heading}\n\n{text}\n" + table(headers, rows)


ALIAS_TEXT: Final = """\
Other names of the two BSD licences. `licenseid.resolvealias.ALIASES`, category
`alias_name`, `EXACT` yes. A name is read in ASCII case folded, with a run of
white space as one space. A final `License` is read first (rule P1).
"""

TITLE_TEXT: Final = """\
The title a licence's own text gives itself. `licenseid.resolvetitle.TITLES`,
category `text_title`, `EXACT` yes. A title that writes a version but no grant
is the bare deprecated ID, `assumed_only`.
"""


def _trove(db: Any, counts: Counter[str]) -> str:
    read, none = [], []
    for name, entry in sorted(TROVE_NAMES.items(), key=lambda kv: kv[0].casefold()):
        path = _classifier(name, entry)
        answer = answer_of(db, path)
        if answer.expression is None:
            none.append((_code(path),))
            continue
        read.append(_trove_row(path, name, answer, counts))
    text = (
        "## Trove classifier names\n\n"
        "The `License ::` classifiers of PyPA's `trove-classifiers`, "
        "`licenseid.trovenames.TROVE_NAMES`, category `trove_name`, `EXACT` "
        "yes. A name that is also an ID or a List name is read as that "
        "first, so its category is `listed_name`; a name that states a bare "
        "deprecated ID is `assumed_only`. Rule T1 reads the whole classifier "
        "and rule T2 the name alone. The table shows the classifier as "
        "PyPI writes it and what `resolve()` gives for it.\n\n"
    )
    out = text + table(
        ["Classifier", "Answer", "Category", "`EXACT`", "Projects"], read
    )
    return (
        out + "\nThese names state no one licence (a category, a family, a name "
        "with no version, or no SPDX ID), and no rule guesses at them:\n\n"
        + table(["Classifier"], none)
    )


def _classifier(name: str, entry: TroveEntry) -> str:
    return f"License :: OSI Approved :: {name}" if entry.osi else f"License :: {name}"


def _trove_row(
    path: str, name: str, answer: Answer, counts: Counter[str]
) -> tuple[str, ...]:
    return (
        _code(path),
        _code(answer.expression),
        _code(answer.category),
        "yes" if answer.exact else "no",
        _count(counts, name),
    )


def _urls() -> str:
    pages = _object("licenseid.resolveurl.ID_PAGES")
    aliases = _object("licenseid.resolveurl.URL_ALIASES")
    parts = [
        (
            "## Licence URLs\n\n"
            "A URL is read as the licence it names through the step "
            "`license_url`, category `license_url`, `EXACT` yes. It is compared "
            "by its key (`licenseid.urlkey.url_key`): the scheme, `www.`, a "
            "fragment and a trailing `/` are dropped. The reader tries four "
            "things in this order; a refusal claims the value, so no later "
            "reader guesses at it.\n"
        ),
        (
            "### Pages whose path holds an ID\n\n"
            "`licenseid.resolveurl.ID_PAGES`. The last segment of a path that "
            "starts with the key is read as an ID. A page of an exception is "
            "refused, and a ScanCode key listed below is not read.\n"
        ),
        table(
            ["Key starts with", "Detail of the step"],
            [(_code(k), _code(v)) for k, v in pages.items()],
        ),
        (
            "### Pages refused, for a choice of licences\n\n"
            "`licenseid.resolveurl.DUAL_PAGES`. The List gives each page one "
            "licence, but the page offers a choice: the value is refused with "
            "`url names several licences`.\n"
        ),
        table(
            ["Key", "Offers", "Source"],
            [
                (_code(k), _code(", ".join(v)), evidence.DUAL_SOURCES[k])
                for k, v in sorted(_object("licenseid.resolveurl.DUAL_PAGES").items())
            ],
        ),
        (
            "### ScanCode keys that are the SPDX ID of another licence\n\n"
            "`licenseid.resolveurl.SCANCODE_NOT_SPDX`. The ScanCode LicenseDB "
            "page with one of these keys is not read as the SPDX ID of the same "
            "spelling, as ScanCode means another licence by it. No package of "
            "the survey declares a ScanCode URL, so the rule rests on the "
            "format.\n"
        ),
        table(
            ["Key"],
            [
                (_code(k),)
                for k in sorted(_object("licenseid.resolveurl.SCANCODE_NOT_SPDX"))
            ],
        ),
        (
            "### Pages read as one licence\n\n"
            "`licenseid.resolveurl.URL_ALIASES`, detail `alias`. A page the List "
            "lacks, or gives a licence and its variants, reviewed by hand. The "
            "source is the page that shows the licence.\n"
        ),
        table(
            ["Key", "ID", "Source", "Packages"],
            [
                (
                    _code(key),
                    _code(alias.license_id),
                    f"<{alias.source}>",
                    str(evidence.URL_PACKAGES.get(key, "—")),
                )
                for key, alias in sorted(aliases.items())
            ],
        ),
    ]
    return "\n".join(parts)


def _slash() -> str:
    pairs = _object("licenseid.resolveslash.REFUSED_PAIRS")
    return (
        "## IDs joined by a slash\n\n"
        "`licenseid.resolveslash.REFUSED_PAIRS`. A value with both IDs of a "
        "pair, in any order and place, is refused: the pair is one licence "
        "under a name with a slash. Another pair needs a measured count.\n\n"
        + table(
            ["Pair", "Why"],
            [
                (", ".join(_code(i) for i in pair), evidence.PAIR_NOTES[pair])
                for pair in sorted(pairs)
            ],
        )
    )


def _versioned() -> str:
    names = _object("licenseid.resolveprose.VERSIONED_NAMES")
    return (
        "## Names with a version in prose\n\n"
        "`licenseid.resolveprose.VERSIONED_NAMES`, read by rule P2. A name "
        "that states no version is read with the version after it, as the "
        "ID of its prefix; the ID must be listed.\n\n"
        + table(
            ["Name (folded)", "ID prefix"],
            [(_code(k), _code(v)) for k, v in sorted(names.items())],
        )
    )


def render(db: Any, projects: dict[str, Counter[str]]) -> str:
    """The whole page, for the database *db* of the corpus and the counts of
    :func:`tools.lists_page.measure.project_counts`."""
    sections = [
        INTRO,
        _glance(),
        _rules(db),
        _sourced_table(
            "BSD names",
            ALIAS_TEXT,
            "licenseid.resolvealias.ALIASES",
            evidence.ALIAS_SOURCES,
            projects["alias"],
        ),
        _sourced_table(
            "Titles of licence texts",
            TITLE_TEXT,
            "licenseid.resolvetitle.TITLES",
            evidence.TITLE_SOURCES,
            projects["title"],
        ),
        _trove(db, projects["trove"]),
        _urls(),
        _slash(),
        _versioned(),
    ]
    return _wrapped("\n".join(s.rstrip("\n") + "\n" for s in sections))
