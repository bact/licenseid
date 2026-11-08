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
   no ``/``, no query; a ``#fragment`` and one trailing ``/`` go first).
2. Every ``%XX`` is decoded, in one pass (:func:`decode`): a ``%`` that
   decoding makes (``%2520`` is ``%20``) is never decoded again.
3. The decoded text must fit the character set of an expression
   (:data:`_PATH`), words one space apart. The set, not a list of escapes,
   refuses the rest: ``%2F``, ``%3F``, ``%23``, ``%3B``, ``%00``, ``%0A``,
   ``%C2%A0`` and a doubled encoding decode to a character outside it.
   :func:`licenseid.urlkey.url_key` itself decodes nothing.
4. Operators are ``AND`` and ``OR`` in upper case, ``WITH`` too; a word is a
   List ID, with a "+" or after ``WITH`` an exception. A phrase ("or
   later"), ``LicenseRef-*`` and an unknown ID name nothing here.
5. One licence is read as it is alone; several are cut, parsed and put in
   licenseid's canonical order (:mod:`licenseid.exprcanon`), each leaf read
   as :func:`licenseid.resolveleaf.read_leaf` reads it.

:mod:`licenseid.resolvecompound` imports :mod:`licenseid.resolveurl`, which
imports this module, so the compound is read here, not there. Standard
library and ``licenseid`` only.
"""

import re
from typing import Final

from licenseid.exprcanon import (
    Token,
    join_leaves,
    leaves,
    missing_operator,
    oversize,
    parse,
    split,
    unbracketed,
    written_upper,
)
from licenseid.exprtokens import is_addition_ref, is_license_ref
from licenseid.listlookup import ListLookup, fold_case
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
    rest = _SCHEME.sub("", url.partition("#")[0], count=1)
    raw = rest.partition("/")[2].removesuffix("/")
    if fold_case(raw) != key[len(HOST) :]:
        return None  # the key dropped more than case: .txt, a query, ...
    text = decode(raw)
    return text if _PATH.fullmatch(text) else None


def read_expression(db: ListLookup, lead: Step, found: Found) -> bool:
    """Read the expression of *lead* (a step from the URL to the decoded
    text) into *found*: *lead*, the steps of each leaf, then those that
    bring the expression to its canonical form. True with ``malformed`` or
    ``unresolved`` and a reason for an expression the grammar refuses, or one
    leaf the leaf reader refuses; False if it names nothing."""
    outer = lead["to"]
    text = unbracketed(outer)  # as resolve() takes them off the whole value
    steps = [lead] if text == outer else [lead, step("brackets", True, outer, text)]
    tokens = split(text)
    words = [text[leaf.start : leaf.end] for leaf in leaves(tokens)]
    if not _is_expression(text, tokens, words):
        return False
    if len(tokens) == 1:
        return _read_one(db, text, steps, found)
    too_big = oversize(tokens)
    if too_big is not None:
        return _refuse(found, "unresolved", too_big)
    return _read_several(db, (text, tokens, words), steps, found)


def _is_expression(text: str, tokens: list[Token], words: list[str]) -> bool:
    """Whether *text*, cut into *tokens* and the leaves *words*, is of the
    shape a path reads: a leaf at least, operators in upper case, no two
    operands side by side, and each leaf an ID or an ID with its exception."""
    if not words or not written_upper(text, tokens) or missing_operator(tokens):
        return False
    return all(_is_leaf(word) for word in words)


def _read_several(
    db: ListLookup,
    cut: tuple[str, list[Token], list[str]],
    steps: list[Step],
    found: Found,
) -> bool:
    """Read the *cut* expression (text, tokens, leaf words) of several
    leaves after *steps*: each leaf alone, then the grammar, then the
    canonical form. A leaf the leaf reader refuses is the refusal."""
    text, tokens, words = cut
    read: dict[str, Found] = {}
    for word in dict.fromkeys(words):
        reading = read[word] = Found()
        if not read_leaf(db, word, reading) or reading.reason is not None:
            return _refuse_leaf(found, reading)
    tree = parse(tokens, words)
    if isinstance(tree, str):
        return _refuse(found, "malformed", tree)
    expression, moves, expansions = join_leaves(
        text,
        tokens,
        tree,
        [(str(read[w].expression), read[w].steps, read[w].expansions) for w in words],
    )
    found.steps = [*steps, *moves]
    found.expansions += expansions
    found.expression = expression
    return True


def _read_one(db: ListLookup, text: str, steps: list[Step], found: Found) -> bool:
    """Read *text*, one leaf, after *steps*, as the leaf reader reads it;
    False if it names nothing."""
    reading = Found()
    if not read_leaf(db, text, reading):
        return False
    found.steps = [*steps, *reading.steps]
    copy_reading(found, reading)
    return True


def _is_leaf(word: str) -> bool:
    """Whether *word*, a leaf of the expression, is an ID alone or an ID,
    ``WITH`` and an exception: no phrase, no ``+`` apart, no reference."""
    parts = word.split(" ")
    if any(is_license_ref(p.rstrip("+")) or is_addition_ref(p) for p in parts):
        return False  # a reference names nothing the List knows
    return len(parts) == 1 or (len(parts) == _WITH_WORDS and parts[1] == "WITH")


def _refuse_leaf(found: Found, reading: Found) -> bool:
    """Make *found* the refusal of a leaf that was read and refused (its
    reason, category and steps); False for a leaf that names nothing."""
    if reading.reason is None:
        return False
    _refuse(found, reading.category or "unresolved", reading.reason)
    found.steps = list(reading.steps)
    return True


def _refuse(found: Found, category: Category, reason: str) -> bool:
    """Make *found* a claim that names no licence, for *reason*; True."""
    refuse(found, category, reason)
    return True
