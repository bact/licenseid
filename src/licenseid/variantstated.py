# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The words of a declared value that state its variant (roadmap item 52): the
reader behind ``variant_stated`` of a tag, a field or an ID (``GPL-2.0 only``,
``GPL-2.0+``, ``GPL-2.0 or later``), and where an ID stands in a text.
:func:`supports` is called by :func:`licenseid.variants.stated_of`.
"""

import re
from typing import Final

from licenseid.classify import grant_end, has_or_later_language, same_version
from licenseid.listlookup import fold_case
from licenseid.normalize import strip_comment_prefixes
from licenseid.plusoperator import PLUS_OPERATOR
from licenseid.types import Evidence

#: An "or" that may start a grant ("GPL-2.0. or later"): :func:`grant_end` reads it.
_OR_WORD: Final = re.compile(r"(?<![\w-])or\b", re.IGNORECASE | re.ASCII)


def _family_pattern(family: str) -> re.Pattern[str]:
    """Where a value names *family* (``GPL-2.0``), in any spelling of its
    name: ``GPLv2``, ``GPL-2``, ``GPL 2.0`` (the ``LGPL`` of ``LGPLv2`` is no
    ``GPL``)."""
    parts = re.fullmatch(r"([A-Za-z]+)-(\d+(?:\.\d+)*)(-.+)?", family)
    if parts is None:
        return re.compile(rf"(?<![\w.:-]){re.escape(family)}(?!\w)", re.IGNORECASE)
    name, version, rest = parts.groups()
    loose = rf"[-\s]?v?{re.escape(_plain_version(version))}(?:\.0)*"
    return re.compile(
        rf"(?<![A-Za-z0-9.:-]){name}{loose}{re.escape(rest or '')}(?!\w|\.\d)",
        re.IGNORECASE,
    )


def supports(item: tuple[str, str, str], evidence: Evidence | None, many: bool) -> bool:
    """Whether the *evidence* says the licence *family* is ``-only`` or
    ``-or-later`` (*item*: its kind, "only" or "later", the family and the form,
    the ID or ID with "+" as the expression writes it). The ID itself in the
    value states it; so do the signals a text match chose; else the words right
    after the licence in the value (``GPL-2.0 only``, ``GPL-2.0+``, ``GPL-2.0 or
    later``), and where the value does not name the licence (a name,
    ``GPLv3-or-later``) the words of the value, if it has one licence (*many*
    false). Another licence's words are never read. A form licenseid *decided*
    (``GPL-2.0-only AND GPL-2.0``: the second, read ``-only``) is never stated,
    even where another operand of the value is. No evidence, none."""
    kind, family, form = item
    if not evidence:
        return False
    value = evidence.get("value", "")
    if fold_case(form) in {fold_case(d) for d in evidence.get("decided", [])}:
        return False
    if times_written(form, value):  # the ID itself is in the input
        return True
    if "later" in evidence or "only" in evidence:  # a text match
        return bool(evidence.get(kind))
    if "\n" in value or "\r" in value:  # a grant wrapped onto a comment line
        value = " ".join(strip_comment_prefixes(v) for v in _LINES.split(value))
    named = list(_family_pattern(family).finditer(value))
    if named:  # the licence may stand twice: ``GPL-2.0-only OR GPL-2.0+``
        own = re.search(r"\d[\d.]*$", family)
        return any(
            _words(kind, value, found.end(), own=own.group() if own else "")
            for found in named
        )
    return not many and _words(kind, value, 0, whole=True)


#: What may stand between a licence and the words that state its variant: an
#: exception, marks, the licence's own version ("GPL-2.0, version 2 or later").
_LEAD: Final = re.compile(
    r"(?:(?:-with-|\s+with\s+)[\w.-]+)?[\s,.()\[\]-]*",
    re.IGNORECASE,
)
_LINES: Final = re.compile(r"\r\n?|\n")
_VERSION: Final = re.compile(r"version\s+(\d[\d.]*)[\s,)\]]*", re.IGNORECASE)
_ONLY_SUFFIX: Final = re.compile(r"(?<![A-Za-z0-9])only\b", re.IGNORECASE)
_LATER_SUFFIX: Final = re.compile(r"(?<![A-Za-z0-9])or[\s-]+later\b", re.IGNORECASE)


def _words(
    kind: str, value: str, at: int, *, whole: bool = False, own: str = ""
) -> bool:
    """Whether the words of *value* say *kind* ("only" or "later"): right
    after *at*, the end of a licence, or (*whole*) anywhere in it, where a
    dash may join them to a re-spelt ID (``GPLv3-or-later``)."""
    if whole:
        if kind == "only":
            return _ONLY_SUFFIX.search(value) is not None
        return bool(
            _LATER_SUFFIX.search(value)
            or PLUS_OPERATOR.search(value)
            or has_or_later_language(value)
            or any(
                grant_end(value, m.start()) is not None
                for m in _OR_WORD.finditer(value)
            )
        )
    lead = _LEAD.match(value, at)
    head = lead.end() if lead else at
    version = _VERSION.match(value, head)
    if version and _same_version(version.group(1), own):
        head = version.end()  # the licence's own version, not another's
    tail = value[head:]
    if kind == "only":
        return re.match(r"only\b", tail, re.IGNORECASE) is not None
    return bool(
        tail.startswith("+")
        or (
            re.match(r"or\b", tail, re.IGNORECASE)
            and grant_end(value, head) is not None
        )
        or (
            re.match(r"any\b", tail, re.IGNORECASE) and has_or_later_language(tail[:40])
        )
    )


def _plain_version(version: str) -> str:
    parts = version.rstrip(".").split(".")
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def _same_version(said: str, own: str) -> bool:
    """Whether the version *said* is the licence's *own* (``2`` is ``2.0``)."""
    return bool(own) and same_version(said, own)


def times_written(license_id: str, text: str) -> int:
    """How often *license_id* stands in *text* as a word of its own."""
    if not text:
        return 0
    pattern = rf"(?<![\w.+-]){re.escape(license_id)}(?![\w-])"
    return len(re.findall(pattern, text, re.IGNORECASE | re.ASCII))
