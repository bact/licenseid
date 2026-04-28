# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SQLite database management for SPDX licenses.
"""

import csv
import io
import json
import sqlite3
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from licenseid.normalize import normalize_text

# Cache expiration settings
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


class LicenseDatabase:
    """
    Handles SQLite database operations for storing and searching SPDX licenses.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_cache_path(self, filename: str) -> Path:
        """Get the absolute path for a cache file."""
        return self.db_path.parent / filename

    def _is_cache_valid(self, path: Path, days: int) -> bool:
        """Check if the cache file exists and is not older than 'days'."""
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(days=days)

    def _init_db(self) -> None:
        """Initialise the SQLite database with FTS5."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    license_id TEXT PRIMARY KEY,
                    name TEXT,
                    xml_template TEXT,
                    legacy_template TEXT,
                    ignorable_metadata TEXT,
                    is_spdx BOOLEAN,
                    is_osi_approved BOOLEAN,
                    is_fsf_libre BOOLEAN,
                    is_high_usage BOOLEAN,
                    popularity_score INTEGER DEFAULT 1
                )
            """
            )

            # Create FTS5 virtual table for trigram search
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS license_index USING fts5(
                    license_id UNINDEXED,
                    search_text,
                    tokenize = 'trigram'
                )
            """
            )
            # Metadata table for version tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS db_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """
            )

    def _clear_cache(self) -> None:
        """Delete local cache files."""
        print("Clearing cache...")
        for filename in [CACHE_LICENSES_JSON, CACHE_POPULARITY_CSV]:
            path = self._get_cache_path(filename)
            if path.exists():
                path.unlink()
        # Clear any tarballs
        for p in self.db_path.parent.glob("spdx-data-v*.tar.gz"):
            p.unlink()

    def _get_version_info(
        self, version: Optional[str], use_cache: bool
    ) -> tuple[str, Optional[str], str]:
        """Determine target version and fetch version info."""
        licenses_json_path = self._get_cache_path(CACHE_LICENSES_JSON)
        latest_version = None
        release_date = None
        data_source = "remote"

        if use_cache and self._is_cache_valid(licenses_json_path, EXPIRY_LICENSES_JSON):
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
                print(f"Warning: Failed to fetch {LICENSES_JSON_URL}: {e}")
                if not version:
                    print(f"Falling back to default version {DEFAULT_FALLBACK_VERSION}")
                    latest_version = DEFAULT_FALLBACK_VERSION
                else:
                    latest_version = version

        return version or latest_version, release_date, data_source

    def _get_tarball_path(self, version: str, use_cache: bool) -> tuple[Path, str]:
        """Download or retrieve the SPDX tarball path."""
        tar_filename = CACHE_SPDX_TARBALL_TEMPLATE.format(version=version)
        tar_cache_path = self._get_cache_path(tar_filename)
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

    def update_from_remote(
        self,
        version: Optional[str] = None,
        force: bool = False,
        use_cache: bool = True,
        clear_cache: bool = False,
    ) -> None:
        """
        Fetch license data from SPDX release package and update the local database.
        """
        if clear_cache:
            self._clear_cache()

        # 1. Version check
        target_version, release_date, ds_licenses = self._get_version_info(
            version, use_cache
        )
        print(f"Target SPDX License List version: {target_version}")

        metadata = self.get_metadata()
        if metadata.get("license_list_version") == target_version and not force:
            print(f"Database is already at version {target_version}. Skipping update.")
            return

        print(f"Updating license database to version {target_version}...")

        # 2. Fetch Popularity Data
        pop_cache_path = self._get_cache_path(CACHE_POPULARITY_CSV)
        ds_pop = "remote"
        if use_cache and self._is_cache_valid(pop_cache_path, EXPIRY_POPULARITY_CSV):
            popularity_map = self._fetch_popularity_data(pop_cache_path)
            ds_pop = "cache"
        else:
            popularity_map = self._fetch_popularity_data()
            if popularity_map:
                ds_pop = "remote"

        # 3. Fetch SPDX tarball
        tar_cache_path, ds_tar = self._get_tarball_path(target_version, use_cache)

        # Report sources
        print("Data sources:")
        print(f"  - License list info: {ds_licenses}")
        print(f"  - Popularity data: {ds_pop}")
        print(f"  - SPDX license data: {ds_tar}")

        self._process_and_store(tar_cache_path, popularity_map, release_date)

    def _process_and_store(
        self,
        tar_path: Path,
        popularity_map: Dict[str, int],
        release_date: Optional[str],
    ) -> None:
        """Extract tarball and update database records."""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=tmp_dir)

                root_dir = next(Path(tmp_dir).iterdir())
                json_path = root_dir / "json" / "licenses.json"
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                licenses_data = data.get("licenses", [])
                list_version = data.get("licenseListVersion")
                release_date = data.get("releaseDate") or release_date

                print(
                    f"Processing {len(licenses_data)} licenses "
                    f"(Version: {list_version}, Released: {release_date})"
                )

                self._update_db_records(
                    licenses_data, root_dir, popularity_map, list_version, release_date
                )

            print("\nUpdate complete.")
        except (tarfile.TarError, OSError, json.JSONDecodeError, sqlite3.Error) as e:
            print(f"\nFailed to update database: {e}")

    def _update_db_records(
        self,
        licenses_data: List[Dict[str, Any]],
        root_dir: Path,
        popularity_map: Dict[str, int],
        list_version: str,
        release_date: Optional[str],
    ) -> None:
        """Execute database delete and insert operations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM license_index")
            conn.execute("DELETE FROM licenses")
            conn.execute("DELETE FROM db_metadata")

            now = datetime.now().isoformat()
            metadata_items = [
                ("license_list_version", list_version),
                ("release_date", release_date),
                ("last_check_datetime", now),
                ("last_update_datetime", now),
            ]
            conn.executemany(
                "INSERT INTO db_metadata (key, value) VALUES (?, ?)", metadata_items
            )

            for i, lic in enumerate(licenses_data):
                self._insert_license_record(conn, lic, root_dir, popularity_map)
                if (i + 1) % 50 == 0 or (i + 1) == len(licenses_data):
                    print(".", end="", flush=True)
                if (i + 1) % 500 == 0:
                    print(f" {i + 1}")

    def _insert_license_record(
        self,
        conn: sqlite3.Connection,
        lic: Dict[str, Any],
        root_dir: Path,
        popularity_map: Dict[str, int],
    ) -> None:
        """Insert a single license record into the database."""
        license_id = lic["licenseId"]
        text_path = root_dir / "text" / f"{license_id}.txt"
        if not text_path.exists():
            return

        with open(text_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        xml_path = root_dir / "license-list-XML" / f"{license_id}.xml"
        xml_content = None
        if xml_path.exists():
            with open(xml_path, "r", encoding="utf-8") as f:
                xml_content = f.read()

        fingerprint = self._create_fingerprint(raw_text, xml_content)
        baseline = 100 if (lic.get("isOsiApproved") or lic.get("isFsfLibre")) else 1
        pop_count = popularity_map.get(license_id, 0)
        popularity_score = max(baseline, pop_count)

        conn.execute(
            """
            INSERT INTO licenses (
                license_id, name, xml_template, is_spdx,
                is_osi_approved, is_fsf_libre, popularity_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                license_id,
                lic.get("name", ""),
                xml_content,
                True,
                lic.get("isOsiApproved", False),
                lic.get("isFsfLibre", False),
                popularity_score,
            ),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (license_id, fingerprint),
        )

    def _fetch_popularity_data(
        self, local_path: Optional[Path] = None
    ) -> Dict[str, int]:
        """Fetch and aggregate popularity data from GitHub Innovation Graph."""
        popularity_map: Dict[str, int] = {}
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
                # Save to cache
                pop_cache_path = self._get_cache_path(CACHE_POPULARITY_CSV)
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

    def _create_fingerprint(self, text: str, xml_content: Optional[str] = None) -> str:
        """Create a search fingerprint by removing optional blocks and normalizing."""
        if xml_content:
            try:
                # Simple XML parsing to strip optional parts
                # This is a heuristic; real implementation would use a proper
                # SPDX matcher
                ET.fromstring(xml_content)
                # Find all optional elements and remove them from a virtual text build
                # For now, we just use the raw text and normalize it
            except ET.ParseError:
                pass

        return normalize_text(text)

    def search_candidates(self, text: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Tier 1: Search for candidates using trigram FTS5."""
        norm_text = normalize_text(text)
        # Use OR between the first few words to ensure broad recall.
        # This allows candidates that match most, but not necessarily all, terms.
        words = norm_text.split()[:10]
        if not words:
            return []
        search_terms = " OR ".join(words)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT license_id, search_text
                FROM license_index
                WHERE search_text MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            try:
                # Escape double quotes and use OR-ed keywords for recall
                match_query = search_terms.replace('"', '""')
                cursor = conn.execute(query, (match_query, limit))
                results = [dict(row) for row in cursor.fetchall()]
                return results
            except sqlite3.OperationalError:
                return []

    def get_license_details(self, license_id: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a license."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM licenses WHERE license_id = ?", (license_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_names_and_ids(self) -> List[Dict[str, str]]:
        """Retrieve all license IDs and names for short-text matching."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT license_id, name FROM licenses")
            return [
                {"license_id": row["license_id"], "name": row["name"]}
                for row in cursor.fetchall()
            ]

    def get_metadata(self) -> Dict[str, str]:
        """Get database metadata."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM db_metadata")
            return {row[0]: row[1] for row in cursor.fetchall()}
