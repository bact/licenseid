# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``coretext.core_text``: a template without its optional parts."""
# pylint: disable=missing-function-docstring

import json
import time
from pathlib import Path

import pytest
from timing import slack

from licenseid.coretext import core_text
from licenseid.normalize import normalize_text

FIXTURES = Path(__file__).parent / "fixtures"
BEGIN = "<<beginOptional>>"
END = "<<endOptional>>"


def var(original: str, name: str = "n", match: str = ".*") -> str:
    return f'<<var;name="{name}";original="{original}";match="{match}">>'


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("plain text", "plain text"),
        ("", ""),
        (f"a {BEGIN}b {END}c", "a c"),
        (f"a {BEGIN}b {BEGIN}c {END}d {END}e", "a e"),  # nested: one level back
        (f"a {BEGIN}b {END}c {BEGIN}d {END}e", "a c e"),
        (f"{BEGIN}all{END}", ""),
        (f"a {BEGIN}{BEGIN}{END}{END}b", "a b"),
        (f"x {var('Apache')} y", "x Apache y"),
        (f"x {BEGIN}{var('gone')}{END} y", "x y"),  # a var inside an optional
        (f"x {var('')} y", "x y"),  # empty original
        # An unescaped quote in the original (Python-2.0.1) and in the match.
        (var('this software ("Python")', match='a"b'), 'this software ("Python")'),
        (var("a;match=b", match="c"), "a;match=b"),
        # A mark's look-alikes are text.
        (
            "a << b <<x>> <<var>> <<beginOptional>",
            "a << b <<x>> <<var>> <<beginOptional>",
        ),
        # A "<" right before a mark (the GPL templates): it is in the optional part.
        (f"x {BEGIN}<{END} y", "x y"),
        (f"x <{BEGIN}z{END}<{END[2:]}", "x < <endOptional>>"),
        (f"x {BEGIN}a{END}>", "x >"),
        ("<<<", "<<<"),
    ],
    ids=[
        "plain",
        "empty",
        "optional",
        "nested",
        "two",
        "all",
        "empty-nested",
        "var",
        "var-in-optional",
        "empty-original",
        "quotes-in-original",
        "separator-in-original",
        "look-alikes",
        "angle-in-optional",
        "angle-before-mark",
        "angle-after",
        "angles",
    ],
)
def test_the_core_of_a_template(template: str, expected: str) -> None:
    core = core_text(template)
    assert core is not None
    assert " ".join(core.split()) == expected


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        # HPND, NTP-0: the template has no space beside the optional part.
        (f"modify{BEGIN},{END}and", "modify and"),
        (f"make{BEGIN}s{END}no", "make no"),
        (f"a{BEGIN}b{BEGIN}c{END}d{END}e", "a e"),
        (f"x{var('A')}y", "x A y"),
        (f"{var('A')}{var('B')}", "A B"),
        # A "<" that is text joins what is beside it.
        ("a<b", "a<b"),
        (f"a<{BEGIN}b{END}", "a<"),
    ],
    ids=["comma", "letter", "nested", "var", "adjacent-vars", "angle", "angle-mark"],
)
def test_a_mark_is_a_word_boundary(template: str, expected: str) -> None:
    core = core_text(template)
    assert core is not None
    assert " ".join(core.split()) == expected


def test_a_placeholder_original_is_kept() -> None:
    """The List's whole text holds the placeholder too (MIT's ``<year>
    <copyright holders>``): both sides of a comparison read it alike."""
    assert core_text(f"(c) {var('<year> <copyright holders>')} x") == (
        "(c)  <year> <copyright holders>  x"
    )


