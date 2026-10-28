# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Measure how ``licenseid.resolve()`` fares on real PyPI licence values.

Two steps, run as ``python -m tools.pypi_licence_sample``:

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

Standard library and ``licenseid`` only. Findings are recorded in
``working-docs/design/resolver-0-7-evidence.md``.
"""

import argparse
import collections
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

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


def analyze(path: Path, top: int) -> None:
    """Print the statistics of the JSON Lines file *path*."""
    from licenseid import resolve  # pylint: disable=import-outside-toplevel

    projects = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
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
        category = resolve(value)["category"]
        categories[category] += 1
        if category == "unresolved":
            group = group_of(value)
            groups[group] += 1
            group_downloads[group] += project["downloads"]
            key = (group, source, value)
            values[key] += 1
            downloads[key] += project["downloads"]
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``fetch`` or ``analyze``."""
    parser = argparse.ArgumentParser(prog="python -m tools.pypi_licence_sample")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch", help="download the licence fields")
    fetch_parser.add_argument("--count", type=int, default=5000)
    fetch_parser.add_argument("--out", type=Path, required=True)
    analyze_parser = commands.add_parser("analyze", help="run resolve() and count")
    analyze_parser.add_argument("sample", type=Path)
    analyze_parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch(args.count, args.out)
    else:
        analyze(args.sample, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
