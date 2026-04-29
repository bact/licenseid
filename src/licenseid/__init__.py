# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID matcher package.
"""

__version__ = "0.1.0"

from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.database import LicenseDatabase
from licenseid.normalize import normalize_text
from licenseid.types import LicenseMatch, MatchRequest

__all__ = [
    "AggregatedLicenseMatcher",
    "LicenseDatabase",
    "LicenseMatch",
    "MatchRequest",
    "normalize_text",
]
