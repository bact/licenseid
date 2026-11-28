# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The type of a database handle, apart from the database.

``resolve(db=...)`` names it in its signature. Defined here, the name
resolves for ``typing.get_type_hints`` (Sphinx, typeguard, pydantic) without
``licenseid.database`` loaded, which a run that reads the packaged list never
needs (start-up). Standard library only.
"""


class DatabaseHandle:  # pylint: disable=too-few-public-methods
    """A database opened to read: the base of
    :class:`licenseid.database.LicenseDatabase`, the one handle there is."""
