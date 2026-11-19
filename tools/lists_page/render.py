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

from trove_classifiers import deprecated_classifiers

from licenseid import LicenseDatabase
from licenseid.resolvefirst import EXACT_CATEGORIES
from licenseid.resolvertypes import Category
from licenseid.trovenames import TROVE_NAMES, TroveEntry
from tools.lists_page import evidence
from tools.lists_page.measure import Answer, answer_of, list_owners, sample_size
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
`EXACT` is yes when an authoritative list defines the reading: the SPDX
License List or a list below, also through a change of case alone (`zlib` is
`Zlib`, `lexical`). These are the categories of
`licenseid.resolvefirst.EXACT_CATEGORIES`: {exact}. Any other is no: a
rewrite rule made the reading (`prose_form`, `version_spelling`, a
`separator` that re-spells, as `BSD 3 Clause`). A compound is exact when
every operand is, so IDs joined by a slash are (`MIT/Apache-2.0`, category
`separator`). A value cut to be read (`"MIT`) is not.

A row is added only with a measured count of the packages that declare it.
The counts of the PyPI tables are projects of a sample of October 2026
(`tests/fixtures/pypi_values_2026-10.tsv`), counted by the generator: the
{counted:,} of the {sampled:,} most downloaded PyPI projects that declare
one short value. The rest declare none, only a licence text or several
classifiers, so a count understates use. The counts of the URL table are
packages of a survey of 2026-11-07 (issue #14: the 1,000 Maven Central
packages with most dependants and the 300 most downloaded NuGet, npm, PyPI and
crates.io packages). A URL page with no count
is one the List gives to a licence and its variants, and that is its
evidence. A dash is no count recorded.
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
list: `prose_form` and `version_spelling` are not exact. Besides the SPDX
List, P1 asks `ALIASES` only (`CC0 License` and `Mulan PSL v2 License` are
not read), so a BSD name with `License` is exact where `The MIT License` and
`BSD 3-Clause License` are not.
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
    """A Markdown table, ending in a blank line; an empty cell is one space."""
    lines = [_row(headers), _row(["---" for _ in headers])]
    lines += [_row(row) for row in rows]
    return "\n".join(lines) + "\n"


def _row(cells: Iterable[object]) -> str:
    return "|" + "|".join(f" {c} " if str(c) else " " for c in cells) + "|"


def _exact(category: Category | str) -> str:
    """``yes`` or ``no``: whether a category of a declared value is exact."""
    return "yes" if category in EXACT_CATEGORIES else "no"


def _count(counts: Counter[str] | dict[str, int], key: str) -> str:
    return f"{counts[key]:,}" if counts.get(key) else "—"


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
            _code(category) + (", or the ID's" if path in _BY_ID else ""),
            _glance_exact(path, category),
            len(_object("licenseid." + path)),
            what,
        )
        for path, category, what in rows
    ]
    return "## The lists at a glance\n\n" + table(
        ["Object", "Category", "`EXACT`", "Rows", "Holds"], out
    )


#: The lists whose category is that of the ID they read (a bare deprecated
#: ID is ``assumed_only``), and whose ``EXACT`` the examples show.
_BY_ID: Final = frozenset({"resolveurl.URL_ALIASES", "resolveurl.ID_PAGES"})


def _glance_exact(path: str, category: str) -> str:
    if category == "unresolved":
        return "—"
    return "see the examples" if path in _BY_ID else _exact(category)


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
            why = _noted(evidence.TROVE_REFUSALS[name], path)
            none.append((_code(path), why, _count(counts, name)))
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
        "PyPI writes it and what `resolve()` gives for it. Projects counts "
        "the values that are the classifier or its name alone, whatever "
        "reads them. A classifier PyPI has deprecated is marked so.\n\n"
    )
    out = text + table(
        ["Classifier", "Answer", "Category", "`EXACT`", "Projects", "Note"], read
    )
    return (
        out + "\nThese names state no one licence, and no rule guesses at "
        "them:\n\n" + table(["Classifier", "Why", "Projects"], none)
    )


def _noted(note: str, path: str) -> str:
    """*note*, with a word for a classifier PyPI has deprecated."""
    if path not in deprecated_classifiers:
        return note
    return f"{note}; deprecated by PyPI" if note else "deprecated by PyPI"


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
        _noted(evidence.TROVE_NOTES.get(name, ""), path),
    )


def _owners(db: LicenseDatabase, key: str) -> str:
    owners = list_owners(db, key)
    return ", ".join(_code(owner) for owner in owners) if owners else "none"


