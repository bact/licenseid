# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The adversarial generator (``harness_gen``): deterministic per seed, every
piece of its grammar used, and the CLI's exit status agreeing with the answer
on what it makes."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import harness_gen as gen
import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from harness_checks import SEED, text_fields
from packaged_list import fixture_bundle
from release_fakes import ship

from licenseid import LicenseDatabase
from licenseid.cli import cli

SAMPLE = list(gen.generate(SEED, 2000))
CLI_SAMPLE = SAMPLE[:: len(SAMPLE) // 60]


def test_the_same_seed_gives_the_same_values() -> None:
    assert list(gen.generate(5, 300)) == list(gen.generate(5, 300))


def test_another_seed_gives_other_values() -> None:
    assert list(gen.generate(5, 50)) != list(gen.generate(6, 50))


def test_a_longer_run_extends_a_shorter_one() -> None:
    assert list(gen.generate(SEED, 500)) == SAMPLE[:500]


def test_the_values_are_mostly_distinct() -> None:
    assert len(set(SAMPLE)) > len(SAMPLE) * 0.9


@pytest.mark.parametrize(
    ("name", "pieces"),
    [
        ("quote marks", [mark for pair in gen.QUOTES for mark in pair if mark]),
        ("end marks", list(gen.END_MARKS)),
        ("operators", [op.strip() for op in gen.OPERATORS if op.strip()]),
        ("plus", ["+"]),
        ("or later", ["later", "newer"]),
        ("white space", [s for s in gen.SPACES if s not in " \n"]),
        ("unicode", [u for u in gen.UNICODE if u != "\u0000"]),
        ("tags", [tag.strip() for tag in gen.TAGS]),
        ("brackets", ["(", ")", "[", "]"]),
    ],
)
def test_every_piece_of_the_grammar_is_used(name: str, pieces: list[str]) -> None:
    used = [piece for piece in set(pieces) if any(piece in v for v in SAMPLE)]
    assert len(used) >= max(1, len(set(pieces)) * 3 // 4), name


def test_the_ids_the_sample_names_are_on_the_list() -> None:
    source = gen.source()
    assert {"MIT", "Apache-2.0", "GPL-2.0-or-later"} <= set(source.ids)
    assert len(source.ids) > 600 and len(source.names) == len(source.ids)
    assert source.exceptions


def test_a_value_may_hold_a_lone_surrogate_or_a_nul() -> None:
    assert any("\udcff" in v for v in gen.generate(SEED, 20000))
    assert any("\u0000" in v for v in gen.generate(SEED, 20000))


def test_match_exits_0_for_an_answer_1_for_none_2_for_unusable_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, fixture_bundle())
    seen = set()
    for value in CLI_SAMPLE:
        result = CliRunner().invoke(cli, ["match", value])
        seen.add(result.exit_code)
        if result.exit_code == 2:
            assert result.stdout == "" and result.stderr.startswith("ERROR: ")
        else:
            expression = text_fields(result.stdout.split("\n")[0])["EXPRESSION"]
            assert result.exit_code == (0 if expression else 1), value
    assert seen == {0, 1, 2}


def test_detect_exits_0_for_an_answer_1_for_none(bundle_db: LicenseDatabase) -> None:
    seen = set()
    for value in CLI_SAMPLE[:30]:
        args = ["--db", str(bundle_db.db_path), "detect", "--text", value]
        result = CliRunner().invoke(cli, args)
        seen.add(result.exit_code)
        if result.exit_code != 2:
            expression = text_fields(result.stdout.split("\n")[0])["EXPRESSION"]
            assert result.exit_code == (0 if expression else 1), value
    assert {0, 1} <= seen
