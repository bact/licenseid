# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Command line of the speed gate."""

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from benchmarks.speedgate import buildinputs, corpusdir
from benchmarks.speedgate.report import compare_folders
from benchmarks.speedgate.runner import Job, Side
from benchmarks.speedgate.session import ALL_SETS, run_side
from benchmarks.speedgate.sidedb import build_database

if TYPE_CHECKING:
    # pylint: disable-next=protected-access
    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]

CACHE = Path.home() / ".local" / "share" / "licenseid"


def _corpus(args: argparse.Namespace) -> int:
    onecall = json.loads(args.onecall.read_text("utf-8"))
    labels = json.loads(args.labels.read_text("utf-8")) if args.labels else {}
    item68 = json.loads(args.item68.read_text("utf-8")) if args.item68 else []
    manifest = corpusdir.build_corpus(args.folder, labels, onecall, item68)
    print(f"{len(manifest['files'])} files in {args.folder}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    problems = corpusdir.verify(args.folder)
    print("\n".join(problems) or "corpus matches its manifest")
    return 1 if problems else 0


def _inputs(args: argparse.Namespace) -> int:
    coretext = args.side / "src" / "licenseid" / "coretext.py"
    headers = args.headers_tarball or args.tarball
    if not headers.is_file():
        print(f"headers: skipped, {headers} not found")
        headers = None
    built = buildinputs.build_inputs(
        args.folder, args.side / "tests" / "fixtures", args.tarball, coretext, headers
    )
    path = buildinputs.write_inputs(args.folder, built, args.name)
    print(f"{path}: {built['counts']}")
    return 0


def _side(args: argparse.Namespace) -> Side:
    return Side(
        path=args.side.resolve(), db=args.db.resolve(), home=args.home.resolve()
    )


def _db(args: argparse.Namespace) -> int:
    args.home.mkdir(parents=True, exist_ok=True)
    print(build_database(_side(args), args.cache))
    return 0


def _run(args: argparse.Namespace) -> int:
    args.home.mkdir(parents=True, exist_ok=True)
    job = Job(args.inputs, args.out / "scratch", args.runs, args.thread_items)
    run_side(_side(args), job, args.out, args.sets or list(ALL_SETS), args.force)
    return 0


def _compare(args: argparse.Namespace) -> int:
    text, failed = compare_folders(
        args.base, args.candidate, args.twin, args.inputs, args.storage_alone
    )
    print(text)
    return 1 if failed else 0


def _add_corpus_commands(sub: "Subparsers") -> None:
    cor = sub.add_parser("corpus", help="copy the real files and write the manifest")
    cor.add_argument("folder", type=Path)
    cor.add_argument("--onecall", type=Path, required=True, help="JSON of 10 texts")
    cor.add_argument("--labels", type=Path, help="weak labels (JSON by key)")
    cor.add_argument("--item68", type=Path, help="JSON list of item 68's file keys")
    cor.set_defaults(run=_corpus)
    ver = sub.add_parser("verify", help="check a corpus folder against its manifest")
    ver.add_argument("folder", type=Path)
    ver.set_defaults(run=_verify)
    inp = sub.add_parser("inputs", help="write inputs.json into the corpus folder")
    inp.add_argument("folder", type=Path)
    inp.add_argument("--side", type=Path, required=True, help="tree with fixtures")
    inp.add_argument("--tarball", type=Path, required=True, help="List data tarball")
    inp.add_argument(
        "--headers-tarball",
        type=Path,
        help="List data archive of the headers set (default: --tarball)",
    )
    inp.add_argument("--name", default=buildinputs.INPUTS, help="inputs file name")
    inp.set_defaults(run=_inputs)


def _add_side_commands(sub: "Subparsers") -> None:
    db = sub.add_parser("db", help="build a side's database from cached files")
    run = sub.add_parser("run", help="run a side over the sets")
    for cmd in (db, run):
        cmd.add_argument("--side", type=Path, required=True)
        cmd.add_argument("--db", type=Path, required=True)
        cmd.add_argument("--home", type=Path, required=True, help="scratch HOME")
    db.add_argument("--cache", type=Path, default=CACHE, help="read only")
    db.set_defaults(run=_db)
    run.add_argument("--inputs", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--sets", nargs="*", choices=ALL_SETS)
    run.add_argument("--runs", type=int, default=11, help="one-call runs")
    run.add_argument("--thread-items", type=int, default=100)
    run.add_argument("--force", action="store_true")
    run.set_defaults(run=_run)


def parser() -> argparse.ArgumentParser:
    """The parser with its commands."""
    top = argparse.ArgumentParser(prog="python -m benchmarks.speedgate")
    sub = top.add_subparsers(dest="command", required=True)
    _add_corpus_commands(sub)
    _add_side_commands(sub)
    cmp_ = sub.add_parser("compare", help="compare two result folders")
    cmp_.add_argument("base", type=Path)
    cmp_.add_argument("candidate", type=Path)
    cmp_.add_argument("--twin", type=Path, help="a second run of base (A/A)")
    cmp_.add_argument("--inputs", type=Path, help="inputs.json, for the labels")
    cmp_.add_argument(
        "--storage-alone", action="store_true", help="judge: no answer moved"
    )
    cmp_.set_defaults(run=_compare)
    return top


def main(argv: list[str] | None = None) -> int:
    """Run the command; its exit status (``compare``: 1 when a gate fails)."""
    args = parser().parse_args(argv)
    status: int = args.run(args)
    return status


if __name__ == "__main__":
    sys.exit(main())
