# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The pinned SPDX list of the build hook (``hatch_build.py``): it is the one
fetched, the only one shipped, and what the built wheel and sdist hold."""
# pylint: disable=missing-function-docstring,protected-access

import json
import re
from pathlib import Path
from typing import Any

import pytest
from hatch_helpers import (
    BUNDLE,
    NAME,
    OTHER_BUILD,
    PIN,
    SDIST_PATH,
    WHEEL_PATH,
    build_artifact,
    clean_environment,
    gz,
    hook,
    names,
    online,
    run,
    sdist_with,
    sdist_with_link,
    serve,
    unpacked_sdist,
    wheel_with,
)

import hatch_build
from hatch_build import SnapshotError


@pytest.fixture(autouse=True)
def pinned_fake_release(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_environment(monkeypatch)


FIXTURES = Path(__file__).parent / "fixtures" / "license-list"


def test_the_pinned_list_is_fetched_whatever_latest_json_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    newer = gz({"format": 1, "licenseListVersion": "10.0"})
    latest = json.dumps({"file": "v10.0.json.gz", "licenseListVersion": "10.0"})
    calls = serve(
        monkeypatch,
        {"latest.json": latest.encode(), "v10.0.json.gz": newer, NAME: BUNDLE},
    )
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    assert Path(next(iter(build_data["force_include"]))).read_bytes() == BUNDLE
    assert names(calls) == [NAME]
    instance.finalize(
        "standard", build_data, build_artifact(tmp_path, "wheel", build_data)
    )


def test_the_same_tree_ships_the_same_bytes_whatever_the_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Formerly the build shipped whichever list ``latest.json`` named."""
    newer = gz({"format": 1, "licenseListVersion": "10.0"})
    shipped: list[bytes] = []
    for version in ("9.99", "10.0"):
        latest = json.dumps({"file": f"v{version}.json.gz"}).encode()
        serve(
            monkeypatch,
            {"latest.json": latest, "v10.0.json.gz": newer, NAME: BUNDLE},
        )
        instance, _ = hook(tmp_path)
        build_data: dict[str, Any] = {"force_include": {}}
        instance.initialize("standard", build_data)
        shipped.append(Path(next(iter(build_data["force_include"]))).read_bytes())
        instance.finalize(
            "standard", build_data, build_artifact(tmp_path, "wheel", build_data)
        )
    assert shipped == [BUNDLE, BUNDLE]


@pytest.mark.parametrize("target", ["wheel", "sdist"])
def test_skip_fails_when_a_snapshot_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """Formerly ``skip`` beat ``LICENSEID_REQUIRE_BUNDLE=1`` without a word."""
    calls = serve(monkeypatch, {})
    monkeypatch.setenv("LICENSEID_BUNDLE", "skip")
    monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
    with pytest.raises(SnapshotError, match="LICENSEID_BUNDLE=skip, but"):
        run(tmp_path, target)
    assert not calls


@pytest.mark.parametrize("required", [False, True], ids=["warns", "fails"])
def test_an_override_that_is_not_the_pin_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    calls = serve(monkeypatch, {})
    mine = tmp_path / "mine.json.gz"
    mine.write_bytes(OTHER_BUILD)
    monkeypatch.setenv("LICENSEID_BUNDLE", str(mine))
    if required:
        monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
        with pytest.raises(SnapshotError, match="mine.json.gz: SHA-256 differs"):
            run(tmp_path)
    else:
        build_data, app = run(tmp_path)
        assert build_data == {"force_include": {}}
        (call,) = app.display_warning.call_args_list
        assert "mine.json.gz: SHA-256 differs from the pin" in call.args[0]
    assert not calls


def test_the_file_in_the_tree_must_be_the_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {})
    unpacked_sdist(tmp_path, gz({"format": 1, "licenseListVersion": "10.0"}))
    monkeypatch.setenv("LICENSEID_REQUIRE_BUNDLE", "1")
    with pytest.raises(
        SnapshotError, match=r"^spdx-bundle\.json\.gz: version '10.0', not '9.99'$"
    ):
        run(tmp_path)


def test_the_pin_names_a_published_bundle() -> None:
    """The real pin: a version ``tools.build_bundle`` names a file after, a
    digest, and the list the ID snapshots of the tests hold."""
    version, digest = PIN
    assert re.fullmatch(r"[0-9]+(\.[0-9]+)*", version)
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    for name in ("spdx-license-ids.json", "spdx-exception-ids.json"):
        doc = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert doc["license_list_version"] == version, name


@pytest.mark.parametrize(
    ("target", "make", "member"),
    [("wheel", wheel_with, WHEEL_PATH), ("sdist", sdist_with, SDIST_PATH)],
    ids=["wheel", "sdist"],
)
def test_read_shipped_reads_the_snapshot_of_an_artifact(
    tmp_path: Path, target: str, make: Any, member: str
) -> None:
    artifact = make(tmp_path / "a", {"licenseid/x.py": b"", member: BUNDLE})
    assert hatch_build.read_shipped(artifact, target) == BUNDLE


