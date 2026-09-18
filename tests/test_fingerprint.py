# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for fingerprint.compute_idf_fingerprints()."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.fingerprint import compute_idf_fingerprints

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
