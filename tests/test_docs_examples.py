# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Every example of the user docs that shows a result runs, and gives that
result (roadmap item 57): the console blocks (``$ licenseid ...``), the
``licenseid ...  # result`` lines of a shell block, an output block whose
command its marker names, the Python blocks, the JSON results of
``resolve()`` and the worked examples of resolve-flow.md.

A block that shows a result and cannot run here carries
``<!-- docs-example: skip: <reason> -->`` (a template, a licence text the
fixtures lack). Marker parts, ``;`` between them: ``run: <command>`` (the
command of an output block), ``head`` (the block shows the first lines),
``shape: <expression>`` (the block is the shape of a Python value).

Commands run in process on the long-text fixtures, copied to the default
database path (List 3.29.0, as the docs say); ``resolve`` reads the database of
the fixture bundle (``--db``), which holds every ID of the List."""
# pylint: disable=missing-function-docstring

import ast
import json
import re
import shlex
import shutil
import sqlite3
import warnings
from contextlib import closing
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from docs_blocks import (
    DOCS,
    Block,
    blocks,
    commands,
    directives,
    json_like,
    marker_above,
    pages,
    python_steps,
    section,
    table,
    unticked,
)
from long_text_db import DB_PATH, LONG_TEXTS, long_text_detector
from packaged_list import fixture_bundle
from release_fakes import ship

import licenseid
from licenseid import LicenseDatabase, get_default_db_path, json_line, resolve
from licenseid.cli import cli

pytestmark = pytest.mark.terse_cli

#: The home directory the docs show.
SHOWN_DB = "/home/me/.local/share/licenseid/licenses.db"
#: ``licenseid ...  # result``, piped from ``echo "..." |`` or not; a line
#: with any other pipe is not run.
_RESULT_LINE = re.compile(
    r"^(?:echo \"(?P<stdin>[^\"]*)\" \| )?"
    r"(?P<cmd>licenseid [^|#]*?)\s{2,}# (?P<want>.+)$"
)


def kind_of(block: Block) -> str:
    """How the runner treats a block (``ignored``: it shows no result)."""
    parts = directives(block.marker) if block.marker else {}
    for key in ("skip", "run", "shape"):
        if key in parts:
            return {"skip": "skipped", "run": "output", "shape": "shape"}[key]
    if block.lang in {"mermaid", "bibtex"}:
        return "ignored"
    if block.lang in {"python", "json"}:
        return block.lang
    if block.body and block.body[0].startswith("$ "):
        return "console"
    if block.lang == "bash":
        return "lines" if any(_RESULT_LINE.match(x) for x in block.body) else "ignored"
    return "unknown"


BLOCKS = [b for page in pages() for b in blocks(page)]


def _of(kind: str) -> list[Block]:
    return [b for b in BLOCKS if kind_of(b) == kind]


@pytest.fixture(name="long_text_file", scope="session")
def _long_text_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The long-text database as a file, its List version as the docs show it
    (a copy: the shared original serves other tests)."""
    long_text_detector()
    path = tmp_path_factory.mktemp("docs_db") / "licenses.db"
    with (
        closing(sqlite3.connect(DB_PATH, uri=True)) as source,
        closing(sqlite3.connect(path)) as copy,
    ):
        source.backup(copy)
        copy.execute(
            "UPDATE db_metadata SET value = '3.29.0' WHERE key = 'license_list_version'"
        )
        copy.commit()
    return path


