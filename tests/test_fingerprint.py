# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for fingerprint.compute_idf_fingerprints()."""
# pylint: disable=missing-function-docstring

import json
import os
import subprocess
import sys

import pytest

from licenseid.fingerprint import compute_idf_fingerprints, extract_ngrams

_TEXT_A = "permission is hereby granted free of charge to any person"
_TEXT_B = "redistribution and use in source and binary forms are permitted"


@pytest.mark.parametrize(
    "rows",
    [[], [("MIT", _TEXT_A)]],
    ids=["empty_corpus", "single_license"],
)
def test_corpus_too_small_to_discriminate_gives_no_fingerprints(
    rows: list[tuple[str, str]],
) -> None:
    """Regression: one license made max_idf = log(1) = 0 and raised
    ZeroDivisionError."""
    assert not compute_idf_fingerprints(rows)


def test_identical_texts_have_no_discriminative_ngrams() -> None:
    assert not compute_idf_fingerprints([("A", _TEXT_A), ("B", _TEXT_A)])


def test_distinct_texts_get_positive_normalised_scores() -> None:
    records = compute_idf_fingerprints([("A", _TEXT_A), ("B", _TEXT_B)])
    assert {lid for lid, _, _ in records} == {"A", "B"}
    assert all(0.0 < score <= 1.0 for _, _, score in records)


# 30 words give 26 distinct 5-grams, each in one text only: all tie at the top
# score, and a licence keeps 20 of them.
_LONG = " ".join(f"w{i}" for i in range(30))

_SCRIPT = f"""
import json
from licenseid.fingerprint import compute_idf_fingerprints
rows = [("A", {_LONG!r}), ("B", {_TEXT_B!r})]
print(json.dumps(compute_idf_fingerprints(rows)))
"""


def _run_under_hash_seed(seed: int) -> list[list[object]]:
    """The fingerprints of a small corpus, from a fresh process whose string
    hashing (and so set order) is fixed by *seed*."""
    env = {**os.environ, "PYTHONHASHSEED": str(seed)}
    out = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)  # type: ignore[no-any-return]


def test_fingerprints_do_not_depend_on_the_hash_seed() -> None:
    """Regression: tied n-grams were kept in set order, which changes per
    process, so two builds of one release stored different fingerprints."""
    runs = {json.dumps(_run_under_hash_seed(seed)) for seed in range(1, 6)}
    assert len(runs) == 1


def test_tied_ngrams_are_kept_in_alphabetical_order() -> None:
    records = compute_idf_fingerprints([("A", _LONG), ("B", _TEXT_B)])
    kept = [ngram for lid, ngram, _ in records if lid == "A"]
    every = sorted(extract_ngrams(_LONG))
    assert kept == every[:20]
