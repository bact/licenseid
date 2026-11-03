# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID detection package.
"""

__version__ = "0.7.0"

from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
)
from licenseid.keptdetector import detect
from licenseid.resolver import match
from licenseid.resolvertypes import (
    Category,
    ListInfo,
    ListSource,
    Operand,
    Resolution,
    Source,
    Step,
    Trust,
)
from licenseid.result import json_line
from licenseid.types import Detection, Method
from licenseid.warning import LicenseIdWarning

# LicenseDatabase is exported as an opaque handle: open one to pass to
# match(db=...) or LicenseDetector, never to query (P2 of the contract batch).
__all__ = [
    "Category",
    "DatabaseNotReadyError",
    "Detection",
    "InvalidInputError",
    "LicenseDatabase",
    "LicenseDetector",
    "LicenseIdError",
    "LicenseIdWarning",
    "ListInfo",
    "ListSource",
    "Method",
    "Operand",
    "Resolution",
    "Source",
    "Step",
    "Trust",
    "detect",
    "get_default_db_path",
    "json_line",
    "match",
]
