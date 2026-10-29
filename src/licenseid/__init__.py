# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID matcher package.
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
from licenseid.normalize import normalize_text
from licenseid.resolver import resolve
from licenseid.types import Detection, DetectRequest, Method

__all__ = [
    "LicenseDetector",
    "DatabaseNotReadyError",
    "InvalidInputError",
    "LicenseDatabase",
    "LicenseIdError",
    "Detection",
    "DetectRequest",
    "Method",
    "get_default_db_path",
    "normalize_text",
    "resolve",
]
