# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules of ``resolve()`` that code and tests name (T1 to T3 in
:mod:`licenseid.resolvetrove`, P1 to P3 in :mod:`licenseid.resolveprose`),
each with an example. The answer, category and ``EXACT`` of the example are
not typed: ``measure`` reads them from ``resolve()``, and
``tests/test_lists_page.py`` pins what the maintainer decided."""

from collections.abc import Callable
from typing import Final, NamedTuple

from licenseid.resolveprose import (
    _after_article,
    _licence_word,
    _read_reduction,
    _reductions,
)
from licenseid.resolvetrove import _name, _trailing
from licenseid.trovenames import strip_trove_path


class Rule(NamedTuple):
    """One row of the rules table.

    Attributes:
        name: The name of the rule in code and tests.
        reads: What the rule reads.
        example: A value the rule reads.
        note: What decides the category or ``EXACT``.
        code: The function that is the rule, the id the page links it by:
            a renamed or removed function fails the import.
    """

    name: str
    reads: str
    example: str
    note: str
    code: Callable[..., object]


_PATH = "License :: OSI Approved :: "
_REWRITE = "a rewrite rule is no list"
_HEAD = "the head's; the inside need only give the same expression"
_ALIASES = "the category of `ALIASES`"

RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "T1",
        "a trove classifier in its real form, read as the name in it is "
        "read alone, with a `trove_path` step",
        _PATH + "MIT License",
        "the category of the name alone",
        strip_trove_path,
    ),
    Rule(
        "T1",
        "the same, for a name only the trove table knows",
        "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication",
        "a name of the trove table",
        strip_trove_path,
    ),
    Rule(
        "T2",
        "a name of the trove table that states one licence",
        "GNU General Public License v3 or later (GPLv3+)",
        "a bare deprecated ID stays `assumed_only`, also exact",
        _name,
    ),
    Rule(
        "T3",
        "`head (inside)` where head and inside each read alone as one "
        "expression, the same",
        "MIT License (MIT)",
        _HEAD,
        _trailing,
    ),
    Rule(
        "T3",
        "the same, where only the inside needed a rewrite rule",
        "Apache-2.0 (Apache2)",
        _HEAD,
        _trailing,
    ),
    Rule(
        "T3",
        "the same, where the head needed a rewrite rule",
        "Apache2 (Apache-2.0)",
        f"the head's: {_REWRITE}",
        _trailing,
    ),
    Rule(
        "P1",
        "a final `license` or `licence` after a value that reads alone",
        "BSD 3-Clause License",
        _REWRITE,
        _licence_word,
    ),
    Rule(
        "P2",
        "`<name> License[,] (Version|v) N` as `<name> N`, also with no "
        "`License` or with the version in brackets",
        "Apache License, Version 2.0",
        _REWRITE,
        _reductions,
    ),
    Rule(
        "P3",
        "a leading `The`, with P1, P2 or a List name",
        "The MIT License",
        _REWRITE,
        _after_article,
    ),
    Rule(
        "P1",
        "a prose form whose reduction is a name of `ALIASES`, the one table "
        "P1 asks besides the List",
        "New BSD License",
        _ALIASES,
        _read_reduction,
    ),
    Rule(
        "P3",
        "a leading `The` before such a prose form",
        "The New BSD License",
        _ALIASES,
        _after_article,
    ),
)
