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

import csv
import importlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

LICENSES_JSON_URL = "https://spdx.org/licenses/licenses.json"
POPULARITY_DATA_URL = (
    "https://raw.githubusercontent.com/github/innovationgraph/main/data/licenses.csv"
)
DEFAULT_FALLBACK_VERSION = "3.28.0"

CACHE_LICENSES_JSON = "licenses.json"
CACHE_POPULARITY_CSV = "popularity.csv"
CACHE_SPDX_TARBALL_TEMPLATE = "spdx-data-v{version}.tar.gz"

# Expiration in days
EXPIRY_LICENSES_JSON = 45
EXPIRY_POPULARITY_CSV = 75


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


def is_cache_valid(path: Path, days: int) -> bool:
    """Check if the cache file exists and is not older than 'days'."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - mtime < timedelta(days=days)


def get_version_info(
    cache_dir: Path, version: str | None, use_cache: bool
) -> tuple[str, str | None, str]:
    """Determine target version and fetch version info."""
    licenses_json_path = cache_dir / CACHE_LICENSES_JSON
    latest_version = None
    release_date = None
    data_source = "remote"

    if use_cache and is_cache_valid(licenses_json_path, EXPIRY_LICENSES_JSON):
        try:
            with open(licenses_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                latest_version = data.get("licenseListVersion")
                release_date = data.get("releaseDate")
                data_source = "cache"
        except (json.JSONDecodeError, OSError):
            pass

    if not latest_version:
        try:
            print(f"Fetching latest license list info from {LICENSES_JSON_URL}...")
            resp = _http_get(LICENSES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data.get("licenseListVersion")
            release_date = data.get("releaseDate")
            with open(licenses_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            data_source = "remote"
        except requests.RequestException as e:
            if not version:
                raise RuntimeError(
                    f"Failed to fetch latest license list info: {e}"
                ) from e
            print(f"Warning: Failed to fetch {LICENSES_JSON_URL}: {e}")
            latest_version = version

    return version or latest_version, release_date, data_source


def get_tarball_path(
    cache_dir: Path, version: str, use_cache: bool
) -> tuple[Path, str]:
    """Download or retrieve the SPDX License List tarball path."""
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
            with open(tar_cache_path, "wb") as f:
                f.writelines(resp.iter_content(chunk_size=8192))
        except requests.RequestException as e:
            raise RuntimeError(f"Error downloading {tar_url}: {e}") from e
    else:
        data_source = "cache"

    return tar_cache_path, data_source


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
    """Cache the CSV atomically; a write failure only costs a re-download.

    Written to a temporary file and renamed, so an interrupted write cannot
    leave a truncated file that parses to partial data and looks fresh.
    """
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(csv_content)
        os.replace(tmp_path, path)
    except OSError as e:
        print(f"Warning: Failed to cache popularity data: {e}")
        tmp_path.unlink(missing_ok=True)


def _parse_count(value: str | None) -> int:
    """Parse a pusher count; 0 if it is missing or not an integer."""
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _aggregate_popularity(csv_content: str) -> dict[str, int]:
    """Sum pushers per SPDX license ID, skipping blank and NOASSERTION rows."""
    popularity_map: dict[str, int] = {}
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            spdx_id = row.get("spdx_license")
            if not spdx_id or spdx_id == "NOASSERTION":
                continue
            count = _parse_count(row.get("num_pushers"))
            popularity_map[spdx_id] = popularity_map.get(spdx_id, 0) + count

        print(f"Aggregated popularity data for {len(popularity_map)} licenses.")
    except (csv.Error, ValueError) as e:
        print(f"Warning: Failed to parse popularity data: {e}")
    return popularity_map


def fetch_popularity_data(
    cache_dir: Path, local_path: Path | None = None
) -> tuple[dict[str, int], str]:
    """Fetch and aggregate popularity data from GitHub Innovation Graph.

    Returns ``(popularity_map, source)`` where source is ``"cache"``,
    ``"remote"``, ``"stale cache"`` or ``"unavailable"``. Order: usable
    *local_path* data, then one download (cached only if it parses), then a
    stale cache file if the download failed.
    """
    local_csv = _read_local_csv(local_path) if local_path else ""
    popularity_map = _aggregate_popularity(local_csv) if local_csv else {}
    if popularity_map:
        return popularity_map, "cache"

    cache_path = cache_dir / CACHE_POPULARITY_CSV
    downloaded = _download_popularity_csv()
    popularity_map = _aggregate_popularity(downloaded) if downloaded else {}
    if popularity_map:
        _write_popularity_cache(cache_path, downloaded)
        return popularity_map, "remote"

    if cache_path.exists():
        print("Warning: Using stale cached popularity data.")
        popularity_map = _aggregate_popularity(_read_local_csv(cache_path))
        if popularity_map:
            return popularity_map, "stale cache"
    return {}, "unavailable"