#: URLs that show how each reader of a URL answers.
URL_EXAMPLES: Final = (
    "https://spdx.org/licenses/MIT.html",
    "https://spdx.org/licenses/GPL-2.0.html",
    "https://spdx.org/licenses/MIT+",
    "https://spdx.org/licenses/preview/MIT",
    "https://licenses.nuget.org/mit",
    "https://licenses.nuget.org/MS-PL%20OR%20Apache-2.0",
    "https://licenses.nuget.org/GPL-2.0%2B",
    "https://openjdk.java.net/legal/gplv2+ce",
)

URL_TEXT: Final = """\
## Licence URLs

A URL is read as the licence it names through the step `license_url`. Its
category is `license_url`, or that of a deprecated ID it reads, as for the ID
alone (`assumed_only`, `deprecated_ambiguous`). It is compared by its key
(`licenseid.urlkey.url_key`): ASCII case is folded, and the scheme, `www.`, a
fragment, a trailing `/` and one page suffix such as `.html` are dropped. A
key can so name a page that does not exist (`licenses.nuget.org/mit`). The
reader tries four things in this order; a refusal claims the value, so no
later reader guesses at it. `EXACT` is `detect()`'s: a variant the value does
not state is not exact (`https://licenses.nuget.org/GPL-2.0%2B` states
`GPL-2.0+`, as the URL with a literal "+" does).
"""

ID_PAGE_TEXT: Final = """\
### Pages whose path holds an ID

`licenseid.resolveurl.ID_PAGES`. The rest of the key after one of these must
be one segment (no `/` or `?`), read as an ID. On the List's own pages `<ID>+`
is read too; on NuGet's the segment may be a whole expression, URL-encoded,
with the detail `expression in path`. A page of an exception is refused, and a
ScanCode key listed below is not read.
"""

SCANCODE_TEXT: Final = """\
### ScanCode keys not read as the ID they spell

`licenseid.resolveurl.SCANCODE_NOT_SPDX`. Each key folds to an SPDX ID, but
ScanCode's own SPDX key for it differs: it names another licence, gives the
same licence only a `LicenseRef-scancode-` key, or is deprecated with none.
The page does not state the ID its key spells, so it is not read. No package
of the survey declares a ScanCode URL, so the rule rests on the format.
"""


def _url_examples(db: LicenseDatabase) -> str:
    rows = []
    for url in URL_EXAMPLES:
        answer = answer_of(db, url)
        found = answer.expression is not None
        rows.append(
            (
                _code(url),
                _code(answer.expression) if found else "none",
                _code(answer.category),
                _code(answer.detail) if found else "—",
                ("yes" if answer.exact else "no") if found else "—",
            )
        )
    return table(["URL", "Answer", "Category", "Detail", "`EXACT`"], rows)


def _scancode() -> str:
    rows = []
    for key in sorted(_object("licenseid.resolveurl.SCANCODE_NOT_SPDX")):
        spdx_key, group = evidence.SCANCODE_KEYS[key]
        rows.append((_code(key), _code(spdx_key) if spdx_key else "none", group))
    return table(["Key", "ScanCode's SPDX key", "Group"], rows)


def _alias_source(key: str, source: str) -> str:
    note = evidence.URL_SOURCE_NOTES.get(key)
    return f"<{source}>" + (f"; {note}" if note else "")


def _urls(db: LicenseDatabase) -> str:
    pages = _object("licenseid.resolveurl.ID_PAGES")
    aliases = _object("licenseid.resolveurl.URL_ALIASES")
    parts = [
        URL_TEXT,
        _url_examples(db),
        ID_PAGE_TEXT,
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
        SCANCODE_TEXT,
        _scancode(),
        (
            "### Pages read as one licence\n\n"
            "`licenseid.resolveurl.URL_ALIASES`, detail `alias`. A page the List "
            "lacks, or gives a licence and its variants, reviewed by hand. The "
            "source is the page that shows the licence. A page the List gives "
            "to the licence and its variants is read as the licence, and its "
            "evidence is the List: the column of the List names the IDs it "
            "gives the page to. Any other row needs a count of packages.\n"
        ),
        table(
            ["Key", "ID", "Source", "Packages", "The List gives the page to"],
            [
                (
                    _code(key),
                    _code(alias.license_id),
                    _alias_source(key, alias.source),
                    str(evidence.URL_PACKAGES.get(key, "—")),
                    _owners(db, key),
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
    sampled, counted = sample_size()
    exact = ", ".join(f"`{c}`" for c in sorted(EXACT_CATEGORIES))
    sections = [
        INTRO.format(exact=exact, sampled=sampled, counted=counted),
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
        _urls(db),
        _slash(),
        _versioned(),
    ]
    return _wrapped("\n".join(s.rstrip("\n") + "\n" for s in sections))
