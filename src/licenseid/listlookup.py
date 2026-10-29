# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The reads the resolver makes of an SPDX License List.

The resolver chain (``resolver``, ``looseid``, ``versionkey`` and
``identifiers.normalize_identifier``) types its list as ``ListLookup``, not as
``licenseid.database.LicenseDatabase``. The database satisfies the protocol
unchanged, and so does the in-memory ``licenseid.listindex.ListIndex``, so
the resolver needs no database file.

Standard library and ``licenseid.types`` only: no import of the database, so
no import cycle.
"""

import contextlib
import string
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypedDict

from typing_extensions import Required

_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def fold_case(value: str) -> str:
    """*value* with ASCII letters lowercased, as SQLite's NOCASE compares.

    ``str.lower`` folds more: the KELVIN SIGN would become ``k``.
    """
    return value.translate(_ASCII_LOWER)


class ListedLicense(TypedDict, total=False):
    """The fields of a licence row that the resolver chain reads. The
    database's ``LicenseDetails`` satisfies it; so can an index that has no
    popularity or word count. ``superseded_by`` is absent when the ID has
    no successor, and a database row holds ``None`` there (typed ``str``, as
    ``LicenseDetails`` is): read it as a truth value."""

    license_id: Required[str]
    is_deprecated: bool
    superseded_by: str


class ListedException(TypedDict, total=False):
    """The fields of an exception row that the resolver chain reads (the
    database's ``ExceptionDetails`` satisfies it)."""

    exception_id: Required[str]
    is_deprecated: Required[bool]
    superseded_by: str


class ListedName(TypedDict):
    """The fields of a licence row found by key that the resolver chain
    reads (the database's ``LicenseNameId`` satisfies it)."""

    license_id: str
    is_deprecated: bool


class ListedMetadata(TypedDict, total=False):
    """The metadata the resolver reads (the database's ``DatabaseMetadata``
    satisfies it). ``release_date`` is ``""`` when the list did not say."""

    license_list_version: str
    release_date: str


class ListLookup(Protocol):
    """What the resolver reads of a licence list.

    The contract an implementation copies from ``LicenseDatabase``:

    - Both ID lookups strip surrounding white space from the ID.
    - IDs compare with ASCII case folding only, as SQLite's NOCASE does
      (``fold_case``), never ``str.lower`` or ``str.casefold``: the KELVIN
      SIGN is not a ``k``.
    - ``get_deprecated_mappings`` returns only the deprecated IDs that have a
      successor: the licences in table order, then the exceptions; on a clash
      an exception wins the key.
    - ``get_metadata`` has no ``license_list_version`` key when the list does
      not say. Its ``release_date`` is ``""`` when the list did not say it
      (the resolver does not read it).
    - The return types hold the fields the resolver chain reads, no more, so
      an index need not invent a popularity or a word count. A caller that
      needs the flags (``identifiers.flag_source``) takes a ``LicenseDatabase``.
    - ``get_active_ids_by_name`` is keyed by ``str.casefold()`` of the name.
    """

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One block of queries (one resolution)."""

    def get_license_details(self, license_id: str) -> ListedLicense | None:
        """The row of a licence (ASCII case-insensitive lookup)."""

    def get_exception_details(self, exception_id: str) -> ListedException | None:
        """The row of an exception (case-insensitive lookup)."""

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> Mapping[str, Sequence[ListedName]]:
        """The licence rows grouped by *key* of each ID."""

    def get_active_ids_by_name(self) -> dict[str, list[str]]:
        """The licence IDs in use by case-folded name."""

    def get_deprecated_mappings(self) -> dict[str, str]:
        """Each deprecated ID that has a successor, with it: the licences in
        table order, then the exceptions (an exception wins a clash)."""

    def get_metadata(self) -> ListedMetadata:
        """The list's metadata (``license_list_version``)."""
