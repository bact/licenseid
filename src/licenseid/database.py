# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import tarfile
import tempfile
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import xml.etree.ElementTree as ET

from licenseid.normalize import normalize_text


class LicenseDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialise the SQLite database with FTS5."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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
            """)

            # Create FTS5 virtual table for trigram search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS license_index USING fts5(
                    license_id UNINDEXED,
                    search_text,
                    tokenize = 'trigram'
                )
            """)
            # Metadata table for version tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def update_from_remote(self, version: str = "3.28.0") -> None:
        """
        Fetch license data from SPDX release package and update the local database.
        """
        print(f"Updating license database to SPDX v{version}...")

        # 1. Fetch Popularity Data from GitHub Innovation Graph
        popularity_map = self._fetch_popularity_data()

        tar_url = f"https://github.com/spdx/license-list-data/archive/refs/tags/v{version}.tar.gz"
        print(f"Downloading release: {tar_url}")

        try:
            resp = requests.get(tar_url, stream=True)
            resp.raise_for_status()

            with tempfile.TemporaryDirectory() as tmp_dir:
                tar_path = Path(tmp_dir) / "data.tar.gz"
                with open(tar_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=tmp_dir)

                # Find the extracted root directory
                root_dir = next(Path(tmp_dir).iterdir())

                licenses_json_path = root_dir / "json" / "licenses.json"
                with open(licenses_json_path, "r") as f:
                    data = json.load(f)

                licenses_data = data.get("licenses", [])
                list_version = data.get("licenseListVersion")
                release_date = data.get("releaseDate")

                print(
                    f"Processing {len(licenses_data)} licenses (Version: {list_version}, Released: {release_date})"
                )

                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM license_index")
                    conn.execute("DELETE FROM licenses")
                    conn.execute("DELETE FROM db_metadata")

                    # Update metadata
                    now = datetime.now().isoformat()
                    metadata = [
                        ("license_list_version", list_version),
                        ("release_date", release_date),
                        ("last_check_datetime", now),
                        ("last_update_datetime", now),
                    ]
                    conn.executemany(
                        "INSERT INTO db_metadata (key, value) VALUES (?, ?)", metadata
                    )

                    for i, lic in enumerate(licenses_data):
                        license_id = lic["licenseId"]
                        license_name = lic.get("name", "")

                        # Read text
                        text_path = root_dir / "text" / f"{license_id}.txt"
                        if not text_path.exists():
                            continue

                        with open(text_path, "r", encoding="utf-8") as f:
                            raw_text = f.read()

                        # Read XML
                        xml_path = root_dir / "license-list-XML" / f"{license_id}.xml"
                        xml_content = None
                        if xml_path.exists():
                            with open(xml_path, "r", encoding="utf-8") as f:
                                xml_content = f.read()

                        # Create search fingerprint
                        fingerprint = self._create_fingerprint(raw_text, xml_content)

                        # Determine popularity score
                        baseline = (
                            100
                            if (
                                lic.get("isOsiApproved", False)
                                or lic.get("isFsfLibre", False)
                            )
                            else 1
                        )
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
                                license_name,
                                xml_content,
                                True,
                                lic.get("isOsiApproved", False),
                                lic.get("isFsfLibre", False),
                                popularity_score,
                            ),
                        )

                        conn.execute(
                            """
                            INSERT INTO license_index (license_id, search_text)
                            VALUES (?, ?)
                        """,
                            (license_id, fingerprint),
                        )

                        # Progress reporting
                        if (i + 1) % 50 == 0 or (i + 1) == len(licenses_data):
                            print(".", end="", flush=True)
                        if (i + 1) % 500 == 0:
                            print(f" {i + 1}")

            print("\nUpdate complete.")

        except Exception as e:
            print(f"\nFailed to update database: {e}")

    def _fetch_popularity_data(self) -> Dict[str, int]:
        """Fetch and aggregate popularity data from GitHub Innovation Graph."""
        url = "https://raw.githubusercontent.com/github/innovationgraph/main/data/licenses.csv"
        print(f"Downloading popularity data: {url}")

        popularity_map: Dict[str, int] = {}
        try:
            resp = requests.get(url)
            resp.raise_for_status()

            import csv
            import io

            content = io.StringIO(resp.text)
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
        except Exception as e:
            print(f"Warning: Failed to fetch popularity data: {e}")

        return popularity_map

    def _create_fingerprint(self, text: str, xml_content: Optional[str] = None) -> str:
        """Create a search fingerprint by removing optional blocks and normalizing."""
        if xml_content:
            try:
                # Simple XML parsing to strip optional parts
                # This is a heuristic; real implementation would use a proper SPDX matcher
                ET.fromstring(xml_content)
                # Find all optional elements and remove them from a virtual text build
                # For now, we just use the raw text and normalize it
                pass
            except Exception:
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
