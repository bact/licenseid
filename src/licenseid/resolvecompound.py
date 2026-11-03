# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The operands of a declared value, each read as it would be alone, and a
compound of them (task T7; 0.7.0 plan, R0 and D1).

A value that names one licence is one operand; :func:`operand_of` puts the
reading of a leaf (:mod:`licenseid.resolveleaf`) in the public shape.
:func:`read_compound` reads a value of several: it cuts it into leaves
(:mod:`licenseid.exprcanon`), reads each leaf as the same text would be read
alone (quotes around it come off first, :mod:`licenseid.quotes`), and
accepts all or nothing.

- An operand is one word, with ``WITH`` and its exception, a ``+`` or an "or
  later" grant (decision Q15). A value with a leaf of several words is no
  compound at all, whatever its operators: ``Apache License 2.0 OR MIT``
  and ``W3C Software and Document Notice License`` are left to the rules
  that read prose, with no reason that would split them.
- One operand that names nothing makes the value name nothing; its reason
  (a dropped mark: ``character dropped: U+003F``) is the value's, else
  ``operand not resolved: <operand>``, the operand on one line and cut to 60
  characters (``errors.reason_detail``). A leaf of several words that reads alone
  (``BSD 3-Clause``) is refused for its shape: ``operand of several words:
  <leaf>``. The operands still come back. With
  an operator in lower case, a value refused for an operand that names
  nothing and says nothing (no dropped mark, no misplaced qualifier) is no
  compound: ``GPL-3.0 or higher`` and ``proprietary and
  confidential`` are prose, and no reason splits them.
- The category is the weakest operand's (``resolvertypes.CATEGORY_ORDER``),
  or ``lexical`` when only the form changed: the steps say which.
- A value the grammar refuses is ``malformed`` when its operators are in
  upper case and one leaf names a licence (``(MIT``, ``MIT AND``), else
  ``unresolved``; with an operator in lower case it is no compound. One with two
  operands and no operator between them (``MIT License (MIT)``,
  ``BSD (3-clause)``) is no compound at all: the later rules read it
  (decision Q18). A mark beside a bracketed group that reads as such two
  operands is the group's refusal (task fixr): a "+" after it (``(MIT)+ OR
  ISC``, ``plus after a bracket``), quote marks around it (``"(MIT)" OR
  Zlib``, ``character dropped``).
