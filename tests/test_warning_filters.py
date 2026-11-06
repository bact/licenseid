# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``warning.once()`` reads the filters in force as CPython does, whatever
shape a filter's fields have: a compiled pattern (``filterwarnings``, ``-W``),
None, or the plain ``str`` of the built-in default filter. A plain ``str``
crashed ``resolve()`` in a plain Python process on a database that warns."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import os
import subprocess
import sys
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db, writer

from licenseid import warning
from licenseid.warning import LicenseIdWarning, once

# The filters CPython starts with, as its C ``_warnings`` module builds them
# (3.10 to 3.14, a release build): the module field of the first is a str.
STARTUP_FILTERS: list[tuple[object, ...]] = [
    ("default", None, DeprecationWarning, "__main__", 0),
    ("ignore", None, DeprecationWarning, None, 0),
    ("ignore", None, PendingDeprecationWarning, None, 0),
    ("ignore", None, ImportWarning, None, 0),
    ("ignore", None, ResourceWarning, None, 0),
]


@pytest.fixture(autouse=True)
def forget() -> Generator[None, None, None]:
    warning.reset_once()
    yield
    warning.reset_once()


def _insert(
    action: str, message: str | None, category: type[Warning], module: str | None
) -> None:
    """Put a filter with plain ``str`` fields first, as CPython's C module
    builds its default one (typeshed types the fields as patterns only)."""
    _filters().insert(0, (action, message, category, module, 0))


def _filters() -> list[tuple[object, ...]]:
    """The filter list in force, as the list of tuples it is."""
    return cast("list[tuple[object, ...]]", warnings.filters)


def _give() -> None:
    warning.warn("database", "build v2 outdated", "current v3")


def _give_once_twice() -> int:
    """How many times ``once()`` gives one text, given twice from two lines."""
    with warnings.catch_warnings(record=True) as given, once():
        _give()
        _give()
    return len([w for w in given if issubclass(w.category, LicenseIdWarning)])


def test_the_startup_filters_have_a_str_module() -> None:
    """What the regression rests on: CPython's own default filter holds a
    plain str. If a release changes that, the test below proves less."""
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import warnings; print(repr(warnings.filters[0][3]))",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert done.stdout.strip() == "'__main__'"


def test_the_startup_filters_do_not_crash_once() -> None:
    with warnings.catch_warnings():
        _filters()[:] = STARTUP_FILTERS
        assert _give_once_twice() == 1


@pytest.mark.parametrize(
    ("category", "ignored"),
    [
        pytest.param(LicenseIdWarning, True, id="ours"),
        pytest.param(UserWarning, True, id="a-base-class"),
        pytest.param(DeprecationWarning, False, id="another-category"),
    ],
)
def test_a_str_module_filter_matches_by_equality(
    category: type[Warning], ignored: bool
) -> None:
    """An "ignore" filter whose module is this module's name, as a str: it
    applies to the warning given here (not counted as given), unless its
    category is another."""
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        _insert("ignore", None, category, __name__)
        assert _give_once_twice() == (0 if ignored else 1)
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        # Not given, so given at the next call; given, so not again.
        assert _give_once_twice() == (1 if ignored else 0)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(__name__[:-1], id="a-prefix"),
        pytest.param(__name__ + "x", id="longer"),
        pytest.param(__name__.upper(), id="another-case"),
        pytest.param("__main__", id="main"),
    ],
)
def test_a_str_module_filter_for_another_module_does_not_apply(name: str) -> None:
    """A str is compared whole, not as a pattern from the start: the
    warning is shown, so once() gives it once and not again."""
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        _insert("ignore", None, LicenseIdWarning, name)
        assert _give_once_twice() == 1
        assert _give_once_twice() == 0


def test_a_str_message_field_matches_by_equality() -> None:
    """CPython reads a str message field the same way as a str module."""
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        text = "database: build v2 outdated: current v3"
        _insert("ignore", text, LicenseIdWarning, None)
        assert _give_once_twice() == 0
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        _insert("ignore", text[:-1], LicenseIdWarning, None)
        assert _give_once_twice() == 1


_RESOLVE = """
import sys
import licenseid
print(licenseid.resolve("MIT", sys.argv[1])["expression"])
"""


def test_resolve_on_an_outdated_database_in_a_plain_process(tmp_path: Path) -> None:
    """``resolve()`` on a database stamped build v2, in a Python process with
    no filter of its own (not pytest, not the CLI): it answers and warns."""
    db = make_ready_file_db(tmp_path / "old.db")
    with writer(db) as conn:
        conn.execute("UPDATE db_metadata SET value = '2' WHERE key = 'build_version'")
    home = tmp_path / "child-home"
    home.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "LICENSEID"))
    }
    env.update(HOME=str(home), USERPROFILE=str(home))
    done = subprocess.run(
        [sys.executable, "-I", "-c", _RESOLVE, str(db)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
        cwd=tmp_path,
    )
    assert "Traceback" not in done.stderr, done.stderr
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "MIT"
    assert "database: build v2 outdated" in done.stderr


# once() under context-aware warnings: an ignored warning is not marked given.
_CONTEXT = """
import sys, warnings
sys.path.insert(0, sys.argv[1])
from licenseid import warning
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    with warning.once():
        warning.warn("input", "x", "1")
with warnings.catch_warnings(record=True) as given:
    warnings.simplefilter("always")
    with warning.once():
        warning.warn("input", "x", "1")
print(len(given))
"""


def test_once_reads_the_filters_of_the_context() -> None:
    """With ``-X context_aware_warnings`` (3.14; a free-threaded build's
    default) ``catch_warnings`` keeps its filters in the context, apart
    from ``warnings.filters``: an ignored warning is still given later.
    Earlier versions take the option and ignore it."""
    source = str(Path(warning.__file__).resolve().parents[1])
    done = subprocess.run(
        [sys.executable, "-I", "-X", "context_aware_warnings=1", "-c", _CONTEXT]
        + [source],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert done.stdout.strip() == "1", done.stderr


def test_once_takes_the_filters_python_says_are_in_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where ``warnings._get_filters`` exists, it says which filters are in
    force, not ``warnings.filters``; elsewhere ``warnings.filters`` does."""
    in_force: list[tuple[object, ...]] = []
    monkeypatch.setattr(warnings, "_get_filters", lambda: in_force, raising=False)
    assert warning._filters() is in_force  # pylint: disable=protected-access
    monkeypatch.delattr(warnings, "_get_filters")
    assert warning._filters() is warnings.filters  # pylint: disable=protected-access