@pytest.fixture(name="env")
def _env(
    long_text_file: Path,
    bundle_db: LicenseDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """A working directory with ``LICENSE`` and ``LICENSE.txt`` (Apache-2.0),
    the long-text database at the default path and the fixture bundle
    shipped. Returns the paths the runner needs."""
    work = tmp_path / "work"
    work.mkdir()
    apache = json.loads((LONG_TEXTS / "Apache-2.0.json").read_text(encoding="utf-8"))
    for name in ("LICENSE", "LICENSE.txt"):  # bytes: the same file on Windows
        (work / name).write_bytes(apache["license_text"].encode("utf-8"))
    monkeypatch.chdir(work)
    default = Path(get_default_db_path())
    default.parent.mkdir(parents=True)
    shutil.copyfile(long_text_file, default)
    ship(monkeypatch, fixture_bundle())
    return {"default": str(default), "bundle": str(bundle_db.db_path)}


def run(
    command: str, env: dict[str, str], stdin: str | None = None
) -> tuple[int, list[str], list[str]]:
    """Exit code, standard output and standard error lines of *command* as
    the docs write it, the default database path shown as the docs show it."""
    args = shlex.split(command)
    assert args[0] == "licenseid", command
    args = args[1:]
    if args[0] == "resolve":
        args = ["--db", env["bundle"], *args]
    if args[0] == "update":  # the docs show a first update
        Path(env["default"]).unlink()
    result = CliRunner().invoke(cli, args, input=stdin)

    def shown(text: str) -> list[str]:
        for path in (env["default"], env["default"].replace("\\", "\\\\")):
            text = text.replace(path, SHOWN_DB)
        return text.splitlines()

    return result.exit_code, shown(result.stdout), shown(result.stderr)


def expected_exit(lines: list[str]) -> int:
    """1 for no answer (an empty line, an empty ``EXPRESSION``) or an empty
    flag (the last field of a predicate), else 0."""
    first = lines[0] if lines else ""
    fields = dict(f.partition("=")[::2] for f in first.split("\t"))
    flag = [v for k, v in fields.items() if k.startswith("IS_")]
    return 1 if not first or fields.get("EXPRESSION") == "" or flag == [""] else 0


@pytest.mark.parametrize("block", _of("console"), ids=lambda b: b.label)
def test_a_console_block_prints_what_it_shows(
    block: Block, env: dict[str, str]
) -> None:
    for command, want in commands(block.body):
        code, out, err = run(command, env)
        assert out == want, f"{block.label}: $ {command}\n{err}"
        assert code == expected_exit(want), f"{block.label}: $ {command}"


@pytest.mark.parametrize("block", _of("output"), ids=lambda b: b.label)
def test_an_output_block_is_what_its_command_prints(
    block: Block, env: dict[str, str]
) -> None:
    parts = directives(str(block.marker))
    if "filled" in parts:  # the copyright line of LICENSE filled in
        license_file = Path("LICENSE")
        text = license_file.read_text(encoding="utf-8")
        filled = text.replace("[yyyy] [name of copyright owner]", parts["filled"])
        license_file.write_bytes(filled.encode("utf-8"))
    code, out, err = run(parts["run"], env)
    got = out + err if block.lang == "diff" else out
    want = list(block.body)
    if "head" in parts:
        got = got[: len(want)]
    assert got == want, f"{block.label}: {parts['run']}"
    assert code == expected_exit(want), block.label


@pytest.mark.parametrize("block", _of("lines"), ids=lambda b: b.label)
def test_a_result_line_gives_its_result(block: Block, env: dict[str, str]) -> None:
    lines = [m for line in block.body if (m := _RESULT_LINE.match(line))]
    for found in lines:
        stdin = None if found["stdin"] is None else found["stdin"] + "\n"
        _, out, _ = run(found["cmd"], env, stdin)
        want = found["want"].split(",")[0].strip()
        assert out == [want], f"{block.label}: {found['cmd']}"


def _run_code(source: str, namespace: dict[str, object], value: bool) -> object:
    """Run a statement, or give the value of an expression, of a block of the
    docs: code of this repository, run as a test runs its own. Warnings are
    left out (also pytest's error filter): the blocks do not say which they
    give."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if value:
            return eval(source, namespace)  # pylint: disable=eval-used
        exec(source, namespace)  # noqa: S102  # pylint: disable=exec-used
    return None


@pytest.mark.parametrize("block", _of("python"), ids=lambda b: b.label)
def test_a_python_block_runs_and_gives_what_it_says(
    block: Block, env: dict[str, str]
) -> None:
    assert env
    namespace: dict[str, object] = {}
    for step in python_steps("\n".join(block.body)):
        got = _run_code(step.source, namespace, step.is_expression)
        if step.has_want:
            assert got == step.want, f"{block.label}+{step.line}: {step.source}"


@pytest.mark.parametrize("block", _of("shape"), ids=lambda b: b.label)
def test_a_shape_block_has_the_shape_of_its_value(
    block: Block, env: dict[str, str]
) -> None:
    assert env
    expression = directives(str(block.marker))["shape"]
    got = _run_code(expression, {"licenseid": licenseid}, True)
    want = ast.literal_eval("\n".join(block.body))
    assert not json_like(want, got), f"{block.label}: {json_like(want, got)}"


@pytest.mark.parametrize("block", _of("json"), ids=lambda b: b.label)
def test_a_json_result_is_what_resolve_gives(
    block: Block, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``resolve()`` of the block's ``input`` with no database file: the
    List shipped in the wheel is read (``source: packaged``)."""
    ship(monkeypatch, fixture_bundle())
    want = json.loads("\n".join(block.body))
    got = json.loads(json_line(resolve(want["input"])))
    assert not json_like(want, got), f"{block.label}: {json_like(want, got)}"


#: The worked examples of resolve-flow.md, each run on the List of the
#: fixture bundle: the expression, category, step kinds (with each detail and
#: "not applied" the row names), the reason and the candidates.
WORKED = table(section(DOCS / "resolve-flow.md", "## Worked examples"), "Value")
_STEP = re.compile(r"`(\w+)`(?: \(detail `([^`]*)`\))?( \(not applied\))?")


def _shown_steps(cell: str) -> list[tuple[str, str | None, bool]]:
    head = re.split(r"\b(?:reason|candidates) `", cell)[0]
    return [(k, d or None, not off) for k, d, off in _STEP.findall(head)]


def _named(cell: str, word: str) -> list[str]:
    found = re.search(rf"\b{word} ((?:`[^`]*`(?:, )?)+)", cell)
    return re.findall(r"`([^`]*)`", found.group(1)) if found else []


@pytest.mark.parametrize("row", WORKED, ids=lambda r: r["Value"][:40])
def test_a_worked_example_gives_what_its_row_shows(
    row: dict[str, str], bundle_db: LicenseDatabase
) -> None:
    got = resolve(unticked(row["Value"]), bundle_db)
    expression = None if row["Expression"] == "none" else unticked(row["Expression"])
    assert (got["expression"], got["category"]) == (expression, row["Category"])
    steps = [*got["steps"], *got["expansions"]]
    shown = _shown_steps(row["Steps"])
    kinds = [(s["kind"], s["applied"]) for s in steps]
    assert kinds == [(kind, applied) for kind, _, applied in shown], (
        f"resolve-flow.md {row['Value']}: steps (kind, applied) {kinds}"
    )
    details = [(s["detail"], d) for s, (_, d, _) in zip(steps, shown) if d]
    assert all(got_detail == d for got_detail, d in details), (
        f"resolve-flow.md {row['Value']}: (detail, shown) {details}"
    )
    assert _named(row["Steps"], "reason") == ([got["reason"]] if got["reason"] else [])
    assert _named(row["Steps"], "candidates") == got["candidates"]


#: The blocks of each page by kind: a new block needs a decision (run it, or
#: mark it), and a runner that stops finding blocks fails here.
COUNTS = {
    "README.md": {"console": 1, "ignored": 4, "lines": 1, "python": 1},
    "docs/cli.md": {"console": 4, "ignored": 4, "output": 1},
    "docs/development.md": {"ignored": 4},
    "docs/expression-canonicalisation.md": {"python": 1},
    "docs/installation.md": {"ignored": 3},
    "docs/output.md": {
        "console": 2,
        "ignored": 2,
        "lines": 1,
        "output": 3,
        "skipped": 3,
    },
    "docs/python-api.md": {"python": 3, "skipped": 2, "shape": 1},
    "docs/resolve-flow.md": {"ignored": 2, "skipped": 1},
    "docs/resolve.md": {"json": 3, "skipped": 1},
}


def test_a_warning_in_a_run_block_does_not_raise() -> None:
    """The error filter of ``filterwarnings`` would fail a block that warns."""
    source = (
        "import warnings\n"
        "warnings.warn(licenseid.warning.LicenseIdWarning('input', 'x'))"
    )
    namespace: dict[str, object] = {"licenseid": licenseid}
    assert _run_code(source, namespace, False) is None


def test_each_block_is_run_or_marked() -> None:
    unknown = [b.label for b in BLOCKS if kind_of(b) == "unknown"]
    assert not unknown, (
        f"blocks that show a result with no command: {unknown}; add"
        " <!-- docs-example: run: <command> --> or <!-- docs-example: skip: <why> -->"
    )
    got: dict[str, dict[str, int]] = {}
    for block in BLOCKS:
        kinds = got.setdefault(block.page, {})
        kinds[kind_of(block)] = kinds.get(kind_of(block), 0) + 1
    assert got == COUNTS, "a block was added, removed or read otherwise: COUNTS"


def test_the_runner_reads_what_the_blocks_assert() -> None:
    """Guard: the values the Python blocks state, the result lines and the
    rows of worked examples the runner checks."""
    stated = [
        step
        for block in _of("python")
        for step in python_steps("\n".join(block.body))
        if step.has_want
    ]
    lines = [x for b in _of("lines") for x in b.body if _RESULT_LINE.match(x)]
    assert (len(stated), len(lines), len(WORKED)) == (7, 5, 33)


def test_a_marker_indented_in_a_list_item_is_found() -> None:
    lines = [
        "- item",
        "",
        "  <!-- docs-example: skip: a template -->",
        "  <!-- markdownlint-disable MD013 -->",
        "",
        "  ```text",
    ]
    assert marker_above(lines, 5) == "skip: a template"
