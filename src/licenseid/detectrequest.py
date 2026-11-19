# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The checks of a ``detect()`` call that need no database: its options and
its one input."""

import os
from collections.abc import Mapping
from typing import Final, TypeAlias, cast

from licenseid.dbcheck import require_path
from licenseid.errors import InvalidInputError, one_line
from licenseid.types import DetectOptions
from licenseid.variants import VARIANTS

# A file path as detect() takes it: a str or an os.PathLike of one.
PathInput: TypeAlias = str | os.PathLike[str]

# The keyword options detect() accepts: the keys of DetectOptions.
MATCH_OPTIONS: frozenset[str] = frozenset(DetectOptions.__annotations__)

# The collections ``exclude`` and ``hint`` take, as types.IdCollection.
ID_COLLECTIONS: Final = (list, tuple, set, frozenset)


def _check_inputs(text: object, license_id: object, file_path: object) -> None:
    """The input rules of :meth:`licenseid.detector.LicenseDetector.detect`:
    :class:`TypeError` for a *text* or *license_id* that is no :class:`str`,
    or a *file_path* that is no path;
    :class:`licenseid.errors.InvalidInputError` unless exactly one of the
    three is given."""
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


def _reject_unknown_options(options: Mapping[str, object]) -> None:
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


def _check_option_values(options: Mapping[str, object]) -> None:
    """:class:`TypeError` for an option of the wrong type: a flag that is no
    :class:`bool`, or an ``exclude``/``hint`` that is no list of IDs (a bare
    string would be read as a list of its characters)."""
    for name in _FLAG_OPTIONS:
        if name in options and not isinstance(options[name], bool):
            raise TypeError(f"{name} must be bool, not {type(options[name]).__name__}")
    _check_variant(options)
    for name in _LIST_OPTIONS:
        value = options.get(name)
        if name in options and (
            not isinstance(value, ID_COLLECTIONS)
            or not all(isinstance(item, str) for item in value)
        ):
            raise TypeError(f"{name} must be a list of str")


def _check_variant(options: Mapping[str, object]) -> None:
    """:class:`TypeError` for a ``variant`` that is no str,
    :class:`licenseid.errors.InvalidInputError` for one that is not a
    variant."""
    if "variant" not in options:
        return
    value = options["variant"]
    if not isinstance(value, str):
        raise TypeError(f"variant must be str, not {type(value).__name__}")
    if value not in VARIANTS:
        raise InvalidInputError(
            f"option: invalid: variant: {one_line(value)}"
            f"; use one of {', '.join(VARIANTS)}"
        )


def check_request(
    text: object, license_id: object, file_path: object, options: Mapping[str, object]
) -> str | None:
    """The checks of a detect() call that need no database: an unknown option
    first (no input hides a typo), then the inputs. ``licenseid.detect()``
    makes them before it opens the default database, so a wrong call is told
    so whether a database is there or not. Returns *file_path* as a str (an
    os.PathLike is read once here), or None."""
    _reject_unknown_options(options)
    _check_option_values(options)
    _check_inputs(text, license_id, file_path)
    return None if file_path is None else os.fspath(cast(PathInput, file_path))
