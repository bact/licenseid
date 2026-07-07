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
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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


def is_cache_valid(path: Path, days: int) -> bool:
    """Check if the cache file exists and is not older than 'days'."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(days=days)


def get_version_info(
    cache_dir: Path, version: Optional[str], use_cache: bool
) -> tuple[str, Optional[str], str]:
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
            resp = requests.get(LICENSES_JSON_URL, timeout=30)
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
            resp = requests.get(tar_url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(tar_cache_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except requests.RequestException as e:
            raise RuntimeError(f"Error downloading {tar_url}: {e}") from e
    else:
        data_source = "cache"

    return tar_cache_path, data_source


def fetch_popularity_data(
    cache_dir: Path, local_path: Optional[Path] = None
) -> dict[str, int]:
    """Fetch and aggregate popularity data from GitHub Innovation Graph."""
    popularity_map: dict[str, int] = {}
    csv_content = ""

    if local_path:
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                csv_content = f.read()
        except OSError as e:
            print(f"Warning: Failed to read local popularity data: {e}")

    if not csv_content:
        print(f"Downloading popularity data: {POPULARITY_DATA_URL}")
        try:
            resp = requests.get(POPULARITY_DATA_URL, timeout=30)
            resp.raise_for_status()
            csv_content = resp.text
            pop_cache_path = cache_dir / CACHE_POPULARITY_CSV
            with open(pop_cache_path, "w", encoding="utf-8") as f:
                f.write(csv_content)
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch popularity data: {e}")
            return {}

    try:
        content = io.StringIO(csv_content)
        reader = csv.DictReader(content)

        for row in reader:
            spdx_id = row.get("spdx_license")
            if not spdx_id or spdx_id == "NOASSERTION":
                continue

            try:
                count = int(row.get("num_pushers", 0))
            except ValueError:
                count = 0

            popularity_map[spdx_id] = popularity_map.get(spdx_id, 0) + count

        print(f"Aggregated popularity data for {len(popularity_map)} licenses.")
    except (csv.Error, ValueError) as e:
        print(f"Warning: Failed to parse popularity data: {e}")

    return popularity_map
