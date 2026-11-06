# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The sampling frame: which packages a sample holds and why, kept apart
from what was fetched for them, so a study can name its population, fetch
the same packages again and say which replies changed.

A frame file is JSON Lines: a first line ``{"frame": {...}}`` with the
criteria (channel, registry, ranking, count, when and from where it was
taken), then one package a line (rank, name, the pinned version, the
ranking figures). A sample file has one line a package of the frame, its
values and each reply it read (URL, SHA-256, or ``null`` when there was
none, and ``error`` for a reply that failed), all at the pinned version, so a
later fetch reads the same documents.
"""

import datetime
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from tools.licence_sample.channels import ECOSYSTEMS_URL, READERS, REGISTRIES

Package = dict[str, Any]
Get = Callable[[str], bytes | None]

#: The version of the frame and sample files' shape.
FORMAT: Final = 1
#: What the frame states it is, for the methods of a study.
POPULATION: Final = (
    "packages of {registry} indexed by ecosyste.ms, ranked by {sort}"
    " (descending), top {count}; each at the latest release ecosyste.ms lists"
)


class FrameError(ValueError):
    """A file that is no frame of this format."""


class FetchError(OSError):
    """A reply that could not be read (not a 404 or 410: the document may
    exist), so a package is not recorded as having no licence."""


def now() -> str:
    """The time, UTC, to the second."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def criteria(channel: str, count: int, taken: str) -> dict[str, Any]:
    """The header of a frame of the top *count* packages of *channel*."""
    registry, sort = REGISTRIES[channel]
    return {
        "format": FORMAT,
        "channel": channel,
        "registry": registry,
        "ranking": sort,
        "count": count,
        "taken": taken,
        "source": ECOSYSTEMS_URL.format(registry=registry, sort=sort, page="N"),
        "population": POPULATION.format(registry=registry, sort=sort, count=count),
    }


def rank(channel: str, count: int, get: Get) -> list[Package]:
    """The top *count* packages of *channel*, ranked by ecosyste.ms: rank,
    name, the pinned version, the ranking figures and the value it lists.

    Only an empty page ends the ranking early (the registry has fewer
    packages); a page that fails raises :class:`FrameError`, so a frame never
    holds fewer packages than its header states without saying so."""
    registry, sort = REGISTRIES[channel]
    packages: list[Package] = []
    page = 1
    while len(packages) < count:
        url = ECOSYSTEMS_URL.format(registry=registry, sort=sort, page=page)
        raw = get(url)
        try:
            rows = json.loads(raw) if raw is not None else None
        except ValueError:
            rows = None
        if not isinstance(rows, list):
            raise FrameError(f"{url}: no ranking page, {len(packages)} packages read")
        if not rows:
            break
        packages += [
            {
                "name": row.get("name"),
                "version": row.get("latest_release_number") or "",
                "downloads": row.get("downloads"),
                "downloads_period": row.get("downloads_period"),
                "dependents": row.get("dependent_packages_count"),
                "listed": row.get("licenses"),
            }
            for row in rows
            if isinstance(row, dict)
        ]
        page += 1
    return [{"rank": n, **p} for n, p in enumerate(packages[:count], 1)]


def write_frame(path: Path, header: dict[str, Any], packages: list[Package]) -> None:
    """Write a frame file: *header*, then one package a line."""
    lines = [json.dumps({"frame": header}, ensure_ascii=False)]
    lines += [json.dumps(p, ensure_ascii=False) for p in packages]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_frame(path: Path) -> tuple[dict[str, Any], list[Package]]:
    """The header and packages of a frame file. Raises :class:`FrameError`
    for a file that is no frame."""
    lines = [line for line in path.read_text("utf-8").splitlines() if line.strip()]
    first = json.loads(lines[0]) if lines else None
    if not isinstance(first, dict) or not isinstance(first.get("frame"), dict):
        raise FrameError(f"{path}: no frame header on the first line")
    if first["frame"].get("format") != FORMAT:
        raise FrameError(f"{path}: frame format {first['frame'].get('format')}")
    return first["frame"], [json.loads(line) for line in lines[1:]]


def cut(
    header: dict[str, Any], packages: list[Package], count: int
) -> tuple[dict[str, Any], list[Package]]:
    """The frame of the top *count* packages of a larger frame: the same
    criteria, with the count and population of the cut and the count it was
    cut from (``cut_from``). Raises :class:`FrameError` when the frame holds
    fewer than *count* packages, or does not rank them 1 to *count*."""
    kept = [p for p in packages if p.get("rank", 0) <= count]
    if sorted(p.get("rank", 0) for p in kept) != list(range(1, count + 1)):
        raise FrameError(f"frame holds no ranks 1 to {count}")
    registry, sort = REGISTRIES[header["channel"]]
    smaller = {
        **header,
        "count": count,
        "population": POPULATION.format(registry=registry, sort=sort, count=count),
        "cut_from": header["count"],
    }
    return smaller, kept


def read_package(channel: str, package: Package, get: Get) -> Package:
    """*package* with its values and the replies they were read from."""
    replies: list[dict[str, str | None]] = []

    def recorded(url: str) -> bytes | None:
        try:
            body = get(url)
        except FetchError as exc:
            replies.append({"url": url, "sha256": None, "error": str(exc)})
            return None
        digest = None if body is None else hashlib.sha256(body).hexdigest()
        replies.append({"url": url, "sha256": digest})
        return body

    reader = READERS[channel]
    args: list[Any] = [package["name"], package["version"], recorded]
    if channel == "cargo":
        args.append(package.get("listed"))
    values = reader(*args)
    return {
        "channel": channel,
        "rank": package["rank"],
        "name": package["name"],
        "version": package["version"],
        "fetched": now(),
        "replies": replies,
        "values": values,
    }
