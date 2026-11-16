# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""In-memory database for ``bench_single.py``, built from the SPDX tarball.

Import only after the source tree under test is on ``sys.path``.
"""

import json
import sqlite3
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase
from licenseid.normalize import normalize_text

# The order of the values in a ``licenses`` row built by ``_license_row``.
ALL_COLUMNS: tuple[str, ...] = (
    "license_id",
    "name",
    "is_spdx",
    "is_osi_approved",
    "is_fsf_libre",
    "is_high_usage",
    "is_deprecated",
    "superseded_by",
    "pop_score",
    "word_count",
)

Rows = tuple[list[tuple[Any, ...]], list[tuple[str, str]], dict[str, str]]


def find_tarball() -> Path:
    """Return the SPDX tarball path, preferring the newest cached version."""
    candidates = sorted(Path.home().glob(".local/share/licenseid/spdx-data-v*.tar.gz"))
    if not candidates:
        print(
            json.dumps(
                {
                    "error": "No SPDX tarball found in ~/.local/share/licenseid/."
                    " Run 'licenseid update' or pass --tarball PATH."
                }
            )
        )
        sys.exit(1)
    return candidates[-1]  # lexicographic sort → newest version last


def _license_row(
    lic: dict[str, Any], active_ids: set[str], raw_text: str
) -> tuple[tuple[Any, ...], str]:
    """Return the ``licenses`` row of *lic* and its normalised text."""
    license_id: str = lic["licenseId"]
    is_deprecated: bool = bool(lic.get("isDeprecatedLicenseId", False))
    superseded_by: str | None = None
    if is_deprecated and license_id.endswith("+"):
        or_later = license_id[:-1] + "-or-later"
        if or_later in active_ids:
            superseded_by = or_later

    is_osi: bool = bool(lic.get("isOsiApproved", False))
    is_fsf: bool = bool(lic.get("isFsfLibre", False))
    # Use a modest baseline; popularity CSV is not downloaded for
    # benchmarks.  The exact pop_score does not affect recall metrics.
    pop_score: int = 100 if (is_osi or is_fsf) else 1

    normalized = normalize_text(raw_text)
    row = (
        license_id,
        lic.get("name", ""),
        True,  # is_spdx
        is_osi,
        is_fsf,
        is_osi or is_fsf,  # is_high_usage
        is_deprecated,
        superseded_by,
        pop_score,
        len(normalized.split()),
    )
    return row, normalized


def _read_rows(root_dir: Path) -> Rows:
    """Read the licence rows from an extracted SPDX data directory."""
    to_insert_licenses: list[tuple[Any, ...]] = []
    to_insert_index: list[tuple[str, str]] = []
    safe_to_canon: dict[str, str] = {}

    with open(root_dir / "json" / "licenses.json", "r", encoding="utf-8") as fh:
        licenses_list: list[dict[str, Any]] = json.load(fh).get("licenses", [])

    # Pre-compute active IDs to resolve superseded_by at index time,
    # mirroring the logic in LicenseDatabase._update_db_records().
    active_ids: set[str] = {
        lic["licenseId"]
        for lic in licenses_list
        if not lic.get("isDeprecatedLicenseId", False)
    }

    for lic in licenses_list:
        license_id: str = lic["licenseId"]
        text_path = root_dir / "text" / f"{license_id}.txt"
        if not text_path.exists():
            continue
        with open(text_path, "r", encoding="utf-8") as fh:
            raw_text = fh.read()
        row, normalized = _license_row(lic, active_ids, raw_text)
        to_insert_licenses.append(row)
        to_insert_index.append((license_id, normalized))
        safe_to_canon[license_id.replace(" ", "_").replace("/", "_")] = license_id
    return to_insert_licenses, to_insert_index, safe_to_canon


def build_rows(tar_path: Path) -> Rows:
    """Extract the SPDX tarball and return DB insertion data.

    Returns:
        to_insert_licenses: rows for the ``licenses`` table.
        to_insert_index: rows for the ``license_index`` table.
        safe_to_canon: filesystem-safe licence ID → canonical licence ID.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)
        return _read_rows(next(Path(tmp_dir).iterdir()))


def new_db_path(label: str) -> str:
    """Return a fresh in-memory SQLite URI."""
    db_name = f"bench_{label}_{uuid.uuid4().hex}"
    return f"file:{db_name}?mode=memory&cache=shared"


def _insert_licenses(
    conn: sqlite3.Connection, to_insert_licenses: list[tuple[Any, ...]]
) -> None:
    """Insert the ``licenses`` rows, only the columns this source tree has."""
    # Dynamically get columns for backward compatibility with 'main' branch
    columns = [row[1] for row in conn.execute("PRAGMA table_info(licenses)")]
    insert_cols = [c for c in ALL_COLUMNS if c in columns]
    col_indices = [ALL_COLUMNS.index(c) for c in insert_cols]
    filtered_licenses = [
        tuple(row[i] for i in col_indices) for row in to_insert_licenses
    ]
    placeholders = ", ".join(["?"] * len(insert_cols))
    col_names = ", ".join(insert_cols)
    conn.executemany(
        f"INSERT INTO licenses ({col_names}) VALUES ({placeholders})",
        filtered_licenses,
    )


def load_db(
    db_path: str,
    to_insert_licenses: list[tuple[Any, ...]],
    to_insert_index: list[tuple[str, str]],
) -> sqlite3.Connection:
    """Create the schema and fill the database at *db_path*.

    Returns the connection, which the caller keeps open: a shared-cache
    memory database dies with its last connection.
    """
    db_manager = LicenseDatabase(db_path)
    _ = db_manager

    conn = sqlite3.connect(db_path, uri=True)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("BEGIN TRANSACTION")
    try:
        _insert_licenses(conn, to_insert_licenses)
        conn.executemany(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            to_insert_index,
        )
        conn.executemany(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            [
                ("last_check_datetime", "2099-01-01T00:00:00"),
                ("license_list_version", "benchmark"),
                ("normalization_version", NORMALIZATION_VERSION),
            ],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return conn
