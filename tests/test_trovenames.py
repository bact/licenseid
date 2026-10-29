# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The trove classifier table agrees with PyPA's list and the SPDX List."""

import json
import re
import time
from pathlib import Path

import pytest
import trove_classifiers
from trove_golden import GOLDEN

from licenseid.trovenames import TROVE_NAMES, strip_trove_path

LIST_FILE = (
    Path(__file__).parent / "fixtures" / "license-list" / "spdx-license-ids.json"
)

# Classifiers of trove_classifiers that the table has not decided yet. A new
# classifier lands here only on purpose; the test below fails until it is
# either in TROVE_NAMES or here. Empty: all are decided, the deprecated ones
# too (old projects still declare them).
NOT_YET_DECIDED: frozenset[str] = frozenset()

PREFIX = "License :: "
CLASSIFIERS = sorted(
    c
    for c in {*trove_classifiers.classifiers, *trove_classifiers.deprecated_classifiers}
    if c.startswith(PREFIX)
)
OSI_PREFIX = "License :: OSI Approved :: "


def segment(classifier: str) -> str:
    """Return the name of a classifier: its last path segment."""
    return classifier.split(" :: ")[-1]


def short_id(classifier: str) -> str:
    """Return a short test ID for a classifier."""
    return segment(classifier)[:30]


SEGMENTS = {segment(c): c for c in CLASSIFIERS}

_LIST = json.loads(LIST_FILE.read_text())
_COLUMNS = {name: i for i, name in enumerate(_LIST["columns"])}
IDS = {
    row[_COLUMNS["license_id"]]: bool(row[_COLUMNS["is_deprecated"]])
    for row in _LIST["licenses"]
}

STATED = {k: v for k, v in TROVE_NAMES.items() if v.reading == "stated"}
ASSUMED = {k: v for k, v in TROVE_NAMES.items() if v.reading == "assumed"}
NONE = {k: v for k, v in TROVE_NAMES.items() if v.reading == "none"}


def numbers_in(name: str) -> set[str]:
    """Return the dotted numbers in a name (``v3`` gives ``3``)."""
    return set(re.findall(r"(?<![\w.])v?(\d+(?:\.\d+)*)(?![\w.]*\d)", name))


def id_version(spdx_id: str) -> str | None:
    """Return the version in an ID (``GPL-3.0-or-later`` gives ``3.0``)."""
    found = re.search(r"-(\d+(?:\.\d+)*)(?:-|\+?$)", spdx_id)
    return found.group(1) if found else None


def version_in_name(spdx_id: str, name: str) -> bool:
    """Tell whether a name writes the version of an ID (``3`` for ``3.0``)."""
    version = id_version(spdx_id)
    if version is None:
        return True
    parts = version.split(".")
    spellings = {".".join(parts[:n]) for n in range(1, len(parts) + 1)}
    return bool(spellings & numbers_in(name))


def test_id_version_reads_a_trailing_plus() -> None:
    """A deprecated ID that ends in a plus still has its version."""
    assert id_version("GPL-2.0+") == "2.0"
    assert id_version("GPL-3.0-or-later") == "3.0"
    assert id_version("Nokia") is None


def test_segments_are_unique() -> None:
    """No two classifiers share a name."""
    assert len(SEGMENTS) == len(CLASSIFIERS)


def test_every_key_is_a_classifier() -> None:
    """Each key is the last segment of a real classifier."""
    assert set(TROVE_NAMES) <= set(SEGMENTS)


def test_every_classifier_is_decided() -> None:
    """A classifier missing from the table must be listed as not decided."""
    undecided = {c for c in CLASSIFIERS if segment(c) not in TROVE_NAMES}
    assert undecided == NOT_YET_DECIDED


@pytest.mark.parametrize("classifier", CLASSIFIERS, ids=short_id)
def test_osi_flag_matches_the_real_classifier(classifier: str) -> None:
    """The table says whether the classifier is under OSI Approved."""
    entry = TROVE_NAMES[segment(classifier)]
    assert entry.osi == classifier.startswith(OSI_PREFIX)


def test_the_table_is_the_golden_answer() -> None:
    """Every entry is the one written out in trove_golden."""
    actual = {k: ("+".join(v.ids), v.reading, v.osi) for k, v in TROVE_NAMES.items()}
    assert actual == GOLDEN


@pytest.mark.parametrize("name", sorted(STATED))
def test_stated_names_say_their_licence(name: str) -> None:
    """A stated name writes the version and the grant of its ID."""
    (spdx_id,) = STATED[name].ids
    assert spdx_id in IDS
    assert not IDS[spdx_id], "a deprecated ID is an assumed reading"
    assert version_in_name(spdx_id, name)
    assert spdx_id.endswith("-or-later") == ("or later" in name)
    assert not spdx_id.endswith("-only")


