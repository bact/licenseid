# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database of made-up licence texts, for the tests of ``TEXTS``: A-1.0
and B-1.0 (A-1.0 with two words changed, so both are candidates of either
text) and the GPL-3.0 pair, which shares one text and has its deprecated bare
ID."""

import sqlite3
from collections.abc import Generator

from matcher_db import Lic, seeded_db

from licenseid.normalize import normalize_text

A = " ".join(
    f"permission is granted to alpha{i} holders to frobnicate widget{i}"
    for i in range(8)
)
B = A.replace("alpha3", "gamma3").replace("widget5", "sprocket5")
GPL = " ".join(
    f"licensee{i} may copy modify and share record{i} freely" for i in range(8)
)

ROWS = (
    Lic("A-1.0", "A licence", search_text=normalize_text(A)),
    Lic("B-1.0", "B licence", search_text=normalize_text(B)),
    Lic("GPL-3.0-only", "GPL 3 only", search_text=normalize_text(GPL)),
    Lic("GPL-3.0-or-later", "GPL 3 or later", search_text=normalize_text(GPL)),
    Lic("GPL-3.0", "GPL 3", is_deprecated=True, superseded_by="GPL-3.0-only"),
)


def texts_database(prefix: str) -> Generator[str, None, None]:
    """The path of an in-memory database of :data:`ROWS`, the GPL pair
    grouped as a build groups twins."""
    for path in seeded_db(prefix, ROWS):
        with sqlite3.connect(path, uri=True) as conn:
            conn.execute(
                "UPDATE licenses SET same_text = ? WHERE license_id LIKE 'GPL-3.0-%'",
                ("GPL-3.0-only GPL-3.0-or-later",),
            )
        yield path
