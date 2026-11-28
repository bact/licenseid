# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The licence classes of a side's own database, for the headers verdict.

One class is one normalised text: the ``same_text`` group of the database
(the ``-only`` and ``-or-later`` twins of one text, the forms of GFDL whose
texts are one). A deprecated ID has no text in the List: it joins the class of
its replacement (``superseded_by``) where it has one, else of its ``-only`` or
``-or-later`` form (bare ``GPL-2.0``), else it is a class of its own. An
expression with no row is a class of its own. Read with the standard library
only, read-only."""

import sqlite3
from pathlib import Path
from typing import Any

QUERY = "SELECT license_id, is_deprecated, superseded_by, same_text FROM licenses"


def _rows(db: Path) -> dict[str, tuple[bool, str, str]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {
            lid: (bool(dep), sup or "", same or "")
            for lid, dep, sup, same in con.execute(QUERY)
        }
    finally:
        con.close()


def _replacement(lid: str, rows: dict[str, Any]) -> str:
    """The licence a deprecated ID without a replacement stands for."""
    stem = lid.removesuffix("+")
    if lid.endswith("+") and stem + "-or-later" in rows:
        return stem + "-or-later"
    for candidate in (stem + "-only", stem.replace("-with-", "-only-with-")):
        if candidate in rows:
            return candidate
    return ""


def classes(db: Path) -> dict[str, str]:
    """The class key of every licence ID of the database."""
    rows = _rows(db)
    key = {
        lid: " ".join(sorted(same.split())) or lid for lid, (_, _, same) in rows.items()
    }
    for lid, (deprecated, superseded, _) in rows.items():
        if not deprecated:
            continue
        target = superseded or _replacement(lid, rows)
        if target in key:
            key[lid] = key[target]
    return key


def attach(result: dict[str, Any], db: Path) -> None:
    """Put the classes of the licences a headers result names (each header's
    own and each top answer) into ``result["classes"]``, from the side's own
    database, so that a comparison needs no database."""
    names: set[str] = set()
    for key, case in (result.get("cases") or {}).items():
        names.add(key.split(":")[2])
        rows = case.get("rows") or []
        if rows and rows[0][0]:
            names.add(rows[0][0])
    known = classes(db)
    result["classes"] = {n: known[n] for n in sorted(names) if n in known}
