# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Sample the licence values of six package channels (PyPI, npm, crates.io,
Maven Central, NuGet, Hugging Face) and count what ``licenseid.resolve()``
reads, URLs apart. Run as ``python -m tools.licence_sample``:

``rank``
    The frame: the top packages of a channel by ecosyste.ms (downloads;
    dependents for Maven Central), each at its pinned version, with the
    criteria on the first line (``frame.py``). Network.

``fetch``
    Each package of a frame: its licence values, read from the channel's
    own registry at the pinned version, and the URL and SHA-256 of each
    reply, one JSON object a package. Network.

``cut``
    The top N of a frame and of its sample, as a frame and sample of their
    own (``cut_from`` in the header), so a smaller study can start from a
    run that stopped or that was larger. No network.

``analyze``
    For each channel: how many packages state a value, in which fields, the
    category ``resolve()`` gives each value, and of the values that are one
    URL, how many the List's ``seeAlso`` names (one licence or several) and
    the hosts of the rest. Needs a List file (``--list``: an SPDX
    ``license-list-data`` tarball or its ``licenses.json``); no network.

Standard library and ``licenseid`` only. See ``README.md`` here.
"""

import argparse
import collections
import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from tools.licence_sample.channels import CHANNELS
from tools.licence_sample.frame import (
    FetchError,
    FrameError,
    criteria,
    cut,
    now,
    rank,
    read_frame,
    read_package,
    write_frame,
)
from tools.licence_sample.urls import host_of, is_url, see_also, url_key

if TYPE_CHECKING:
    from licenseid.listsource import GivenDatabase

#: Names the sampler to the registries' operators; no personal address.
USER_AGENT: Final = "licenseid-research (https://github.com/bact/licenseid)"
THREADS: Final = 8
RETRIES: Final = 3
#: A value longer than this, or on several lines, is licence text.
MAX_VALUE_LENGTH: Final = 200

Package = dict[str, Any]


def get(url: str) -> bytes | None:
    """The body at *url*, None for a 404 or 410. Raises :class:`FetchError`
    after :data:`RETRIES` failures."""
    reason = "no attempt"
    for attempt in range(RETRIES):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return None
            reason = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise FetchError(reason)


def rank_command(channel: str, count: int, out: Path) -> None:
    """Write the frame of the top *count* packages of *channel*."""
    taken = now()
    packages = rank(channel, count, get)
    write_frame(out, criteria(channel, count, taken), packages)
    print(f"{channel}: {len(packages)} packages in the frame", file=sys.stderr)


def fetch(frame_path: Path, out: Path) -> None:
    """Write the licence values of every package of the frame at *frame_path*."""
    header, packages = read_frame(frame_path)
    channel = header["channel"]
    with (
        concurrent.futures.ThreadPoolExecutor(THREADS) as pool,
        out.open("w", encoding="utf-8") as handle,
    ):
        read = pool.map(lambda p: read_package(channel, p, get), packages)
        failed = 0
        for done, package in enumerate(read, 1):
            failed += failed_reply(package)
            handle.write(json.dumps(package, ensure_ascii=False) + "\n")
            if done % 200 == 0:
                print(
                    f"{channel}: {done} of {len(packages)}", file=sys.stderr, flush=True
                )
    if failed:
        print(
            f"WARNING: {channel}: {failed} packages with a failed reply",
            file=sys.stderr,
        )


def failed_reply(package: Package) -> bool:
    """Whether a reply of *package* failed: its values are not known."""
    return any("error" in reply for reply in package.get("replies", []))


def cut_command(paths: tuple[Path, Path], count: int, outs: tuple[Path, Path]) -> None:
    """Write the top *count* of the frame and sample *paths* to *outs*.
    Raises :class:`FrameError` when the sample lacks a package of the cut."""
    header, packages = read_frame(paths[0])
    smaller, kept = cut(header, packages, count)
    read: dict[int, str] = {}
    for line in paths[1].read_text("utf-8").splitlines():
        if line.strip() and (rank_of := json.loads(line).get("rank", 0)) <= count:
            read[rank_of] = line
    if sorted(read) != list(range(1, count + 1)):
        raise FrameError(f"{paths[1]}: no ranks 1 to {count}")
    write_frame(outs[0], smaller, kept)
    outs[1].write_text("".join(read[n] + "\n" for n in sorted(read)), "utf-8")
    print(f"{header['channel']}: top {count} of {header['count']}", file=sys.stderr)


def short(value: str) -> bool:
    """Whether *value* is a declared value, not licence text."""
    return len(value) <= MAX_VALUE_LENGTH and "\n" not in value.strip()


def tally(
    packages: list[Package],
    table: dict[str, set[str]],
    db: "GivenDatabase | None" = None,
) -> dict[str, Any]:
    """The counts :func:`analyze` prints for one channel's *packages*, each
    value resolved on *db* (``resolve()``'s default list when None)."""
    from licenseid import resolve  # pylint: disable=import-outside-toplevel

    counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for package in packages:
        values = [v for v in package.get("values", []) if short(v["value"])]
        if failed_reply(package):
            counts["packages"]["failed"] += 1
            continue
        counts["packages"]["with a value" if values else "none"] += 1
        if any(is_url(v["value"]) for v in values):
            counts["packages stating a URL"]["with a URL"] += 1
        for item in values:
            value = item["value"]
            counts["fields"][item["field"]] += 1
            if not is_url(value):
                category = resolve(value, db)["category"]
                counts["categories"][category] += 1
                if category == "unresolved":
                    counts["unresolved values"][value] += 1
                continue
            key = url_key(value) or ""
            listed = table.get(key, set())
            kind = (
                "one licence" if len(listed) == 1 else "several" if listed else "none"
            )
            counts["urls"][kind] += 1
            if not listed:
                counts["unlisted hosts"][host_of(value)] += 1
                counts["unlisted urls"][key] += 1
            elif len(listed) > 1:
                counts["shared urls"][key + " " + ",".join(sorted(listed))] += 1
    return counts


def analyze(
    paths: list[Path], list_path: Path, top: int, db_path: Path | None = None
) -> None:
    """Print :func:`tally` of each channel in the sample files *paths*,
    resolved on the database at *db_path* (the default list when None)."""
    table = see_also(list_path)
    by_channel: dict[str, list[Package]] = collections.defaultdict(list)
    for path in paths:
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                package = json.loads(line)
                by_channel[package["channel"]].append(package)
    for channel in CHANNELS:
        if channel not in by_channel:
            continue
        print(f"\n== {channel}: {len(by_channel[channel])} packages")
        for name, counter in tally(by_channel[channel], table, db_path).items():
            total = sum(counter.values())
            print(f"  {name} ({total}):")
            for key, number in counter.most_common(top):
                print(f"    {number:6} {number / total:6.1%}  {key}")


def main(argv: list[str] | None = None) -> int:
    """Run a command; 0 when done, 1 for a frame that cannot be made."""
    parser = argparse.ArgumentParser(prog="python -m tools.licence_sample")
    commands = parser.add_subparsers(dest="command", required=True)
    ranking = commands.add_parser("rank", help="write one channel's frame")
    ranking.add_argument("channel", choices=CHANNELS)
    ranking.add_argument("--count", type=int, default=1000)
    ranking.add_argument("--out", type=Path, required=True)
    fetching = commands.add_parser("fetch", help="read the values of a frame")
    fetching.add_argument("frame", type=Path)
    fetching.add_argument("--out", type=Path, required=True)
    cutting = commands.add_parser("cut", help="the top N of a frame and sample")
    cutting.add_argument("frame", type=Path)
    cutting.add_argument("sample", type=Path)
    cutting.add_argument("--count", type=int, required=True)
    cutting.add_argument("--out-frame", type=Path, required=True)
    cutting.add_argument("--out-sample", type=Path, required=True)
    analysing = commands.add_parser("analyze", help="count what resolve() reads")
    analysing.add_argument("samples", type=Path, nargs="+")
    analysing.add_argument("--list", type=Path, required=True, dest="list_path")
    analysing.add_argument("--top", type=int, default=15)
    analysing.add_argument("--db", type=Path, dest="db_path")
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except FrameError as exc:
        print(f"ERROR: frame: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.command == "rank":
        rank_command(args.channel, args.count, args.out)
    elif args.command == "fetch":
        fetch(args.frame, args.out)
    elif args.command == "cut":
        cut_command(
            (args.frame, args.sample), args.count, (args.out_frame, args.out_sample)
        )
    else:
        analyze(args.samples, args.list_path, args.top, args.db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
