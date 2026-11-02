# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where licenseid keeps its database when ``--db`` names none."""

import os
import sys
from pathlib import Path

from licenseid.dbcheck import refused


def get_default_db_path() -> str:
    """Return the default path for the licence database.

    Public: ``from licenseid import get_default_db_path``. The file need not
    exist yet.

    Raises :class:`licenseid.errors.DatabaseNotReadyError` (exit 2, not 1,
    which means "no") when the account has no home directory: Windows ignores
    ``HOME``, and a service or a container user may have no ``USERPROFILE``
    or passwd entry either. An empty ``USERPROFILE`` or ``HOME`` makes
    ``Path.home()`` relative (the current directory), or on Python 3.10 the
    root directory ``/`` (an empty ``HOME``): that is no home either.
    """
    if _home_variable_is_blank():
        raise refused("not found", "no home directory", "; pass --db")
    try:
        home = Path.home()
    except RuntimeError:
        home = Path()
    if not home.is_absolute():
        raise refused("not found", "no home directory", "; pass --db")
    return str(home / ".local" / "share" / "licenseid" / "licenses.db")


def _home_variable_is_blank() -> bool:
    """Whether the variable ``Path.home()`` reads here is set to nothing.

    Python 3.10 turns an empty ``HOME`` into ``/``, which is absolute, so the
    relative-home test alone would put the database in ``/.local``. Windows
    reads ``USERPROFILE`` and ignores ``HOME``. An unset variable is not
    blank: ``Path.home()`` then asks the passwd database.
    """
    name = "USERPROFILE" if sys.platform == "win32" else "HOME"
    value = os.environ.get(name)
    return value is not None and not value.strip()