BROKEN_ARTIFACTS = {
    "wheel without": ("wheel", wheel_with, {"licenseid/x.py": b""}, "KeyError"),
    "sdist without": ("sdist", sdist_with, {"licenseid-0/x": b""}, "no snapshot"),
    "sdist, top level": ("sdist", sdist_with, {hatch_build.IN_TREE: BUNDLE}, "no"),
    "sdist, too deep": ("sdist", sdist_with, {f"a/{SDIST_PATH}": BUNDLE}, "no"),
    "wheel too large": ("wheel", wheel_with, {WHEEL_PATH: b"x" * 11}, "larger"),
    "sdist too large": ("sdist", sdist_with, {SDIST_PATH: b"x" * 11}, "larger"),
}


@pytest.mark.parametrize("case", BROKEN_ARTIFACTS.values(), ids=BROKEN_ARTIFACTS.keys())
def test_read_shipped_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    target, make, members, reason = case
    monkeypatch.setattr(hatch_build, "MAX_BUNDLE", 10)
    artifact = make(tmp_path / "a", members)
    with pytest.raises(SnapshotError, match=f"^a: .*{reason}"):
        hatch_build.read_shipped(artifact, target)


@pytest.mark.parametrize("target", ["wheel", "sdist"])
@pytest.mark.parametrize("content", [b"", b"not an archive"], ids=["empty", "junk"])
def test_read_shipped_refuses_what_is_not_an_archive(
    tmp_path: Path, target: str, content: bytes
) -> None:
    artifact = tmp_path / "a"
    artifact.write_bytes(content)
    with pytest.raises(SnapshotError, match="^a: "):
        hatch_build.read_shipped(artifact, target)
    with pytest.raises(SnapshotError, match="^absent: .*Error"):
        hatch_build.read_shipped(tmp_path / "absent", target)


@pytest.mark.parametrize("target", ["wheel", "sdist"])
def test_finalize_fails_when_the_built_artifact_holds_another_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """The check after the build: what the artifact holds is the pin."""
    online(monkeypatch)
    instance, _ = hook(tmp_path, target)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    member = WHEEL_PATH if target == "wheel" else SDIST_PATH
    make = wheel_with if target == "wheel" else sdist_with
    artifact = make(tmp_path / "built", {member: OTHER_BUILD})
    with pytest.raises(SnapshotError, match="^built: SHA-256 differs"):
        instance.finalize("standard", build_data, str(artifact))
    # Deleted: a later upload of dist/* cannot take it.
    assert not artifact.exists()
    assert instance._scratch is None
    # The check is made once: a second finalize has nothing to check.
    instance.finalize("standard", build_data, str(artifact))


@pytest.mark.parametrize("override", ["skip", "missing"])
def test_finalize_checks_nothing_when_nothing_was_shipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    serve(monkeypatch, {})
    value = "skip" if override == "skip" else str(tmp_path / "absent")
    monkeypatch.setenv("LICENSEID_BUNDLE", value)
    instance, _ = hook(tmp_path)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    instance.finalize("standard", build_data, str(tmp_path / "no-such.whl"))


WORKFLOWS = Path(__file__).parent.parent / ".github" / "workflows"


@pytest.mark.parametrize("workflow", ["build.yml", "pypi-publish.yml"])
def test_the_workflows_require_and_check_the_pinned_bundle(workflow: str) -> None:
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    assert 'LICENSEID_REQUIRE_BUNDLE: "1"' in text
    assert "python scripts/check_dist_bundle.py dist\n" in text
    assert text.index("python -m build") < text.index("check_dist_bundle.py")


@pytest.mark.parametrize("target", ["wheel", "sdist"])
def test_read_shipped_takes_a_snapshot_of_the_largest_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    monkeypatch.setattr(hatch_build, "MAX_BUNDLE", 10)
    member = WHEEL_PATH if target == "wheel" else SDIST_PATH
    make = wheel_with if target == "wheel" else sdist_with
    artifact = make(tmp_path / "a", {member: b"x" * 10})
    assert hatch_build.read_shipped(artifact, target) == b"x" * 10


def test_read_shipped_takes_no_link_in_an_sdist(tmp_path: Path) -> None:
    """Only a file is the snapshot, not a link to another member."""
    artifact = sdist_with_link(tmp_path / "a")
    with pytest.raises(SnapshotError, match="^a: no snapshot in it$"):
        hatch_build.read_shipped(artifact, "sdist")


@pytest.mark.parametrize("target", ["wheel", "sdist"])
def test_finalize_deletes_an_artifact_it_cannot_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    online(monkeypatch)
    instance, _ = hook(tmp_path, target)
    build_data: dict[str, Any] = {"force_include": {}}
    instance.initialize("standard", build_data)
    artifact = tmp_path / "built"
    artifact.write_bytes(b"cut short")
    with pytest.raises(SnapshotError, match="^built: "):
        instance.finalize("standard", build_data, str(artifact))
    assert not artifact.exists()


def test_finalize_keeps_a_good_artifact_and_raises_when_one_is_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    online(monkeypatch)
    build_data, _ = run(tmp_path, "wheel")
    assert (tmp_path / "dist" / "licenseid-0-py3-none-any.whl").is_file()
    instance, _ = hook(tmp_path)
    instance.initialize("standard", build_data)
    with pytest.raises(SnapshotError, match="^absent.whl: "):
        instance.finalize("standard", build_data, str(tmp_path / "absent.whl"))
