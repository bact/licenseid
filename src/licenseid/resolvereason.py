# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The reason of a refusal no reader gave one (P5 of the contract batch).

Every ``unresolved`` or ``malformed`` answer of ``match()`` carries a
``reason``, one line, ``CONDITION[: DETAIL]``. A reader that knows why it
refused says so (``character dropped``, ``operand not resolved``); for the
rest, :func:`no_reading` says what is left to say once every reader has
declined the value. The wording is the CONDITION style of the diagnostics
(AGENTS.md "CLI output"), and a detail from the input is folded to one line
and cut (:func:`licenseid.errors.one_line`, P61).
"""

from collections.abc import Callable
from typing import Final

from licenseid.errors import one_line
from licenseid.listlookup import ListLookup
from licenseid.looseid import WITH_OPERATOR

#: SPDX's own values for "no licence" and "not stated", which name no
#: licence; case-sensitive, as the SPDX specification writes them.
SPECIAL_VALUES: Final = ("NONE", "NOASSERTION")
#: The reason of a value with nothing in it once trimmed and unquoted.
EMPTY: Final = "empty"


def too_long(length: int) -> str:
    """The reason of a value longer than the resolver reads."""
    return f"too long: {length} characters"


def stated_twice(text: str) -> str:
    """The reason of a licence whose qualifier is stated twice
    (``GPL-2.0-only+``, ``MIT++``, ``GPL-2.0-only or later``)."""
    return f"qualifier stated twice: {one_line(text)}"


def on_reference(text: str) -> str:
    """The reason of a ``LicenseRef-*`` with a "+" or an "or later": SPDX
    gives a reference no qualifier."""
    return f"qualifier on a reference: {one_line(text)}"


def after_bracket(text: str) -> str:
    """The reason of a "+" after a bracket (``(MIT)+``): it qualifies an
    ID, not a bracketed expression."""
    return f"plus after a bracket: {one_line(text)}"


def no_reading(db: ListLookup, text: str, names: Callable[[str], bool]) -> str:
    """Why *text*, the value as the readers saw it (trimmed, unquoted), names
    nothing, when no reader said: an SPDX special value, an exception not on
    the List after a licence that *names* reads, else ``not found``."""
    if not text:
        return EMPTY
    if text in SPECIAL_VALUES:
        return f"special value: {text}"
    parts = WITH_OPERATOR.split(text)
    if (
        len(parts) == 2
        and parts[1].strip()
        and not _listed_exception(db, parts[1])
        and names(parts[0])
    ):
        return f"exception not found: {one_line(parts[1].strip())}"
    return f"not found: {one_line(text)}"


def _listed_exception(db: ListLookup, text: str) -> bool:
    """Whether *text* is the ID of an exception on the List."""
    return db.get_exception_details(text.strip()) is not None
