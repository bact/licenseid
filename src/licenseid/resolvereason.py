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
and cut, its ";" kept (:func:`licenseid.errors.reason_detail`, P61).
"""

from collections.abc import Callable
from typing import Final

from licenseid.dropguard import trim_end_mark
from licenseid.errors import reason_detail
from licenseid.exprtokens import WHITE_SPACE, is_white_space
from licenseid.listlookup import ListLookup
from licenseid.looseid import WITH_OPERATOR
from licenseid.quotes import encloses_nothing

#: SPDX's own values for "no licence" and "not stated", which name no
#: licence; case-sensitive, as the SPDX specification writes them.
SPECIAL_VALUES: Final = ("NONE", "NOASSERTION")
#: The reason of a value with nothing in it once trimmed and unquoted.
EMPTY: Final = "empty"


def is_empty(text: str) -> bool:
    """Whether *text*, trimmed, holds nothing, or quote marks around nothing
    (``""``), with one end mark or a "+" after them too (``"".``, ``""+``):
    :data:`EMPTY`, not ``not found``."""
    core = text.strip(WHITE_SPACE)
    ended = trim_end_mark(core) or core.removesuffix("+")
    return not core or encloses_nothing(core) or encloses_nothing(ended)


def too_long(length: int) -> str:
    """The reason of a value longer than the resolver reads."""
    return f"too long: {length} characters"


def stated_twice(text: str) -> str:
    """The reason of a licence whose qualifier is stated twice
    (``GPL-2.0-only+``, ``MIT++``, ``GPL-2.0-only or later``)."""
    return f"qualifier stated twice: {reason_detail(text)}"


def on_reference(text: str) -> str:
    """The reason of a ``LicenseRef-*`` with a "+" or an "or later": SPDX
    gives a reference no qualifier."""
    return f"qualifier on a reference: {reason_detail(text)}"


def after_bracket(text: str) -> str:
    """The reason of a "+" after a bracket (``(MIT)+``): it qualifies an
    ID, not a bracketed expression."""
    return f"plus after a bracket: {reason_detail(text)}"


def after_space(text: str) -> str:
    """The reason of a "+" after white space (``GPL-2.0 +``): the operator
    touches its ID (``plusoperator.PLUS_OPERATOR``), and a "+" apart may
    say "and"."""
    return f"plus after a space: {reason_detail(text)}"


def after_exception(text: str) -> str:
    """The reason of a "+" after an exception (``MIT WITH
    Classpath-exception-2.0+``): it qualifies a licence ID, and an
    exception takes no qualifier."""
    return f"plus after an exception: {reason_detail(text)}"


def no_reading(db: ListLookup, text: str, names: Callable[[str], bool]) -> str:
    """Why *text*, the value as the readers saw it (trimmed, unquoted), names
    nothing, when no reader said: an SPDX special value, an exception not on
    the List after a licence that *names* reads, else ``not found``. The
    exception is one word: words after it (``MIT WITH
    Classpath-exception-2.0 or something``) make the value ``not found``,
    not the exception."""
    if is_empty(text):
        return EMPTY
    if text in SPECIAL_VALUES:
        return f"special value: {text}"
    parts = WITH_OPERATOR.split(text)
    if (
        len(parts) == 2
        and _one_word(exception := parts[1].strip(WHITE_SPACE))
        and not _listed_exception(db, exception)
        and names(parts[0])
    ):
        return f"exception not found: {reason_detail(exception)}"
    return f"not found: {reason_detail(text)}"


def _one_word(text: str) -> bool:
    """Whether *text*, trimmed, is one word: not empty, no white space."""
    return bool(text) and not any(map(is_white_space, text))


def _listed_exception(db: ListLookup, text: str) -> bool:
    """Whether *text* is the ID of an exception on the List."""
    return db.get_exception_details(text.strip()) is not None
