# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where licenseid keeps its database when ``--db`` names none."""

from pathlib import Path

from licenseid.errors import DatabaseNotReadyError


def get_default_db_path() -> str:
    """Return the default path for the licence database.

    Raises DatabaseNotReadyError (exit 2, not 1, which means "no") when the
    account has no home directory: Windows ignores ``HOME``, and a service or
    a container user may have no ``USERPROFILE`` or passwd entry either.
    """
    try:
        home = Path.home()
    except (KeyError, RuntimeError) as exc:
        raise DatabaseNotReadyError(
            "database: not found: no home directory; pass --db"
        ) from exc
    return str(home / ".local" / "share" / "licenseid" / "licenses.db")
