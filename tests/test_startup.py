# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Start-up: ``import licenseid`` and the CLI load only what they use.

A public name loads its module at its first use (``licenseid.__getattr__``),
and a command loads its module when it is named
(``licenseid.clicommands``). Children, not this process, say what a run
loads: the test run imports everything.
"""

import ast
import importlib
import json
import os
import pkgutil
import subprocess
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

import licenseid
from licenseid import cli as cli_module
from licenseid.cli import cli
from licenseid.clicommands import COMMANDS, LazyCommands, short_help
from licenseid.database import LicenseDatabase

# What no run of `--version`, `--help` or the package import may load.
HEAVY = ("rapidfuzz", "requests", "sqlite3", "licenseid.detector", "licenseid.database")
# Nor the resolver, which a command line that names no command never uses.
LIGHT = (*HEAVY, "licenseid.result", "licenseid.resolver", "licenseid.textinput")

# A child runs `argv` and writes the names of the modules it loaded to a file at
# exit (not those the interpreter held: `coverage` loads sqlite3 in every child).
_CHILD = (
    "import atexit, json, sys\n"
    "target, before = sys.argv[1], set(sys.modules)\n"
    "def dump():\n"
    "    with open(target, 'w') as out:\n"
    "        json.dump(sorted(set(sys.modules) - before), out)\n"
    "atexit.register(dump)\n"
    "{body}"
)
_CLI = (
    "from licenseid.cli import main\nsys.argv = ['licenseid', *sys.argv[2:]]\nmain()\n"
)
_IMPORT = "import licenseid\n"


# pylint: disable=missing-function-docstring
Loaded = Callable[[str, tuple[str, ...]], frozenset[str]]


@pytest.fixture(name="loaded", scope="module")
def _loaded_in_a_child(tmp_path_factory: pytest.TempPathFactory) -> Loaded:
    """``loaded(body, *argv)``: the modules a child holds at exit, from a
    scratch home (the real cache is never read)."""
    home = tmp_path_factory.mktemp("home")
    out = tmp_path_factory.mktemp("out")

    @cache
    def run(body: str, argv: tuple[str, ...]) -> frozenset[str]:
        target = out / f"{len(list(out.iterdir()))}.json"
        subprocess.run(
            [sys.executable, "-c", _CHILD.format(body=body), str(target), *argv],
            env={**os.environ, "HOME": str(home), "USERPROFILE": str(home)},
            capture_output=True,
            check=False,
        )
        return frozenset(json.loads(target.read_text(encoding="utf-8")))

    return run


@pytest.mark.parametrize("heavy", LIGHT)
@pytest.mark.parametrize(
    ("body", "argv"),
    [
        (_IMPORT, ()),
        (_CLI, ("--version",)),
        (_CLI, ("-V",)),
        (_CLI, ("--help",)),
        (_CLI, ("detct",)),  # an unknown command, offered "did you mean"
    ],
    ids=["import", "version", "V", "help", "unknown-command"],
)
def test_what_a_light_run_does_not_load(
    loaded: Loaded, body: str, argv: tuple[str, ...], heavy: str
) -> None:
    assert heavy not in loaded(body, argv)


@pytest.mark.parametrize(
    "heavy",
    ["rapidfuzz", "requests", "licenseid.detector", "licenseid.database", "tarfile"],
)
def test_what_resolve_does_not_load(loaded: Loaded, heavy: str) -> None:
    """``resolve`` of a value reads a list, never a text: with no database
    (the scratch home has none) it needs neither the detector nor RapidFuzz
    (SQLite it loads: the readiness check of the default path)."""
    assert heavy not in loaded(_CLI, ("resolve", "MIT"))


@pytest.mark.parametrize(
    "heavy",
    ["rapidfuzz", "requests", "licenseid.detector", "tarfile"],
)
def test_what_resolve_with_a_database_does_not_load(
    loaded: Loaded, bundle_db: LicenseDatabase, heavy: str
) -> None:
    """A ready database is opened to read its list, never its texts: the
    modules of the database (``licenseid.database``) load no RapidFuzz."""
    modules = loaded(_CLI, ("--db", str(bundle_db.db_path), "resolve", "MIT"))
    assert "licenseid.database" in modules  # the database was opened
    assert heavy not in modules


def test_a_database_is_loaded_when_it_is_opened(loaded: Loaded) -> None:
    """The control: the heavy names above are what a detection loads."""
    modules = loaded(_CLI, ("detect", "--text", "MIT"))
    assert {"rapidfuzz", "licenseid.detector", "licenseid.database"} <= modules


# ---- the public names ----------------------------------------------------


def _type_checking_imports() -> dict[str, str]:
    """Each name the ``if TYPE_CHECKING:`` block of ``licenseid/__init__``
    imports, with the module it comes from."""
    tree = ast.parse(Path(licenseid.__file__ or "").read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        # `if TYPE_CHECKING:` only; `if not TYPE_CHECKING:` holds __getattr__.
        if (
            isinstance(node, ast.If)
            and "TYPE_CHECKING" in ast.dump(node.test)
            and not isinstance(node.test, ast.UnaryOp)
        ):
            for item in node.body:
                assert isinstance(item, ast.ImportFrom) and item.module
                for alias in item.names:
                    found[alias.name] = item.module.removeprefix("licenseid.")
    return found


@pytest.mark.parametrize("name", licenseid.__all__)
def test_a_public_name_is_its_home_modules(name: str) -> None:
    table = licenseid._HOME  # pylint: disable=protected-access
    home = importlib.import_module(f"licenseid.{table[name]}")
    assert getattr(licenseid, name) is getattr(home, name)
    assert vars(licenseid)[name] is getattr(home, name)  # kept after the first use


def test_the_table_the_all_list_and_the_type_imports_agree() -> None:
    table = licenseid._HOME  # pylint: disable=protected-access
    assert sorted(table) == sorted(licenseid.__all__) == sorted(set(licenseid.__all__))
    assert _type_checking_imports() == table


def test_dir_holds_every_public_name_before_any_is_used() -> None:
    done = _run(
        "import licenseid\n"
        "assert not set(licenseid.__all__) & set(vars(licenseid)), 'loaded'\n"
        "names = dir(licenseid)\n"
        "assert set(licenseid.__all__) <= set(names), names\n"
        "assert '__version__' in names and names == sorted(names)\n"
    )
    assert done.returncode == 0, done.stderr


NO_SUCH = "nope"


def test_an_unknown_name_is_an_attribute_error() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'nope'") as raised:
        _ = getattr(licenseid, NO_SUCH)  # the type checker would flag the dot
    assert str(raised.value) == "module 'licenseid' has no attribute 'nope'"
    assert not hasattr(licenseid, "nope")
    assert getattr(licenseid, "nope", 7) == 7


def test_a_private_name_is_not_a_public_one() -> None:
    with pytest.raises(AttributeError):
        _ = getattr(licenseid, "__wrapped" + "__")


@pytest.mark.parametrize("name", ["InvalidInputError", "LicenseIdError", "Variant"])
def test_exceptions_and_types_are_the_same_objects_after_a_pickle(name: str) -> None:
    import pickle  # pylint: disable=import-outside-toplevel

    obj = getattr(licenseid, name)
    if isinstance(obj, type) and issubclass(obj, Exception):
        again = pickle.loads(pickle.dumps(obj("detail")))
        assert again.__class__ is obj and again.args == ("detail",)
        assert issubclass(obj, licenseid.LicenseIdError)
    else:
        assert pickle.loads(pickle.dumps(obj)) is obj


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
    )


def test_a_star_import_binds_the_public_names() -> None:
    done = _run(
        "from licenseid import *\n"
        "import licenseid\n"
        "assert all(globals()[n] is getattr(licenseid, n) for n in licenseid.__all__)\n"
        "print(len(licenseid.__all__))\n"
    )
    assert done.returncode == 0, done.stderr
    assert int(done.stdout) == len(licenseid.__all__)


def test_the_package_imports_without_a_warning() -> None:
    done = subprocess.run(
        [sys.executable, "-W", "error", "-c", "import licenseid; licenseid.resolve"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")


@pytest.mark.parametrize("name", ["detect", "resolve", "LicenseDetector", "Detection"])
def test_the_first_use_from_eight_threads_gives_one_object(name: str) -> None:
    done = _run(
        "import threading, licenseid\n"
        "got, gate = [], threading.Barrier(8)\n"
        "def use():\n"
        "    gate.wait()\n"
        f"    got.append(licenseid.{name})\n"
        "threads = [threading.Thread(target=use) for _ in range(8)]\n"
        "[t.start() for t in threads]\n"
        "[t.join() for t in threads]\n"
        "assert len(got) == 8 and all(g is got[0] for g in got), got\n"
    )
    assert done.returncode == 0, done.stderr


# ---- the commands --------------------------------------------------------


def test_the_table_is_the_commands_the_modules_define() -> None:
    modules = {entry.module for entry in COMMANDS.values()}
    defined = {}
    for module in sorted(modules):
        for command in importlib.import_module(f"licenseid.{module}").COMMANDS:
            assert command.name is not None
            defined[command.name] = (module, command)
    assert sorted(defined) == sorted(COMMANDS)
    assert {n: m for n, (m, _) in defined.items()} == {
        n: e.module for n, e in COMMANDS.items()
    }


@pytest.mark.parametrize("limit", [0, 10, 20, 30, 45, 56, 64, 72, 100, 500])
@pytest.mark.parametrize("name", list(COMMANDS))
def test_a_commands_table_help_is_its_short_help(name: str, limit: int) -> None:
    command = cli.commands[name]
    assert short_help(name, limit) == command.get_short_help_str(limit)
    first_paragraph = (command.help or "").split("\n\n")[0]
    assert COMMANDS[name].help == " ".join(first_paragraph.split())


def test_the_group_help_is_pinned() -> None:
    result = CliRunner().invoke(cli, ["--help"], prog_name="licenseid")
    assert result.exit_code == 0
    assert result.output == (
        "Usage: licenseid [OPTIONS] [COMMAND] [ARGS]...\n"
        "\n"
        "  A portable SPDX licence identification tool.\n"
        "\n"
        "Options:\n"
        "  -V, --version  Print the version and exit.\n"
        "  --db TEXT      Path to the license database.\n"
        "  --help         Show this message and exit.\n"
        "\n"
        "Commands:\n"
        "  clear-cache  Delete the database and the cache files beside it.\n"
        "  detect       Identify license text and return the closest matched "
        "SPDX...\n"
        "  is-fsf       True if the license is FSF-libre, judged as is-osi "
        "judges.\n"
        "  is-osi       True if the license is OSI-approved: every operand of "
        "an...\n"
        "  is-spdx      True if every licence and exception ID is on the SPDX...\n"
        "  resolve      Resolve one declared licence value to an SPDX "
        "expression.\n"
        "  update       Update the license database from remote sources.\n"
    )


def test_the_command_mapping_behaves_as_a_dict_of_commands() -> None:
    commands = LazyCommands()
    assert list(commands) == list(COMMANDS) and len(commands) == len(COMMANDS)
    assert "detect" in commands and "detct" not in commands
    assert commands.get("detct") is None
    with pytest.raises(KeyError):
        _ = commands["detct"]
    first = commands["is-osi"]
    assert first is commands["is-osi"] and first.name == "is-osi"
    replacement = click.Command("is-osi")
    commands["is-osi"] = replacement
    assert commands["is-osi"] is replacement
    del commands["is-osi"]
    assert commands["is-osi"] is first  # loaded again, from its module


def test_an_unknown_command_is_offered_its_neighbours() -> None:
    result = CliRunner().invoke(cli, ["detct"])
    assert result.exit_code == 2
    assert result.stderr == ("ERROR: command: not found: detct; did you mean detect\n")


def test_the_default_database_path_is_the_datadirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from licenseid import datadir  # pylint: disable=import-outside-toplevel

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert cli_module.get_default_db_path() == datadir.get_default_db_path()


@pytest.mark.parametrize("sqlite_loaded", [True, False], ids=["loaded", "unloaded"])
def test_a_failure_that_is_not_sqlites_passes_through(
    monkeypatch: pytest.MonkeyPatch, sqlite_loaded: bool
) -> None:
    """The group words a SQLite error and no other, whether or not the module
    that defines it was ever imported."""

    @click.command(name="boom")
    def boom() -> None:
        raise ValueError("not sqlite")

    if not sqlite_loaded:
        monkeypatch.delitem(sys.modules, "sqlite3")
    monkeypatch.setitem(cli.commands, "boom", boom)
    result = CliRunner().invoke(cli, ["boom"])
    assert isinstance(result.exception, ValueError)


# ---- the text-file call ---------------------------------------------------

#: What a call that reads a licence text never needs: the SPDX expression
#: parser (a text has no expression to parse), the gzip reader of a bundle
#: (only a bundle is read through it), and ``fractions`` with ``decimal``.
TEXT_FILE_SKIPS = ("py_spdx_license", "gzip", "fractions", "decimal")


@pytest.fixture(name="mit_file", scope="module")
def _mit_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A file holding the MIT licence text."""
    fixture = Path(__file__).parent / "fixtures" / "license-text-long" / "MIT.json"
    text = json.loads(fixture.read_text(encoding="utf-8"))["license_text"]
    path = tmp_path_factory.mktemp("mit") / "LICENSE"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("skipped", TEXT_FILE_SKIPS)
def test_what_a_text_file_call_does_not_load(
    loaded: Loaded, bundle_db: LicenseDatabase, mit_file: Path, skipped: str
) -> None:
    argv = ("--db", str(bundle_db.db_path), "detect", str(mit_file))
    modules = loaded(_CLI, argv)
    assert {"rapidfuzz", "licenseid.detector"} <= modules  # the call ran
    assert skipped not in modules


def test_the_parser_is_loaded_when_an_expression_is_parsed(
    loaded: Loaded, bundle_db: LicenseDatabase
) -> None:
    """The control: the module the text-file call skips is the one a compound
    value loads, at its first use."""
    argv = ("--db", str(bundle_db.db_path), "resolve", "MIT OR Apache-2.0")
    assert "py_spdx_license" in loaded(_CLI, argv)


def test_every_module_of_the_package_imports() -> None:
    """Each module imports: a lazy import is a name written where it is used,
    and a typo there would fail only when that path runs."""
    package = Path(licenseid.__file__ or "").parent
    names = [m.name for m in pkgutil.iter_modules([str(package)])]
    assert len(names) > 90
    for name in names:
        importlib.import_module(f"licenseid.{name}")
