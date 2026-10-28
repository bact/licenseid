# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The reads the resolver makes of an SPDX License List.

The resolver chain (``resolver``, ``looseid``, ``versionkey`` and
``identifiers.normalize_identifier``) types its list as ``ListLookup``, not as
``licenseid.database.LicenseDatabase``. The database satisfies the protocol
unchanged; an in-memory index will too in 0.7.0, so the resolver needs no
database file.

Standard library and ``licenseid.types`` only: no import of the database, so
no import cycle.
"""

import contextlib
import string
from collections.abc import Callable
from typing import Protocol

from licenseid.types import (
    DatabaseMetadata,
    ExceptionDetails,
    LicenseDetails,
    LicenseNameId,
)

_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def fold_case(value: str) -> str:
    """*value* with ASCII letters lowercased, as SQLite's NOCASE compares.

    ``str.lower`` folds more: the KELVIN SIGN would become ``k``.
    """
    return value.translate(_ASCII_LOWER)


class ListLookup(Protocol):
    """What the resolver reads of a licence list.

    The contract an implementation copies from ``LicenseDatabase``:

    - Both ID lookups strip surrounding white space from the ID.
    - IDs compare with ASCII case folding only, as SQLite's NOCASE does
      (``fold_case``), never ``str.lower`` or ``str.casefold``: the KELVIN
      SIGN is not a ``k``.
    - ``get_deprecated_mappings`` covers licence and exception IDs.
    - ``get_active_ids_by_name`` is keyed by ``str.casefold()`` of the name.
    """

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One block of queries (one resolution)."""

    def get_license_details(self, license_id: str) -> LicenseDetails | None:
        """Full metadata for a licence (ASCII case-insensitive lookup)."""

    def get_exception_details(self, exception_id: str) -> ExceptionDetails | None:
        """Full metadata for an exception (case-insensitive lookup)."""

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> dict[str, list[LicenseNameId]]:
        """The licence rows grouped by *key* of each ID."""

    def get_active_ids_by_name(self) -> dict[str, list[str]]:
        """The licence IDs in use by case-folded name."""

    def get_deprecated_mappings(self) -> dict[str, str]:
        """All deprecated IDs, each with its successor."""

    def get_metadata(self) -> DatabaseMetadata:
        """The list's metadata (``license_list_version``)."""
