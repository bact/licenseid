# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The speed gate (``benchmarks/speedgate``): manifests, set builders, the
comparison of two runs and the release gates, on made-up inputs."""

import json
from pathlib import Path
from typing import Any

import pytest
from speedgate_helpers import case, core_of, result, row, write_fixtures

from benchmarks.speedgate import corpusdir, gates, sets_core, sets_synth
from benchmarks.speedgate.damage import REFERENCE
from benchmarks.speedgate.item68 import item68_keys
from benchmarks.speedgate.model import base_id, digest
from benchmarks.speedgate.moved import fixture_counts, label_counts, moved_answers
from benchmarks.speedgate.report import compare_folders
from benchmarks.speedgate.results import kind_of, kind_times

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture()
def fixtures(tmp_path: Path) -> Path:
    return write_fixtures(tmp_path / "fx")


# --- the manifest ---------------------------------------------------------


def _corpus(tmp_path: Path) -> Path:
    folder = tmp_path / "corpus"
    files = []
    for name, text in (("a/one.txt", "one"), ("a/two.txt", "two")):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(text.encode())
        files.append({"path": name, "sha256": corpusdir.sha256(text.encode())})
    manifest = {"format": 1, "files": files, "item68": []}
    (folder / corpusdir.MANIFEST).write_text(json.dumps(manifest))
    return folder


def test_a_corpus_matching_its_manifest_has_no_problem(tmp_path: Path) -> None:
    assert not corpusdir.verify(_corpus(tmp_path))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda f: (f / "a/one.txt").write_text("other"), "changed: a/one.txt"),
        (lambda f: (f / "a/two.txt").unlink(), "missing: a/two.txt"),
        (lambda f: (f / "a/new.txt").write_text("x"), "unlisted: a/new.txt"),
    ],
    ids=["changed", "missing", "unlisted"],
)
def test_a_corpus_that_moved_from_its_manifest_is_reported(
    tmp_path: Path, change: Any, expected: str
) -> None:
    folder = _corpus(tmp_path)
    change(folder)
    assert corpusdir.verify(folder) == [expected]


def test_the_real_files_are_picked_the_same_way_each_time(tmp_path: Path) -> None:
    paths = []
    for number in range(12):
        path = tmp_path / f"d{number}" / "LICENSE"
        path.parent.mkdir()
        path.write_text(f"licence number {number % 9}")  # three are copies
        paths.append(str(path))
    (tmp_path / "d0" / "README").write_text("not a licence file")
    big = tmp_path / "big" / "COPYING"
    big.parent.mkdir()
    big.write_bytes(b"x" * (corpusdir.MAX_BYTES + 1))
    nul = tmp_path / "zero" / "NOTICE"  # not "nul": a device on Windows
    nul.parent.mkdir()
    nul.write_bytes(b"a\0b")
    paths += [str(tmp_path / "d0" / "README"), str(big), str(nul)]
    first = corpusdir.pick_real(paths, limit=5)
    assert first == corpusdir.pick_real(paths, limit=5)
    assert len(first) == 5
    assert len({d for _, _, d in first}) == 5
    assert all(k.startswith("real:") and k.endswith(":LICENSE") for k, _, _ in first)


def test_readmes_need_the_word_licens_and_a_fair_length(tmp_path: Path) -> None:
    paths = []
    for number, body in enumerate(["licensed " * 40, "nothing here " * 40, "licens"]):
        path = tmp_path / f"pkg{number}.dist-info" / "METADATA"
        path.parent.mkdir()
        path.write_text(f"Name: x\n\n{body}")
        paths.append(str(path))
    picked = corpusdir.pick_readmes(paths)
    assert [k.split(":")[0] for k, _ in picked] == ["pkg0.dist-info"]


# --- the sets -------------------------------------------------------------


def test_the_core_fixtures_are_the_same_each_time(fixtures: Path) -> None:
    first = sets_core.fixture_cases(fixtures)
    assert first == sets_core.fixture_cases(fixtures)
    keys = [c["key"] for c in first]
    assert len(keys) == len(set(keys))
    assert sum(c["kind"] == "short" for c in first) == 160
    assert {c["kind"] for c in first if c["kind"] != "short"} == {
        "long:clean",
        *(f"long:distorted_{n}" for n in ("01", "02", "05", "10", "20")),
    }
    assert all(c["want"] and c["text"] for c in first)


def test_many_texts_are_165_and_deterministic(fixtures: Path) -> None:
    many = sets_synth.many_cases(fixtures)
    assert many == sets_synth.many_cases(fixtures)
    assert len(many) == 165
    assert {c["kind"] for c in many} == {
        "many:clean",
        "many:distorted_02",
        "many:distorted_05",
    }
    two = next(c for c in many if c["key"] == "many:clean:2:0")
    assert len((two.get("want") or "").split()) == 2 and two["text"].count("\n\n") >= 1


def test_cores_come_from_templates(fixtures: Path) -> None:
    out = sets_synth.core_many_cases(fixtures, core_of)
    assert [c["kind"] for c in out].count("many:cores") == 12
    assert [c["kind"] for c in out].count("many:coremix") == 6
    assert "title" not in next(c for c in out if c["kind"] == "many:cores")["text"]


def test_the_other_synthetic_sets_have_their_counts(fixtures: Path) -> None:
    assert len(sets_synth.cjk_cases(fixtures)) == 24
    assert len(sets_synth.option_cases(fixtures)) == 36
    assert len(sets_core.notice_cases()) == 96
    options = {c["key"]: c.get("options") for c in sets_synth.option_cases(fixtures)}
    assert options["options:MIT:exclude self"] == {"exclude": ["MIT"]}
    assert options["options:MIT:only_spdx off"] == {"only_spdx": False}


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [("abcdef", 4, "abcd\nef"), ("abc", 5, "abc"), ("", 3, "")],
)
def test_wrap_cuts_at_a_width(text: str, width: int, expected: str) -> None:
    assert sets_synth.wrap(text, width) == expected


def test_the_digest_of_inputs_changes_with_one_character() -> None:
    assert digest({"a": ["x"]}) == digest({"a": ["x"]})
    assert digest({"a": ["x"]}) != digest({"a": ["y"]})


# --- keys, kinds, labels ----------------------------------------------------


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        ("real:ab12cd34:LICENSE", "real"),
        ("long:MIT:distorted_05", "long:distorted_05"),
        ("short:MIT:head_300", "short"),
        ("many:clean:5:0", "many:clean"),
        ("many:cores:2:1", "many:cores"),
        ("68 file: real:aa:LICENSE", "roadmap:68"),
        ("11: Apache-2.0, 3,000-character slice", "roadmap:11"),
        ("stress:MIT x 50", "stress:MIT x 50"),
    ],
)
def test_the_kind_of_a_key(key: str, kind: str) -> None:
    assert kind_of(key) == kind


@pytest.mark.parametrize(
    ("expression", "base"),
    [
        ("GPL-2.0-only", "GPL-2.0"),
        ("GPL-2.0-or-later", "GPL-2.0"),
        ("MIT+", "MIT"),
        ("MIT", "MIT"),
        (None, None),
    ],
)
def test_base_id_drops_the_variant_tail(
    expression: str | None, base: str | None
) -> None:
    assert base_id(expression) == base


def test_labels_are_counted_at_each_bar() -> None:
    cases = {
        "real:1": case(1, "MIT", 0.95),
        "real:2": case(1, "GPL-2.0-only", 0.9),
        "real:3": case(1, "ISC", 0.6),
        "real:4": case(1, None),
    }
    labels = {
        "real:1": ["MIT"],
        "real:2": ["GPL-2.0"],
        "real:3": ["ISC"],
        "real:4": ["MIT"],
        "real:5": ["A", "B"],
    }
    at85 = label_counts(cases, labels, 0.85)
    assert (at85["agree"], at85["other"], at85["none"]) == (2, 0, 2)
    at50 = label_counts(cases, labels, 0.5)
    assert (at50["agree"], at50["none"]) == (3, 1)


def test_a_score_at_the_bar_counts_as_an_answer() -> None:
    counts = label_counts({"real:1": case(1, "MIT", 0.85)}, {"real:1": ["MIT"]}, 0.85)
    assert counts["agree"] == 1
    assert (
        label_counts({"real:1": case(1, "MIT", 0.8499)}, {"real:1": ["MIT"]}, 0.85)[
            "none"
        ]
        == 1
    )


def test_fixtures_are_right_wrong_or_none() -> None:
    cases = {
        "long:MIT:clean": case(1, "MIT"),
        "long:MIT:distorted_01": case(1, "ISC"),
        "short:MIT:head_300": case(1, None),
        "real:1": case(1, "ISC"),
    }
    counts = fixture_counts(cases, 0.85)
    assert (counts["right"], counts["wrong"], counts["none"]) == (1, 1, 1)


# --- answers that moved ----------------------------------------------------


def test_an_answer_that_moved_is_listed_with_its_key() -> None:
    base = {"a": case(10, "MIT"), "b": case(10, "ISC"), "c": case(10, "Zlib")}
    cand = {"a": case(1, "MIT"), "b": case(1, "JSON"), "d": case(1, "Zlib")}
    moved = moved_answers("core", base, cand)
    assert [(m.key, m.field) for m in moved] == [
        ("b", "rows"),
        ("c", "missing"),
        ("d", "missing"),
    ]
    assert moved[0].base == [row("ISC")] and moved[0].cand == [row("JSON")]


def test_texts_that_moved_are_listed_and_times_alone_never_are() -> None:
    base = {"a": case(10, "MIT", texts=["MIT"])}
    assert not moved_answers("many", base, {"a": case(99, "MIT", texts=["MIT"])})
    moved = moved_answers("many", base, {"a": case(10, "MIT", texts=["ISC"])})
    assert [m.field for m in moved] == ["texts_row"]


def test_item_68_files_are_those_where_one_text_is_not_the_answer() -> None:
    cases = {
        "real:1": case(1, None, texts=["MIT"]),
        "real:2": case(1, "JSON", 0.92, texts=["MIT"]),
        "real:3": case(1, "MIT", 1.0, texts=["MIT"]),
        "real:4": case(1, "MIT", 1.0, texts=["MIT", "ISC"]),
        "real:5": case(1, "GPL-2.0-only", 1.0, texts=["GPL-2.0-or-later"]),
        "long:x:clean": case(1, None, texts=["MIT"]),
    }
    assert item68_keys(cases) == ["real:1", "real:2"]


# --- times and gates ---------------------------------------------------------


def _timed(real_ms: float, long_ms: float, n: int = 20) -> dict[str, Any]:
    cases = {f"real:{i}": case(real_ms) for i in range(n)}
    cases.update({f"long:MIT:clean{i}": case(long_ms) for i in range(n)})
    cases.update({f"long:MIT{i}:clean": case(long_ms) for i in range(n)})
    return result(cases)


def test_cpu_is_summed_by_kind() -> None:
    times = kind_times(_timed(100, 50, n=10)["cases"])
    assert times["real"].cases == 10 and times["real"].seconds == pytest.approx(1.0)
    assert times["long:clean"].median_ms == 50


@pytest.mark.parametrize(
    ("cand_ms", "status"), [(50, gates.PASS), (83, gates.PASS), (900, gates.FAIL)]
)
def test_the_core_gate_wants_twelve_times(cand_ms: float, status: str) -> None:
    base, cand = {"core": _timed(1000, 1000)}, {"core": _timed(cand_ms, cand_ms)}
    assert gates.core_cpu(base, cand).status == status


def test_the_core_gate_boundary_is_exactly_twelve() -> None:
    base = {"core": _timed(1200, 1200)}
    assert gates.core_cpu(base, {"core": _timed(100, 100)}).status == gates.PASS
    assert gates.core_cpu(base, {"core": _timed(101, 101)}).status == gates.FAIL


@pytest.mark.parametrize(("median", "status"), [(15, gates.PASS), (15.5, gates.FAIL)])
def test_the_real_file_median_limit_is_fifteen_ms(median: float, status: str) -> None:
    assert gates.real_median({"core": _timed(median, 1)}).status == status


def test_a_class_over_1_2_times_the_last_tag_fails_and_is_named() -> None:
    base = {"core": _timed(100, 100)}
    ok = {"core": _timed(120, 100)}
    slow = {"core": _timed(100, 121)}
    assert gates.no_class_slower(base, ok).status == gates.PASS
    gate = gates.no_class_slower(base, slow)
    assert gate.status == gates.FAIL and "long:clean 1.21x" in gate.detail


def test_a_tiny_class_is_not_judged() -> None:
    base = {"core": result({"real:1": case(1)})}
    cand = {"core": result({"real:1": case(5)})}
    assert gates.no_class_slower(base, cand).status == gates.NA


def _prose(*cases: tuple[str, str | None, float]) -> dict[str, Any]:
    return {
        "prose": result(
            {f"readme:{i}": case(1, a, s) for i, (_, a, s) in enumerate(cases)}
        )
    }


def test_a_moved_prose_answer_fails_its_gate() -> None:
    base = _prose(("a", "MIT", 1.0), ("b", None, 0.0))
    same = _prose(("a", "MIT", 0.9), ("b", None, 0.0))
    assert gates.prose(base, same).status == gates.PASS
    for moved in (
        _prose(("a", "ISC", 1.0), ("b", None, 0.0)),  # changed
        _prose(("a", None, 0.0), ("b", None, 0.0)),  # disappeared
        _prose(("a", "MIT", 1.0), ("b", "MIT", 0.86)),  # appeared at 0.85+
    ):
        gate = gates.prose(base, moved)
        assert gate.status == gates.FAIL and "readme:" in gate.detail


def test_prose_counts_low_rows_that_moved_but_does_not_fail_on_them() -> None:
    base = _prose(("a", "MIT", 1.0), ("b", "ISC", 0.8), ("c", "X11", 0.6))
    cand = _prose(("a", "MIT", 1.0), ("b", "MIT", 0.8), ("c", "ISC", 0.6))
    gate = gates.prose(base, cand)
    assert gate.status == gates.PASS
    assert "0 of 3 answers moved" in gate.detail
    assert "1 at 0.7 or more, 2 at 0.5 or more, 2 at any score" in gate.detail


def test_texts_compare_texts_call_where_recorded_and_not_a_missing_row() -> None:
    def many(**kw: Any) -> dict[str, Any]:
        return {"many": result({"many:1": case(1, None, **kw)})}

    base = many(called=["A", "B"])
    assert gates.texts(base, many(called=["A", "B"])).status == gates.PASS
    # A record with no rows has no TEXTS row; texts() is what is compared.
    assert gates.texts(base, many(called=["A", "B"], texts=["X"])).status == gates.PASS
    differing = gates.texts(base, many(called=["A"]))
    assert differing.status == gates.FAIL and "many:1" in differing.detail


def test_texts_row_is_compared_under_options_and_core_where_the_answer_is_same() -> (
    None
):
    many = {"many": result({"many:1": case(1, "MIT", called=["A"])})}

    def with_set(name: str, answer: str, texts: list[str]) -> dict[str, Any]:
        return {**many, name: result({f"{name}:k": case(1, answer, texts=texts)})}

    for name in ("options", "core"):
        base = with_set(name, "MIT", ["MIT"])
        assert gates.texts(base, with_set(name, "MIT", ["MIT"])).status == gates.PASS
        assert gates.texts(base, with_set(name, "MIT", ["X"])).status == gates.FAIL
        assert gates.texts(base, with_set(name, "ISC", ["X"])).status == gates.PASS


def test_the_labels_gate_wants_190_agree_and_at_most_16_other() -> None:
    labels = {f"real:{i}": ["MIT"] for i in range(210)}
    cases = {f"real:{i}": case(1, "MIT" if i < 190 else "ISC") for i in range(210)}
    assert gates.labels({"core": result(cases)}, labels).detail.startswith("agree 190")
    assert (
        gates.labels({"core": result(cases)}, labels).status == gates.FAIL
    )  # 20 other
    cases.update({f"real:{i}": case(1, None) for i in range(190, 210)})
    assert gates.labels({"core": result(cases)}, labels).status == gates.PASS
    cases["real:189"] = case(1, None)
    assert gates.labels({"core": result(cases)}, labels).status == gates.FAIL


def test_fixtures_gate_needs_right_not_lower_and_wrong_not_higher() -> None:
    base = {
        "core": result(
            {"long:MIT:clean": case(1, "MIT"), "long:ISC:clean": case(1, "JSON")}
        )
    }
    better = {
        "core": result(
            {"long:MIT:clean": case(1, "MIT"), "long:ISC:clean": case(1, "ISC")}
        )
    }
    worse = {
        "core": result(
            {"long:MIT:clean": case(1, "ISC"), "long:ISC:clean": case(1, "JSON")}
        )
    }
    assert gates.fixtures(base, better).status == gates.PASS
    assert gates.fixtures(base, worse).status == gates.FAIL


def test_a_new_answer_on_an_hpnd_fragment_fails_item_68() -> None:
    key = "64 HPND: HPND-DEC head_300"
    base = {"roadmap": result({key: case(1, None)})}
    assert (
        gates.item_68(base, {"roadmap": result({key: case(1, "HPND-DEC", 0.9)})}).status
        == gates.PASS
    )
    gate = gates.item_68(base, {"roadmap": result({key: case(1, "HPND-SMC", 0.9)})})
    assert gate.status == gates.FAIL and "HPND-SMC" in gate.detail


def test_roadmap_inputs_need_under_a_fifth_of_a_second() -> None:
    fast = {
        "roadmap": result({"11: a": case(200), "61: b": case(1), "70: c": case(5000)})
    }
    slow = {"roadmap": result({"68 file: x": case(201)})}
    assert gates.roadmap_time(fast).status == gates.PASS
    assert gates.roadmap_time(slow).status == gates.FAIL


@pytest.mark.parametrize(
    ("times", "status"),
    [
        ({"real-MIT": 150, "real-BSD-3-Clause": 150, "long-GPL-3.0": 300}, gates.PASS),
        ({"real-MIT": 151, "real-BSD-3-Clause": 100, "long-GPL-3.0": 100}, gates.FAIL),
        ({"real-MIT": 100, "real-BSD-3-Clause": 100, "long-GPL-3.0": 301}, gates.FAIL),
    ],
)
def test_one_call_limits(times: dict[str, float], status: str) -> None:
    named = result({f"detect {n}": {"min_ms": v} for n, v in times.items()})
    assert gates.one_call({"onecall": named}).status == status


def test_damage_is_judged_against_the_intact_build_or_its_reference() -> None:
    intact = {"damage:MIT": case(1, "MIT")}
    changed = {"damage:MIT": case(1, "MIT", 0.99)}
    kinds = {
        "none": {"applicable": True, "cases": intact},
        "codes changed": {"applicable": True, "cases": intact},
        "no checks table": {"applicable": False},
        "text changed": {"applicable": True, "cases": changed},
        "text changed" + REFERENCE: {"applicable": True, "cases": changed},
    }
    assert gates.damage({"damage": {"kinds": kinds}}).status == gates.PASS
    kinds["codes changed"] = {"applicable": True, "cases": changed}
    gate = gates.damage({"damage": {"kinds": kinds}})
    assert gate.status == gates.FAIL and "codes changed" in gate.detail


NOT_READY = "exit 1: licenseid.errors.DatabaseNotReadyError: database: empty: x"


@pytest.mark.parametrize(
    ("result", "passed"),
    [
        ({"error": NOT_READY, "grams_error": "e", "bytes_same": True}, True),
        ({"error": NOT_READY}, True),
        ({"error": NOT_READY, "bytes_same": False}, False),
        ({"error": "exit 1: ValueError: x", "bytes_same": True}, False),
        ({"cases": {"damage:MIT": case(1, "MIT")}, "bytes_same": True}, False),
        ({"error": NOT_READY, "cases": {}}, False),
    ],
    ids=["refused", "no-bytes", "written", "other-error", "answered", "with-cases"],
)
def test_a_copy_not_of_the_build_must_be_refused(
    result: dict[str, Any], passed: bool
) -> None:
    intact = {"damage:MIT": case(1, "MIT")}
    kinds = {
        "none": {"applicable": True, "cases": intact},
        "no checks table": {"applicable": True, **result},
        "checks table misshaped": {"applicable": False},
    }
    gate = gates.damage({"damage": {"kinds": kinds}})
    assert (gate.status == gates.PASS) is passed
    assert passed or "no checks table" in gate.detail


@pytest.mark.parametrize(
    ("change", "failed"),
    [
        ({}, False),
        ({"grams": {"MIT": {"digest": "y", "rows": 3}}}, True),
        ({"bytes_same": False}, True),
        ({"grams_error": "exit 1"}, True),
        ({"grams": None}, False),  # a side without the tables: no field at all
    ],
)
def test_damage_judges_gram_tables_and_the_file_bytes(
    change: dict[str, Any], failed: bool
) -> None:
    cases = {"damage:MIT": case(1, "MIT")}
    tables = {"MIT": {"digest": "x", "rows": 3}}
    plain = {"applicable": True, "cases": cases}
    intact = {**plain, "grams": tables, "bytes_same": True}
    damaged = {**intact, **change}
    if change.get("grams", 1) is None:
        intact, damaged = plain, dict(plain)
    kinds = {
        "none": intact,
        "postings table emptied": damaged,
        "postings without a stamp": {"applicable": False},
    }
    gate = gates.damage({"damage": {"kinds": kinds}})
    assert (gate.status == gates.FAIL) is failed
    if failed:
        assert "postings table emptied" in gate.detail
    else:
        assert "2 kinds equal their reference; 1 not applicable" in gate.detail


def test_threads_and_memory_and_size() -> None:
    good = {
        "threads": 4,
        "items": 9,
        "differing": 0,
        "first_call_race_same": True,
        "errors": [],
    }
    assert gates.threads({"threads": good}).status == gates.PASS
    for bad in ({"differing": 1}, {"first_call_race_same": False}, {"errors": ["x"]}):
        assert gates.threads({"threads": {**good, **bad}}).status == gates.FAIL
    base = {"memory": {"peak_mb": {"all": 100.0}}}
    assert (
        gates.memory(base, {"memory": {"peak_mb": {"all": 101.0}}}).status == gates.PASS
    )
    assert (
        gates.memory(base, {"memory": {"peak_mb": {"all": 101.1}}}).status == gates.FAIL
    )
    assert gates.db_size({"meta": {"db_bytes": 19_999_999}}).status == gates.PASS
    assert gates.db_size({"meta": {"db_bytes": 20_000_000}}).status == gates.FAIL


def test_the_noise_floor_of_two_runs_of_one_side() -> None:
    base = {"core": _timed(100, 100)}
    ratio, widest = gates.noise(base, {"core": _timed(110, 100)})
    assert 1.0 < ratio < 1.1 and 1.09 < widest < 1.11


# --- the report --------------------------------------------------------------


def _write(folder: Path, sets: dict[str, dict[str, Any]]) -> Path:
    folder.mkdir(parents=True)
    for name, value in sets.items():
        (folder / f"{name}.json").write_text(json.dumps(value))
    return folder


def test_the_report_lists_a_moved_answer_before_the_times(tmp_path: Path) -> None:
    base = _write(tmp_path / "a", {"core": _timed(1000, 1000)})
    twin = _write(tmp_path / "t", {"core": _timed(1010, 1000)})
    moved = _timed(10, 10)
    moved["cases"]["real:3"] = case(10, "Moved-ID")
    cand = _write(tmp_path / "b", {"core": moved})
    text, failed = compare_folders(base, cand, twin, None)
    assert text.index("real:3") < text.index("CPU seconds")
    assert "Moved-ID" in text and "A/A core" in text
    assert "licenseid ['0.0.0'] from ['/side/src/licenseid/__init__.py']" in text
    assert failed is False  # a moved answer is read, not a gate by itself


def test_a_clean_faster_candidate_passes_its_core_gate(tmp_path: Path) -> None:
    base = _write(tmp_path / "a", {"core": _timed(1000, 1000)})
    cand = _write(tmp_path / "b", {"core": _timed(10, 10)})
    text, _ = compare_folders(base, cand, None, None)
    assert "PASS         Core, CPU: " in text
    assert "0 fields differ in 0 inputs" in text


def test_a_wrong_import_and_a_busy_machine_are_shown(tmp_path: Path) -> None:
    base = _write(tmp_path / "a", {"core": _timed(10, 10)})
    odd = _timed(10, 10)
    odd.update(from_side=False, loaded=True)
    cand = _write(tmp_path / "b", {"core": odd})
    text, _ = compare_folders(base, cand, None, None)
    assert "WRONG IMPORT in ['core']" in text
    assert "machine busy during ['core']" in text


def test_the_exit_status_says_whether_a_gate_failed(tmp_path: Path) -> None:
    base = _write(tmp_path / "a", {"core": _timed(1000, 1000)})
    slow = _write(tmp_path / "b", {"core": _timed(500, 500)})
    text, failed = compare_folders(base, slow, None, None)
    assert failed is True and "FAIL         Core, CPU" in text
