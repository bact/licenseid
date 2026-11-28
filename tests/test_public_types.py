# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The public names are typed: a type checker sees a misspelt one, and
``typing.get_type_hints`` reads every signature (Sphinx, typeguard, pydantic).
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

import licenseid

SRC = Path(licenseid.__file__ or "").parent.parent


def test_the_lazy_getattr_is_hidden_from_type_checkers() -> None:
    """The module ``__getattr__`` sits under ``if not TYPE_CHECKING:``: a
    type checker that read it would type every misspelt name as ``object``
    (the mypy test below runs where mypy is installed)."""
    tree = ast.parse(Path(licenseid.__file__ or "").read_text(encoding="utf-8"))
    hidden = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "not typing.TYPE_CHECKING"
    ]
    names = [
        f.name for node in hidden for f in node.body if isinstance(f, ast.FunctionDef)
    ]
    assert names == ["__getattr__"]
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
        for node in tree.body
    )


def test_a_type_checker_sees_a_misspelt_public_name(tmp_path: Path) -> None:
    """The lazy ``__getattr__`` is for run time only: mypy reports the two
    misspelt names and none of the right one."""
    pytest.importorskip("mypy")
    source = tmp_path / "use.py"
    source.write_text(
        "from licenseid import LicenseDetector, LicenseDetecter\n"
        "import licenseid\n"
        "licenseid.resolv('MIT')\n"
        "licenseid.resolve('MIT')\n",
        encoding="utf-8",
    )
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--cache-dir",
            str(tmp_path / "cache"),
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={**os.environ, "MYPYPATH": str(SRC)},
    )
    errors = [line for line in done.stdout.splitlines() if line.startswith("use.py")]
    assert len(errors) == 2, done.stdout
    assert 'Module "licenseid" has no attribute "LicenseDetecter"' in errors[0]
    assert 'Module has no attribute "resolv"' in errors[1]
    assert all("[attr-defined]" in line for line in errors)


def _hints_failures(code: str) -> str:
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout + done.stderr


def test_every_public_signature_resolves_its_type_hints() -> None:
    """In a process that imported only ``licenseid``: each public function,
    class and public method of a class."""
    failures = _hints_failures(
        "import inspect, typing, licenseid\n"
        "bad = []\n"
        "def check(label, obj):\n"
        "    try:\n"
        "        typing.get_type_hints(obj)\n"
        "    except Exception as error:\n"
        "        bad.append(f'{label}: {type(error).__name__}: {error}')\n"
        "for name in licenseid.__all__:\n"
        "    obj = getattr(licenseid, name)\n"
        "    if not (inspect.isroutine(obj) or inspect.isclass(obj)):\n"
        "        continue\n"
        "    check(name, obj)\n"
        "    for key, member in inspect.getmembers(obj, inspect.isroutine):\n"
        "        if inspect.isclass(obj) and (key == '__init__'\n"
        "                or not key.startswith('_')):\n"
        "            check(name + '.' + key, member)\n"
        "print(*bad, sep='\\n', end='')\n"
    )
    assert failures == ""
