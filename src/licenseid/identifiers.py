# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX Identifier and Expression normalization and validation.
"""

import re
from typing import Optional

from licenseid.database import LicenseDatabase

# Deprecated SPDX License IDs (pre-2.0 naming) mapped to their canonical
# successors.
# Plain version (e.g. GPL-2.0) -> -only; "+" suffix -> -or-later.
DEPRECATED_SPDX_LICENSE_IDS: dict[str, str] = {
    "GPL-1.0": "GPL-1.0-only",
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "LGPL-2.0": "LGPL-2.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPL-3.0": "LGPL-3.0-only",
    "AGPL-1.0": "AGPL-1.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
    "GPL-1.0+": "GPL-1.0-or-later",
    "GPL-2.0+": "GPL-2.0-or-later",
    "GPL-3.0+": "GPL-3.0-or-later",
    "LGPL-2.0+": "LGPL-2.0-or-later",
    "LGPL-2.1+": "LGPL-2.1-or-later",
    "LGPL-3.0+": "LGPL-3.0-or-later",
    "AGPL-1.0+": "AGPL-1.0-or-later",
    "AGPL-3.0+": "AGPL-3.0-or-later",
}

# Mapping of deprecated "-with-" IDs to their modern counterparts
DEPRECATED_WITH_IDS: dict[str, str] = {
    "GPL-2.0-with-font-exception": "GPL-2.0-only WITH Font-exception-2.0",
    "GPL-2.0-with-GCC-exception": "GPL-2.0-only WITH GCC-exception-2.0",
    "GPL-2.0-with-autoconf-exception": "GPL-2.0-only WITH Autoconf-exception-2.0",
    "GPL-2.0-with-bison-exception": "GPL-2.0-only WITH Bison-exception-2.2",
    "GPL-3.0-with-autoconf-exception": "GPL-3.0-only WITH Autoconf-exception-3.0",
    "GPL-3.0-with-GCC-exception": "GPL-3.0-only WITH GCC-exception-3.1",
}


def normalize_identifier(identifier: str, db: Optional[LicenseDatabase] = None) -> str:
    """
    Normalises a single SPDX License ID or a full License Expression.
    """
    if not identifier:
        return identifier

    # 1. Handle full expression parsing if AND/OR/WITH/+/( are present
    upper_ident = identifier.upper()
    if any(op in upper_ident for op in ["AND", "OR", "WITH", "+", "("]):
        return _normalize_expression(identifier, db)

    # 2. Handle single ID normalization
    return _normalize_single_id(identifier, db)


def _normalize_single_id(lic_id: str, db: Optional[LicenseDatabase] = None) -> str:
    """Normalises a single license or exception ID."""
    # 1. Database lookup (most accurate/up-to-date)
    if db:
        mappings = db.get_deprecated_mappings()
        normalized = mappings.get(lic_id)
        if not normalized:
            # Case-insensitive search in mappings
            lic_id_upper = lic_id.upper()
            for dep_id, canonical in mappings.items():
                if dep_id.upper() == lic_id_upper:
                    normalized = canonical
                    break

        if normalized:
            return normalized

    # 2. Hardcoded fallback (fast path and legacy "+" conventions)
    normalized = DEPRECATED_SPDX_LICENSE_IDS.get(lic_id)
    lic_id_upper = lic_id.upper()

    if not normalized:
        for dep_id, canonical in DEPRECATED_SPDX_LICENSE_IDS.items():
            if dep_id.upper() == lic_id_upper:
                normalized = canonical
                break

    if not normalized:
        normalized = DEPRECATED_WITH_IDS.get(lic_id)
        if not normalized:
            lic_id_lower = lic_id.lower()
            for dep_id, canonical in DEPRECATED_WITH_IDS.items():
                if dep_id.lower() == lic_id_lower:
                    normalized = canonical
                    break

    if normalized:
        return normalized

    # 3. Canonical-case lookup: the DB uses COLLATE NOCASE, so we can retrieve
    # the correctly-cased ID for any known (non-deprecated) license.
    if db:
        details = db.get_license_details(lic_id)
        if details:
            return details["license_id"]

    return lic_id


def _normalize_expression(expression: str, db: Optional[LicenseDatabase] = None) -> str:
    """Parses and normalises an SPDX License Expression."""
    # Tokenize: keeping separators and identifiers
    # Identifiers can contain letters, numbers, dots, and hyphens.
    # "+" is a separate operator that attaches to an ID.
    tokens = re.findall(
        r"\(|\)|AND|OR|WITH|\+|[a-zA-Z0-9.-]+", expression, re.IGNORECASE
    )

    # 1. Pre-process to attach "+" to identifiers
    # This ensures "GPL-2.0" "+" becomes "GPL-2.0+" before normalization
    combined_tokens = []
    i = 0
    while i < len(tokens):
        if (
            i + 1 < len(tokens)
            and tokens[i + 1] == "+"
            and tokens[i] not in ("(", ")", "AND", "OR", "WITH")
        ):
            combined_tokens.append(tokens[i] + "+")
            i += 2
        else:
            combined_tokens.append(tokens[i])
            i += 1

    normalized_tokens = []
    for token in combined_tokens:
        upper_token = token.upper()
        if upper_token in ("AND", "OR", "WITH"):
            normalized_tokens.append(upper_token)
        elif token in ("(", ")"):
            normalized_tokens.append(token)
        else:
            # It's an identifier (possibly with + already attached)
            normalized_tokens.append(_normalize_single_id(token, db))

    # Reconstruct the expression with proper spacing
    # result will contain tokens that should be joined with spaces if needed
    result = []
    for i, token in enumerate(normalized_tokens):
        result.append(token)

    # Join with spaces, but handle parentheses carefully
    expr = ""
    for i, part in enumerate(result):
        if i == 0:
            expr = part
        elif part == ")":
            expr += part
        elif result[i - 1] == "(":
            expr += part
        else:
            expr += " " + part

    return expr
