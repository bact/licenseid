# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The trove classifier table agrees with PyPA's list and the SPDX List."""

import json
import re
from pathlib import Path

import pytest
import trove_classifiers

from licenseid.trovenames import TROVE_NAMES, strip_trove_path

LIST_FILE = (
    Path(__file__).parent / "fixtures" / "license-list" / "spdx-license-ids.json"
)

# Classifiers of trove_classifiers that the table has not decided yet. A new
# classifier lands here only on purpose; the test below fails until it is
# either in TROVE_NAMES or here. Empty: all are decided.
NOT_YET_DECIDED: frozenset[str] = frozenset()

PREFIX = "License :: "
CLASSIFIERS = sorted(c for c in trove_classifiers.classifiers if c.startswith(PREFIX))
SEGMENTS = {c.split(" :: ")[-1]: c for c in CLASSIFIERS}

# id -> is_deprecated, from the 3.29.0 List fixture (rows: id, name, deprecated, ...)
IDS = {row[0]: bool(row[2]) for row in json.loads(LIST_FILE.read_text())["licenses"]}

STATED = {k: v for k, v in TROVE_NAMES.items() if v.reading == "stated"}
ASSUMED = {k: v for k, v in TROVE_NAMES.items() if v.reading == "assumed"}
NONE = {k: v for k, v in TROVE_NAMES.items() if v.reading == "none"}


def numbers_in(name: str) -> set[str]:
    """Return the dotted numbers in a name (``v3`` gives ``3``)."""
    return set(re.findall(r"(?<![\w.])v?(\d+(?:\.\d+)*)(?![\w.]*\d)", name))


def id_version(spdx_id: str) -> str | None:
    """Return the version in an ID (``GPL-3.0-or-later`` gives ``3.0``)."""
    found = re.search(r"-(\d+(?:\.\d+)*)(?:-|$)", spdx_id)
    return found.group(1) if found else None


def version_in_name(spdx_id: str, name: str) -> bool:
    """Tell whether a name writes the version of an ID (``3`` for ``3.0``)."""
    version = id_version(spdx_id)
    if version is None:
        return True
    parts = version.split(".")
    spellings = {".".join(parts[:n]) for n in range(1, len(parts) + 1)}
    return bool(spellings & numbers_in(name))


def test_segments_are_unique() -> None:
    """Segments are unique."""
    assert len(SEGMENTS) == len(CLASSIFIERS)


def test_every_key_is_a_classifier() -> None:
    """Every key is a classifier."""
    assert set(TROVE_NAMES) <= set(SEGMENTS)


def test_every_classifier_is_decided() -> None:
    """Every classifier is decided."""
    undecided = {c for c in CLASSIFIERS if c.split(" :: ")[-1] not in TROVE_NAMES}
    assert undecided == NOT_YET_DECIDED


@pytest.mark.parametrize("name", sorted(STATED))
def test_stated_names_say_their_licence(name: str) -> None:
    """Stated names say their licence."""
    (spdx_id,) = STATED[name].ids
    assert spdx_id in IDS
    assert not IDS[spdx_id], "a deprecated ID is an assumed reading"
    assert version_in_name(spdx_id, name)
    assert spdx_id.endswith("-or-later") == ("or later" in name)
    assert not spdx_id.endswith("-only")


@pytest.mark.parametrize("name", sorted(ASSUMED))
def test_assumed_names_state_a_bare_deprecated_id(name: str) -> None:
    """Assumed names state a bare deprecated id."""
    (spdx_id,) = ASSUMED[name].ids
    assert IDS[spdx_id], "an assumed reading is a deprecated ID"
    assert not spdx_id.endswith(("-only", "-or-later"))
    assert version_in_name(spdx_id, name)
    assert "or later" not in name


@pytest.mark.parametrize("name", sorted(NONE))
def test_none_names_have_no_id(name: str) -> None:
    """None names have no id."""
    assert NONE[name].ids == ()


def test_every_reading_is_known() -> None:
    """Every reading is known."""
    assert {v.reading for v in TROVE_NAMES.values()} == {"stated", "assumed", "none"}


def test_lgplv2_special_case_is_read_as_written() -> None:
    """Lgplv2 special case is read as written."""
    entry = TROVE_NAMES["GNU Lesser General Public License v2 (LGPLv2)"]
    assert entry == (("LGPL-2.0",), "assumed")  # Q23


def test_no_other_lesser_v2_name_is_read() -> None:
    """No other lesser v2 name is read."""
    entry = TROVE_NAMES["GNU Lesser General Public License v2 or later (LGPLv2+)"]
    assert entry.reading == "none"


@pytest.mark.parametrize(
    "name",
    ["Apache Software License", "Python Software Foundation License"],
)
def test_usage_names_are_not_read(name: str) -> None:
    """Usage names are not read."""
    assert TROVE_NAMES[name].reading == "none"  # T4, deferred (Q3)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("License :: OSI Approved :: MIT License", "MIT License"),
        ("License :: OSI Approved :: ISC License (ISCL)", "ISC License (ISCL)"),
        ("License :: Public Domain", "Public Domain"),
        ("  License  ::  OSI Approved  ::  MIT License  ", "MIT License"),
        ("License::OSI Approved::MIT License", "MIT License"),
        ("License :: OSI Approved", None),
        ("License :: OSI Approved ::", None),
        ("License :: OSI Approved :: ", None),
        ("License ::", None),
        ("License :: Foo :: Bar", None),
        ("License :: OSI Approved :: A :: B", None),
        ("MIT License", None),
        ("OSI Approved :: MIT License", None),
        ("license :: osi approved :: MIT License", None),
        ("Programming Language :: Python :: 3", None),
        ("", None),
    ],
    ids=lambda v: repr(v)[:30],
)
def test_strip_trove_path(text: str, expected: str | None) -> None:
    """Strip trove path."""
    assert strip_trove_path(text) == expected


@pytest.mark.parametrize("classifier", CLASSIFIERS, ids=lambda c: c[11:40])
def test_every_classifier_path_strips_to_its_key(classifier: str) -> None:
    """Every classifier path strips to its key."""
    category = classifier == "License :: OSI Approved"
    expected = None if category else classifier.split(" :: ")[-1]
    assert strip_trove_path(classifier) == expected


def test_strip_trove_path_is_linear() -> None:
    """Strip trove path is linear."""
    assert strip_trove_path("License" + " " * 20_000 + "x") is None
