# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The gates Versions and Storage alone of the speed gate, on made-up
results: no side, corpus or database needed."""

import copy
from pathlib import Path
from typing import Any

import pytest
from speedgate_helpers import case, result

from benchmarks.speedgate import gates, storage, versions
from benchmarks.speedgate.runner import Side

# pylint: disable=missing-function-docstring

OUTDATED = "ERROR: database: build v7 outdated: current v10; run 'licenseid update'\n"
STATE = {"sha256": "a", "mtime_ns": 1, "beside": ["licenses.db"]}


def _run(name: str, stderr: str, rc: int = 2) -> dict[str, Any]:
    return {"name": name, "rc": rc, "stdout": "", "stderr": stderr, "after": STATE}


def _versions() -> dict[str, Any]:
    """A Versions result that passes."""
    invalid = "ERROR: database: invalid: /new/licenses.db\n"
    return {
        "new_on_old": {
            "before": STATE,
            "runs": [_run(name, OUTDATED) for name, _ in versions.LOOKUPS],
        },
        "update": {"rc": 0, "same_tables": True, "same_answers": True},
        "clear_cache": {"rc": 0, "deleted": True},
        "old_on_new": {
            "path": "/new/licenses.db",
            "before": STATE,
            "runs": [_run(name, invalid) for name, _ in versions.OLD_COMMANDS],
        },
    }


def test_a_passing_versions_result_has_no_problem() -> None:
    assert not versions.problems(_versions())
    assert gates.versions_gate({"versions": _versions()}).status == gates.PASS


def test_a_versions_set_not_run_is_not_measured() -> None:
    assert gates.versions_gate({}).status == gates.NA
    assert versions.problems({"error": "no old side"}) == ["no old side"]


def _broken(path: tuple[Any, ...], value: Any) -> dict[str, Any]:
    found = copy.deepcopy(_versions())
    target = found
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return found


@pytest.mark.parametrize(
    ("path", "value", "said"),
    [
        (("new_on_old", "runs", 0, "rc"), 1, "new on old detect: exit 1"),
        (("new_on_old", "runs", 2, "stdout"), "MIT\n", "new on old resolve"),
        (("new_on_old", "runs", 3, "stderr"), "ERROR: x\n", "new on old is-osi"),
        (
            ("new_on_old", "runs", 1, "after"),
            {**STATE, "mtime_ns": 2},
            "new on old: the file changed",
        ),
        (("update", "same_tables"), False, "update:"),
        (("update", "same_answers"), False, "update:"),
        (("update", "rc"), 1, "update:"),
        (("clear_cache", "deleted"), False, "clear-cache"),
        (("clear_cache", "rc"), 1, "clear-cache"),
        (("old_on_new", "runs", 6, "rc"), 0, "old on new update: exit 0"),
        (("old_on_new", "runs", 7, "stderr"), OUTDATED, "old on new clear-cache"),
        (
            ("old_on_new", "runs", 0, "after"),
            {**STATE, "beside": ["licenses.db", "licenses.db-journal"]},
            "old on new: the file changed",
        ),
    ],
)
def test_each_way_a_versions_result_can_fail_is_named(
    path: tuple[Any, ...], value: Any, said: str
) -> None:
    found = versions.problems(_broken(path, value))
    assert len(found) == 1 and found[0].startswith(said), found
    assert gates.versions_gate({"versions": _broken(path, value)}).status == gates.FAIL


def test_the_outdated_line_must_be_the_whole_error() -> None:
    assert versions.OUTDATED.fullmatch(OUTDATED)
    assert not versions.OUTDATED.fullmatch("WARNING: x\n" + OUTDATED)
    assert not versions.OUTDATED.fullmatch(OUTDATED.replace("; run", ";"))


def test_the_old_tree_and_database_sit_beside_the_side_unless_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    side = Side(
        path=tmp_path / "sides" / "T7",
        db=tmp_path / "db" / "T7" / "licenses.db",
        home=tmp_path,
    )
    monkeypatch.delenv("SPEEDGATE_OLD_SIDE", raising=False)
    monkeypatch.delenv("SPEEDGATE_OLD_DB", raising=False)
    assert versions.old_paths(side) == (
        tmp_path / "sides" / "0.9.4",
        tmp_path / "db" / "0.9.4" / "licenses.db",
    )
    monkeypatch.setenv("SPEEDGATE_OLD_SIDE", "/x")
    monkeypatch.setenv("SPEEDGATE_OLD_DB", "/y.db")
    assert versions.old_paths(side) == (Path("/x"), Path("/y.db"))


def test_the_state_of_a_file_names_what_lies_beside_it(tmp_path: Path) -> None:
    path = tmp_path / "licenses.db"
    path.write_bytes(b"x")
    before = versions.file_state(path)
    (tmp_path / "licenses.db-wal").write_bytes(b"")
    assert versions.file_state(path) != before
    assert before["beside"] == ["licenses.db"]


# --- storage alone -----------------------------------------------------------


def _sets(cpu_ms: float, answer: str = "MIT") -> dict[str, Any]:
    cases = {f"long:MIT{i}:clean": case(cpu_ms, answer) for i in range(10)}
    return {"core": result(cases)}


def test_storage_alone_passes_with_no_moved_field_and_cpu_within_noise() -> None:
    gate = storage.storage_alone(_sets(100), _sets(102), _sets(101))
    assert gate.status == gates.PASS, gate.detail
    assert "0 fields differ over 1 sets" in gate.detail


@pytest.mark.parametrize(
    ("cand", "status"),
    [
        (_sets(100, answer="ISC"), gates.FAIL),  # a field moved
        (_sets(110), gates.FAIL),  # CPU past the twin's spread and the floor
        (_sets(97.5), gates.PASS),  # inside the 3 percent floor
    ],
)
def test_storage_alone_fails_on_a_moved_field_or_cpu_past_the_noise(
    cand: dict[str, Any], status: str
) -> None:
    assert storage.storage_alone(_sets(100), cand, _sets(100)).status == status


def test_storage_alone_needs_a_twin_and_the_core_set() -> None:
    assert storage.storage_alone(_sets(100), _sets(100), None).status == gates.NA
    assert storage.storage_alone({}, _sets(100), _sets(100)).status == gates.NA


def test_the_damage_kinds_both_runs_have_are_compared() -> None:
    def damaged(answer: str) -> dict[str, Any]:
        kinds = {"no texts table": result({"x": case(1, answer)})}
        return {"damage": {"kinds": kinds}}

    assert storage.moved_fields(damaged("MIT"), damaged("MIT")) == {
        "damage: no texts table": 0
    }
    assert storage.moved_fields(damaged("MIT"), damaged("ISC")) == {
        "damage: no texts table": 1
    }
    assert storage.moved_fields(damaged("MIT"), {}) == {}
