# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The version key: one key for each way of writing an ID ("Apache2",
"apache 2", "Apache_2.0", "Apache-2.0"), and the row an input names by it.

Apart from looseid, so identifiers can read an ID before a "+" by it
without importing looseid, which imports identifiers.
"""

import re

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