@pytest.mark.parametrize(
    "template",
    [
        f"a {BEGIN}b",
        f"a {END}",
        f"{END}{BEGIN}",
        f"{BEGIN}{BEGIN}a{END}",
        f"{BEGIN}a{END}{END}",
        '<<var;name="n";original="x";match="y">',
        '<<var;name="n";match="y">>',
        '<<var;name="n";original="x">>',
        '<<var;name="n";original="x";match="y',
        "<<var;",
        f"a {BEGIN}{var('x')[:-1]}",
    ],
    ids=[
        "unclosed",
        "stray-end",
        "end-first",
        "unclosed-nested",
        "extra-end",
        "var-end",
        "var-no-original",
        "var-no-match",
        "var-unterminated",
        "var-bare",
        "var-in-unclosed",
    ],
)
def test_a_malformed_template_has_no_core(template: str) -> None:
    assert core_text(template) is None


def _template(license_id: str) -> str:
    path = FIXTURES / "license-template" / f"{license_id}.template.txt"
    return path.read_text(encoding="utf-8")


def _text(license_id: str) -> str:
    path = FIXTURES / "license-text-long" / f"{license_id}.json"
    return str(json.loads(path.read_text(encoding="utf-8"))["license_text"])


def _words(text: str) -> int:
    return len(normalize_text(text).split())


@pytest.mark.parametrize("license_id", ["Apache-2.0", "HPND", "LGPL-3.0-only"])
def test_no_mark_is_left_in_a_real_core(license_id: str) -> None:
    core = core_text(_template(license_id))
    assert core is not None
    assert "<<beginOptional" not in core
    assert "<<endOptional" not in core
    assert "<<var;" not in core


@pytest.mark.parametrize(
    ("license_id", "whole", "core"),
    [("Apache-2.0", 1595, 1393), ("LGPL-3.0-only", 6888, 1211), ("HPND", 176, 45)],
)
def test_the_words_of_a_real_core(license_id: str, whole: int, core: int) -> None:
    text = core_text(_template(license_id))
    assert text is not None
    assert _words(_text(license_id)) == whole
    assert _words(text) == core


def test_the_core_of_apache_has_no_appendix() -> None:
    core = core_text(_template("Apache-2.0"))
    assert core is not None
    assert "Accepting Warranty or Additional Liability" in core
    assert "END OF TERMS AND CONDITIONS" not in core
    assert "APPENDIX" not in core
    assert "Licensed under the Apache License" not in core
    assert "APPENDIX" in _text("Apache-2.0")
    assert "Licensed under the Apache License" in _text("Apache-2.0")


def test_the_core_of_the_lgpl_has_no_copy_of_the_gpl() -> None:
    core = core_text(_template("LGPL-3.0-only"))
    assert core is not None
    whole = _text("LGPL-3.0-only")
    assert "Exception to Section 3" in core
    assert "How to Apply These Terms" not in core
    assert "How to Apply These Terms" in whole
    assert core.count("GNU General Public License") < whole.count(
        "GNU General Public License"
    )


def test_a_core_keeps_the_original_of_a_var() -> None:
    """HPND is made of its variable parts: dropping them left 39 words."""
    core = core_text(_template("HPND"))
    assert core is not None
    assert _words(core) == 45


def test_a_real_core_has_no_word_glued_across_a_mark() -> None:
    """HPND has ``modify<<beginOptional>>,<<endOptional>>and``."""
    core = normalize_text(str(core_text(_template("HPND"))))
    assert "modify and" in core
    assert "granted provided" in core
    assert "modifyand" not in core


@pytest.mark.parametrize(
    "payload",
    [
        "<<" * 100_000,
        BEGIN * 50_000 + END * 50_000,
        "<<var;" * 50_000,
        "a " + var("x") * 20_000,
        "<" * 100_000 + END,
        (BEGIN + "<") * 20_000 + END * 20_000,
    ],
    ids=["angles", "nested", "bare-vars", "vars", "angle-run", "angle-optionals"],
)
def test_the_scan_is_linear(payload: str) -> None:
    started = time.monotonic()
    core_text(payload)
    assert time.monotonic() - started < slack(2.0)
