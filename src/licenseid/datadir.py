# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where licenseid keeps its database when ``--db`` names none."""

from pathlib import Path

from licenseid.errors import DatabaseNotReadyError


def get_default_db_path() -> str:
    """Return the default path for the licence database.

    Public: ``from licenseid import get_default_db_path``. The file need not
    exist yet.

    Raises :class:`licenseid.errors.DatabaseNotReadyError` (exit 2, not 1,
    which means "no") when the account has no home directory: Windows ignores
    ``HOME``, and a service or a container user may have no ``USERPROFILE``
    or passwd entry either. An empty ``USERPROFILE`` or ``HOME`` makes
    ``Path.home()`` relative (the current directory): that is no home either.
    """
    try:
        home = Path.home()
    except RuntimeError:
        home = Path()
    if not home.is_absolute():
        raise DatabaseNotReadyError("database: not found: no home directory; pass --db")
    return str(home / ".local" / "share" / "licenseid" / "licenses.db")
