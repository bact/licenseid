# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID matcher package.
"""

__version__ = "0.4.2"

from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
)
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text
from licenseid.types import LicenseMatch, MatchRequest, Method

__all__ = [
    "AggregatedLicenseMatcher",
    "DatabaseNotReadyError",
    "InvalidInputError",
    "LicenseDatabase",
    "LicenseIdError",
    "LicenseMatch",
    "MatchRequest",
    "Method",
    "get_default_db_path",
    "normalize_text",
]
