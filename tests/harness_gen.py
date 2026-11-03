# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""One seeded, grammar-based generator of adversarial licence values, for
tests, reviewers and fixers: ``python -c "from harness_gen import generate;
print(*generate(7, 20), sep=chr(10))"`` from ``tests/``. Deterministic per
seed (``random.Random(seed)``, no clock, no hash order).

The grammar is the shape of a declared value: an atom (an ID, a name, a
loose spelling) with the things a human adds around it (quote marks, end
marks, a ``+``, an "or later" phrasing, operators between atoms, brackets, a
tag prefix, odd white space, Unicode), then a few slips (a cut, a case flip,
a doubled or dropped character). Any ``str`` it makes is a valid input of
``resolve()`` and ``detect(text=...)``."""

import random
from collections.abc import Callable, Iterator

from ordering_helpers import PHRASES
from resolver_corpus import EXCEPTION_LIST, LICENSE_LIST, list_rows


def u(spec: str) -> str:
    """The characters of the hex code points in *spec* (a formatter rewrites
    a literal escape into the character, which no reader can tell apart)."""
    return "".join(chr(int(code, 16)) for code in spec.split())


#: Atoms that are no List entry: loose spellings, near misses, references.
LOOSE = (
    "Apache2",
    "Apache 2",
    "Apache License, Version 2.0",
    "GPLv3",
    "GPLv2 or any later version",
    "GNU GPL v2",
    "LGPL 2.1",
    "BSD",
    "BSD 3-Clause License",
    "MIT License",
    "The MIT License (MIT)",
    "ISC license",
    "MPL 2.0",
    "CC0",
    "Public Domain",
    "Proprietary",
    "LicenseRef-Custom",
    "LicenseRef-x.y-1",
    "License :: OSI Approved :: MIT License",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "No-Such-1.0",
    "UNKNOWN",
    "see LICENSE",
)
#: The IDs most values name, so the operators meet the ones that matter.
COMMON = (
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-or-later",
    "LGPL-2.1",
    "LGPL-3.0-only",
    "AGPL-3.0",
    "MPL-2.0",
    "Zlib",
)
QUOTES = (
    ('"', '"'),
    ("'", "'"),
    (u("201c"), u("201d")),
    (u("2018"), u("2019")),
    (u("201e"), u("201c")),
    (u("ab"), u("bb")),
    (u("300c"), u("300d")),
    ("`", "`"),
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
    ("<", ">"),
    ('"', ""),
    ("", ")"),
)
END_MARKS = (".", "?", "!", ",", ";", ":", u("3002"), u("2026"), "...", ".)", u("b7"))
OPERATORS = (
    " OR ",
    " AND ",
    " WITH ",
    " or ",
    " and ",
    " With ",
    " / ",
    " & ",
    ", ",
    " ; ",
    ";",
    " | ",
    " || ",
    " + ",
    " - ",
    "\tOR\t",
    u("a0") + "OR" + u("a0"),
    " OR  ",
    " OR\u001fAND ",
    " OR OR ",
    " AND OR ",
)
PLUSES = ("+", " +", "++", "+ ", "+.", "+)", u("207a"), u("ff0b"))
SPACES = (
    " ",
    "  ",
    "\t",
    u("a0"),
    u("2003"),
    u("3000"),
    u("200b"),
    u("feff"),
    u("1c"),
    u("1d"),
    u("1e"),
    u("1f"),
    u("85"),
    u("2028"),
    "\r",
    "\n",
    "\x0b",
    "\x0c",
)
UNICODE = (
    u("e9"),
    u("65 301"),
    u("130"),
    u("df"),
    u("1c5"),
    u("212a"),
    u("fb01"),
    u("627"),
    u("202e"),
    u("1f600"),
    u("10000"),
    u("0"),
    u("7f"),
    u("80"),
    u("2011"),
    u("2212"),
    u("ff2d ff29 ff34"),
    u("dcff"),
)
TAGS = (
    "SPDX-License-Identifier: ",
    "License: ",
    "license = ",
    "License-Expression: ",
    "Licence: ",
    "(c) 2024 Someone. ",
    "SPDX-License-Identifier:",
    "REM ",
    "# ",
)
BRACKETS = (("(", ")"), ("((", "))"), ("(", ""), ("", ")"), ("[", "]"))


class Source:
    """The pieces the grammar draws on, built once: every ID and name of the
    List fixtures and its exceptions."""

    def __init__(self) -> None:
        licences = list_rows(LICENSE_LIST, "licenses")
        exceptions = list_rows(EXCEPTION_LIST, "exceptions")
        self.ids = tuple(str(row[0]) for row in licences)
        self.names = tuple(str(row[1]) for row in licences)
        self.exceptions = tuple(str(row[0]) for row in exceptions)
        self.phrases = tuple(PHRASES)


_SOURCE: list[Source] = []


def source() -> Source:
    """The shared :class:`Source`."""
    if not _SOURCE:
        _SOURCE.append(Source())
    return _SOURCE[0]


def _atom(rng: random.Random, src: Source) -> str:
    makers: tuple[Callable[[], str], ...] = (
        lambda: rng.choice(COMMON),
        lambda: rng.choice(src.ids),
        lambda: rng.choice(src.ids),
        lambda: rng.choice(src.names),
        lambda: rng.choice(LOOSE),
        lambda: rng.choice(src.ids).lower(),
        lambda: rng.choice(COMMON) + " " + rng.choice(src.phrases),
        lambda: rng.choice(src.ids) + rng.choice(PLUSES),
        lambda: rng.choice(COMMON) + rng.choice(PLUSES),
    )
    return rng.choice(makers)()


def _expression(rng: random.Random, src: Source, depth: int) -> str:
    roll = rng.randrange(10)
    if depth <= 0 or roll < 4:
        return _atom(rng, src)
    if roll < 7:
        left, right = _expression(rng, src, depth - 1), _expression(rng, src, depth - 1)
        return left + rng.choice(OPERATORS) + right
    if roll == 7:
        return _expression(rng, src, depth - 1) + " WITH " + rng.choice(src.exceptions)
    opening, closing = rng.choice(BRACKETS)
    return opening + _expression(rng, src, depth - 1) + closing


def _quote(rng: random.Random, text: str) -> str:
    opening, closing = rng.choice(QUOTES)
    return opening + text + closing


def _spaces(rng: random.Random, text: str) -> str:
    return text.replace(" ", rng.choice(SPACES), rng.randrange(1, 4))


def _unicode(rng: random.Random, text: str) -> str:
    at = rng.randrange(len(text) + 1)
    return text[:at] + rng.choice(UNICODE) + text[at:]


def _slip(rng: random.Random, text: str) -> str:
    if not text:
        return text
    at = rng.randrange(len(text))
    kind = rng.randrange(4)
    if kind == 0:
        return text[:at]
    if kind == 1:
        return text.swapcase()
    if kind == 2:
        return text[:at] + text[at] + text[at:]
    return text[:at] + text[at + 1 :]


#: The decorations, each with its weight (out of 100) of being applied.
_DECORATIONS: tuple[tuple[int, Callable[[random.Random, str], str]], ...] = (
    (18, _quote),
    (22, lambda rng, text: text + rng.choice(END_MARKS)),
    (10, lambda rng, text: rng.choice(TAGS) + text),
    (16, _spaces),
    (14, lambda rng, text: rng.choice(SPACES) + text),
    (14, lambda rng, text: text + rng.choice(SPACES)),
    (14, _unicode),
    (12, _slip),
)


def one(rng: random.Random) -> str:
    """The next value of the stream *rng* drives."""
    src = source()
    text = _expression(rng, src, rng.randrange(4))
    for weight, decorate in _DECORATIONS:
        if rng.randrange(100) < weight:
            text = decorate(rng, text)
    return text


def generate(seed: int, count: int) -> Iterator[str]:
    """*count* values, the same ones for the same *seed*."""
    rng = random.Random(seed)
    for _ in range(count):
        yield one(rng)
