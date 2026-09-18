# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Fetching and caching SPDX License List data and GitHub popularity data
from remote sources.

Kept independent of SQLite storage (see database.py): these functions only
read/write plain cache files under a caller-supplied directory and return
parsed data, so they can be reasoned about and tested without a database.
"""

import contextlib
import csv
import importlib
import io
import json
import os
import re
import tarfile
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

LICENSES_JSON_URL = "https://spdx.org/licenses/licenses.json"
POPULARITY_DATA_URL = (
    "https://raw.githubusercontent.com/github/innovationgraph/main/data/licenses.csv"
)
DEFAULT_FALLBACK_VERSION = "3.28.0"

# License list versions become part of a cache file name and a download URL, so
# reject anything that could carry a path separator or URL syntax, whether it
# comes from --version or from a third-party licenses.json.
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

CACHE_LICENSES_JSON = "licenses.json"
CACHE_POPULARITY_CSV = "popularity.csv"
CACHE_SPDX_TARBALL_TEMPLATE = "spdx-data-v{version}.tar.gz"

# Expiration in days
EXPIRY_LICENSES_JSON = 45
EXPIRY_POPULARITY_CSV = 75

# A cache file may look slightly newer than "now" (clock differences on a
# network filesystem); beyond this it is treated as a bad timestamp.
_CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)


def user_agent() -> str:
    """User-Agent that identifies this client to third-party servers, so they
    can contact or rate-limit us instead of an anonymous python-requests.

    Resolved at call time: importing licenseid.__version__ at module level
    would make a cycle (the package __init__ imports database, which imports
    this module).
    """
    version = importlib.import_module("licenseid").__version__
    return f"licenseid/{version} (+https://github.com/bact/licenseid)"


def _http_get(url: str, timeout: int, stream: bool = False) -> requests.Response:
    """GET with an identifying User-Agent, a single attempt, and a timeout.

    Deliberately no retries or backoff loops: a failing third-party server is
    hit once per run, and callers fall back to cached data.
    """
    return requests.get(
        url, headers={"User-Agent": user_agent()}, timeout=timeout, stream=stream
    )


@contextlib.contextmanager
def _atomic_path(path: Path) -> Iterator[Path]:
    """Yield a unique temporary path next to *path*; rename it onto *path* if
    the block succeeds, remove it either way.

    An interrupted write can therefore never leave a truncated file at
    *path* that looks like a valid cache, and concurrent runs cannot
    clobber each other's temporary file.
    """
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        yield tmp_path
        os.replace(tmp_path, path)
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)


def _is_valid_version(version: object) -> bool:
    """True if *version* is a string safe to use in a file name and URL."""
    return isinstance(version, str) and _VERSION_RE.fullmatch(version) is not None


def is_cache_valid(path: Path, days: int) -> bool:
    """Check if the cache file exists and is not older than 'days'.

    A file dated well into the future (clock change, bad timestamp) is not
    valid, or it would never expire.
    """
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime
    return -_CLOCK_SKEW_TOLERANCE <= age < timedelta(days=days)


def _read_licenses_json(path: Path) -> tuple[str | None, str | None]:
    """(licenseListVersion, releaseDate) of a cached licenses.json, or
    (None, None) if it is missing, unreadable, or not a usable object."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):  # incl. JSONDecodeError, UnicodeDecodeError
        return None, None
    if not isinstance(data, dict) or not _is_valid_version(
        data.get("licenseListVersion")
    ):
        return None, None
    return data["licenseListVersion"], data.get("releaseDate")


