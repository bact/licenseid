# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Exceptions raised by licenseid.
"""


class LicenseIdError(RuntimeError):
    """A failure whose message follows the ``SUBJECT: CONDITION[: DETAIL]
    [; ACTION]`` grammar (see ``licenseid.console``), so the CLI can print it
    as is after ``ERROR:``.

    Subclasses RuntimeError so existing ``except RuntimeError`` callers keep
    working. Other RuntimeErrors (e.g. RecursionError) are not worded this
    way and must not be printed raw.
    """


class DatabaseNotReadyError(LicenseIdError):
    """The license database is missing, empty, invalid or unreadable, so an
    answer from it could not be trusted. The CLI exits with code 2, not 1,
    because 1 means "no" for ``match`` and every ``is-*`` command."""


class InvalidInputError(LicenseIdError):
    """An invalid option or input (e.g. a malformed ``--version`` or binary
    input): a usage error, so the CLI exits with code 2 rather than 1."""
