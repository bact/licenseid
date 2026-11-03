# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, item 3: a keyword of a reader ignores case in ASCII
only. Python's ``re.IGNORECASE`` alone folds U+0130 (dotted capital I),
U+0131 (dotless small i), U+017F (long s) and U+212A (Kelvin sign) into
"i", "s" and "k", so ``WITH`` spelt with a dotted capital I was a WITH.

A guard walks every compiled pattern of the readers and fails on a letter
those four fold into that ignores case without ``re.ASCII`` (on the whole
pattern, or ``(?a:...)`` around the word).
"""
# pylint: disable=missing-function-docstring,protected-access

import importlib
import inspect
import re
import sys
from types import ModuleType
from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, bsdclauses, classify, looseid, resolve
from licenseid.detector import LicenseDetector
from licenseid.markers import MarkerDetector
from licenseid.plusoperator import PLUS_OPERATOR, strip_plus_operator

# The parser of the re module: private, read by name so that no version
# warns or lacks a stub (sre_parse until 3.10, re._parser since 3.11).
_PARSER = importlib.import_module(
    "re._parser" if sys.version_info >= (3, 11) else "sre_parse"
)
#: The ASCII letters a non-ASCII letter folds into under IGNORECASE.
FOLDED = frozenset("iskISK")
#: Each non-ASCII letter and the ASCII one it folds into.
LOOK_ALIKES = {
    "I": "\u0130",
    "i": "\u0131",
    "S": "\u017f",
    "s": "\u017f",
    "K": "\u212a",
    "k": "\u212a",
}
#: The readers held to the rule; the earlier fix covered the last three.
READERS = [
    "licenseid.bsdclauses",
    "licenseid.classify",
    "licenseid.identifiers",
    "licenseid.looseid",
    "licenseid.manifest",
    "licenseid.markers",
    "licenseid.plusoperator",
    "licenseid.exprcanon",
    "licenseid.exprtokens",
    "licenseid.resolveprose",
]


def _patterns(module: ModuleType) -> dict[str, re.Pattern[str]]:
    """The compiled patterns of *module* and of the classes it defines."""
    found = {k: v for k, v in vars(module).items() if isinstance(v, re.Pattern)}
    for name, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ == module.__name__:
            found.update(
                {
                    f"{name}.{k}": v
                    for k, v in vars(cls).items()
                    if isinstance(v, re.Pattern)
                }
            )
    return found


def _folded(items: Any, flags: int) -> list[str]:
    """The letters of the parsed *items* that fold a non-ASCII letter: a
    literal or a class member in FOLDED, ignoring case without ASCII."""
    found: list[str] = []
    for op, arg in items:
        kind = str(op)
        if kind == "SUBPATTERN":
            _, add, remove, sub = arg
            found += _folded(sub, (flags | add) & ~remove)
        elif kind == "BRANCH":
            for branch in arg[1]:
                found += _folded(branch, flags)
        elif kind in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            found += _folded(arg[2], flags)
        elif kind in ("ASSERT", "ASSERT_NOT"):
            found += _folded(arg[1], flags)
        elif not flags & re.IGNORECASE or flags & re.ASCII:
            continue
        elif kind == "LITERAL" and chr(arg) in FOLDED:
            found.append(chr(arg))
        elif kind == "IN" and not any(str(o) == "NEGATE" for o, _ in arg):
            found += [_member(o, a) for o, a in arg if _member(o, a)]
    return found


def _member(op: Any, arg: Any) -> str:
    """The folded letters a class member takes, or ""."""
    if str(op) == "LITERAL":
        return chr(arg) if chr(arg) in FOLDED else ""
    if str(op) == "RANGE":
        return "".join(c for c in sorted(FOLDED) if arg[0] <= ord(c) <= arg[1])
    return ""


@pytest.mark.parametrize("name", READERS)
def test_every_keyword_ignores_case_in_ascii_only(name: str) -> None:
    module = importlib.import_module(name)
    folded = {}
    for key, pattern in _patterns(module).items():
        parsed = _PARSER.parse(pattern.pattern, pattern.flags)
        letters = _folded(parsed, parsed.state.flags)
        if letters:
            folded[key] = sorted(set(letters))
    assert not folded


@pytest.mark.parametrize(
    "pattern",
    [
        re.compile("WITH", re.IGNORECASE),
        re.compile("(?:x|w[a-k])", re.IGNORECASE),
        re.compile("(?i:a)s+"),  # a scoped flag goes no further than its group
    ],
    ids=["literal", "range", "scoped"],
)
def test_the_guard_finds_a_folding_letter(pattern: re.Pattern[str]) -> None:
    parsed = _PARSER.parse(pattern.pattern, pattern.flags)
    # The scoped one has none: "s" is outside "(?i:".
    expected = pattern.pattern != "(?i:a)s+"
    assert bool(_folded(parsed, parsed.state.flags)) is expected


def _spelt(text: str, letter: str) -> str:
    """*text* with each *letter* written as the non-ASCII one that folds
    into it."""
    return text.replace(letter, LOOK_ALIKES[letter])


@pytest.mark.parametrize("look_alike", ["\u0130", "\u0131"])
def test_with_takes_no_look_alike(corpus_db: LicenseDatabase, look_alike: str) -> None:
    value = f"MIT W{look_alike}TH Classpath-exception-2.0"
    assert resolve(value, corpus_db)["expression"] is None
    assert looseid.WITH_OPERATOR.search(value) is None
    assert looseid.WITH_OPERATOR.search("MIT WITH X")
    found = LicenseDetector(corpus_db.location).detect(
        f"SPDX-License-Identifier: {value}"
    )
    assert [r["expression"] for r in found[:1]] == ["MIT"]


def test_the_plus_operator_takes_no_look_alike() -> None:
    # "W\u0130TH" is no WITH: the "+" is an operator after an ID.
    assert strip_plus_operator("MIT W\u0130TH x+") == "MIT W\u0130TH x"
    assert strip_plus_operator("MIT WITH x+") == "MIT WITH x+"
    assert [m["id"] for m in PLUS_OPERATOR.finditer("w\u0131th+ MIT+")] == [
        "w\u0131th",
        "MIT",
    ]


@pytest.mark.parametrize(
    ("text", "letter"),
    [
        ("GPL-2.0 or at your option any later version", "i"),
        ("GPL-2.0 any later version", "s"),
    ],
)
def test_a_grant_takes_no_look_alike(text: str, letter: str) -> None:
    assert classify.OR_LATER_PHRASE.search(text)
    phrase = text[8:]
    assert not classify.OR_LATER_PHRASE.search(_spelt(phrase, letter))


def test_the_words_after_a_grant_take_no_look_alike() -> None:
    words = " versions of the license"
    for text, end in [(words, len(words)), (_spelt(words, "i"), 0)]:
        found = looseid.RE_GRANT_WORDS.match(text)
        assert found is not None
        assert found.end() == end
    found = looseid.RE_GRANT_WORDS.match(_spelt(words, "s"))
    assert found is not None
    assert found.end() == 0


@pytest.mark.parametrize(
    ("pattern", "text", "letter"),
    [
        (MarkerDetector._RE_SPDX, "SPDX-License-Identifier: ", "I"),
        (MarkerDetector._RE_SPDX, "SPDX-License-Identifier: ", "i"),
        (MarkerDetector._RE_LICENSE_FIELD, "license = 'MIT'", "s"),
        (MarkerDetector._RE_MD_HEADING, "## Licensing", "i"),
        (MarkerDetector._RE_LINE_HEADING, "LICENSE", "I"),
        (MarkerDetector._RE_VERSION_WORD, ", Version ", "s"),
        (MarkerDetector._RE_GPL_FAMILY, "GNU Lesser General Public License", "s"),
        (MarkerDetector._RE_GPL_VERSION, "either version 2", "i"),
        (MarkerDetector._RE_LICENSE_MENTION, "licensed under the MIT", "s"),
        (MarkerDetector._RE_LICENSE_TAIL, "MIT License", "s"),
        (MarkerDetector._RE_PROJECT_WORD, "project's ", "s"),
        (MarkerDetector._RE_GPL_NAME, "GPL License version 3", "i"),
        (
            MarkerDetector._RE_FONT_EXCEPTION,
            "As a special exception, embed this font",
            "s",
        ),
        (bsdclauses._RE_DISCLAIMER, "THIS SOFTWARE IS PROVIDED", "S"),
        (bsdclauses._RE_LATER_CONDITION, "Redistributions in binary form", "s"),
        (classify._RE_NON_LICENSE_SECTION, "## Quick Start", "i"),
        (classify._RE_NON_LICENSE_SECTION, "## Acknowledgements", "k"),
    ],
    ids=lambda value: value.pattern[:24] if isinstance(value, re.Pattern) else None,
)
def test_a_keyword_takes_no_look_alike(
    pattern: re.Pattern[str], text: str, letter: str
) -> None:
    assert pattern.search(text)
    assert pattern.search(_spelt(text, letter)) is None
