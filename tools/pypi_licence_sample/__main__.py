# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Measure how ``licenseid.resolve()`` fares on real PyPI licence values.

Three steps, run as ``python -m tools.pypi_licence_sample``:

``fetch``
    Reads the ``top-pypi-packages`` list (download counts, hugovk) and asks
    the PyPI JSON API for each project's latest release: ``info.license``,
    ``info.license_expression`` and the ``License ::`` classifiers. One JSON
    object per project goes to a JSON Lines file. Network; a few minutes for
    5,000 projects at 16 requests at a time.

``analyze``
    Picks the value a consumer would use for each project (the first of
    ``License-Expression``, a short ``License``, the classifiers), runs
    ``resolve()`` on it and prints: which source was used, the category of
    each answer, and the unresolved values grouped by what would resolve them
    (:data:`GROUPS`, a first reading by pattern, not tested rules), each with
    its project count and download total. Needs the licence database
    (``licenseid update``); no network.

``export``
    Writes the distinct short values (the value a consumer would use, as
    ``analyze`` picks it) with their project and download counts and the
    answer of ``resolve()`` to tab-separated files of at most 790 lines, for
    a test fixture (``tests/fixtures/pypi_values_*.tsv``). The values are
    escaped as Python ``unicode_escape``. Several classifiers (joined by
    ``AND``) are left out, as ``analyze`` counts them apart. When the values
    do not fit in ``--max-files`` files, every value whose category is not
    ``exact`` is kept and the header records the count and the SHA-256 of the
    full sorted set (the value and every answer column).

