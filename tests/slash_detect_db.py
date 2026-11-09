# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A seeded database for the ``detect()`` tests of the "/" rule: the licences
a slash value is near, each with a text (a row with none is never retrieved,
and a negative test passes for nothing)."""

import json
from pathlib import Path

from matcher_db import Lic

from licenseid.normalize import normalize_text

FIXTURES = Path(__file__).parent / "fixtures"
NEIGHBOURS = (
    "MIT", "X11", "ECL-2.0", "Zlib", "Libpng", "TCL", "NCSA", "Apache-2.0", "ISC",
    "GPL-2.0-only", "GPL-2.0-or-later",
)  # fmt: skip


def rows() -> list[Lic]:
    """One row for each neighbour, with the text of its long fixture (the
    short one where the List has no long text: TCL)."""
    out = []
    for license_id in NEIGHBOURS:
        path = FIXTURES / "license-text-long" / f"{license_id}.json"
        if not path.exists():
            path = FIXTURES / "license-text-short" / f"{license_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        text = normalize_text(data["license_text"])
        out.append(Lic(license_id, data.get("name", license_id), search_text=text))
    return out
