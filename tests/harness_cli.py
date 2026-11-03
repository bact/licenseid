# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Every CLI command run on a fixed set of inputs (the CLI golden and the
invariants over it). Each case runs twice, as text and with ``--json``; its
record keeps the exit status and both streams, with the scratch paths named.
No network: the SPDX bundle shipped in the wheel is a fake, ``requests.get``
fails."""

import json
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

import pytest
import requests
from click.testing import CliRunner
from packaged_list import database_of, fixture_bundle
from release_fakes import release_bundle, ship

from licenseid import __version__
from licenseid.cli import cli
from licenseid.result import json_line


class Case(NamedTuple):
    """One command line. ``db`` is ``list`` (a ready database of the fixtures'
    List), ``release`` (a ready database of the one-licence release), ``fresh``
    (a path with no file), ``cache`` (a ``list`` database with a cache file
    beside it) or ``none`` (no ``--db``: ``resolve`` reads the
    shipped List). ``wheel`` is the bundle the wheel ships: ``list``,
    ``release`` (one licence) or ``none``."""

    name: str
    db: str
    args: tuple[str, ...]
    stdin: str = ""
    wheel: str = "list"


def _c(name: str, db: str, *args: str, stdin: str = "", wheel: str = "list") -> Case:
    return Case(name, db, args, stdin, wheel)


DETECT = [
    _c("detect-id", "list", "detect", "MIT"),
    _c("detect-id-deprecated", "list", "detect", "GPL-2.0"),
    _c("detect-name", "list", "detect", "Apache License 2.0"),
    _c("detect-flag-id", "list", "detect", "--id", "Apache-2.0"),
    _c("detect-flag-id-plus", "list", "detect", "--id", "GPL-2.0+"),
    _c("detect-flag-id-unknown", "list", "detect", "--id", "No-Such-1.0"),
    _c("detect-flag-id-compound", "list", "detect", "--id", "MIT OR ISC"),
    _c("detect-text", "list", "detect", "--text", "The text of MIT License."),
    _c("detect-text-no-answer", "list", "detect", "--text", "lorem ipsum dolor"),
    _c("detect-tag", "list", "detect", "--text", "SPDX-License-Identifier: MIT OR ISC"),
    _c("detect-tag-or-later", "list", "detect", "--text", "GPL-2.0 or later"),
    _c("detect-top-three", "list", "detect", "--top", "3", "--threshold", "0", "MIT"),
    _c("detect-id-only", "list", "detect", "--id-only", "MIT"),
    _c("detect-stdin", "list", "detect", "-", stdin="Apache-2.0\n"),
    _c("detect-no-input", "list", "detect"),
    _c("detect-two-inputs", "list", "detect", "MIT", "--text", "x"),
    _c("detect-unknown-option", "list", "detect", "--jsn", "MIT"),
    _c("detect-missing-file", "list", "detect", "no-such-file.txt"),
    _c("detect-missing-db", "fresh", "detect", "MIT"),
    _c("detect-unreadable-text", "list", "detect", "--text", "café \U0001f600"),
]
MATCH = [
    _c("resolve-id", "none", "resolve", "MIT"),
    _c("resolve-plus-or", "none", "resolve", "GPLv2+ or MIT"),
    _c("resolve-prose", "none", "resolve", "BSD 3-Clause License"),
    _c("resolve-trove", "none", "resolve", "License :: OSI Approved :: MIT License"),
    _c("resolve-deprecated", "none", "resolve", "GPL-3.0"),
    _c("resolve-semicolon", "none", "resolve", "MIT ; Apache 2"),
    _c("resolve-end-mark", "none", "resolve", "Apache 2.0?"),
    _c("resolve-quotes", "none", "resolve", "“MIT”"),
    _c("resolve-tab", "none", "resolve", "MIT\tOR ISC"),
    _c("resolve-unicode", "none", "resolve", "“MIT” \\ café \U0001f600"),
    _c("resolve-unknown", "none", "resolve", "No-Such-1.0"),
    _c("resolve-empty", "none", "resolve", ""),
    _c("resolve-line-break", "none", "resolve", "line\nbreak"),
    _c("resolve-stdin", "none", "resolve", "-", stdin="Apache-2.0\n"),
    _c("resolve-no-input", "none", "resolve"),
    _c("resolve-no-list", "none", "resolve", "MIT", wheel="none"),
]
FLAGS = [
    _c(f"{cmd}-{name}", "list", cmd, *args)
    for cmd in ("is-osi", "is-fsf", "is-spdx")
    for name, args in (
        ("id", ("MIT",)),
        ("flag-id", ("--id", "GPL-3.0-only")),
        ("unknown", ("--id", "No-Such-1.0")),
    )
]
UPDATE = [
    _c("update-packaged", "fresh", "update", "--source", "packaged", wheel="release"),
    _c("update-current", "release", "update", "--source", "packaged", wheel="release"),
    _c(
        "update-force",
        "release",
        "update",
        "--source",
        "packaged",
        "--force",
        wheel="release",
    ),
    _c("update-offline", "fresh", "update", wheel="release"),
    _c("update-cache", "cache", "update", "--source", "packaged", wheel="release"),
    _c("update-bad-source", "fresh", "update", "--source", "nowhere"),
    _c("clear-cache-found", "cache", "clear-cache"),
    _c("clear-cache-none", "fresh", "clear-cache"),
]
CASES = [*DETECT, *MATCH, *FLAGS, *UPDATE]


class Record(NamedTuple):
    """What one run of a case printed."""

    case: str
    mode: str
    exit: int
    stdout: str
    stderr: str


def _down(*_: object, **__: object) -> None:
    raise requests.ConnectionError("down")


@contextmanager
def cli_env(base: Path) -> Iterator["CliEnv"]:
    """The scratch home, the fake wheel bundle and a network that is down,
    for the cases run inside."""
    with pytest.MonkeyPatch.context() as patch:
        home = base / "home"
        home.mkdir()
        patch.setenv("HOME", str(home))
        patch.setenv("USERPROFILE", str(home))
        patch.setattr(Path, "home", staticmethod(lambda: home))
        patch.setattr(requests, "get", _down)
        yield CliEnv(base, patch)


class CliEnv:
    """Runs cases under *base*. The ``list`` and ``release`` databases are
    built once and copied for a case that writes."""

    def __init__(self, base: Path, patch: pytest.MonkeyPatch) -> None:
        self.base, self.patch = base, patch
        self._made: dict[str, Path] = {}
        self._count = 0

    def _template(self, kind: str) -> Path:
        if kind not in self._made:
            raw = release_bundle() if kind == "release" else fixture_bundle()
            self._made[kind] = self.base / f"template-{kind}.db"
            database_of(raw, self._made[kind])
        return self._made[kind]

    def _database(self, kind: str) -> str:
        """The ``--db`` path of a case: a copy of a template where the
        command writes (``release``, ``cache``), the ``list`` one itself."""
        if kind == "list":
            return str(self._template("list"))
        self._count += 1
        folder = self.base / f"case-{self._count}"
        folder.mkdir()
        path = folder / "licenses.db"
        if kind in ("release", "cache"):
            template = "release" if kind == "release" else "list"
            shutil.copyfile(self._template(template), path)
        if kind == "cache":
            (folder / "popularity.csv").write_text("x\n", encoding="utf-8")
        return str(path)

    def run(self, case: Case) -> list[Record]:
        """The text run and the ``--json`` run of *case*."""
        records = []
        bundle = {"list": fixture_bundle, "release": release_bundle}.get(case.wheel)
        command, *rest = case.args
        for mode in ("text", "json"):
            db = self._database(case.db)
            ship(self.patch, bundle() if bundle else None)
            where = ["--db", db] if case.db != "none" else []
            flags = ["--json"] if mode == "json" else []
            result = CliRunner().invoke(
                cli, [*where, command, *flags, *rest], input=case.stdin or None
            )
            records.append(
                Record(
                    case.name,
                    mode,
                    result.exit_code,
                    self._scrub(result.stdout_bytes.decode("utf-8"), db),
                    self._scrub(result.stderr_bytes.decode("utf-8"), db),
                )
            )
        return records

    def _scrub(self, text: str, db: str) -> str:
        """*text* with the database and scratch paths named, as typed and as
        the output escapes a backslash, and the package version named, so a
        version bump moves no golden record."""
        for path, name in ((db, "<DB>"), (str(self.base), "<TMP>")):
            for form in (path, path.replace("\\", "\\\\")):
                text = text.replace(form, name)
        return slash_the_tails(text).replace(__version__, "<VERSION>")


_PATH_TAIL = re.compile(r"<(?:DB|TMP)>[^\s;'\"]*")


def slash_the_tails(text: str) -> str:
    """*text* with the rest of each named path (``<TMP>\\home\\x``) written
    with ``/``, the escaped backslash too: one form on every platform."""
    return _PATH_TAIL.sub(lambda m: re.sub(r"\\+", "/", m.group()), text)


def record_line(record: Record) -> str:
    """The record as one JCS line, the form of the golden file."""
    return json_line(record._asdict())


def read_record(line: str) -> Record:
    """The record a golden line holds."""
    return Record(**json.loads(line))