Standard library and ``licenseid`` only. Findings are recorded in
``working-docs/design/resolver-0-7-evidence.md``.
"""

import argparse
import collections
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from tools.pypi_licence_sample.answer import (
    ANSWER_COLUMNS,
    answer_fields,
    answer_of,
    escape_field,
)

if TYPE_CHECKING:
    from licenseid import LicenseDatabase

TOP_URL: Final = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"
PYPI_URL: Final = "https://pypi.org/pypi/{name}/json"
#: Names the sampler to PyPI's operators; carries no personal address.
USER_AGENT: Final = "licenseid-research (https://github.com/bact/licenseid)"
THREADS: Final = 16
RETRIES: Final = 3
#: A value longer than this, or on several lines, is licence text, not a name.
MAX_VALUE_LENGTH: Final = 200
#: The trove category, not a licence: left out as the readers leave it out.
CATEGORY_CLASSIFIER: Final = "License :: OSI Approved"

#: Unresolved values grouped by what would resolve them, first match wins.
#: Patterns on the lower-cased value. A first reading to rank work by, not a
#: rule set: a rule is promised only after a run against the sample.
GROUPS: Final = (
    (
        "bare or family name (more than one licence)",
        (
            r"^(bsd( license)?|gpl|lgpl|apache|mit license|gnu lgpl|lgpl license"
            r"|gpl license|gnu gpl|new bsd|bsd-like|isc|mozilla|python)$"
        ),
    ),
    (
        "trove classifier name",
        (
            r"^(apache software license|python software foundation license"
            r"|other/proprietary license|gnu library or lesser general public "
            r"license \(lgpl\)|gnu lesser general public license v3 \(lgplv3\)"
            r"|gnu general public license v3 or later \(gplv3\+\)"
            r"|isc license \(iscl\)|mozilla public license 2\.0 \(mpl 2\.0\)"
            r"|gnu general public license \(gpl\)|public domain|artistic license"
            r"|gnu affero general public license v3|zope public license"
            r"|common development and distribution license 1\.0 \(cddl-1\.0\)"
            r"|eclipse public license 2\.0 \(epl-2\.0\)|osi approved)$"
        ),
    ),
    ("full trove path in License", r"^license :: "),
    (
        "prose form of one id",
        (
            r"(apache.*(license|licence).*(version|v)\s*2|apache.*2(\.0)?.*licen[cs]e"
            r"|apache-2\.0 license|bsd[- ]?[23]|[23][- ]clause|\bmit\b.*licen[cs]e"
            r"|licen[cs]e.*\bmit\b|gpl.*v?[23]|lgpl.*v?[23]|mpl)"
        ),
    ),
    ("trailing parenthesis after a name", r"\([^)]*\)\s*$"),
    (
        "alias or abbreviation",
        r"^(expat licen[cs]e|psf|psfl|iscl|zlib/libpng|cc0)$",
    ),
    (
        "proprietary or custom",
        (
            r"(proprietary|custom|commercial|all rights reserved|see license"
            r"|license\.txt|^license$|licen[cs]e file|copyright|eula|nvidia"
            r"|databricks|private)"
        ),
    ),
)

Project = dict[str, Any]


class SampleError(ValueError):
    """The sample file holds a line that is not a JSON object: a data error,
    not a usage error."""


def read_projects(path: Path) -> list[Project]:
    """The projects of the JSON Lines file *path*. Raises :class:`SampleError`
    for a line that is not a JSON object."""
    try:
        lines = path.read_text("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise SampleError(f"{path}: unreadable: {exc}") from exc
    projects: list[Project] = []
    for number, line in enumerate(lines, 1):
        try:
            project = json.loads(line)
        except ValueError as exc:
            raise SampleError(f"{path}:{number}: not JSON: {exc}") from exc
        if not isinstance(project, dict):
            raise SampleError(f"{path}:{number}: not a JSON object")
        projects.append(project)
    return projects


#: The lines of one exported file, header comments included.
MAX_LINES: Final = 790
#: Comment and header lines of an exported file (the header is 6 lines, and
#: the file mark and the column row 2 more; some room is left).
HEADER_LINES: Final = 10
#: The files an export may use before it keeps only the values that are
#: not ``exact``.
MAX_FILES: Final = 6
EXPORT_COLUMNS: Final = ("value", "field", "projects", "downloads", *ANSWER_COLUMNS)


def _fetch_one(row: dict[str, Any]) -> Project:
    """The licence fields of one project's latest release, or an ``error``."""
    name = str(row["project"])
    result: Project = {"name": name, "downloads": row["download_count"]}
    for attempt in range(RETRIES):
        request = urllib.request.Request(
            PYPI_URL.format(name=name), headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                info = json.load(response)["info"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {**result, "error": 404}
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(2 * (attempt + 1))
        else:
            classifiers = info.get("classifiers") or []
            return {
                **result,
                "license": info.get("license"),
                "license_expression": info.get("license_expression"),
                "classifiers": [c for c in classifiers if c.startswith("License ::")],
            }
    return {**result, "error": "failed"}


def fetch(count: int, out: Path) -> None:
    """Write the licence fields of the *count* most downloaded projects."""
    request = urllib.request.Request(TOP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = json.load(response)["rows"][:count]
    with (
        concurrent.futures.ThreadPoolExecutor(THREADS) as pool,
        out.open("w", encoding="utf-8") as handle,
    ):
        for done, project in enumerate(pool.map(_fetch_one, rows), 1):
            handle.write(json.dumps(project) + "\n")
            if done % 500 == 0:
                print(f"{done} of {len(rows)}", file=sys.stderr, flush=True)


def _short(value: str | None) -> str | None:
    """*value* when it is a one-line name, else ``None`` (blank, ``UNKNOWN``,
    licence text)."""
    text = (value or "").strip()
    if not text or text == "UNKNOWN" or len(text) > MAX_VALUE_LENGTH:
        return None
    return None if "\n" in text else text


def declared_value(project: Project) -> tuple[str, str | None]:
    """``(source, value)`` a consumer would use for *project*: the first of
    ``License-Expression``, a short ``License``, the classifiers (their names
    joined by `` AND `` when several). ``License-text`` when only licence text
    is declared, ``none`` when nothing is."""
    expression = _short(project.get("license_expression"))
    if expression:
        return "License-Expression", expression
    licence = _short(project.get("license"))
    if licence:
        return "License", licence
    names = sorted(
        {
            c.rsplit("::", 1)[-1].strip()
            for c in project.get("classifiers", [])
            if c != CATEGORY_CLASSIFIER
        }
    )
    if names:
        return "Classifier", " AND ".join(names)
    text = (project.get("license") or "").strip()
    return ("License-text", None) if text and text != "UNKNOWN" else ("none", None)


def group_of(value: str) -> str:
    """The first :data:`GROUPS` entry that matches *value*, else ``other``."""
    lowered = value.strip().lower()
    for name, pattern in GROUPS:
        if re.search(pattern, lowered):
            return name
    return "other"


def _open_database(path: Path | None) -> "LicenseDatabase | None":
    """The database at *path*, read only; ``None`` for the default one."""
    from licenseid import LicenseDatabase  # pylint: disable=import-outside-toplevel

    return None if path is None else LicenseDatabase(path, create=False)


def analyze(path: Path, top: int, db_path: Path | None = None) -> None:
    """Print the statistics of the JSON Lines file *path*, answered from the
    database at *db_path* (the default database when ``None``)."""
    from licenseid import resolve  # pylint: disable=import-outside-toplevel

    db = _open_database(db_path)
    projects = read_projects(path)
    fetched = [p for p in projects if "error" not in p]
    print(f"projects {len(projects)}, fetched {len(fetched)}")
    sources: collections.Counter[str] = collections.Counter()
    categories: collections.Counter[str] = collections.Counter()
    groups: collections.Counter[str] = collections.Counter()
    group_downloads: collections.Counter[str] = collections.Counter()
    values: collections.Counter[tuple[str, str, str]] = collections.Counter()
    downloads: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for project in fetched:
        source, value = declared_value(project)
        sources[source] += 1
        if value is None:
            continue
        if source == "Classifier" and " AND " in value:
            categories["several classifiers"] += 1
            continue
        category = resolve(value, db)["category"]
        categories[category] += 1
        if category == "unresolved":
            group = group_of(value)
            groups[group] += 1
            group_downloads[group] += project["downloads"]
            key = (group, source, value)
            values[key] += 1
            downloads[key] += project["downloads"]
    _report(sources, categories, (groups, group_downloads, values, downloads), top)


def _report(
    sources: collections.Counter[str],
    categories: collections.Counter[str],
    tables: tuple[collections.Counter[Any], ...],
    top: int,
) -> None:
    """Print the counts of :func:`analyze`; *tables* is the projects and
    the downloads by group, then the projects and downloads by value."""
    groups, group_downloads, values, downloads = tables
    valued = sum(categories.values())
    print("\nsource used:", dict(sources))
    print(f"\nanswer of resolve() ({valued} projects with a short value)")
    for name, count in categories.most_common():
        print(f"  {name:22} {count:5} {100 * count / valued:5.1f}%")
    unresolved = sum(groups.values())
    print(f"\nunresolved values by group ({unresolved} projects)")
    for name, count in groups.most_common():
        print(
            f"  {count:5} {100 * count / unresolved:5.1f}% "
            f"{group_downloads[name] / 1e9:5.2f}G downloads  {name}"
        )
    print(f"\ntop {top} unresolved values")
    for (group, source, value), count in values.most_common(top):
        print(
            f"  {count:4} {downloads[(group, source, value)] / 1e6:8.1f}M "
            f"{source:18} {group[:28]:28} {value[:60]}"
        )


def distinct_values(projects: Sequence[Project]) -> list[tuple[str, str, int, int]]:
    """``(value, field, projects, downloads)`` for each distinct short value,
    sorted by the escaped value. *field* is the source most projects used.
    Several classifiers, which ``analyze`` counts apart, are left out."""
    sources: dict[str, collections.Counter[str]] = {}
    downloads: collections.Counter[str] = collections.Counter()
    for project in projects:
        if "error" in project:
            continue
        source, value = declared_value(project)
        if value is None or (source == "Classifier" and " AND " in value):
            continue
        sources.setdefault(value, collections.Counter())[source] += 1
        downloads[value] += project["downloads"]
    return [
        (
            value,
            max(sorted(counts), key=counts.__getitem__),
            sum(counts.values()),
            downloads[value],
        )
        for value, counts in sorted(sources.items(), key=lambda kv: escape_field(kv[0]))
    ]


def _export_rows(
    values: Sequence[tuple[str, str, int, int]], db: "LicenseDatabase | None"
) -> tuple[list[tuple[str, ...]], str]:
    """The exported rows of *values*, and the SHA-256 (hex) of the sorted
    ``value`` and answer lines (every answer column) of all of them."""
    from licenseid import resolve  # pylint: disable=import-outside-toplevel

    rows: list[tuple[str, ...]] = []
    digest = hashlib.sha256()
    for value, field, count, downloads in values:
        answer = answer_fields(answer_of(value, resolve(value, db)))
        digest.update(("\t".join((escape_field(value), *answer)) + "\n").encode())
        rows.append((escape_field(value), field, str(count), str(downloads), *answer))
    return rows, digest.hexdigest()


def _export_header(
    sample: Path, projects: int, db: "LicenseDatabase | None", counts: tuple[int, int]
) -> list[str]:
    """The comment lines that start every exported file; *counts* is the
    number of distinct values and the number kept."""
    from licenseid import __version__  # pylint: disable=import-outside-toplevel

    return [
        (
            f"# PyPI licence values of {sample.name}: {projects} projects,"
            f" licenseid {__version__}, SPDX {_list_version(db)}."
        ),
        (
            "# value: the first of License-Expression, a short License or the"
            " classifiers, as Python unicode_escape."
        ),
        (
            "# field: the source most projects used. '-' is None or empty. The"
            " _0_6_0 columns are the answer of resolve() before the 0.7.0 work."
        ),
        (
            f"# distinct values: {counts[0]}; kept in these files: {counts[1]}."
            " See tests/fixtures/README.md."
        ),
    ]


def export(
    sample: Path,
    prefix: Path,
    db_path: Path | None = None,
    max_files: int = MAX_FILES,
    max_lines: int = MAX_LINES,
) -> list[Path]:
    """Write the distinct values of *sample* to ``<prefix>.tsv`` (or
    ``<prefix>-1.tsv`` and on, when more than one file is needed) and return
    the files. See the module docstring for what is kept.

    Raises :class:`SampleError` for a bad sample file, and
    :class:`ValueError` when *max_files* is below 1, *max_lines*
    leaves no room for a row, or the values that are kept (every value that is
    not ``exact``, when all do not fit) still need more than *max_files*."""
    chunk = max_lines - HEADER_LINES
    if max_files < 1 or chunk < 1:
        raise ValueError(f"need max_files >= 1 and max_lines > {HEADER_LINES}")
    db = _open_database(db_path)
    projects = read_projects(sample)
    rows, digest = _export_rows(distinct_values(projects), db)
    kept = rows if len(rows) <= max_files * chunk else _not_exact(rows)
    if len(kept) > max_files * chunk:
        raise ValueError(
            f"{len(kept)} values that are not exact need over {max_files} files"
        )
    header = _export_header(sample, len(projects), db, (len(rows), len(kept)))
    header.append(
        f"# sha256 of the sorted (value, every answer column) lines: {digest}"
    )
    parts = [kept[i : i + chunk] for i in range(0, len(kept), chunk)] or [[]]
    written = []
    for number, part in enumerate(parts, 1):
        suffix = f"-{number}" if len(parts) > 1 else ""
        path = prefix.with_name(prefix.name + suffix + ".tsv")
        lines = [*header, f"# file {number} of {len(parts)}", "\t".join(EXPORT_COLUMNS)]
        lines += ["\t".join(row) for row in part]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(path)
    return written


def _not_exact(rows: Sequence[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The rows whose category (the sixth field) is not ``exact``."""
    return [row for row in rows if row[5] != "exact"]


def _list_version(db: "LicenseDatabase | None") -> str:
    """The SPDX License List version of *db* (the default database for
    ``None``)."""
    from licenseid import resolve  # pylint: disable=import-outside-toplevel

    version = resolve("MIT", db)["lists"][0]["version"]
    return version or "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``fetch``, ``analyze`` or ``export``."""
    parser = argparse.ArgumentParser(prog="python -m tools.pypi_licence_sample")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch", help="download the licence fields")
    fetch_parser.add_argument("--count", type=int, default=5000)
    fetch_parser.add_argument("--out", type=Path, required=True)
    analyze_parser = commands.add_parser("analyze", help="run resolve() and count")
    analyze_parser.add_argument("sample", type=Path)
    analyze_parser.add_argument("--top", type=int, default=40)
    analyze_parser.add_argument("--db", type=Path, help="database (default: cache)")
    export_parser = commands.add_parser(
        "export", help="write the distinct values and their answers as TSV"
    )
    export_parser.add_argument("sample", type=Path)
    export_parser.add_argument(
        "--out", type=Path, required=True, help="path prefix; .tsv is added"
    )
    export_parser.add_argument("--db", type=Path, help="database (default: cache)")
    export_parser.add_argument("--max-files", type=int, default=MAX_FILES)
    export_parser.add_argument("--max-lines", type=int, default=MAX_LINES)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            fetch(args.count, args.out)
        elif args.command == "analyze":
            analyze(args.sample, args.top, args.db)
        else:
            for path in export(
                args.sample, args.out, args.db, args.max_files, args.max_lines
            ):
                print(path)
    except SampleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:  # an export option the values cannot meet
        parser.error(f"{args.command}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
