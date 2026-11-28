# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SPDX License ID detection package.
"""

__version__ = "0.10.0"

import importlib
import typing

if typing.TYPE_CHECKING:  # the names below load at use: see __getattr__
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

# Each public name and the module that defines it. A name is imported at its
# first use (start-up: `import licenseid` loads no detector, no RapidFuzz, no
# SQLite). A new public name goes here and in __all__ below.
_HOME = {
    "Category": "resolvertypes",
    "DatabaseNotReadyError": "errors",
    "DetectOptions": "types",
    "Detection": "types",
    "InvalidInputError": "errors",
    "LicenseDatabase": "database",
    "LicenseDetector": "detector",
    "LicenseIdError": "errors",
    "LicenseIdWarning": "warning",
    "ListInfo": "resolvertypes",
    "ListSource": "resolvertypes",
    "Method": "types",
    "Operand": "resolvertypes",
    "Resolution": "resolvertypes",
    "Source": "resolvertypes",
    "Step": "resolvertypes",
    "ToolInfo": "resolvertypes",
    "Trust": "resolvertypes",
    "Variant": "types",
    "detect": "keptdetector",
    "get_default_db_path": "datadir",
    "json_line": "result",
    "resolve": "resolver",
    "texts": "keptdetector",
}


if not typing.TYPE_CHECKING:
    # Hidden from type checkers: they read the imports above, so a misspelt
    # public name is an error there, not an `object`.

    def __getattr__(name: str) -> object:
        """PEP 562: import a public name's module at its first use and keep
        the name on this module, so the next lookup never comes here. Two
        threads may both come here: both read the same object from a module
        Python imports once, so the assignment is safe."""
        home = _HOME.get(name)
        if home is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        value: object = getattr(importlib.import_module(f"licenseid.{home}"), name)
        globals()[name] = value
        return value


def __dir__() -> list[str]:
    """The public names, loaded or not."""
    return sorted({*globals(), *_HOME})


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
