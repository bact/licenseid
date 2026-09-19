# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The optional Java tier (tools-java via JPype) is gone: nothing that used to
switch it on may change results, and nothing may pretend it still exists."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import re
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import MIT_SEARCH_TEXT, make_mit_db_path

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.types import InternalMatch, LicenseMatch, MatchRequest


@pytest.fixture
def mit_db() -> Generator[str, None, None]:
    db_path, keep_alive = make_mit_db_path(
        "test_no_java", datetime.now(timezone.utc).isoformat()
    )
    yield db_path
    keep_alive.close()


@pytest.mark.parametrize(
    "flags",
    [["--java"], ["--no-java"], ["--java", "--bold"], ["--pop", "--java"]],
    ids=["java", "no_java", "java_bold", "pop_java"],
)
def test_java_options_are_rejected(mit_db: str, flags: list[str]) -> None:
    """click's usage error (exit 2); its wording is click's, not our grammar."""
    result = CliRunner().invoke(cli, ["--db", mit_db, "match", "MIT", *flags])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert re.search(r"[Nn]o such option:? '?--(no-)?java", result.stderr)


@pytest.mark.parametrize("args", [["--help"], ["match", "--help"]])
def test_help_does_not_mention_java(args: list[str]) -> None:
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0
    assert "java" not in result.stdout.lower()


@pytest.fixture(params=["missing", "empty", "a_file"])
def tools_jar_env(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    """SPDX_TOOLS_JAR values that used to matter: a path that does not exist,
    an empty string, and a real file."""
    jar = tmp_path / "tool.jar"
    jar.write_bytes(b"PK\x03\x04 not really a jar")
    value = {"missing": str(tmp_path / "nope.jar"), "empty": "", "a_file": str(jar)}
    monkeypatch.setenv("SPDX_TOOLS_JAR", value[request.param])
    return str(request.param)


def test_tools_jar_variable_is_ignored(mit_db: str, tools_jar_env: str) -> None:
    del tools_jar_env  # only its side effect (the environment variable) matters
    for args in (["--id", "MIT"], ["--text", MIT_SEARCH_TEXT]):
        result = CliRunner().invoke(cli, ["--db", mit_db, "match", "--bold", *args])
        assert (result.exit_code, result.stdout, result.stderr) == (0, "MIT\n", "")
    assert AggregatedLicenseMatcher(mit_db).match(text=MIT_SEARCH_TEXT)


def test_matcher_has_no_java_state(mit_db: str) -> None:
    matcher = AggregatedLicenseMatcher(mit_db)
    for name in ("enable_java", "jar_path", "has_java", "_consult_java", "_ensure_jvm"):
        assert not hasattr(matcher, name), name
    with pytest.raises(TypeError, match="enable_java"):
        # pylint: disable-next=unexpected-keyword-arg
        AggregatedLicenseMatcher(mit_db, enable_java=True)  # type: ignore[call-arg]


def test_enable_popularity_is_keyword_only(mit_db: str) -> None:
    """It took the positional slot enable_java used to hold, so a stale
    AggregatedLicenseMatcher(db, True) must fail, not turn popularity on."""
    with pytest.raises(TypeError):
        # pylint: disable-next=too-many-function-args
        AggregatedLicenseMatcher(mit_db, True)  # type: ignore[call-arg]
    assert AggregatedLicenseMatcher(mit_db, enable_popularity=True).enable_popularity


def test_result_types_have_no_java_fields() -> None:
    assert "java_verified" not in LicenseMatch.__annotations__
    assert "java_verified" not in InternalMatch.__annotations__
    assert "enable_java" not in MatchRequest.__annotations__


def test_match_result_has_no_java_key(mit_db: str) -> None:
    results = AggregatedLicenseMatcher(mit_db).match(text=MIT_SEARCH_TEXT)
    assert results
    assert all("java_verified" not in r for r in results)


def test_stale_enable_java_option_is_ignored_silently(mit_db: str) -> None:
    """BUG: match() takes **options and does not reject an unknown one, so a
    caller that still passes enable_java=True (or mistypes any option) gets
    no error and no effect. Pinned, not fixed (roadmap)."""
    matcher = AggregatedLicenseMatcher(mit_db)
    plain = matcher.match(text=MIT_SEARCH_TEXT)
    assert matcher.match(text=MIT_SEARCH_TEXT, enable_java=True) == plain
    assert matcher.match(text=MIT_SEARCH_TEXT, enable_javaa=True) == plain
