# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

from licenseid.normalize import normalize_text


def test_normalize_whitespace():
    text = "  Multiple    spaces\n and\tline breaks.  "
    expected = "multiple spaces and line breaks"
    assert normalize_text(text) == expected


def test_normalize_punctuation():
    # Smart quotes and dashes are all stripped
    text = "“Double” ‘Single’ —EmDash"
    expected = "double single emdash"
    assert normalize_text(text) == expected


def test_normalize_html():
    text = "<html><body><p>Hello <b>World</b></p></body></html>"
    expected = "hello world"
    assert normalize_text(text) == expected


def test_normalize_url():
    text = "Visit https://spdx.org/licenses/"
    # http is kept, but punctuation stripped
    expected = "visit http spdx org licenses"
    assert normalize_text(text) == expected
