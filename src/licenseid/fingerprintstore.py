# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The fingerprint table: what ``update`` stores and what a match reads.

The scoring is in ``fingerprint.py`` (no SQLite there); this module is the
SQL side: the fingerprints ``update`` stores and the hits a match reads.
"""

from licenseid.console import status
from licenseid.dbconnection import Connections
from licenseid.fingerprint import compute_idf_fingerprints, extract_ngrams

_CHUNK = 500  # n-grams per query, well under SQLite's limit of 32,766 parameters


def store_fingerprints(connections: Connections) -> None:
    """Compute and store discriminative n-gram fingerprints for all licenses.

    See ``fingerprint.compute_idf_fingerprints`` for the scoring method.
    Must be called after ``license_index`` has been fully populated.
    Replaces any previously stored fingerprints.
    """
    status("Computing discriminative fingerprints...", end="")

    with connections.connection() as conn:
        rows: list[tuple[str, str]] = conn.execute(
            "SELECT license_id, search_text FROM license_index"
        ).fetchall()

    if not rows:
        status(" no data.")
        return

    fp_records = compute_idf_fingerprints(rows)

    with connections.connection(write=True) as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM license_fingerprints")
            conn.executemany(
                "INSERT INTO license_fingerprints (license_id, ngram, idf_norm)"
                " VALUES (?, ?, ?)",
                fp_records,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    status(f" {len(fp_records)} fingerprints for {len(rows)} licenses.")


def fingerprint_hits(connections: Connections, norm_input: str) -> dict[str, float]:
    """Return a map of ``license_id → max_idf_norm`` for fingerprint matches.

    The ``idf_norm`` value is in ``[0, 1]``: 1.0 means the matching n-gram
    appears in exactly one license in the corpus (maximally discriminative).

    Returns an empty dict when the table is empty, the input is too short to
    form any n-grams, or no n-grams match. The table always exists: opening a
    database creates it, so a failed query is a failed database and raises.
    """
    # Distinct n-grams, a chunk at a time: a text of 33,000 words would pass
    # more parameters than one SQL statement may hold.
    query_ngrams = list(dict.fromkeys(extract_ngrams(norm_input)))
    hits: dict[str, float] = {}
    for start in range(0, len(query_ngrams), _CHUNK):
        chunk = query_ngrams[start : start + _CHUNK]
        marks = ", ".join(["?"] * len(chunk))
        sql = (
            f"SELECT license_id, MAX(idf_norm) AS max_idf"
            f" FROM license_fingerprints"
            f" WHERE ngram IN ({marks})"
            f" GROUP BY license_id"
        )
        with connections.connection() as conn:
            for license_id, best in conn.execute(sql, chunk).fetchall():
                hits[license_id] = max(best, hits.get(license_id, 0.0))
    return hits
