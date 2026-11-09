# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Properties of the ``/`` reading (roadmap item 43): it never says more
than ``A OR B`` says, and a pair that is not two exact IDs is never read."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import itertools
import json
import random
from pathlib import Path
from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from test_resolver_slash import weakest

from licenseid import LicenseDatabase, resolve
from licenseid.cliinput import names_licences
from licenseid.resolveslash import slash_parts
from licenseid.trovenames import TROVE_NAMES

FIXTURES = Path(__file__).parent / "fixtures" / "license-list"
SEED = 43


@pytest.fixture(scope="module")
def ids(corpus_db: LicenseDatabase) -> list[str]:
    return sorted(row["license_id"] for row in corpus_db.get_all_names_and_ids())


def same_as_or(db: LicenseDatabase, first: str, second: str) -> None:
    slashed = resolve(f"{first}/{second}", db)
    if {first, second} in ({"MIT", "X11"}, {"Libpng", "Zlib"}):  # refused pairs
        assert slashed["expression"] is None
        return
    alone = resolve(f"{first} OR {second}", db)
    assert slashed["expression"] == alone["expression"], (first, second)
    if alone["expression"] is not None:
        assert slashed["category"] == weakest("separator", alone["category"])
        assert slashed["reason"] is None
        assert len(slashed["operands"]) == 2
    else:
        assert slashed["category"] == "unresolved"


def test_the_list_has_ids(ids: list[str]) -> None:
    assert len(ids) > 600
    assert "MIT" in ids


def test_every_id_beside_mit_reads_as_or_in_both_orders(
    corpus_db: LicenseDatabase, ids: list[str]
) -> None:
    for license_id in ids:
        same_as_or(corpus_db, license_id, "MIT")
        same_as_or(corpus_db, "MIT", license_id)


def test_random_pairs_read_as_or(corpus_db: LicenseDatabase, ids: list[str]) -> None:
    rng = random.Random(SEED)
    for _ in range(300):
        same_as_or(corpus_db, rng.choice(ids), rng.choice(ids))


@pytest.mark.benchmark
def test_all_pairs_read_as_or(corpus_db: LicenseDatabase, ids: list[str]) -> None:
    for first, second in itertools.product(ids, repeat=2):
        same_as_or(corpus_db, first, second)


def perturbations(license_id: str) -> list[str]:
    """Spellings one character away from *license_id*."""
    middle = len(license_id) // 2
    spelt = [
        license_id.swapcase(),
        license_id.lower(),
        license_id.upper(),
        license_id[:middle] + license_id[middle + 1 :],
        license_id.replace("-", "_", 1),
        license_id[:middle] + "." + license_id[middle:],
        license_id + " ",
        license_id + "x",
        "\u041c" + license_id[1:],  # Cyrillic capital Em
        "\uff2d" + license_id[1:],  # fullwidth M
        license_id[:middle] + "\u200b" + license_id[middle:],
        license_id[:middle] + "\u00a0" + license_id[middle:],
        "(" + license_id,
    ]
    return [s for s in spelt if s != license_id]


def is_listed(db: LicenseDatabase, text: str) -> bool:
    row = db.get_license_details(text.strip())
    return row is not None and row["license_id"] == text.strip()


def test_a_misspelt_operand_is_never_read(
    corpus_db: LicenseDatabase, ids: list[str]
) -> None:
    rng = random.Random(SEED)
    checked = 0
    for _ in range(2000):
        first, second = rng.choice(ids), rng.choice(ids)
        mutated = rng.choice(perturbations(second))
        if is_listed(corpus_db, mutated) or mutated.strip() != mutated:
            continue
        for value in (f"{first}/{mutated}", f"{mutated}/{first}"):
            assert slash_parts(value, corpus_db) is None, value
            result = resolve(value, corpus_db)
            assert result["expression"] is None, value
            checked += 1
    assert checked > 1500


def slash_names(db: LicenseDatabase) -> list[str]:
    """Every name of a licence, exception or trove classifier with a "/"."""
    exceptions = json.loads((FIXTURES / "spdx-exception-ids.json").read_text("utf-8"))
    names = [row["name"] for row in db.get_all_names_and_ids()]
    names += [row[1] for row in exceptions["exceptions"]]
    names += list(TROVE_NAMES)
    return sorted({name for name in names if "/" in name})


def test_the_names_with_a_slash_exist(corpus_db: LicenseDatabase) -> None:
    names = slash_names(corpus_db)
    assert len(names) >= 14
    assert any("TCL/TK" in name for name in names)


def test_no_slash_pair_in_a_name_is_read(corpus_db: LicenseDatabase) -> None:
    for name in slash_names(corpus_db):
        assert slash_parts(name, corpus_db) is None, name
        before = name
        for index, char in enumerate(name):
            if char == "/":
                pair = f"{name[:index].strip()}/{name[index + 1 :].strip()}"
                assert slash_parts(pair, corpus_db) is None, (before, pair)


def test_what_the_gate_accepts_the_cli_takes_as_a_value(
    corpus_db: LicenseDatabase, ids: list[str]
) -> None:
    """``cliinput.names_licences`` tells a value from a path: it must not
    turn an accepted value into a file name."""
    rng = random.Random(SEED)
    for _ in range(300):
        value = "/".join(rng.choice(ids) for _ in range(rng.randint(2, 4)))
        parts = slash_parts(value, corpus_db)
        assert parts is not None, value
        assert names_licences(corpus_db, value), value


def test_a_value_with_a_slash_in_prose_is_never_whole(
    corpus_db: LicenseDatabase,
) -> None:
    texts: list[Any] = [
        "Licensed under MIT/Apache-2.0",
        "MIT/Apache-2.0 at your option",
        "See LICENSE-MIT/LICENSE-APACHE",
        "MIT/Apache-2.0\nplease read",
    ]
    for text in texts:
        assert slash_parts(text, corpus_db) is None


def test_more_than_150_operands_are_refused(corpus_db: LicenseDatabase) -> None:
    assert slash_parts("/".join(["MIT"] * 150), corpus_db) is not None
    assert slash_parts("/".join(["MIT"] * 151), corpus_db) is None
