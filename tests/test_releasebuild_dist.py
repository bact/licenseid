# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The check of ``dist/`` after the build (``scripts/check_dist_bundle.py``):
one wheel and one sdist, each holding the pinned SPDX bundle."""
# pylint: disable=missing-function-docstring

import hashlib
from pathlib import Path

import pytest
from hatch_helpers import (
    BUNDLE,
    OTHER_BUILD,
    PIN,
    ROOT,
    SDIST_PATH,
    WHEEL_PATH,
    gz,
    load_script,
    sdist_with,
    sdist_with_link,
    wheel_with,
)

import hatch_build

script = load_script("check_dist_bundle")
NEWER = gz({"format": 1, "licenseListVersion": "10.0"})
PIN_OF_BUNDLE = hashlib.sha256(BUNDLE).hexdigest()


def hook_file(tmp_path: Path, version: str = "9.99", raw: bytes = BUNDLE) -> Path:
    """A hook file pinning *version* and the digest of *raw*, as the real one
    spells them."""
    path = tmp_path / "hatch_build.py"
    path.write_text(
        "from typing import Final\n"
        f'BUNDLE_VERSION: Final = "{version}"\n'
        "BUNDLE_SHA256: Final = (\n"
        f'    "{hashlib.sha256(raw).hexdigest()}"\n'
        ")\n",
        encoding="utf-8",
    )
    return path


def dist_with(
    tmp_path: Path, wheel: bytes | None = BUNDLE, sdist: bytes | None = BUNDLE
) -> Path:
    """A dist/ with a wheel and an sdist holding *wheel* and *sdist* (None:
    no bundle in it)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel_with(
        dist / "licenseid-0-py3-none-any.whl",
        {"licenseid/__init__.py": b""} | ({} if wheel is None else {WHEEL_PATH: wheel}),
    )
    sdist_with(
        dist / "licenseid-0.tar.gz",
        {"licenseid-0/PKG-INFO": b""} | ({} if sdist is None else {SDIST_PATH: sdist}),
    )
    return dist


def test_the_script_and_the_hook_agree_on_names() -> None:
    assert script.WHEEL_MEMBER == hatch_build.ARCHIVE_PATH["wheel"]
    assert script.SDIST_MEMBER == hatch_build.IN_TREE
    assert script.MAX_BUNDLE == hatch_build.MAX_BUNDLE
    assert script.MAX_UNZIPPED == hatch_build.MAX_UNZIPPED


def test_the_pin_is_read_from_the_real_hook() -> None:
    assert script.read_pin(ROOT / "hatch_build.py") == PIN


def test_a_correct_dist_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dist = dist_with(tmp_path)
    assert script.main([str(dist), "--hook", str(hook_file(tmp_path))]) == 0
    digest = hashlib.sha256(BUNDLE).hexdigest()
    assert capsys.readouterr().out.splitlines() == [
        f"licenseid-0-py3-none-any.whl: SPDX License List 9.99, SHA-256 {digest}",
        f"licenseid-0.tar.gz: SPDX License List 9.99, SHA-256 {digest}",
    ]


def refused(tmp_path: Path, dist: Path, hook: Path | None = None) -> str:
    """The error ``check_dist`` raises for *dist*."""
    pin = script.read_pin(hook or hook_file(tmp_path))
    with pytest.raises(script.CheckError) as caught:
        script.check_dist(dist, pin)
    return str(caught.value)


def test_a_wheel_alone_is_refused(tmp_path: Path) -> None:
    dist = dist_with(tmp_path)
    (dist / "licenseid-0.tar.gz").unlink()
    assert refused(tmp_path, dist) == "dist: 0 files *.tar.gz, not 1"


def test_two_wheels_are_refused(tmp_path: Path) -> None:
    dist = dist_with(tmp_path)
    wheel_with(dist / "licenseid-1-py3-none-any.whl", {WHEEL_PATH: BUNDLE})
    assert refused(tmp_path, dist) == "dist: 2 files *.whl, not 1"


def test_a_wheel_without_the_bundle_is_refused(tmp_path: Path) -> None:
    assert refused(tmp_path, dist_with(tmp_path, wheel=None)).startswith(
        "dist: KeyError: "
    )


def test_an_sdist_without_the_bundle_is_refused(tmp_path: Path) -> None:
    message = refused(tmp_path, dist_with(tmp_path, sdist=None))
    assert message == f"licenseid-0.tar.gz: no {script.SDIST_MEMBER}"


