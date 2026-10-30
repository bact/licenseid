# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.detect()``: one call on the database at the default path.

A :class:`licenseid.detector.LicenseDetector` costs a handful of connections
to build, and an outdated database warns when it is opened. So the function
keeps one detector while the default path and its file are the same (the
stamp ``licenseid.listsource.file_stamp`` reads), as ``listsource`` keeps
its choice of list, and says each build warning once per process, as
``match()`` does. A detector that could not be built is never kept, and
neither is one on a path with no file to stamp (an in-memory URI).
``reset()`` forgets the detector, for a test that swaps the home directory
or the file behind the default path.
"""

import threading
from typing import Any

from licenseid.datadir import get_default_db_path
from licenseid.detector import LicenseDetector
from licenseid.listsource import file_stamp, warn_once
from licenseid.types import Detection

# Held to look the detector up and to store it, never while building one: a
# build waits on SQLite and warns through ``warn_once``, which takes its own
# lock.
_LOCK = threading.Lock()
_kept: tuple[str, tuple[int, ...], LicenseDetector] | None = None


def detect(
    text: str | None = None,
    *,
    license_id: str | None = None,
    file_path: str | None = None,
    **options: Any,
) -> list[Detection]:
    """Detect the licence of a *text*, a file or a declared *license_id*.

    ``LicenseDetector(...).detect(...)`` on the database at the default
    path, with one detector kept while that file is unchanged. Raises
    :class:`licenseid.errors.DatabaseNotReadyError` when that database is
    not ready (missing, empty, invalid or unreadable), and
    :class:`licenseid.errors.InvalidInputError` as the method does.
    """
    return _detector().detect(
        text, license_id=license_id, file_path=file_path, **options
    )


def _detector() -> LicenseDetector:
    """The detector on the default database: the kept one, or a new one."""
    global _kept  # pylint: disable=global-statement
    path = get_default_db_path()
    stamp = file_stamp(path)  # before the build: a change meanwhile is seen
    if isinstance(stamp, Exception) or stamp is None:
        return LicenseDetector(path, report=warn_once)  # nothing to key by
    with _LOCK:
        kept = _kept
    if kept is not None and kept[:2] == (path, stamp):
        return kept[2]
    built = LicenseDetector(path, report=warn_once)  # a raise keeps nothing
    with _LOCK:
        _kept = (path, stamp, built)
    return built


def reset() -> None:
    """Forget the kept detector."""
    global _kept  # pylint: disable=global-statement
    with _LOCK:
        _kept = None
