# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The reason of a refusal no reader gave one (P5 of the contract batch).

Every ``unresolved`` or ``malformed`` answer of ``resolve()`` carries a
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
from licenseid.exprtokens import RE_OPERATOR, WHITE_SPACE
from licenseid.listlookup import ListLookup
from licenseid.looseid import WITH_OPERATOR
from licenseid.quotes import encloses_nothing
from licenseid.resolvefirst import MIN_TEXT_WORDS

#: SPDX's own values for "no licence" and "not stated", which name no
#: licence; case-sensitive, as the SPDX specification writes them.
SPECIAL_VALUES: Final = ("NONE", "NOASSERTION")
#: The reason of a value with nothing in it once trimmed and unquoted.
EMPTY: Final = "empty"

#: The conditions of a refusal for a "+" that is no operator, which a text
#: match must not answer round (``detect()``: ``normalize_text`` drops the "+").
STATED_TWICE: Final = "qualifier stated twice"
ON_REFERENCE: Final = "qualifier on a reference"
AFTER_BRACKET: Final = "plus after a bracket"
AFTER_SPACE: Final = "plus after a space"
AFTER_EXCEPTION: Final = "plus after an exception"
_PLUS_CONDITIONS: Final = (
    STATED_TWICE,
    ON_REFERENCE,
    AFTER_BRACKET,
    AFTER_SPACE,
    AFTER_EXCEPTION,
)


#: The conditions of a refusal for a character or a word a loose reading
#: would drop, or a bracket that does not pair: a text match would drop or
#: ignore it in silence too.
_NO_TEXT_CONDITIONS: Final = (
    "character dropped",
    "word dropped",
    "control or format character",
    "lone surrogate",
    "parse failed",
)
_PLUS_SIGNS: Final = "+\uff0b"  # the plus sign and the fullwidth one


def refuses_text_match(reason: str | None, text: str) -> bool:
    """Whether a text match must not answer *text*, a short value that
    ``resolve()`` refused for *reason*: a "+" that is no operator (the
    refusal of its family, or a "+" run ending a word that no reader took:
    ``「MIT++」``, ``<GPL-2.0+>``), or a mark or word dropped. ``normalize_text``
    drops all of these."""
    condition = None if reason is None else reason.partition(":")[0]
    return (
        is_plus_refusal(reason)
        or condition in _NO_TEXT_CONDITIONS
        # From 10 words on a sentence is text, not a value: its name is matched
        # as before (``This library is licensed under the MIT++ license, see ...``).
        or (len(text.split()) < MIN_TEXT_WORDS and ends_a_word_with_plus(text))
    )


def ends_a_word_with_plus(text: str) -> bool:
    """Whether *text* has a "+" (or "＋") that is no operator and no part of a
    word like ``C++``: a run ending a word right after a letter or digit,
    closing marks aside (``MIT++``, ``「GPL-2.0+」``); one that starts a word
    (``+GPL-2.0``); one alone in marks (``GPL-2.0 (+)``, ``"+"``); or a "+"
    apart that ends the text (``"MIT +"``). Not ``C++``, ``g++`` or
    ``Objective-C++`` (a language: the letter before a ``++`` is c or g), nor
    a "+" apart in the middle (``MIT + file LICENSE``). One pass over each
    word, by index: a long run of marks costs no more than its length."""
    words = text.split()
    if words and _is_only_plus(words[-1]):
        return True
    return any(_stray_plus(word) for word in words)


def _is_only_plus(word: str) -> bool:
    """Whether *word*, closing marks aside, is a run of "+" signs only."""
    core = _plus_core(word)
    return bool(core) and not core.strip(_PLUS_SIGNS)


def _plus_core(word: str) -> str:
    """*word* without the marks at its ends: what lies between the first and
    the last letter, digit or "+"."""
    lo, hi = 0, len(word)
    while hi > lo and not (word[hi - 1].isalnum() or word[hi - 1] in _PLUS_SIGNS):
        hi -= 1
    while lo < hi and not (word[lo].isalnum() or word[lo] in _PLUS_SIGNS):
        lo += 1
    return word[lo:hi]


