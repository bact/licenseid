# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The public form of a match, and its two output lines.

A tier's record carries its ranking state: a raw score on a scale of its
own (a tag 1.0, an exact ID or name 1.0 or 1.02, a name that only shares
the input's words 1.01, a text match up to about 1.08 with its bonuses)
and, for a text match, the aligned window and the popularity and
deprecation keys. The public form keeps what a reader can use, the same
keys for every method.
"""

from licenseid.types import InternalMatch, LicenseMatch, RawMatch

# Digits kept in score, similarity and coverage: the text output prints
# four, so JSON and text agree.
_DIGITS = 4


def _rounded(value: float | None) -> float | None:
    # + 0.0 turns -0.0 into 0.0, which text prints as "-0.0000" but JSON as 0.
    return None if value is None else round(value, _DIGITS) + 0.0


def public_result(raw: RawMatch | InternalMatch) -> LicenseMatch:
    """*raw* as match() returns it. The ranking key is capped to 0-1: above
    1 it only orders a tier's own results, and the order is in the list."""
    return LicenseMatch(
        license_id=raw["license_id"],
        method=raw["method"],
        exact=bool(raw["exact"]),
        score=round(max(0.0, min(raw["score"], 1.0)), _DIGITS),
        similarity=_rounded(raw["similarity"]),
        coverage=_rounded(raw["coverage"]),
        is_spdx=bool(raw.get("is_spdx", False)),
        is_osi_approved=bool(raw.get("is_osi_approved", False)),
        is_fsf_libre=bool(raw.get("is_fsf_libre", False)),
    )


def json_line(result: LicenseMatch) -> str:
    """*result* as one line of JSON Lines, in the JSON Canonicalization
    Scheme (RFC 8785): sorted keys, no white space, ECMAScript numbers (1.0
    is 1), so equal results print equal bytes. Every key and value is
    ASCII: an ID is, and no licence text is in a result."""
    # Only --json needs it, so match() and the API do not import it.
    import rfc8785  # pylint: disable=import-outside-toplevel

    fields: dict[str, str | float | bool | None] = {
        "license_id": result["license_id"],
        "method": result["method"],
        "exact": result["exact"],
        "score": result["score"],
        "similarity": result["similarity"],
        "coverage": result["coverage"],
        "is_spdx": result["is_spdx"],
        "is_osi_approved": result["is_osi_approved"],
        "is_fsf_libre": result["is_fsf_libre"],
    }
    return rfc8785.dumps(fields).decode("utf-8")


def text_line(result: LicenseMatch) -> str:
    """*result* as KEY=VALUE fields on one line; a value nothing measured
    is empty (``SIMILARITY=``), so every line has the same fields."""

    def number(value: float | None) -> str:
        return "" if value is None else f"{value:.{_DIGITS}f}"

    return (
        f"LICENSE_ID={result['license_id']} METHOD={result['method']} "
        f"EXACT={str(result['exact']).lower()} "
        f"SCORE={number(result['score'])} "
        f"SIMILARITY={number(result['similarity'])} "
        f"COVERAGE={number(result['coverage'])}"
    )