@pytest.mark.parametrize("where", ["wheel", "sdist"])
def test_another_version_is_refused_before_its_digest(
    tmp_path: Path, where: str
) -> None:
    """The version is checked on its own, first: the pin is NEWER's, and the
    other artefact holds NEWER."""
    held = {"wheel": NEWER, "sdist": NEWER} | {where: BUNDLE}
    hook = hook_file(tmp_path, "10.0", NEWER)
    message = refused(tmp_path, dist_with(tmp_path, **held), hook)
    assert message.endswith(": version '9.99', not '10.0'")
    name = {"wheel": "licenseid-0-py3-none-any.whl", "sdist": "licenseid-0.tar.gz"}
    assert message.startswith(f"{name[where]}: ")


@pytest.mark.parametrize("where", ["wheel", "sdist"])
def test_other_bytes_of_the_version_are_refused(tmp_path: Path, where: str) -> None:
    message = refused(tmp_path, dist_with(tmp_path, **{where: OTHER_BUILD}))
    digest = hashlib.sha256(OTHER_BUILD).hexdigest()
    assert message.endswith(f": SHA-256 {digest}, not {PIN_OF_BUNDLE}")


def test_a_symlinked_bundle_in_the_sdist_is_refused(tmp_path: Path) -> None:
    dist = dist_with(tmp_path, sdist=None)
    sdist_with_link(dist / "licenseid-0.tar.gz")
    assert refused(tmp_path, dist) == f"licenseid-0.tar.gz: no {script.SDIST_MEMBER}"


@pytest.mark.parametrize("raw", [b"junk", gz([]), gz({})], ids=["junk", "list", "{}"])
def test_what_is_not_a_bundle_is_refused(tmp_path: Path, raw: bytes) -> None:
    message = refused(tmp_path, dist_with(tmp_path, wheel=raw))
    assert message.startswith("licenseid-0-py3-none-any.whl: not a bundle: ")


@pytest.mark.parametrize("where", ["wheel", "sdist"])
@pytest.mark.parametrize("size", [10, 11, 12])
def test_a_bundle_is_read_up_to_one_byte_over_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int, where: str
) -> None:
    monkeypatch.setattr(script, "MAX_BUNDLE", 10)
    dist = dist_with(tmp_path, **{where: b"x" * size})
    if where == "wheel":
        raw = script.wheel_bundle(dist / "licenseid-0-py3-none-any.whl")
    else:
        raw = script.sdist_bundle(dist / "licenseid-0.tar.gz")
    assert raw == b"x" * min(size, 11)


@pytest.mark.parametrize("size", [10, 11])
def test_a_bundle_over_the_cap_is_refused(
    monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    monkeypatch.setattr(script, "MAX_BUNDLE", 10)
    with pytest.raises(script.CheckError) as caught:
        script.check_artifact(Path("a.whl"), b"x" * size, ("9.99", PIN_OF_BUNDLE))
    if size == 10:
        assert str(caught.value).startswith("a.whl: not a bundle: ")
    else:
        assert str(caught.value) == "a.whl: bundle larger than 10 bytes"


def test_a_bundle_deeper_in_the_sdist_is_refused(tmp_path: Path) -> None:
    dist = dist_with(tmp_path, sdist=None)
    sdist = dist / "licenseid-0.tar.gz"
    sdist.unlink()
    sdist_with(sdist, {f"x/{SDIST_PATH}": BUNDLE})
    assert refused(tmp_path, dist) == f"licenseid-0.tar.gz: no {script.SDIST_MEMBER}"


@pytest.mark.parametrize(
    "text",
    ['BUNDLE_VERSION: Final = "9.99"\n', "x = 1\n", 'BUNDLE_SHA256 = "a"\n'],
    ids=["no digest", "neither", "not annotated"],
)
def test_a_hook_without_the_pin_is_refused(tmp_path: Path, text: str) -> None:
    hook = tmp_path / "hook.py"
    hook.write_text(text, encoding="utf-8")
    with pytest.raises(
        script.CheckError, match="^hook.py: no BUNDLE_VERSION and BUNDLE_SHA256$"
    ):
        script.read_pin(hook)


def test_main_reports_a_failure_on_standard_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dist = dist_with(tmp_path, wheel=OTHER_BUILD)
    assert script.main([str(dist), "--hook", str(hook_file(tmp_path))]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("check_dist_bundle: licenseid-0-py3-none-any.whl: SHA")
    assert script.main([str(dist), "--hook", str(tmp_path / "absent.py")]) == 1
    assert capsys.readouterr().err.startswith("check_dist_bundle: [Errno 2]")