def _stray_plus(word: str) -> bool:
    """Whether *word* has a "+" of the kinds :func:`ends_a_word_with_plus`
    names, except the last "+" apart."""
    core = _plus_core(word)
    if not core:
        return False
    if _is_only_plus(word):
        return core != word  # in marks ("(+)"): a bare "+" is the caller's
    if core[0] in _PLUS_SIGNS:
        return True  # "+GPL-2.0"
    base = core.rstrip(_PLUS_SIGNS)
    if base == core or not base[-1].isalnum():
        return False
    return not (core[len(base) :] == "++" and base[-1] in "cCgG")


def is_plus_refusal(reason: str | None) -> bool:
    """Whether *reason*, the reason of a refusal, is of the "+" family: the
    value has a "+" that is no operator, so no text match may answer it."""
    return reason is not None and reason.partition(":")[0] in _PLUS_CONDITIONS


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
    return f"{STATED_TWICE}: {reason_detail(text)}"


def on_reference(text: str) -> str:
    """The reason of a ``LicenseRef-*`` with a "+" or an "or later": SPDX
    gives a reference no qualifier."""
    return f"{ON_REFERENCE}: {reason_detail(text)}"


def after_bracket(text: str) -> str:
    """The reason of a "+" after a bracket (``(MIT)+``): it qualifies an
    ID, not a bracketed expression."""
    return f"{AFTER_BRACKET}: {reason_detail(text)}"


def names_expression(text: str) -> str:
    """The reason of an operand that is itself an expression (a NuGet
    ``licenses.nuget.org`` URL of ``MIT OR ISC``): an operand names one
    licence."""
    return f"operand names an expression: {reason_detail(text)}"


def after_space(text: str) -> str:
    """The reason of a "+" after white space (``GPL-2.0 +``): the operator
    touches its ID (``plusoperator.PLUS_OPERATOR``), and a "+" apart may
    say "and"."""
    return f"{AFTER_SPACE}: {reason_detail(text)}"


def after_exception(text: str) -> str:
    """The reason of a "+" after an exception (``MIT WITH
    Classpath-exception-2.0+``): it qualifies a licence ID, and an
    exception takes no qualifier."""
    return f"{AFTER_EXCEPTION}: {reason_detail(text)}"


def no_reading(db: ListLookup, text: str, names: Callable[[str], bool]) -> str:
    """Why *text*, the value as the readers saw it (trimmed, unquoted), names
    nothing, when no reader said: an SPDX special value, an exception not on
    the List after a licence that *names* reads, else ``not found``. What
    follows WITH is the exception unless it goes on past one: an operator
    in upper case in it (``Autoconf-exception-macro OR Zlib``) or a listed
    exception and more words (``Classpath-exception-2.0 or something``)
    make the value ``not found``; a name (``LLVM exception``) is the
    exception not found."""
    if is_empty(text):
        return EMPTY
    if text in SPECIAL_VALUES:
        return f"special value: {text}"
    parts = WITH_OPERATOR.split(text)
    if (
        len(parts) == 2
        and _exception_alone(db, exception := parts[1].strip(WHITE_SPACE))
        and names(parts[0])
    ):
        return f"exception not found: {reason_detail(exception)}"
    return f"not found: {reason_detail(text)}"


def _exception_alone(db: ListLookup, text: str) -> bool:
    """Whether *text*, the trimmed words after WITH, is one exception the
    List does not have: not empty, no operator in upper case (as SPDX
    spells one; a lower-case "and" may be prose), and not starting with a
    listed exception, alone or with more words after it."""
    words = text.split()
    upper = any(op.group().isupper() for op in RE_OPERATOR.finditer(text))
    return bool(words) and not upper and not _listed_exception(db, words[0])


def _listed_exception(db: ListLookup, text: str) -> bool:
    """Whether *text* is the ID of an exception on the List."""
    return db.get_exception_details(text.strip()) is not None
