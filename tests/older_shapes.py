# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Older shapes of a licence database, made from a file of this build.

Until build 9 (0.9.x, and 0.10.0's own builds 8 and 9) the texts were in the
FTS5 table ``license_index``, with a trigram index nothing reads since build
10: :data:`TO_FTS` moves them back there. :func:`rename_shadow` damages that
table the way a file can be damaged without SQLite's help (a defensive
SQLite refuses to drop or write a shadow table): it renames one shadow
table in the file's bytes, so the FTS5 table misses it."""

from pathlib import Path

# The texts in the FTS5 table of 0.9.x, in their order, and no plain table.
TO_FTS = (
    "CREATE VIRTUAL TABLE license_index USING fts5("
    "license_id UNINDEXED, search_text, tokenize = 'trigram');"
    " INSERT INTO license_index (license_id, search_text)"
    " SELECT license_id, search_text FROM license_texts ORDER BY text_id;"
    " DROP TABLE license_texts;"
)
# A file of 0.9.4 (build 7): the FTS5 table, no postings, no checks.
BUILD_7 = (
    TO_FTS + " DROP TABLE text_postings; DROP TABLE text_posting_ids;"
    " DROP TABLE text_code_checks;"
    " DELETE FROM db_metadata WHERE key IN ('text_postings', 'text_postings_update');"
    " UPDATE db_metadata SET value = '7' WHERE key = 'build_version'"
)
# The shadow tables of the FTS5 table, each of which a file may lack.
SHADOWS = ("config", "content", "data", "docsize", "idx")


def rename_shadow(path: Path, shadow: str) -> None:
    """Rename the shadow table ``license_index_<shadow>`` of the file at
    *path* in its bytes (one letter, so every record keeps its length): the
    FTS5 table then misses it, and a table of another name is left."""
    name = f"license_index_{shadow}".encode()
    data = path.read_bytes()
    if name not in data:
        raise ValueError(f"no {name!r} in {path}")
    path.write_bytes(data.replace(name, name[:-1] + b"Q"))