def _download_licenses_json(path: Path) -> tuple[str | None, str | None]:
    """Download licenses.json and cache it if usable.

    Returns (licenseListVersion, releaseDate), or (None, None) if the
    response has no license list version (and is then not cached). Raises
    requests.RequestException on a network, HTTP or JSON-decoding failure.
    """
    print(f"Fetching latest license list info from {LICENSES_JSON_URL}...")
    resp = _http_get(LICENSES_JSON_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or not _is_valid_version(
        data.get("licenseListVersion")
    ):
        return None, None
    try:
        with _atomic_path(path) as tmp_path, open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        print(f"Warning: Failed to cache license list info: {e}")
    return data["licenseListVersion"], data.get("releaseDate")


def get_version_info(
    cache_dir: Path, version: str | None, use_cache: bool
) -> tuple[str, str | None, str]:
    """Determine target version and fetch version info.

    Returns ``(version, release_date, source)`` where source is ``"cache"``,
    ``"remote"``, ``"stale cache"`` or ``"unavailable"``. Order: a valid
    cache, then one download, then (only if *use_cache*) a stale cache. If
    all fail, an explicit *version* is used as is; otherwise RuntimeError is
    raised.
    """
    if version and not _is_valid_version(version):
        raise RuntimeError(f"Invalid SPDX License List version: {version!r}")
    licenses_json_path = cache_dir / CACHE_LICENSES_JSON

    if use_cache and is_cache_valid(licenses_json_path, EXPIRY_LICENSES_JSON):
        latest_version, release_date = _read_licenses_json(licenses_json_path)
        if latest_version:
            return version or latest_version, release_date, "cache"
        print("Warning: Cached license list info is unusable; fetching it again.")

    try:
        latest_version, release_date = _download_licenses_json(licenses_json_path)
        error = "response has no valid license list version"
    except requests.RequestException as e:
        latest_version, release_date, error = None, None, str(e)
    if latest_version:
        return version or latest_version, release_date, "remote"

    if use_cache:  # --no-cache means never fall back to cached data
        latest_version, release_date = _read_licenses_json(licenses_json_path)
        if latest_version:
            print(f"Warning: Failed to fetch {LICENSES_JSON_URL}: {error}")
            print("Warning: Using stale cached license list info.")
            return version or latest_version, release_date, "stale cache"
    if not version:
        raise RuntimeError(f"Failed to fetch latest license list info: {error}")
    print(f"Warning: Failed to fetch {LICENSES_JSON_URL}: {error}")
    return version, None, "unavailable"


def get_tarball_path(
    cache_dir: Path, version: str, use_cache: bool
) -> tuple[Path, str]:
    """Download or retrieve the SPDX License List tarball path."""
    if not _is_valid_version(version):
        raise RuntimeError(f"Invalid SPDX License List version: {version!r}")
    tar_filename = CACHE_SPDX_TARBALL_TEMPLATE.format(version=version)
    tar_cache_path = cache_dir / tar_filename
    data_source = "remote"

    if not (use_cache and tar_cache_path.exists()):
        tar_url = (
            "https://github.com/spdx/license-list-data/archive/"
            f"refs/tags/v{version}.tar.gz"
        )
        print(f"Downloading release: {tar_url}")
        try:
            resp = _http_get(tar_url, timeout=60, stream=True)
            resp.raise_for_status()
            with _atomic_path(tar_cache_path) as tmp_path, open(tmp_path, "wb") as f:
                f.writelines(resp.iter_content(chunk_size=8192))
        except requests.RequestException as e:
            raise RuntimeError(f"Error downloading {tar_url}: {e}") from e
    else:
        data_source = "cache"

    return tar_cache_path, data_source


def _is_within(root: Path, target: Path) -> bool:
    """True if the resolved *target* is *root* or inside it."""
    return target == root or root in target.parents


def extract_tarball(tar_path: Path, dest: Path) -> None:
    """Extract a downloaded (third-party) tarball, refusing members that
    would land outside *dest* (CWE-22, tarfile path traversal).

    Behaves the same with and without the ``data`` extraction filter (which
    older Pythons lack): leading slashes are stripped, and links are allowed
    only if they stay inside *dest*.
    """
    with tarfile.open(tar_path, "r:gz") as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(path=dest, filter="data")
            return
        # Python < 3.10.12 / 3.11.4 has no extraction filters: check by hand.
        root = dest.resolve()
        for member in tar.getmembers():
            member.name = member.name.lstrip("/" + os.sep)
            if not _is_within(root, (root / member.name).resolve()):
                raise tarfile.TarError(f"unsafe path in tarball: {member.name!r}")
            if member.issym():  # target is relative to the link's directory
                link_target = root / Path(member.name).parent / member.linkname
            elif member.islnk():  # target is relative to the archive root
                link_target = root / member.linkname
            else:
                continue
            if not _is_within(root, link_target.resolve()):
                raise tarfile.TarError(f"unsafe link in tarball: {member.name!r}")
        tar.extractall(path=dest)


def _read_local_csv(path: Path) -> str:
    """Read a local popularity CSV; empty string (with a warning) on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Failed to read local popularity data: {e}")
        return ""


def _download_popularity_csv() -> str:
    """Download the popularity CSV; empty string on failure."""
    print(f"Downloading popularity data: {POPULARITY_DATA_URL}")
    try:
        resp = _http_get(POPULARITY_DATA_URL, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"Warning: Failed to fetch popularity data: {e}")
        return ""


def _write_popularity_cache(path: Path, csv_content: str) -> None:
    """Cache the CSV atomically; a write failure only costs a re-download."""
    try:
        with _atomic_path(path) as tmp_path:
            tmp_path.write_text(csv_content, encoding="utf-8")
    except OSError as e:
        print(f"Warning: Failed to cache popularity data: {e}")


def _parse_count(value: str | None) -> int | None:
    """Parse a pusher count; None if it is missing or not an integer."""
    try:
        return int(value or "")
    except ValueError:
        return None


def _aggregate_popularity(csv_content: str) -> dict[str, int]:
    """Sum pushers per SPDX license ID, skipping blank and NOASSERTION rows.

    A row with a missing or non-numeric count still lists the license, with 0
    pushers; the number of such rows is reported. On a CSV parse error
    nothing is returned, so partial data is never used or cached.
    """
    popularity_map: dict[str, int] = {}
    bad_counts = 0
    try:
        for row in csv.DictReader(io.StringIO(csv_content)):
            spdx_id = row.get("spdx_license")
            if not spdx_id or spdx_id == "NOASSERTION":
                continue
            count = _parse_count(row.get("num_pushers"))
            if count is None:
                bad_counts += 1
                count = 0
            popularity_map[spdx_id] = popularity_map.get(spdx_id, 0) + count
    except (csv.Error, ValueError) as e:
        print(f"Warning: Failed to parse popularity data: {e}")
        return {}

    if bad_counts:
        print(
            f"Warning: {bad_counts} popularity rows have a missing or "
            "non-numeric num_pushers (counted as 0)."
        )
    if popularity_map:
        print(f"Aggregated popularity data for {len(popularity_map)} licenses.")
    return popularity_map


def fetch_popularity_data(
    cache_dir: Path, local_path: Path | None = None, allow_stale: bool = True
) -> tuple[dict[str, int], str]:
    """Fetch and aggregate popularity data from GitHub Innovation Graph.

    Returns ``(popularity_map, source)`` where source is ``"cache"``,
    ``"remote"``, ``"stale cache"`` or ``"unavailable"``. Order: usable
    *local_path* data, then one download (cached only if it parses), then, if
    *allow_stale*, a stale cache file. Every fallback prints a warning.
    """
    local_csv = _read_local_csv(local_path) if local_path else ""
    popularity_map = _aggregate_popularity(local_csv) if local_csv else {}
    if popularity_map:
        return popularity_map, "cache"
    if local_csv:
        print("Warning: Cached popularity data has no usable rows; downloading.")

    cache_path = cache_dir / CACHE_POPULARITY_CSV
    downloaded = _download_popularity_csv()
    popularity_map = _aggregate_popularity(downloaded) if downloaded else {}
    if popularity_map:
        _write_popularity_cache(cache_path, downloaded)
        return popularity_map, "remote"
    if downloaded:
        print("Warning: Downloaded popularity data has no usable rows; not cached.")

    if allow_stale and cache_path.exists():
        print("Warning: Using stale cached popularity data.")
        popularity_map = _aggregate_popularity(_read_local_csv(cache_path))
        if popularity_map:
            return popularity_map, "stale cache"
        print("Warning: Stale cached popularity data has no usable rows.")
    return {}, "unavailable"
