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


def invalid_id_error(option: str, value: str) -> InvalidInputError:
    """The one wording for a value declared as a license ID that names no
    single license. *option* is what the caller spells it: ``--id`` on the
    command line, ``license_id`` in the API.

    A minified line can be declared too, so the value is cut: one error must
    not fill the terminal, nor span two lines, so white space (a line break
    included) is folded to single spaces. ASCII only, because stderr may be
    in any encoding.
    """
    value = " ".join(value.split())
    if len(value) > 60:
        value = value[:60] + "..."
    return InvalidInputError(f"option: invalid: {option}: {value}; pass one license ID")
