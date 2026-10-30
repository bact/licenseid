# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID detection package.
"""

__version__ = "0.6.0"

from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
)
from licenseid.keptdetector import detect
from licenseid.normalize import normalize_text
from licenseid.resolver import match
from licenseid.types import Detection, DetectRequest, Method

__all__ = [
    "DatabaseNotReadyError",
    "DetectRequest",
    "Detection",
    "InvalidInputError",
    "LicenseDatabase",
    "LicenseDetector",
    "LicenseIdError",
    "Method",
    "detect",
    "get_default_db_path",
    "match",
    "normalize_text",
]
