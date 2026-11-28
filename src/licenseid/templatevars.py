# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where the variable parts of a licence template sit in its stored text.

A template marks text that may vary as ``<<var;...;original="..";
match="..">>`` (SPDX matching guidelines B.3.3): a copy may write its own
copyright holder or project name there, as long as the ``match`` pattern
accepts it. The search of whole texts (``licenseid.textmask``) leaves those
words out of the comparison, so it needs them as token ranges of the
normalised text the database stores (``var_regions``), each with its
pattern; ``fill_pattern`` reads a pattern on normalised words.

A region is found by rendering the template with a sentinel word on each side
of every var, normalising it as the stored text was, and aligning its tokens
to the stored ones. A var whose words do not all match one run of the stored
text is no region (fail closed: its words are compared as today), and an
empty one (an ``original`` normalisation drops) is a point between two
matched tokens or none. The template of the List is read the one way
``licenseid.coretext`` reads it (``coretext.pieces``).

Prototype and measurements: roadmap item 64 (PR to be linked).
"""

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache
from typing import Final, NamedTuple

from licenseid.coretext import pieces
from licenseid.normalize import normalize_text
from licenseid.textcorpus import VarRegion
from licenseid.textgrams import split_words

#: Words around each var in a rendered template. No List text holds them, and
#: normalisation keeps them as they are (lower-case letters only).
OPEN: Final = "qqvaropenqq"
CLOSE: Final = "qqvarcloseqq"

#: A fill longer than this (characters) is never exempt: no ``original`` of
#: the List comes near, and a pattern is not run on a whole licence.
MAX_FILL_CHARS: Final = 3_000

# Rendered tokens are coded one character each for the alignment, from here
# up and below the surrogates.
_FIRST_CODE: Final = 0x100
_LAST_CODE: Final = 0xD7FF

# The syntax of a pattern, kept as it is, and the escapes of white space:
# normalisation folds every character that is not a word character to a
# space, so in a pattern each other character is at most one space.
_SYNTAX: Final = frozenset(".^$*+?{}[]|()")
_WHITE_ESCAPES: Final = frozenset("stnrfv")
_QUANTIFIERS: Final = "*+?"
_REPEAT: Final = re.compile(r"\{\d*,?\d*\}")


def marked_text(template: str, keep_optional: bool) -> str | None:
    """*template* rendered with OPEN and CLOSE around each var's ``original``,
    its optional parts kept (the whole text) or dropped (the core, as
    ``coretext.core_text`` drops them), or None when it is malformed."""
    walked = pieces(template)
    if walked is None:
        return None
    parts: list[str] = []
    line_start = True
    for piece in walked:
        if piece.depth and not keep_optional:
            continue
        if piece.kind == "var" and line_start:
            # A var that starts a line (a list number, "1.") stays at the start
            # of one, so normalisation drops it as it did from the stored text.
            part = f"{OPEN}\n{piece.text} {CLOSE} "
        elif piece.kind == "var":
            part = f" {OPEN} {piece.text} {CLOSE} "
        elif piece.kind in ("plain", "text"):
            part = piece.text
        else:  # where an optional part opens or closes: a word boundary
            part = " "
        parts.append(part)
        line_start = _ends_line(part, line_start)
    return "".join(parts)


def _ends_line(part: str, line_start: bool) -> bool:
    """Whether text that was at a line start (*line_start*) is still there
    after *part*: nothing but spaces and tabs after its last line break."""
    head, newline, tail = part.rpartition("\n")
    rest = tail if newline else head + tail
    return (bool(newline) or line_start) and not rest.strip(" \t")


class _Marked(NamedTuple):
    """The tokens of a rendered template without the sentinels, and each
    var as a range of them with its pattern."""

    words: list[str]
    spans: list[tuple[int, int, str]]


def _unmarked(tokens: Sequence[str], patterns: Sequence[str]) -> _Marked | None:
    """*tokens* without OPEN and CLOSE, each var as a token range, or None
    when the sentinels do not pair up with the vars."""
    words: list[str] = []
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    for token in tokens:
        if token == OPEN:
            if start is not None or len(spans) == len(patterns):
                return None
            start = len(words)
        elif token == CLOSE:
            if start is None:
                return None
            spans.append((start, len(words), patterns[len(spans)]))
            start = None
        else:
            words.append(token)
    if start is not None or len(spans) != len(patterns):
        return None
    return _Marked(words, spans)


def _matches(rendered: Sequence[str], stored: Sequence[str]) -> list[int] | None:
    """For each token of *rendered*, the token of *stored* it matches in
    their alignment, or -1; None when they have too many words to code."""
    codes: dict[str, str] = {}
    for word in (*rendered, *stored):
        if word not in codes:
            if _FIRST_CODE + len(codes) > _LAST_CODE:
                return None
            codes[word] = chr(_FIRST_CODE + len(codes))
    first = "".join([codes[word] for word in rendered])
    second = "".join([codes[word] for word in stored])
    # RapidFuzz loads here, not at import: only a build reads templates, and
    # a lookup imports this module through ``licenseid.records`` (start-up).
    from rapidfuzz.distance import Indel  # pylint: disable=import-outside-toplevel

    matched = [-1] * len(rendered)
    for block in Indel.editops(first, second).as_matching_blocks():
        for k in range(block.size):
            matched[block.a + k] = block.b + k
    return matched


def _region(
    matched: Sequence[int], start: int, end: int, stored: int
) -> tuple[int, int] | None:
    """The stored tokens of rendered tokens *start* to *end*, or None when
    one of them is unmatched or they are not one run. An empty range is the
    point between its neighbours, which must be matched and adjacent (the
    ends of the text count as matched)."""
    if start == end:
        before = matched[start - 1] if start else -1
        after = matched[start] if start < len(matched) else stored
        if (start and before < 0) or after < 0 or after != before + 1:
            return None
        return after, after
    first, last = matched[start], matched[end - 1]
    if min(matched[start:end]) < 0 or last - first != end - 1 - start:
        return None
    return first, last + 1


def var_regions(
    template: str, stored: Sequence[str], keep_optional: bool
) -> tuple[VarRegion, ...]:
    """The vars of *template* as regions of the stored tokens *stored* (the
    normalised text, or the core when *keep_optional* is false), in order;
    a var that maps onto no run of *stored* is left out. None of a malformed
    template."""
    rendered = marked_text(template, keep_optional)
    if rendered is None:
        return ()
    patterns = [
        piece.pattern
        for piece in pieces(template) or ()
        if piece.kind == "var" and (keep_optional or not piece.depth)
    ]
    marked = _unmarked(split_words(normalize_text(rendered)), patterns)
    if marked is None:
        return ()
    matched = _matches(marked.words, stored)
    if matched is None:
        return ()
    regions = []
    for start, end, pattern in marked.spans:
        found = _region(matched, start, end, len(stored))
        if found is not None:
            regions.append(VarRegion(found[0], found[1], pattern))
    return tuple(regions)


def shared_regions(
    members: Iterable[tuple[VarRegion, ...]],
) -> tuple[VarRegion, ...]:
    """The regions every one of *members* has (same tokens, same pattern),
    in order: a same-text group whose templates differ (GPL-2.0-only and
    GPL-2.0-or-later) exempts only what all of them let vary."""
    common: tuple[VarRegion, ...] | None = None
    for regions in members:
        if common is None:
            common = regions
        else:
            keep = set(regions)
            common = tuple(region for region in common if region in keep)
    return common or ()


def row_regions(
    text: str, core: str | None, templates: Iterable[str]
) -> tuple[tuple[VarRegion, ...], tuple[VarRegion, ...]]:
    """The regions of the normalised *text* and *core* that every one of
    *templates* (those of a same-text group) shares; none without a
    template."""
    text_words = split_words(text)
    core_words = None if core is None else split_words(core)
    texts: list[tuple[VarRegion, ...]] = []
    cores: list[tuple[VarRegion, ...]] = []
    for template in templates:
        texts.append(var_regions(template, text_words, True))
        if core_words is not None:
            cores.append(var_regions(template, core_words, False))
    return shared_regions(texts), shared_regions(cores)


def _pattern_source(pattern: str) -> str:
    """*pattern* (a ``match`` of the List, a Java regular expression on the
    raw text) as one on normalised text, where every character that is not a
    word character is gone or a space: each such character outside a class
    (white space, a punctuation mark, an escaped mark, ``\\s``), with any
    quantifier after it, becomes one optional space, a run of them one too.
    Word characters, the syntax of the expression, classes and ``{m,n}``
    are kept."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "[":
            end = _class_end(pattern, i)
            token = pattern[i:end]
            i = end
            if _has_word(token):
                out.append(token)
                continue
        elif char == "{" and (repeat := _REPEAT.match(pattern, i)) is not None:
            out.append(repeat.group())
            i = repeat.end()
            continue
        else:
            step = 2 if char == "\\" and i + 1 < len(pattern) else 1
            token = pattern[i : i + step]
            i += step
            if _is_kept(token):
                out.append(token)
                continue
        if not out or out[-1] != " ?":
            out.append(" ?")
        i = _past_quantifier(pattern, i)
    return "".join(out)


def _has_word(token: str) -> bool:
    """Whether the class *token* may match a word character: it is negated
    or holds one, or an escape of one (``\\w``), not only white space and
    marks (``[ \\t]``, ``[\\(\\[]``)."""
    body = token[1:-1] if token.endswith("]") else token[1:]
    if body.startswith("^"):
        return True
    body = re.sub(r"\\[stnrfv]", "", body)
    return any(char.isalnum() or char == "_" for char in body)


def _is_kept(token: str) -> bool:
    """Whether *token* (a character or an escape) of a pattern outside a
    class is kept: a word character, the syntax of the expression or an
    escape of a letter that is no white space (``\\d``, ``\\b``)."""
    last = token[-1]
    if len(token) == 1:
        return last in _SYNTAX or last.isalnum() or last == "_"
    return (last.isalnum() or last == "_") and last not in _WHITE_ESCAPES


def _past_quantifier(pattern: str, i: int) -> int:
    """Where *pattern* goes on after the quantifiers (``*``, ``+``, ``?``,
    ``{m,n}``) at *i*, if any."""
    while i < len(pattern):
        if pattern[i] in _QUANTIFIERS:
            i += 1
        elif (found := _REPEAT.match(pattern, i)) is not None:
            i = found.end()
        else:
            break
    return i


def _class_end(pattern: str, start: int) -> int:
    """Where the class that opens at *start* ends (after its ``]``), or the
    end of *pattern*. A ``]`` first in the class, or escaped, is in it."""
    i = start + 1
    if pattern.startswith("^", i):
        i += 1
    if pattern.startswith("]", i):
        i += 1
    while i < len(pattern) and pattern[i] != "]":
        i += 2 if pattern[i] == "\\" else 1
    return min(i + 1, len(pattern))


@lru_cache(maxsize=512)
def fill_pattern(pattern: str) -> "re.Pattern[str] | None":
    """*pattern* compiled to read a normalised fill (``_pattern_source``),
    case-insensitive, or None when Python cannot compile it: such a var is
    never exempt."""
    try:
        return re.compile(_pattern_source(pattern), re.IGNORECASE | re.DOTALL)
    except re.error:
        return None


def fill_matches(pattern: str, fill: str) -> bool:
    """Whether the normalised *fill* is a wording *pattern* accepts: one of
    MAX_FILL_CHARS or fewer that the pattern matches whole."""
    if len(fill) > MAX_FILL_CHARS:
        return False
    compiled = fill_pattern(pattern)
    return compiled is not None and compiled.fullmatch(fill) is not None