@pytest.mark.parametrize("name", sorted(ASSUMED))
def test_assumed_names_state_a_bare_deprecated_id(name: str) -> None:
    """An assumed name gives a bare deprecated ID with its version written."""
    (spdx_id,) = ASSUMED[name].ids
    assert IDS[spdx_id], "an assumed reading is a deprecated ID"
    assert not spdx_id.endswith(("-only", "-or-later", "+"))
    assert version_in_name(spdx_id, name)
    assert "or later" not in name


@pytest.mark.parametrize("name", sorted(NONE))
def test_none_names_have_no_id(name: str) -> None:
    """A name that reads as none has no ID."""
    assert NONE[name].ids == ()


def test_every_reading_is_known() -> None:
    """The table uses all three readings and no other."""
    assert {v.reading for v in TROVE_NAMES.values()} == {"stated", "assumed", "none"}


def test_lgplv2_special_case_is_read_as_written() -> None:
    """Q23: the Lesser v2 name is the bare deprecated LGPL-2.0."""
    entry = TROVE_NAMES["GNU Lesser General Public License v2 (LGPLv2)"]
    assert entry == (("LGPL-2.0",), "assumed", True)


def test_no_other_lesser_v2_name_is_read() -> None:
    """P45: the Lesser v2 or later name stays unresolved."""
    entry = TROVE_NAMES["GNU Lesser General Public License v2 or later (LGPLv2+)"]
    assert entry.reading == "none"


@pytest.mark.parametrize(
    "name",
    ["Apache Software License", "Python Software Foundation License", "W3C License"],
    ids=lambda name: name[:20],
)
def test_names_read_by_usage_or_by_q22_are_not_read(name: str) -> None:
    """T4 (Q3, deferred) and Q22: no ID, though one is often meant."""
    assert TROVE_NAMES[name].ids == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("License :: OSI Approved :: MIT License", "MIT License"),
        ("License :: OSI Approved :: ISC License (ISCL)", "ISC License (ISCL)"),
        ("License :: Public Domain", "Public Domain"),
        ("  License  ::  OSI Approved  ::  MIT License  ", "MIT License"),
        ("\tLicense\t::\tOSI Approved\t::\tMIT License\t", "MIT License"),
        ("License::OSI Approved::MIT License", "MIT License"),
        ("License :: OSI Approved", None),
        ("License :: OSI Approved ::", None),
        ("License :: OSI Approved :: ", None),
        ("License ::", None),
        ("License :: Foo :: Bar", None),
        ("License :: OSI Approved :: A :: B", None),
        ("License :: OSI Approved :: Foo", None),
        ("License :: MIT License", None),
        ("License :: OSI Approved :: Aladdin Free Public License (AFPL)", None),
        ("License :: OSI Approved :: Public Domain", None),
        ("MIT License", None),
        ("OSI Approved :: MIT License", None),
        ("license :: OSI Approved :: MIT License", None),
        ("License :: osi approved :: MIT License", None),
        ("License :: OSI Approved :: mit license", None),
        ("License ::\nOSI Approved :: MIT License", None),
        ("License :: OSI Approved ::\r\nMIT License", None),
        ("License :: OSI Approved :: MIT\nLicense", None),
        ("\nLicense :: OSI Approved :: MIT License", None),
        ("License :: OSI Approved :: MIT License\x0b", None),
        ("Programming Language :: Python :: 3", None),
        ("", None),
    ],
    ids=lambda v: repr(v)[:30],
)
def test_strip_trove_path(text: str, expected: str | None) -> None:
    """Only a real classifier in its real form gives a name."""
    assert strip_trove_path(text) == expected


@pytest.mark.parametrize("classifier", CLASSIFIERS, ids=short_id)
def test_every_classifier_path_strips_to_its_key(classifier: str) -> None:
    """Each real classifier gives its name, but the category gives none."""
    category = classifier == "License :: OSI Approved"
    expected = None if category else segment(classifier)
    assert strip_trove_path(classifier) == expected


@pytest.mark.parametrize("filler", [" ", "\t", ":", "::"], ids=repr)
def test_strip_trove_path_answers_a_long_input(filler: str) -> None:
    """A long run of white space or separators is refused, not slow."""
    assert strip_trove_path("License" + filler * 2_000 + "x") is None
    assert strip_trove_path("License" + filler * 2_000 + "::MIT License") is None


@pytest.mark.benchmark
def test_strip_trove_path_time_grows_linearly() -> None:
    """Four times the input takes about four times as long, not sixteen."""

    def seconds(count: int) -> float:
        text = "License" + " " * count + "x"
        start = time.monotonic()
        strip_trove_path(text)
        return time.monotonic() - start

    seconds(10_000)  # warm up
    small = max(seconds(40_000), 1e-4)
    assert seconds(160_000) / small < 10
