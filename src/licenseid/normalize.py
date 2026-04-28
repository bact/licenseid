# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""License text normalisation per SPDX License List Matching Guidelines.

Reference: https://spdx.github.io/spdx-spec/v3.1-dev/annexes/
           license-matching-guidelines-and-templates/
"""

import re
from typing import Final

from bs4 import BeautifulSoup

# Guideline 0: HTML detection heuristic.
# Closing tags (</p>, </div>, …) are used in practice only in HTML — unlike
# opening tags, they are never used as plain-text placeholders such as
# <name>, <year>, or <organization> that appear in license templates.
_HTML_TAG: Final = re.compile(r"</[a-z][a-z0-9]*\s*>", re.IGNORECASE)

# Guideline 2: Collapse any sequence of whitespace to a single space.
_WHITESPACE: Final = re.compile(r"\s+")

# Guideline 3 / step 12: Remove remaining punctuation after the specific
# normalisations above. Keep alphanumerics and whitespace only.
_NON_WORD: Final = re.compile(r"[^\w\s]")

# Guideline 4 (hyphens): Any hyphen, dash, en dash, em dash, or similar
# variant shall be considered equivalent. Normalise to ASCII hyphen-minus.
# Unicode ranges covered: figure dash, en dash, em dash, horizontal bar,
# non-breaking hyphen, minus sign, small/full-width hyphen.
_DASHES: Final = re.compile(
    r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]"
)

# Guideline 4 (quotes): Any variation of quotations shall be considered
# equivalent. Normalise to ASCII single quote before stripping punctuation.
_QUOTES: Final = re.compile(
    r'["\u00AB\u00BB'  # " « »
    r"\u2018\u2019"  # ' '
    r"\u201A\u201B"  # ‚ ‛
    r"\u201C\u201D"  # " "
    r"\u201E\u201F"  # „ ‟
    r"\u2039\u203A"  # ‹ ›
    r"\u2032\u2033\u2034"  # ′ ″ ‴
    r"\u02B9\u02BA"  # ʹ ʺ
    r"\u02BB\u02BC\u02BD"  # ʻ ʼ ʽ
    r"]",
)

# Guideline 5a: Code comment prefixes at the start of a line.
# Covers: // /* * # ' (as VB comment) REM -- -}
# A trailing space/tab after the marker is also consumed.
_COMMENT_PREFIX: Final = re.compile(
    r"(?m)^[ \t]*"
    r"(?://|/\*|\*\)|/\*\*"  # C/Java-style
    r"|\*(?![\*\w])"  # lone * but not ** or word char
    r"|#"  # Shell / Python
    r"|'(?=[ \t])"  # VB-style (apostrophe then space)
    r"|REM(?=[ \t])"  # BASIC REM
    r"|--(?=[ \t])"  # Lua / SQL
    r"|-\})"  # Pascal end-comment
    r"[ \t]*",
)

# Guideline 5b: Repeated non-letter separator characters (3 or more),
# e.g. ---, ===, ___, ***. Used as visual dividers, not meaningful text.
_SEPARATOR: Final = re.compile(r"([^\w\s])\1{2,}")

# Guideline 6: Bullets and list-item markers at the start of a line,
# followed by a space, are ignored.
# Covers: *, -, •, 1. a. (1) (a) iv.
_BULLETS: Final = re.compile(
    r"(?m)^[ \t]*"
    r"(?:"
    r"[*\-•◦‣▪▸]"  # symbol bullets
    r"|(?:[0-9]{1,3}|[a-zA-Z])[.)\/]"  # 1. / a. / 1) / a/
    r"|\(?[0-9]{1,3}[.)]\)?"  # (1) / (1. / 1.)
    r"|\(?[a-zA-Z][.)]\)?"  # (a) / a.
    r"|[ivxlcdmIVXLCDM]{1,6}\."  # roman numerals
    r")"
    r"[ \t]+",
)

# Guideline 7: Varietal word spelling
# Pairs of equivalent spellings; both map to the same canonical form.
# Source: https://spdx.org/licenses/equivalentwords.txt
_VARIETAL_WORDS: Final[dict[str, str]] = {
    "acknowledgment": "acknowledgement",
    "analogue": "analog",
    "analyse": "analyze",
    "artefact": "artifact",
    "authorisation": "authorization",
    "authorised": "authorized",
    "calibre": "caliber",
    "cancelled": "canceled",
    "capitalisations": "capitalizations",
    "catalogue": "catalog",
    "categorise": "categorize",
    "centre": "center",
    "emphasised": "emphasized",
    "favour": "favor",
    "favourite": "favorite",
    "fulfil": "fulfill",
    "fulfilment": "fulfillment",
    "initialise": "initialize",
    "judgment": "judgement",
    "labelling": "labeling",
    "labour": "labor",
    "licence": "license",
    "maximise": "maximize",
    "modelled": "modeled",
    "modelling": "modeling",
    "non-commercial": "noncommercial",
    "offence": "offense",
    "optimise": "optimize",
    "organisation": "organization",
    "organise": "organize",
    "owner": "holder",
    "per cent": "percent",
    "practise": "practice",
    "programme": "program",
    "realise": "realize",
    "recognise": "recognize",
    "signalling": "signaling",
    "sub-license": "sublicense",
    "sub license": "sublicense",
    "utilisation": "utilization",
    "whilst": "while",
    "wilful": "wilfull",
}

# Guideline 8: Copyright symbol equivalence — ©, Ⓒ, ⓒ.
# Normalise to the ASCII form "(c)" before lowercasing.
_COPYRIGHT_SYMBOL: Final = re.compile(r"[©Ⓒⓒ]")

# Guideline 9: Copyright notice — remove lines starting with a copyright
# indicator (©, Ⓒ, ⓒ, (c), (C), Copyright).  Must run before lowercasing so
# the capital-C check works.
_COPYRIGHT_NOTICE: Final = re.compile(
    r"(?m)^[ \t]*(?:[©Ⓒⓒ]|\(c\)|\(C\)|Copyright)(?=[ \t\d(])[^\n]*",
    re.IGNORECASE,
)

# Guideline 12: HTTP protocol — https:// and http:// are equivalent.
_HTTPS: Final = re.compile(r"https://")


def normalize_text(text: str) -> str:
    """Normalise license text per SPDX License List Matching Guidelines.

    Applies the following transformations, in order:

    1.  HTML → plain text (if HTML markup is detected).
    2.  Copyright notice removal (guideline 9).
    3.  Code comment prefix removal (guideline 5a).
    4.  Repeated separator removal — ---/===/*** (guideline 5b).
    5.  Bullet and list-marker removal (guideline 6).
    6.  URL normalisation — https:// → http:// (guideline 12).
    7.  Copyright symbol normalisation — © Ⓒ ⓒ → (c) (guideline 8).
    8.  Dash/hyphen normalisation — all variants → - (guideline 4).
    9.  Quote normalisation — all variants → ' (guideline 4).
    10. Case normalisation — all letters → lowercase (guideline 3).
    11. Varietal word spelling normalisation (guideline 7).
    12. Remaining punctuation removal.
    13. Whitespace collapse — all whitespace → single space (guideline 2).

    Args:
        text: Raw license text, possibly containing HTML markup or code
            comment characters.

    Returns:
        Normalised text suitable for fuzzy license matching.
    """
    # 1. HTML to plain text
    if _HTML_TAG.search(text):
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator="\n")

    # 2. Copyright notice removal (before lowercasing)
    text = _COPYRIGHT_NOTICE.sub("", text)

    # 3. Code comment prefix removal (per-line, before whitespace collapse)
    text = _COMMENT_PREFIX.sub("", text)

    # 4. Repeated separator characters
    text = _SEPARATOR.sub(" ", text)

    # 5. Bullet and list-marker removal (per-line)
    text = _BULLETS.sub("", text)

    # 6. URL normalisation
    text = _HTTPS.sub("http://", text)

    # 7. Copyright symbol normalisation
    text = _COPYRIGHT_SYMBOL.sub("(c)", text)

    # 8. Dash/hyphen normalisation (before stripping punctuation)
    text = _DASHES.sub("-", text)

    # 9. Quote normalisation (before stripping punctuation)
    text = _QUOTES.sub("'", text)

    # 10. Case normalisation
    text = text.lower()

    #11. Varietal word spelling
    for variant, canonical in _VARIETAL_WORDS.items():
        text = text.replace(variant, canonical)

    # 12. Remaining punctuation removal
    text = _NON_WORD.sub(" ", text)

    # 13. Whitespace collapse
    return _WHITESPACE.sub(" ", text).strip()
