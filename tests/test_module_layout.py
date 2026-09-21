# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How the matching modules depend on each other: matcher.py is the top, the
modules it was split into (ranking, retrieval, shorttext) never import it back,
they import in any order, and the match path stays off `requests`."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import licenseid
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.retrieval import get_candidates
from licenseid.shorttext import match_short_text
from licenseid.types import MatchRequest

SPLIT = ["ranking", "retrieval", "shorttext"]
MATCH_PATH = ["matcher", "ranking", "retrieval", "shorttext", "markers", "identifiers"]


def imported_after(statement: str, home: Path) -> set[str]:
    """Module names loaded by `statement`, in a fresh interpreter (so nothing
    the test session already imported can hide a dependency)."""
    code = f"import sys; {statement}; print(*sorted(sys.modules))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={"HOME": str(home), "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=60,
    )
    return set(result.stdout.split())


def imports_of(module: str) -> set[str]:
    """Every module a source file imports, from its syntax tree (importing
    `licenseid.<anything>` runs the package __init__, which loads the matcher,
    so a run-time check could not tell)."""
    path = Path(str(licenseid.__path__[0])) / f"{module}.py"
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", SPLIT)
def test_a_split_module_never_imports_the_matcher(module: str) -> None:
    """matcher.py is the top of the stack; an upward import is a cycle in
    waiting."""
    assert "licenseid.matcher" not in imports_of(module)


def test_the_split_modules_form_a_stack_ranking_below_shorttext() -> None:
    """ranking -> nothing of ours but classify and types; retrieval and
    shorttext may use ranking and the leaf modules, never each other."""
    assert "licenseid.retrieval" not in imports_of("shorttext")
    assert "licenseid.shorttext" not in imports_of("retrieval")
    for module in ("ranking", "retrieval", "shorttext"):
        assert not {"licenseid.matcher", "licenseid.markers"} & imports_of(module)
    assert not {"licenseid.retrieval", "licenseid.shorttext"} & imports_of("ranking")


@pytest.mark.parametrize("module", MATCH_PATH)
def test_the_match_path_never_loads_requests(module: str, tmp_path: Path) -> None:
    """Loading `requests` costs start-up time on every `match`; only `update`
    needs it (database.py imports spdx_source lazily)."""
    loaded = imported_after(f"import licenseid.{module}", tmp_path)
    assert "requests" not in loaded
    assert "licenseid.spdx_source" not in loaded


@pytest.mark.parametrize("first", SPLIT)
def test_the_modules_import_in_any_order(first: str, tmp_path: Path) -> None:
    others = [m for m in ["matcher", *SPLIT] if m != first]
    statement = "; ".join(f"import licenseid.{m}" for m in [first, *others])
    loaded = imported_after(statement, tmp_path)
    assert {f"licenseid.{m}" for m in [first, *others]} <= loaded


def test_the_matcher_methods_are_thin_wrappers(ordering_matcher: object) -> None:
    """_get_candidates and _match_short_text stay as the entry points tests and
    benchmarks use; they must give the module functions' answers."""
    assert isinstance(ordering_matcher, AggregatedLicenseMatcher)
    text = "permission is hereby granted free of charge to any person"
    request = MatchRequest()
    assert ordering_matcher._get_candidates(  # pylint: disable=protected-access
        request, text
    ) == get_candidates(ordering_matcher.db, request, text)
    assert ordering_matcher._match_short_text(  # pylint: disable=protected-access
        "mit"
    ) == match_short_text(ordering_matcher.db, "mit")
