# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``ini_license_values`` stops at the first line configparser surely
refuses, because configparser builds its error message one bad line at a time
(quadratic; item 23). The pre-scan may miss a bad line, never call a good
one bad."""
# pylint: disable=protected-access,missing-function-docstring

import configparser
import itertools
import random
import time

import pytest
from timing import slack

from licenseid.manifest import _has_bad_ini_line, ini_license_values

LINES = [
    "[a]", "[b]", "[a] tail", "[x", "x]", "[]", "k = v", "k: v", "= v", ": v",
    "  = v", "junk", "  junk", "\tjunk", " k = v", "  k = v", "license = MIT",
    "# c", "; c", "  # c", "", "   ", "\r", "k =", "k", "[a]\r", "k = v\r",
    "麻 = 1", "麻", "a b = c", "k = v # not a comment", "\x0c k = v",
    "\x85junk", "\u3000k = v", "[DEFAULT]", "\x0bjunk",
]  # fmt: skip


def refused(text: str) -> bool:
    try:
        configparser.ConfigParser().read_string(text)
    except configparser.Error:
        return True
    return False


def corpus() -> list[str]:
    rng = random.Random(23)
    pairs = ["\n".join(p) for p in itertools.product(LINES, repeat=2)]
    triples = [
        rng.choice(["\n", "\r\n", "\r"]).join(rng.choices(LINES, k=rng.randint(1, 6)))
        for _ in range(4000)
    ]
    return pairs + triples


def test_a_line_called_bad_is_refused_by_configparser() -> None:
    """The one-way rule, against every pair of lines and 4,000 random files."""
    called_bad = 0
    for text in corpus():
        if _has_bad_ini_line(text):
            called_bad += 1
            assert refused(text), repr(text)
    assert called_bad > 500  # the table reaches the rule


@pytest.mark.parametrize(
    "text",
    [
        "[a]\njunk",
        "[a]\n  junk",
        "junk",
        "[a]\nk = v\n# c\n  junk\nz",
        "[a]\n= v",
        "k = v\n[a]",
    ],
)
def test_a_bad_line_gives_none(text: str) -> None:
    assert _has_bad_ini_line(text) and ini_license_values(text) is None


@pytest.mark.parametrize(
    "text",
    ["[a]\nlicense = MIT\n  more\n", "[a]\nlicense = MIT\n\n  more\n", "[a]\nk=v\r\n"],
)
def test_good_ini_is_not_called_bad(text: str) -> None:
    assert not _has_bad_ini_line(text)


@pytest.mark.parametrize(
    "line",
    ["junk{}", "  junk{}", "= {}", "\tjunk{}", "麻{}", "[x{}"],
    ids=["bare", "indented", "no-key", "tab", "cjk", "open-header"],
)
def test_many_bad_lines_read_in_linear_time(line: str) -> None:
    """100,000 bad lines took 2.8 s in configparser on 3.10 and 3.3 s on 3.13.
    3.14.10 joins its error parts and takes 0.35 s, so this guards only the
    Pythons that still append (3.10 to 3.14.3 at least; CI's 3.10 runs it)."""
    text = "[a]\n" + "".join(line.format(i) + "\n" for i in range(100_000))
    start = time.monotonic()
    assert ini_license_values(text) is None
    assert time.monotonic() - start < slack(0.5)
