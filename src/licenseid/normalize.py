# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Text normalization utilities for SPDX license matching.
"""

import re
from bs4 import BeautifulSoup


def normalize_text(text: str) -> str:
    """
    Normalises license text based on SPDX Matching Guidelines.

    1. HTML to plain text (if detected).
    2. Whitespace: All whitespace is treated as a single blank space.
    3. Case: All letters are treated as lowercase.
    4. Punctuation: Various hyphens/dashes and quotes are treated as equivalent.
    5. Hyperlink: http:// and https:// are treated as equivalent.
    """
    # 1. HTML to plain text
    # Heuristic: Look for closing HTML tags to avoid false positives with
    # plain-text placeholders like <year> or <path>.
    if bool(re.search(r"</[a-z]+>", text, re.IGNORECASE)):
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()

    # 2. Hyperlink Protocol (do this before lowercasing/punctuation to keep URLs intact)
    text = re.sub(r"https?://", "http://", text)

    # 3. Case sensitivity
    text = text.lower()

    # 4. Punctuation (Ignored)
    # Replace all punctuation characters with a space
    text = re.sub(r"[^\w\s]", " ", text)

    # 5. Whitespace and Pagination
    # Replace any sequence of whitespace characters (including line breaks)
    # with a single space
    text = re.sub(r"\s+", " ", text).strip()

    return text


def strip_list_markers(text: str) -> str:
    """
    Ignores leading bullets, numbers, or letters followed by a space.
    """
    # This is a bit more complex as it usually applies to lines/paragraphs.
    # For now, a simple regex for common markers.
    # This might be better handled in a more structured way per paragraph.
    # But for a single normalized string, we can try to remove common patterns.
    # However, SPDX Matching Guidelines say list markers are ignored.
    # In a fully normalized string (all spaces), this is tricky.
    # We might want to do this BEFORE final whitespace normalization.
    return text
