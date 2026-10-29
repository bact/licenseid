# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The SPDX License List in memory, for ``resolve()`` with no database.

:class:`ListIndex` answers the reads of
:class:`licenseid.listlookup.ListLookup` from one
:class:`licenseid.spdxdata.SpdxData`, as ``LicenseDatabase`` answers them
from the rows ``licenseid.records`` builds of the same release:

- the licences kept are the ones the database keeps
  (:func:`licenseid.listrules.kept_licenses`: a text, or deprecated), with
  the same successors; the exceptions are all kept, with
  :func:`licenseid.listrules.exception_successor`;
- an ID is stripped and folded with :func:`licenseid.listlookup.fold_case`,
  as SQLite's NOCASE folds it, and the first entry in list order wins, as
  the first row does;
- ``get_active_ids_by_name`` is built from the kept licences only, as the
  database's is from its rows: an ID in use with no text is not kept, even
  where it is the successor of a rename (``listrules.kept_licenses``).

IDs and names only: no texts (dropped once the index is built, about 5 MiB),
no popularity and no word count (normalising every text costs about 1.2 s).

:func:`packaged_index` loads the bundle shipped in the wheel once per
process. Standard library and ``licenseid`` only: no ``requests`` on this
path.
"""

import contextlib
import threading
from collections.abc import Callable

from licenseid import spdxdata
from licenseid.console import warn
from licenseid.listlookup import (
    ListedException,
    ListedLicense,
    ListedMetadata,
    ListedName,
    fold_case,
)
from licenseid.listrules import (
    active_exceptions_by_name,
    exception_successor,
    is_deprecated,
    kept_licenses,
)
from licenseid.spdxdata import SpdxData

__all__ = ["ListIndex", "packaged_index", "packaged_problem", "reset_packaged_index"]


class ListIndex:
    """One release of the SPDX License List as a
    :class:`licenseid.listlookup.ListLookup`, in memory."""

    def __init__(self, data: SpdxData) -> None:
        #: The version of the List, as the bundle states it.
        self.version = data.version
        self._licenses: dict[str, ListedLicense] = {}  # by folded ID
        self._rows: list[ListedName] = []  # the kept licences, in list order
        self._active_by_name: dict[str, list[str]] = {}
        self._deprecated: dict[str, str] = {}
        self._keyed: tuple[Callable[[str], str], dict[str, list[ListedName]]] | None
        self._keyed = None
        self._add_licenses(data)
        self._exceptions: dict[str, ListedException] = {}  # by folded ID
        self._add_exceptions(data)
        self._metadata: ListedMetadata = {
            "license_list_version": data.version,
            "release_date": data.release_date or "",
        }

    def _add_licenses(self, data: SpdxData) -> None:
        """The kept licences, each read as its database row is."""
        kept = kept_licenses(
            data.licenses, lambda license_id: data.texts.get(license_id) is not None
        )
        for lic, successor in kept:
            license_id, deprecated = lic["licenseId"], is_deprecated(lic)
            row: ListedLicense = {"license_id": license_id, "is_deprecated": deprecated}
            if successor is not None:
                row["superseded_by"] = successor
                self._deprecated.setdefault(license_id, successor)
            self._licenses.setdefault(fold_case(license_id), row)
            self._rows.append({"license_id": license_id, "is_deprecated": deprecated})
            if not deprecated:
                by_name = self._active_by_name.setdefault(lic["name"].casefold(), [])
                by_name.append(license_id)

    def _add_exceptions(self, data: SpdxData) -> None:
        """Every exception; a deprecated one points to the exception in use
        of the same name. Its successor goes into the deprecated mappings
        after the licences', and wins a clash, as in the database."""
        by_name = active_exceptions_by_name(data.exceptions)
        for exc in data.exceptions:
            exception_id = exc["licenseExceptionId"]
            row: ListedException = {
                "exception_id": exception_id,
                "is_deprecated": is_deprecated(exc),
            }
            successor = exception_successor(exc, by_name)
            if successor is not None:
                row["superseded_by"] = successor
                self._deprecated[exception_id] = successor
            self._exceptions.setdefault(fold_case(exception_id), row)

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One block of reads: nothing to open or close in memory."""
        return contextlib.nullcontext()

    def get_license_details(self, license_id: str) -> ListedLicense | None:
        """The licence *license_id* names, in any ASCII case, or None."""
        row = self._licenses.get(fold_case(license_id.strip()))
        return None if row is None else row.copy()

    def get_exception_details(self, exception_id: str) -> ListedException | None:
        """The exception *exception_id* names, in any ASCII case, or None."""
        row = self._exceptions.get(fold_case(exception_id.strip()))
        return None if row is None else row.copy()

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> dict[str, list[ListedName]]:
        """The kept licences by *key* of each ID, in list order. One key is
        kept; a call with another builds it again."""
        keyed = self._keyed
        if keyed is None or keyed[0] is not key:
            index: dict[str, list[ListedName]] = {}
            for row in self._rows:
                index.setdefault(key(row["license_id"]), []).append(row)
            keyed = self._keyed = (key, index)
        return keyed[1]

    def get_active_ids_by_name(self) -> dict[str, list[str]]:
        """The kept licence IDs in use by case-folded name."""
        return self._active_by_name

    def get_deprecated_mappings(self) -> dict[str, str]:
        """Each deprecated ID that has a successor, with it: the licences in
        list order, then the exceptions (an exception wins a clash)."""
        return self._deprecated

    def get_metadata(self) -> ListedMetadata:
        """The version of the List and its release date (``""`` if none)."""
        return self._metadata.copy()


# The packaged index of this process, or why there is none ("not found",
# "invalid: <detail>"), once loaded; the lock makes it one load.
_LOCK = threading.Lock()
_loaded: list[ListIndex | str] = []


def packaged_index() -> ListIndex | None:
    """The index of the bundle shipped in the wheel, loaded at the first call
    of the process; None when there is none (an editable install, a wheel
    built with ``LICENSEID_BUNDLE=skip``) or it is unusable. An unusable one
    warns once: ``spdx-bundle.json.gz: invalid: <detail>``."""
    found = _packaged()
    return found if isinstance(found, ListIndex) else None


def packaged_problem() -> str:
    """Why there is no packaged index (``not found``, ``invalid: <detail>``);
    ``""`` when there is one."""
    found = _packaged()
    return "" if isinstance(found, ListIndex) else found


def reset_packaged_index() -> None:
    """Forget the packaged index, for a test that ships another bundle."""
    with _LOCK:
        _loaded.clear()


def _packaged() -> ListIndex | str:
    """The packaged index or why there is none, loaded once."""
    with _LOCK:
        if not _loaded:
            _loaded.append(_load_packaged())
        return _loaded[0]


def _load_packaged() -> ListIndex | str:
    """Read the shipped bundle: through the module, so a test can patch
    ``spdxdata.packaged_bundle``."""
    raw = spdxdata.packaged_bundle()
    if raw is None:
        return "not found"
    try:
        data = SpdxData.from_bundle(raw, None)
    except spdxdata.BundleError as exc:
        problem = f"invalid: {exc}"
        warn(f"{spdxdata.PACKAGED_NAME}: {problem}")
        return problem
    return ListIndex(data)
