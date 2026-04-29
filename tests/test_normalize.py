# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for license text normalization logic.
"""

from licenseid.normalize import normalize_text


def test_normalize_whitespace() -> None:
    """Verify that multiple whitespaces and newlines are collapsed."""
    text = "  Multiple    spaces\n and\tline breaks.  "
    expected = "multiple spaces and line breaks"
    assert normalize_text(text) == expected


def test_normalize_punctuation() -> None:
    """Verify that smart quotes and various dashes are simplified."""
    # Smart quotes and dashes are all stripped
    text = "“Double” ‘Single’ —EmDash"
    expected = "double single emdash"
    assert normalize_text(text) == expected


def test_normalize_html() -> None:
    """Verify that HTML tags are stripped and content is preserved."""
    text = "<html><body><p>Hello <b>World</b></p></body></html>"
    expected = "hello world"
    assert normalize_text(text) == expected


def test_normalize_url() -> None:
    """Verify that URLs are normalized by removing protocols and punctuation."""
    text = "Visit https://spdx.org/licenses/"
    # http is kept, but punctuation stripped
    expected = "visit http spdx org licenses"
    assert normalize_text(text) == expected
