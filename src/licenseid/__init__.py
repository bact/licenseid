# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID detection package.
"""

__version__ = "0.9.4"

from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
)
from licenseid.keptdetector import detect, texts
from licenseid.resolver import resolve
from licenseid.resolvertypes import (
    Category,
    ListInfo,
    ListSource,
    Operand,
    Resolution,
    Source,
    Step,
    ToolInfo,
    Trust,
)
from licenseid.result import json_line
from licenseid.types import Detection, DetectOptions, Method, Variant
from licenseid.warning import LicenseIdWarning

# LicenseDatabase is exported as an opaque handle: open one to pass to
# resolve(db=...) or LicenseDetector, never to query.
__all__ = [
    "Category",
    "DatabaseNotReadyError",
    "DetectOptions",
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
    "ToolInfo",
    "Trust",
    "Variant",
    "detect",
    "get_default_db_path",
    "json_line",
    "resolve",
    "texts",
]
