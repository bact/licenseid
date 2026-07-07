# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for license text normalization logic.
"""

from licenseid import normalize as normalize_module
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


def test_normalize_varietal_words() -> None:
    """Guideline 7: variant spellings map to their canonical form."""
    assert normalize_text("This Licence is granted") == "this license is granted"
    assert (
        normalize_text("the copyright owner grants")
        == "the copyright holder grants"
    )
    assert normalize_text("sub-license the work") == "sublicense the work"
    assert normalize_text("per cent of the fee") == "percent of the fee"
    assert normalize_text("free of charge & use") == "free of charge and use"
    # No substring bleed: a variant appearing inside a larger word/token is
    # left untouched.
    assert normalize_text("AT&T Labs") == "at t labs"
    assert normalize_text("unlicenced") == "unlicenced"


def test_normalize_bullets() -> None:
    """Guideline 6: bullets and list markers at line start are ignored."""
    text = "1. Redistributions of source\n(a) must retain\n- the above notice"
    expected = "redistributions of source must retain the above notice"
    assert normalize_text(text) == expected


def test_normalize_copyright_notice_kept_by_default() -> None:
    """Guideline 9 (copyright notice removal) is implemented but disabled
    by default: a full-corpus benchmark showed it costs more recall than
    it gains (see _STRIP_COPYRIGHT_NOTICE in normalize.py). Verify the
    off-by-default behavior: copyright text is left in place."""
    text = "Copyright (c) 2024 Example Corp\nPermission is hereby granted"
    expected = "copyright c 2024 example corp permission is hereby granted"
    assert normalize_text(text) == expected


def test_normalize_copyright_notice_when_enabled(monkeypatch) -> None:
    """Guideline 9: when enabled, copyright notice lines are removed."""
    monkeypatch.setattr(normalize_module, "_STRIP_COPYRIGHT_NOTICE", True)
    text = "Copyright (c) 2024 Example Corp\nPermission is hereby granted"
    assert normalize_text(text) == "permission is hereby granted"
    text = "© 2024 Someone\nThe software is provided as is"
    assert normalize_text(text) == "the software is provided as is"


def test_normalize_copyright_body_text_kept_when_enabled(monkeypatch) -> None:
    """When enabled, lines merely containing the word 'copyright' without a
    notice cue (digit, symbol, <year>) nearby are NOT removed."""
    monkeypatch.setattr(normalize_module, "_STRIP_COPYRIGHT_NOTICE", True)
    text = "Copyright and Related Rights include the following"
    expected = "copyright and related rights include the following"
    assert normalize_text(text) == expected


def test_normalize_comment_prefixes() -> None:
    """Guideline 5a: code comment prefixes are stripped per line."""
    text = "// Permission is hereby granted\n# to any person\n * obtaining a copy"
    expected = "permission is hereby granted to any person obtaining a copy"
    assert normalize_text(text) == expected


def test_normalize_separators() -> None:
    """Guideline 5b: repeated separator characters are ignored."""
    text = "----------\nMIT License\n=========="
    assert normalize_text(text) == "mit license"
