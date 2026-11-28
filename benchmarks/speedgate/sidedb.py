# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The database of a side: built by that side's own ``update`` from cached
List files, never downloaded, never from the real cache folder itself."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

from benchmarks.speedgate.runner import CLI_BOOT, Side

CACHE_FILES: Final = ("latest.json", "licenses.json", "popularity.csv")
TARBALL: Final = re.compile(r"spdx-data-v(\d[\w.]*)\.tar\.gz$")
DEAD_PROXY: Final = "http://127.0.0.1:9"


class BuildError(RuntimeError):
    """The side's ``update`` did not build from the cached files."""


def copy_cache(source: Path, dest: Path) -> str:
    """Copy the cached List files (read only) next to the future database;
    the List version of the tarball."""
    dest.mkdir(parents=True, exist_ok=True)
    found = sorted(p for p in source.iterdir() if TARBALL.search(p.name))
    if not found:
        raise BuildError(f"no spdx-data tarball in {source}")
    tarball = found[-1]
    match = TARBALL.search(tarball.name)
    version = match.group(1) if match else ""
    for name in (*CACHE_FILES, tarball.name):
        if (source / name).is_file():
            shutil.copy2(source / name, dest / name)
    return version


def build_database(side: Side, cache: Path) -> str:
    """Build ``side.db`` with the side's ``update`` from the files of *cache*
    (the cache of a real data folder, only read). A dead proxy makes a
    download impossible; the status lines must say the data came from the
    cache. Returns the status text."""
    side.db.parent.mkdir(parents=True, exist_ok=True)
    version = copy_cache(cache, side.db.parent)
    env = side.env()
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env[name] = DEAD_PROXY
    cmd = [
        side.python,
        "-c",
        CLI_BOOT,
        "--db",
        str(side.db),
        "update",
        "--source",
        "upstream",
        "--list",
        f"spdx-license-list@{version}",
    ]
    done = subprocess.run(
        cmd, env=env, cwd=str(side.home), capture_output=True, text=True, check=False
    )
    text = done.stdout + done.stderr
    if done.returncode != 0 or "upstream (cache)" not in text:
        raise BuildError(f"update did not build from the cache:\n{text[-600:]}")
    return text
