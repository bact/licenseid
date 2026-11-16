# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The version key: one key for each way of writing an ID ("Apache2",
"apache 2", "Apache_2.0", "Apache-2.0"), and the row an input names by it.

Apart from looseid, so identifiers can read an ID before a "+" by it
without importing looseid, which imports identifiers.

The key folds ``N.0`` to ``N``, so a bare major (``Apache-1``) shares its key
with ``Apache-1.0``. Where the List has another minor of the same ID
(``Apache-1.1``) the cut value names none of them: :func:`ambiguous_ids`.
"""

import re
from collections.abc import Iterable

from licenseid.listlookup import ListedName, ListLookup
from licenseid.normalize import normalize_text
from licenseid.plusoperator import replace_plus_operator

# The longest input read as a loose ID: the longest SPDX ID has 36
# characters. A longer input names no ID, and its key would cost a second
# normalize_text() of a text that can be megabytes in one word.
MAX_KEY_INPUT = 100
# "v" directly before a digit is a version prefix: "GPLv3", "v2.0".
_RE_VERSION_PREFIX = re.compile(r"v(?=\d)", re.IGNORECASE)
# A boundary between a letter and a digit: "Apache2", "0BSD".
_RE_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
# A whole version number whose every part after the major is 0: "2.0" and
# "2.0.0", not "1.2.0", "2.0.1" or "2.00". The lookarounds keep it to the
# whole number: no digit, and no digit and full stop, before it ("1.2.0"
# keeps its "2.0"), while a full stop alone is a separator ("Apache.2.0").
# After it, a full stop ends a sentence.
_RE_ZERO_VERSION = re.compile(r"(?<!\d)(?<!\d\.)(\d+)(?:\.0){1,2}(?!\.?\d)")


def version_key(text: str, *, line_rules: bool = True) -> str:
    """*text* as a version-tolerant ID: "Apache2", "apache 2", "Apache_2.0"
    and "Apache-2.0" all give "apache 2", and "CC by 3 nl" gives the key of
    CC-BY-3.0-NL.

    Order matters: the "+" operator becomes the "or later" it means while
    the ID it follows is still one token (plusoperator.replace_plus_operator,
    the reader expressions use), or GPL-2.0+ and GPL-2.0 would share a key;
    "_" becomes a space, as normalize_text() keeps it; the prefix goes before
    the split, or "GPLv3" would become "gplv 3"; the split goes before the
    fold, or "Apache2.0" would keep its ".0"; the fold reads the full stops
    normalize_text() drops ("2.0" and "2 0" differ). normalize_text() then
    folds case, dashes and punctuation as for an ID. *line_rules* false
    keeps the words normalize_text() takes off a line (a list or comment
    marker): :func:`licenseid.dropguard.dropped_words` compares the two.
    """
    text = replace_plus_operator(text, " or later").replace("_", " ")
    text = _RE_VERSION_PREFIX.sub(" ", text)
    text = _RE_LETTER_DIGIT.sub(" ", text)
    text = _RE_ZERO_VERSION.sub(r"\1", text)
    return normalize_text(text, line_rules=line_rules)


def keyed_row(db: ListLookup, key: str) -> ListedName | None:
    """The one row whose ID has *key*. A row in use wins over a deprecated
    one ("GPL2+" is GPL-2.0-or-later, not GPL-2.0+); two in use are none."""
    rows = db.get_names_by_key(version_key).get(key, []) if key else []
    rows = [row for row in rows if not row["is_deprecated"]] or rows
    return rows[0] if len(rows) == 1 else None


def named_row(db: ListLookup, text: str) -> ListedName | None:
    """The one row *text* names by its version key, or None; a text longer
    than MAX_KEY_INPUT names none."""
    text = text.strip()
    if len(text) > MAX_KEY_INPUT:
        return None
    return keyed_row(db, version_key(text))


# The last number a text writes: digits with the parts joined by full stops
# ("1.0.6"); a full stop with no digit after it ends a sentence ("Apache-1.").
_RE_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)*")
_RE_DIGITS = re.compile(r"[0-9]+")


def writes_bare_major(text: str) -> bool:
    """Whether the last number *text* writes is all digits, with no full stop
    and digit after it: ``Apache-1``, ``Apache 1.``, ``LGPLv2``, ``CC-BY-3-DE``
    are, ``Apache-1.0``, ``Python-2.0.1``, ``OLDAP-2.2`` and ``MIT`` are not.
    ASCII digits only: a text in other digits keeps the reading it has."""
    numbers = _RE_NUMBER.findall(text)
    return bool(numbers) and _RE_DIGITS.fullmatch(numbers[-1]) is not None


def sibling_keys(keys: Iterable[str], key: str) -> list[str]:
    """The keys of *keys* that are *key* with one or more numbers inserted
    right after its last number: ``apache 1 1`` and ``lgpl 2 1 only`` for
    ``apache 1`` and ``lgpl 2 only``, ``python 2 0 1`` for ``python 2``. A
    different word is no sibling (``cc by 3 de`` for ``cc by 3``), and no key
    is its own."""
    tokens = key.split()
    last = max((i for i, t in enumerate(tokens) if _RE_DIGITS.fullmatch(t)), default=-1)
    if last < 0:
        return []
    head, tail = " ".join(tokens[: last + 1]) + " ", tokens[last + 1 :]
    found = []
    for other in keys:
        if other == key or not other.startswith(head):
            continue
        rest = other[len(head) :].split()
        added = 0
        while added < len(rest) and _RE_DIGITS.fullmatch(rest[added]):
            added += 1
        if added and rest[added:] == tail:
            found.append(other)
    return found


def ambiguous_ids(db: ListLookup, text: str) -> list[str]:
    """The IDs a bare major *text* may mean, sorted: its own row and the
    rows of the other minors of the List (deprecated ones too), or an empty
    list if *text* is no bare major, names no row, or the row is an
    ``-or-later`` form or ends in "+": a grant covers every later version,
    so the lowest is what was written (``LGPL-2-or-later``). The caller
    exempts a grant it has read off the text (``LGPLv2+``)."""
    text = text.strip()
    if len(text) > MAX_KEY_INPUT or not writes_bare_major(text):
        return []
    key = version_key(text)
    row = keyed_row(db, key)
    if row is None or row["license_id"].endswith(("-or-later", "+")):
        return []
    by_key = db.get_names_by_key(version_key)
    siblings = sibling_keys(by_key, key)
    if not siblings:
        return []
    rows = [*by_key[key], *(r for other in siblings for r in by_key[other])]
    return sorted({r["license_id"] for r in rows})
