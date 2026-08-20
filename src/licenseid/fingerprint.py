# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Pure n-gram/IDF math for the discriminative license fingerprint index.

Split out of ``database.py`` so the SQL-facing module stays focused on
schema and query methods; this module has no SQLite dependency and can
be unit-tested directly.
"""

import math
from collections import Counter

# Discriminative n-gram fingerprint settings.
# Each license keeps its top FINGERPRINT_TOP_N highest-IDF word n-grams
# (n = FINGERPRINT_N) as a compact discriminative signature.  At query time
# a single indexed SQL lookup finds which candidates share at least one
# fingerprint n-gram with the query, allowing the ranker to boost them
# without a full RapidFuzz string comparison.
FINGERPRINT_N: int = 5  # word n-gram size
FINGERPRINT_TOP_N: int = 20  # fingerprints stored per license


def extract_ngrams(search_text: str, n: int = FINGERPRINT_N) -> list[str]:
    """Return the ``n``-word n-grams of *search_text*, in order."""
    tokens = search_text.split()
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def compute_idf_fingerprints(
    rows: list[tuple[str, str]],
    n: int = FINGERPRINT_N,
    top_n: int = FINGERPRINT_TOP_N,
) -> list[tuple[str, str, float]]:
    """Compute top discriminative n-gram fingerprints per license.

    *rows* is ``(license_id, search_text)`` pairs for the whole corpus.
    IDF is computed across the corpus so that n-grams shared by many
    licenses score near 0 and n-grams unique to one license score near 1.
    Returns ``(license_id, ngram, idf_norm)`` records, ``idf_norm > 0``
    only, top ``top_n`` per license.
    """
    if not rows:
        return []

    k = len(rows)
    # IDF of an n-gram that appears in exactly one license = log(k/1) = log(k).
    # Dividing by log(k) normalises scores to [0, 1].
    max_idf = math.log(k)

    license_ngrams: dict[str, set[str]] = {}
    doc_freq: Counter[str] = Counter()
    for license_id, search_text in rows:
        ngrams = set(extract_ngrams(search_text, n))
        if ngrams:
            license_ngrams[license_id] = ngrams
            doc_freq.update(ngrams)

    fp_records: list[tuple[str, str, float]] = []
    for license_id, ngrams in license_ngrams.items():
        scored = sorted(
            (
                (ng, math.log(k / doc_freq[ng]) / max_idf)
                for ng in ngrams
                if doc_freq[ng] > 0
            ),
            key=lambda x: -x[1],
        )
        for ng, idf_norm in scored[:top_n]:
            if idf_norm > 0.0:
                fp_records.append((license_id, ng, idf_norm))

    return fp_records
