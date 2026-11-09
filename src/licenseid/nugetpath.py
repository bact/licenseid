# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The licence expression in the path of a ``licenses.nuget.org`` URL
(issue #187).

NuGet's ``licenseUrl`` for a package that declares a licence expression is
``https://licenses.nuget.org/`` and the expression as the path, URL-encoded:
a space is ``%20``, ``(``, ``)`` and ``+`` stay as written (source:
https://learn.microsoft.com/en-ie/nuget/nuget-org/licenses.nuget.org). The
path is another licence expression, so it is read as one, in this order:

1. Only a URL of that host is read, and only a path that is the URL's own
   last segment as written (the key dropped nothing but case: no ``.txt``,
   no ``/``, no query; a ``#fragment``, an empty ``?`` and one trailing
   ``/`` go first).
2. Every ``%XX`` is decoded, in one pass (:func:`decode`): a ``%`` that
   decoding makes (``%2520`` is ``%20``) is never decoded again.
3. The decoded text must fit the character set of an expression
   (:data:`_PATH`), words one space apart. The set, not a list of escapes,
   refuses the rest: ``%2F``, ``%3F``, ``%23``, ``%3B``, ``%00``, ``%0A``,
   ``%C2%A0`` and a doubled encoding decode to a character outside it.
   :func:`licenseid.urlkey.url_key` itself decodes nothing.
4. Operators are ``AND`` and ``OR`` in upper case, ``WITH`` too; a word is a
   List ID (case folded as the List folds it), with a "+" or after ``WITH``
   an exception ID. A loose spelling (``Apache2``, ``GPLv3``), a phrase ("or
   later"), ``LicenseRef-*`` and an unknown ID name nothing here: NuGet
   serves only a valid SPDX expression.
5. One licence is read as it is alone; several are cut, parsed and put in
   licenseid's canonical order (:mod:`licenseid.exprcanon`), each leaf read
   as :func:`licenseid.resolveleaf.read_leaf` reads it (so a rename and a
   deprecation read as they do for the ID). A refusal has no step.

:mod:`licenseid.resolvecompound` imports :mod:`licenseid.resolveurl`, which
imports this module, so the compound is read here, not there. Standard
library and ``licenseid`` only.
"""

import re
from typing import Final

from licenseid.exprcanon import (
    Token,
    cut,
    join_leaves,
    missing_operator,
    oversize,
    parse,
    unbracketed,
    written_upper,
)
from licenseid.listlookup import ListLookup, fold_case
from licenseid.plusoperator import strip_plus_operator
from licenseid.resolveleaf import Found, read_leaf, refuse
from licenseid.resolvertypes import Category, Step, step
from licenseid.resolvetrove import copy_reading

HOST: Final = "licenses.nuget.org/"
DETAIL: Final = "expression in path"

# The characters of an expression, words one space apart: linear, as the
# space is the only thing that tells two words apart.
_PATH: Final = re.compile(r"[A-Za-z0-9.+()-]+(?: [A-Za-z0-9.+()-]+)*")
_PERCENT: Final = re.compile(r"%([0-9A-Fa-f]{2})")
_SCHEME: Final = re.compile(r"\Ahttps?://", re.IGNORECASE)
_WITH_WORDS: Final = 3  # ID, WITH, exception


def decode(raw: str) -> str:
    """*raw* with every ``%XX`` replaced by the character of that code
    point, once: no result is decoded again."""
    return _PERCENT.sub(lambda match: chr(int(match[1], 16)), raw)


def decoded_path(url: str, key: str) -> str | None:
    """The expression in the path of *url*, whose key
    (:func:`licenseid.urlkey.url_key`) is *key*, or None: not this host, a
    path that is not the last segment as written, or a decoded text outside
    the character set of an expression."""
    if not key.startswith(HOST):
        return None
    rest, _, query = _SCHEME.sub("", url.partition("#")[0], count=1).partition("?")
    if query:
        return None  # defence in depth: the key comparison below refuses it too
    raw = rest.partition("/")[2].removesuffix("/")
    if fold_case(raw) != key[len(HOST) :]:
        return None  # the key dropped more than case: .txt, a query, ...
    text = decode(raw)
    return text if _PATH.fullmatch(text) else None


def read_expression(db: ListLookup, lead: Step, found: Found) -> bool:
    """Read the expression of *lead* (a step from the URL to the decoded
    text) into *found*: *lead*, the steps of each leaf, then those that
    bring the expression to its canonical form. True, with no step, for an
    expression the grammar refuses or a leaf the leaf reader refuses
    (``malformed`` or ``unresolved`` and a reason); False if it names
    nothing."""
    outer = lead["to"]
    text = unbracketed(outer)  # as resolve() takes them off the whole value
    steps = [lead] if text == outer else [lead, step("brackets", True, outer, text)]
    tokens, _, words = cut(text)
    if not _is_expression(db, text, tokens, words):
        return False
    too_big = oversize(tokens)
    if too_big is not None:
        return _refuse(found, "unresolved", too_big)
    read = _read_words(db, words)
    if read is None:
        return False
    refused = [r for r in read.values() if r.reason is not None]
    if refused:
        return _refuse(
            found, refused[0].category or "unresolved", str(refused[0].reason)
        )
    return _assemble((text, tokens, words), read, steps, found)


def _read_words(db: ListLookup, words: list[str]) -> dict[str, Found] | None:
    """The reading of each distinct leaf of *words*, or None if the leaf
    reader finds nothing in one."""
    read: dict[str, Found] = {}
    for word in dict.fromkeys(words):
        read[word] = Found()
        if not read_leaf(db, word, read[word]):
            return None
    return read


def _assemble(
    cut_text: tuple[str, list[Token], list[str]],
    read: dict[str, Found],
    steps: list[Step],
    found: Found,
) -> bool:
    """Put the expression of *cut_text* (text, tokens, leaf words), whose
    leaves are in *read*, into *found* after *steps*: the leaf as it is for
    one, else the parse and the canonical form."""
    text, tokens, words = cut_text
    readings = [read[word] for word in words]
    if len(tokens) == 1:
        found.steps = [*steps, *readings[0].steps]
        copy_reading(found, readings[0])
        return True
    tree = parse(tokens, words)
    if isinstance(tree, str):
        return _refuse(found, "malformed", tree)
    expression, moves, expansions = join_leaves(
        text,
        tokens,
        tree,
        [(str(r.expression), r.steps, r.expansions) for r in readings],
    )
    found.steps = [*steps, *moves]
    found.expansions += expansions
    found.expression = expression
    return True


def _is_expression(
    db: ListLookup, text: str, tokens: list[Token], words: list[str]
) -> bool:
    """Whether *text*, cut into *tokens* and the leaves *words*, is of the
    shape a path reads: a leaf at least, operators in upper case, no two
    operands side by side, and each leaf an ID of the List or such an ID,
    ``WITH`` and an exception of the List."""
    if not words or not written_upper(text, tokens) or missing_operator(tokens):
        return False
    return all(_is_leaf(db, word) for word in words)


def _is_leaf(db: ListLookup, word: str) -> bool:
    """Whether *word* is an ID of the List (case folded as the List folds it,
    with a "+" if the "+" operator takes one), or such an ID, ``WITH`` and
    an exception ID of the List. Not a phrase, a ``LicenseRef-*`` or a loose
    spelling (``Apache2``, ``GPLv3``): NuGet serves a valid SPDX expression."""
    parts = word.split(" ")
    if len(parts) == _WITH_WORDS and parts[1] == "WITH":
        return _is_licence(db, parts[0]) and _is_exception(db, parts[2])
    return len(parts) == 1 and _is_licence(db, word)


def _is_licence(db: ListLookup, word: str) -> bool:
    """Whether *word* is a licence ID of the List, or one with a "+" operator."""
    return any(
        db.get_license_details(base) is not None
        for base in (word, strip_plus_operator(word))
    )


def _is_exception(db: ListLookup, word: str) -> bool:
    """Whether *word* is an exception ID of the List."""
    return db.get_exception_details(word) is not None


def _refuse(found: Found, category: Category, reason: str) -> bool:
    """Make *found* a claim that names no licence, for *reason*: no step, as
    a page the List refuses has none. True."""
    refuse(found, category, reason)
    return True