"""

import re
from collections.abc import Callable, Iterable
from typing import Final, NamedTuple

from licenseid.errors import reason_detail
from licenseid.exprcanon import (
    Node,
    Token,
    canonical,
    leaves,
    missing_operator,
    oversize,
    parse,
    split,
    written_upper,
)
from licenseid.exprtokens import ID_WORD
from licenseid.listlookup import ListLookup
from licenseid.looseid import WITH_OPERATOR, declared_grant_id_text, granted_id_text
from licenseid.quotes import unquote
from licenseid.resolveleaf import Found, category_of, refuse_dropped
from licenseid.resolveprose import read_alone
from licenseid.resolvereason import after_bracket
from licenseid.resolvertypes import (
    CATEGORY_ORDER,
    TRUST,
    Category,
    Operand,
    Step,
    step,
)

# A mark people write between two licences that SPDX does not read as an
# operator ("MIT/Apache-2.0", "MIT, ISC", "MIT | ISC", "MIT & ISC").
_RE_MARK: Final = re.compile(r"\s*([/|&;,]+)\s*")
_RE_ID_WORD: Final = re.compile(ID_WORD)
_OPEN: Final = ("(", "[", "{")  # the bracket kinds of exprcanon.split
_CLOSE: Final = (")", "]", "}")


class Compound(NamedTuple):
    """What :func:`read_compound` found besides what it put in the
    :class:`licenseid.resolveleaf.Found`: the operands, whether the
    expression parser ran, and whether the value is a compound at all. A
    value of compound form that is not claimed may carry the refusal of its
    first refused operand in *fallback*, for when no later rule reads it."""

    operands: list[Operand]
    parsed: bool
    claimed: bool
    fallback: Found | None = None


class _Leaf(NamedTuple):
    """One leaf read: its reading, and whether it is shaped as an operand."""

    found: Found
    shaped: bool


def operand_of(text: str, start: int, found: Found) -> Operand:
    """The public form of the leaf *text*, which starts at code point
    *start* of the raw input, read into *found*. A leaf that resolved to
    nothing, and was not refused, keeps no step."""
    category = category_of(found)
    kept = found.expression is not None or found.reason is not None
    return {
        "text": text,
        "span": [start, start + len(text)],
        "expression": found.expression,
        "category": category,
        "trust": TRUST[category],
        "steps": list(found.steps) if kept else [],
        "expansions": list(found.expansions) if kept else [],
        "candidates": list(found.candidates),
        "reason": found.reason,
    }


def absorb(found: Found, leaf: Found) -> None:
    """Put the reading of one *leaf* into *found*, after the steps taken on
    the text around it. A leaf that resolved to nothing keeps only its own
    steps (a refusal's ``drop``), as no step before it led anywhere."""
    if leaf.expression is None:
        found.steps = list(leaf.steps)
    else:
        found.steps = found.steps + leaf.steps
    found.expansions = found.expansions + leaf.expansions
    found.candidates = list(leaf.candidates)
    found.expression, found.category = leaf.expression, leaf.category
    found.reason = leaf.reason


def not_an_operator(text: str) -> str | None:
    """``not an SPDX operator: /`` when *text* is IDs joined by a mark that
    people use to join licences and SPDX does not (``MIT/Apache-2.0``,
    ``MIT, ISC``), else None: a URL or prose with a comma is no such list."""
    mark = _RE_MARK.search(text)
    parts = _RE_MARK.split(text)[::2]  # split keeps the marks: every 2nd
    if mark is None or not all(_RE_ID_WORD.fullmatch(part) for part in parts):
        return None
    return f"not an SPDX operator: {mark.group(1)}"


def read_compound(db: ListLookup, text: str, start: int, found: Found) -> Compound:
    """Read *text* (which starts at code point *start* of the raw input) as
    an expression of several leaves into *found*. Not ``claimed`` when it
    holds no operator and no bracket, has a leaf of several words, or two
    operands with no operator between them: then *found* is left as it
    was."""
    tokens = split(text)
    if len(tokens) == 1:
        return Compound([], False, False)
    spans = leaves(tokens)
    parts = [text[leaf.start : leaf.end] for leaf in spans]
    if not all(_is_operand(_unquoted(part)[0]) for part in parts):  # first:
        # prose ("Apache License 2.0 OR MIT") is no compound, however long
        return Compound([], False, False, _fallback(db, text, tokens, parts))
    refusal = oversize(tokens)
    if refusal in ("too many operators", "too deeply nested"):
        _refuse(found, "unresolved", refusal)
        return Compound([], False, True)
    cache: dict[str, _Leaf] = {}
    reading = _Reading(text, start, tokens, spans, [])
    for part in parts:
        if part not in cache:
            cache[part] = _read_operand(db, part)
        reading.read.append(cache[part])
    if refusal is not None:  # mismatched brackets: no parse
        return _refuse_grammar(found, reading, refusal, False)
    tree = parse(tokens, parts)
    if isinstance(tree, str):
        return _refuse_grammar(found, reading, tree, True)
    return _combine(found, reading, tree)


class _Reading(NamedTuple):
    """A value cut into leaves, and the reading of each leaf."""

    text: str
    start: int
    tokens: list[Token]
    spans: list[Token]
    read: list[_Leaf]


def _refuse_grammar(
    found: Found, reading: _Reading, reason: str, parsed: bool
) -> Compound:
    """A value of operand-shaped leaves the grammar refuses, for *reason*:
    ``malformed`` when a leaf names a licence; no compound when two operands
    have no operator between them, or an operator is in lower case. A mark
    beside a bracketed group that makes two operands of it is that group's
    refusal (:func:`_misplaced`)."""
    tokens = reading.tokens
    misplaced = _misplaced(reading)
    if misplaced is not None:
        _refuse(found, category_of(misplaced), str(misplaced.reason))
        found.steps = list(misplaced.steps)
        return Compound([], parsed, True)
    if missing_operator(tokens) or not written_upper(reading.text, tokens):
        return Compound([], parsed, False)  # prose: "BSD (3-clause)"
    named = any(leaf.found.expression is not None for leaf in reading.read)
    _refuse(found, "malformed" if named else "unresolved", reason)
    return Compound([], parsed, True)


def _misplaced(reading: _Reading) -> Found | None:
    """The refusal of a value whose operators are in upper case and which
    holds a bracketed group with a mark the grammar does not take beside it,
    the same refusal as that group alone, or None. A "+" after the group
    (``(MIT)+ OR ISC``) qualifies an ID, not a bracket: ``malformed``, ``plus
    after a bracket: (MIT)+``, when a licence in it is named. Quote marks
    around the group (``"(MIT)" OR Zlib``) come off an operand, not off a
    group: ``character dropped``, as for a quote mark in an operand (``"MIT
    OR ISC" OR Zlib``), when every licence in it is named. Read otherwise,
    as two operands side by side, the value was "not found"."""
    tokens, text = reading.tokens, reading.text
    if not written_upper(text, tokens) or not any(
        token.kind in ("AND", "OR") for token in tokens
    ):
        return None
    for index, token in enumerate(tokens):
        if token.kind != "leaf":
            continue
        refusal = _plus_after_group(reading, index) or _quoted_group(reading, index)
        if refusal is not None:
            return refusal
    return None


def _plus_after_group(reading: _Reading, index: int) -> Found | None:
    """The refusal of the "+" that the leaf at *index* of the tokens is,
    right after a closing bracket, a licence in its group named; or None."""
    tokens, text = reading.tokens, reading.text
    plus = tokens[index]
    if text[plus.start : plus.end] != "+" or not _touch(tokens, index - 1):
        return None
    if tokens[index - 1].kind not in _CLOSE:
        return None
    opening = _partner(tokens, index - 1, -1)
    if opening is None or not _named(reading, opening, index, any):
        return None
    group = text[tokens[opening].start : plus.end]
    return Found(category="malformed", reason=after_bracket(group))


def _quoted_group(reading: _Reading, index: int) -> Found | None:
    """The refusal of the quote marks that the leaf at *index* of the tokens
    opens, right before a bracketed group closed by the same marks, every
    licence in it named; or None."""
    tokens, text = reading.tokens, reading.text
    if not _touch(tokens, index) or tokens[index + 1].kind not in _OPEN:
        return None
    closing = _partner(tokens, index + 1, 1)
    if closing is None or not _touch(tokens, closing):
        return None
    group = text[tokens[index].start : tokens[closing + 1].end]
    unquoted = unquote(group)
    if unquoted is None or not unquoted.balanced:  # quote marks, no other
        return None
    if not _named(reading, index + 1, closing, all):
        return None
    inner = unquoted.text
    lost = group[: unquoted.start] + group[unquoted.start + len(inner) :]
    refusal = Found()
    refuse_dropped(refusal, group, "".join(dict.fromkeys(lost)), inner)
    return refusal


def _touch(tokens: list[Token], index: int) -> bool:
    """Whether a token follows the one at *index* of *tokens* with nothing
    between them."""
    return 0 <= index < len(tokens) - 1 and (
        tokens[index].end == tokens[index + 1].start
    )


def _partner(tokens: list[Token], index: int, direction: int) -> int | None:
    """The index of the bracket that pairs with the one at *index* of the
    tokens, looking forward (*direction* 1) or back (-1); None if none."""
    depth = 0
    while 0 <= index < len(tokens):
        kind = tokens[index].kind
        depth += (kind in _OPEN) - (kind in _CLOSE)
        if depth == 0:
            return index
        index += direction
    return None


def _named(
    reading: _Reading, first: int, last: int, judge: Callable[[Iterable[bool]], bool]
) -> bool:
    """Whether the leaves between the tokens at *first* and *last* name
    licences, as *judge* (``any`` or ``all``) holds them."""
    low, high = reading.tokens[first].end, reading.tokens[last].start
    inside = [
        leaf.found.expression is not None
        for span, leaf in zip(reading.spans, reading.read)
        if low <= span.start and span.end <= high
    ]
    return bool(inside) and judge(inside)


def _combine(found: Found, reading: _Reading, tree: Node) -> Compound:
    """The compound of *tree*, its leaves read: all of them named, or the
    refusal of the first that names nothing."""
    text, read = reading.text, reading.read
    operands = [
        operand_of(text[leaf.start : leaf.end], reading.start + leaf.start, r.found)
        for leaf, r in zip(reading.spans, read)
    ]
    expressions = [r.found.expression for r in read]
    if None in expressions:
        refused = [i for i, e in enumerate(expressions) if e is None]
        if not written_upper(text, reading.tokens):  # only an operand's own
            refused = [i for i in refused if not _is_nothing(operands[i])]
            if not refused:  # reason: "GPL-3.0 or higher" is prose
                return Compound([], True, False)
        _refuse_operands(found, operands, read, refused[0])
        return Compound(operands, True, True)
    named = [str(expression) for expression in expressions]
    expression, steps = canonical(text, reading.tokens, tree, named)
    for leaf in read:
        found.steps = found.steps + leaf.found.steps
        found.expansions = found.expansions + leaf.found.expansions
    found.steps += steps
    found.expression = expression
    return Compound(operands, True, True)


def _fallback(
    db: ListLookup, text: str, tokens: list[Token], parts: list[str]
) -> Found | None:
    """The refusal a value of compound form with a leaf of several words
    gives when no later rule reads it (Q15, P43): the first refused leaf's
    own reason (a dropped mark), else, with the operators in upper case,
    ``operand of several words: <leaf>`` for a leaf that reads alone, or
    ``operand not resolved: <leaf>`` for one that does not; None for a value
    with no operator or two operands side by side, and for a lower-case one
    with no reason."""
    if missing_operator(tokens) or not any(t.kind in ("AND", "OR") for t in tokens):
        return None
    upper = written_upper(text, tokens)
    for part in dict.fromkeys(parts):
        leaf = _read_operand(db, part)
        named = leaf.found.expression is not None
        if leaf.shaped and named:
            continue
        if leaf.found.reason is not None:
            return Found(
                category="unresolved",
                reason=leaf.found.reason,
                steps=list(leaf.found.steps),
            )
        if upper:  # a leaf that reads alone is refused for its shape (P43)
            what = "operand of several words" if named else "operand not resolved"
            return Found(category="unresolved", reason=f"{what}: {reason_detail(part)}")
    return None


def _unquoted(text: str) -> tuple[str, list[Step]]:
    """*text* without the quotes around it, a balanced pair only (a lone
    mark may pair with one in another operand), and the step that says so."""
    unquoted = unquote(text)
    if unquoted is None or not unquoted.balanced:
        return text, []
    return unquoted.text, [step("unquote", True, text, unquoted.text, unquoted.detail)]


def _read_operand(db: ListLookup, text: str) -> _Leaf:
    """*text*, one leaf, read as the same text alone would be, after the
    quotes around it, and whether it is shaped as an operand (Q15). A leaf
    of another shape is read too, for the reason it may give (a dropped
    mark), never for its licence."""
    inner, steps = _unquoted(text)
    found = Found(steps=steps)
    leaf = Found()
    if read_alone(db, inner, leaf):
        absorb(found, leaf)
    else:
        found.category, found.reason = "unresolved", not_an_operator(inner)
    return _Leaf(found, _is_operand(inner))


def _is_operand(text: str) -> bool:
    """Whether *text* is one word, ``WITH`` and one word, each with its
    "or later" grant if it has one; a "+" is part of its word."""
    halves = WITH_OPERATOR.split(text)
    return len(halves) <= 2 and all(_one_word(half) for half in halves)


def _one_word(text: str) -> bool:
    """Whether *text*, without an "or later" grant or a "+" that ends it,
    is one word: the grant read as ``resolveleaf`` reads it, the "+" after
    white space too (``GPL-2.0 +``, which ``match`` reads alone)."""
    named = granted_id_text(text) or declared_grant_id_text(text)
    core = text if named is None else named.rstrip(" \t([")
    words = core.split()
    return len(words) == 1 or (len(words) == 2 and words[1] == "+")


def _is_nothing(operand: Operand) -> bool:
    """Whether *operand* names nothing and says nothing: unresolved, with no
    reason (not a dropped mark, not a misplaced qualifier)."""
    return operand["category"] == "unresolved" and operand["reason"] is None


def _refuse(found: Found, category: Category, reason: str) -> None:
    """Make *found* a value that names nothing, for *reason*."""
    found.expression, found.category, found.reason = None, category, reason
    found.steps, found.expansions, found.candidates = [], [], []


def _refuse_operands(
    found: Found, operands: list[Operand], read: list[_Leaf], first: int
) -> None:
    """Make *found* the refusal of a compound whose operand names nothing,
    *first* the first such: the weakest operand's category; that operand's
    own reason and steps (a ``drop``), else ``operand not resolved: <it>``."""
    weakest = max(
        (operand["category"] for operand in operands), key=CATEGORY_ORDER.index
    )
    own = read[first].found
    unnamed = reason_detail(operands[first]["text"])
    _refuse(found, weakest, own.reason or f"operand not resolved: {unnamed}")
    if own.reason is not None:
        found.steps = list(own.steps)
