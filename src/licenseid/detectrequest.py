# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The checks of a ``detect()`` call that need no database: its options and
its one input."""

from typing import Any

from licenseid.dbcheck import require_path
from licenseid.errors import InvalidInputError
from licenseid.types import DetectRequest

# The keyword options detect() accepts; `text`, `license_id` and `file_path`
# are its named parameters, so a request can carry no other key.
MATCH_OPTIONS: frozenset[str] = frozenset(DetectRequest.__annotations__) - {
    "text",
    "license_id",
    "file_path",
}


def _check_inputs(text: object, license_id: object, file_path: object) -> None:
    """The input rules of :meth:`LicenseDetector.detect` (P6 of the contract
    batch): :class:`TypeError` for a *text* or *license_id* that is no
    :class:`str` (it failed deep inside), or a *file_path* that is no path;
    :class:`licenseid.errors.InvalidInputError` unless exactly one of the
    three is given (none answered nothing; of two, one won unsaid)."""
    for name, value in (("text", text), ("license_id", license_id)):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{name} must be str, not {type(value).__name__}")
    if file_path is not None:
        require_path(file_path, "file_path")
    given = [
        name
        for name, value in (
            ("text", text),
            ("license_id", license_id),
            ("file_path", file_path),
        )
        if value is not None
    ]
    if not given:
        raise InvalidInputError("input: missing; pass text, license_id or file_path")
    if len(given) > 1:
        raise InvalidInputError(
            f"input: invalid: {given[0]}: with {given[1]}; pass one input"
        )


def _reject_unknown_options(options: dict[str, Any]) -> None:
    """Raise InvalidInputError for an option detect() does not know, so a typo
    or a removed option (`enable_java`) cannot pass with no effect."""
    unknown = sorted(options.keys() - MATCH_OPTIONS)
    if unknown:
        raise InvalidInputError(
            f"option: invalid: {', '.join(map(repr, unknown))}"
            f"; use one of {', '.join(sorted(MATCH_OPTIONS))}"
        )


_FLAG_OPTIONS: tuple[str, ...] = ("enable_popularity", "only_common", "only_spdx")
_LIST_OPTIONS: tuple[str, ...] = ("exclude", "hint")


def _check_option_values(options: dict[str, Any]) -> None:
    """:class:`TypeError` for an option of the wrong type: a flag that is no
    :class:`bool`, or an ``exclude``/``hint`` that is no list of IDs. A bare
    string was read as a list of its characters (``exclude="MIT"`` kept
    every ID that is a substring of it), so the call failed unsaid."""
    for name in _FLAG_OPTIONS:
        if name in options and not isinstance(options[name], bool):
            raise TypeError(f"{name} must be bool, not {type(options[name]).__name__}")
    for name in _LIST_OPTIONS:
        value = options.get(name)
        if name in options and (
            not isinstance(value, (list, tuple, set, frozenset))
            or not all(isinstance(item, str) for item in value)
        ):
            raise TypeError(f"{name} must be a list of str")


def check_request(
    text: object, license_id: object, file_path: object, options: dict[str, Any]
) -> None:
    """The checks of a detect() call that need no database: an unknown option
    first (no input hides a typo), then the inputs. ``licenseid.detect()``
    makes them before it opens the default database, so a wrong call is told
    so whether a database is there or not."""
    _reject_unknown_options(options)
    _check_option_values(options)
    _check_inputs(text, license_id, file_path)
