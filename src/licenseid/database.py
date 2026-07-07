# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SQLite database management for SPDX licenses.
"""

import csv
import io
import json
import math
import sqlite3
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, cast

import requests

from licenseid.normalize import normalize_text
from licenseid.types import (
    CandidateMatch,
    DatabaseMetadata,
    ExceptionDetails,
    LicenseDetails,
    LicenseNameId,
    SpdxExceptionEntry,
    SpdxLicenseEntry,
)

# (license_id, name, xml_template, is_spdx, is_osi, is_fsf,
#  is_high_usage, is_deprecated, superseded_by, pop_score, word_count,
#  norm_license_id, norm_name)
_LicenseInsertRecord = tuple[
    str,
    str,
    Optional[str],
    bool,
    bool,
    bool,
    bool,
    bool,
    Optional[str],
    int,
    int,
    str,
    str,
]
_IndexInsertRecord = tuple[str, str]


def get_default_db_path() -> str:
    """Return the default path for the licence database."""
    db_dir = Path.home() / ".local" / "share" / "licenseid"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "licenses.db")


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

# Version of the normalize_text() rule set used to build the stored
# search_text and fingerprints.  Bump whenever normalization rules change so
# that databases built with the old rules can be detected and rebuilt.
# Version 2: SPDX Matching Guidelines rules (varietal words, bullets,
# copyright notices, comment prefixes, separators).
NORMALIZATION_VERSION = "2"

# Discriminative n-gram fingerprint settings.
# Each license keeps its top FINGERPRINT_TOP_N highest-IDF word n-grams
# (n = FINGERPRINT_N) as a compact discriminative signature.  At query time
# a single indexed SQL lookup finds which candidates share at least one
# fingerprint n-gram with the query, allowing the ranker to boost them
# without a full RapidFuzz string comparison.
_FINGERPRINT_N: int = 5  # word n-gram size
_FINGERPRINT_TOP_N: int = 20  # fingerprints stored per license


class LicenseDatabase:
    """
    Handles SQLite database operations for storing and searching SPDX licenses.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        # Check if it's an in-memory URI
        db_path_str = str(self.db_path)
        self.use_uri = "mode=memory" in db_path_str or db_path_str.startswith("file:")
        self._keep_alive: Optional[sqlite3.Connection] = None

        if self.use_uri or db_path_str == ":memory:":
            # For in-memory databases, we must keep at least one connection
            # open to prevent the database from being deleted.
            self._keep_alive = self._connect()

        self._init_db()
        self._deprecated_mappings_cache: Optional[dict[str, str]] = None
        self._norm_cols_backfilled = False
        self._check_normalization_version()

    def _check_normalization_version(self) -> None:
        """Warn when the DB was built with an older normalize_text() rule set.

        Stored search_text and fingerprints are normalised at build time; if
        the rules changed since, query-side normalisation no longer matches
        the index and recall degrades silently.
        """
        metadata = self.get_metadata()
        # Empty/new databases have no version yet — nothing to warn about.
        if not metadata.get("license_list_version"):
            return
        stored = metadata.get("normalization_version", "1")
        if stored != NORMALIZATION_VERSION:
            print(
                "Warning: license database was built with an older text "
                f"normalization rule set (v{stored}, current "
                f"v{NORMALIZATION_VERSION}). "
                "Run 'licenseid update --force' to rebuild it.",
                file=sys.stderr,
            )

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection to the database."""
        return sqlite3.connect(str(self.db_path), uri=self.use_uri)

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
        with self._connect() as conn:
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
                    is_deprecated BOOLEAN,
                    superseded_by TEXT,
                    pop_score INTEGER DEFAULT 1,
                    word_count INTEGER,
                    norm_license_id TEXT,
                    norm_name TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exceptions (
                    exception_id TEXT PRIMARY KEY,
                    name TEXT,
                    is_deprecated BOOLEAN,
                    superseded_by TEXT
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
            # Discriminative n-gram fingerprints.
            # idf_norm: IDF score normalised to [0, 1] where 1.0 means the
            # n-gram appears in exactly one license in the corpus.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS license_fingerprints (
                    license_id  TEXT NOT NULL,
                    ngram       TEXT NOT NULL,
                    idf_norm    REAL NOT NULL,
                    PRIMARY KEY (license_id, ngram),
                    FOREIGN KEY (license_id) REFERENCES licenses(license_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fp_ngram
                ON license_fingerprints(ngram)
            """)

            # Migration: databases created before norm_license_id/norm_name
            # existed have a "licenses" table without them (CREATE TABLE IF
            # NOT EXISTS above only creates the table when missing entirely,
            # it doesn't add columns to one that already exists).
            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(licenses)")
            }
            if "norm_license_id" not in existing_cols:
                conn.execute("ALTER TABLE licenses ADD COLUMN norm_license_id TEXT")
            if "norm_name" not in existing_cols:
                conn.execute("ALTER TABLE licenses ADD COLUMN norm_name TEXT")

    def clear_cache(self) -> None:
        """Delete local cache files."""
        print("Clearing cache...")
        for filename in [
            CACHE_LICENSES_JSON,
            CACHE_POPULARITY_CSV,
        ]:
            path = self._get_cache_path(filename)
            if path.exists():
                path.unlink()
        # Clear any tarballs
        for p in self.db_path.parent.glob("spdx-data-v*.tar.gz"):
            p.unlink()
        # Delete the database file itself to force a schema rebuild
        if self.db_path.exists():
            print(f"Deleting database at {self.db_path}...")
            self.db_path.unlink()

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
                if not version:
                    raise RuntimeError(
                        f"Failed to fetch latest license list info: {e}"
                    ) from e
                print(f"Warning: Failed to fetch {LICENSES_JSON_URL}: {e}")
                latest_version = version

        return version or latest_version, release_date, data_source

    def _get_tarball_path(self, version: str, use_cache: bool) -> tuple[Path, str]:
        """Download or retrieve the SPDX License List tarball path."""
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
    ) -> bool:
        """
        Fetch license data from SPDX release package and update the local database.
        Returns True if the database was updated, False if it was already up-to-date.
        """

        # 1. Version check
        target_version, release_date, ds_licenses = self._get_version_info(
            version, use_cache
        )
        print(f"Target SPDX License List version: {target_version}")

        metadata = self.get_metadata()
        if metadata.get("license_list_version") == target_version and not force:
            print(f"Database is already at version {target_version}. Skipping update.")
            return False

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
        print(f"  - SPDX License List metadata   : {ds_licenses}")
        print(f"  - SPDX License List data       : {ds_tar}")
        print(f"  - GitHub license ranking data  : {ds_pop}")

        self._process_and_store(tar_cache_path, popularity_map, release_date)
        return True

    def _process_and_store(
        self,
        tar_path: Path,
        popularity_map: dict[str, int],
        release_date: Optional[str],
    ) -> None:
        """Extract tarball and update database records."""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=tmp_dir)

                root_dir = next(Path(tmp_dir).iterdir())
                # 1. Read licenses
                lic_json_path = root_dir / "json" / "licenses.json"
                with open(lic_json_path, "r", encoding="utf-8") as f:
                    lic_data = json.load(f)

                licenses_data: list[SpdxLicenseEntry] = lic_data.get("licenses", [])
                list_version = lic_data.get("licenseListVersion")
                release_date = lic_data.get("releaseDate") or release_date

                # 2. Read exceptions
                exc_json_path = root_dir / "json" / "exceptions.json"
                exceptions_data: list[SpdxExceptionEntry] = []
                if exc_json_path.exists():
                    with open(exc_json_path, "r", encoding="utf-8") as f:
                        exc_data = json.load(f)
                        exceptions_data = exc_data.get("exceptions", [])

                print(
                    f"Processing {len(licenses_data)} licenses and "
                    f"{len(exceptions_data)} exceptions "
                    f"(Version: {list_version}, Released: {release_date})"
                )

                self._update_db_records(
                    licenses_data,
                    root_dir,
                    popularity_map,
                    list_version,
                    release_date,
                    exceptions_data,
                )

            print("\nUpdate complete.")
        except (tarfile.TarError, OSError, json.JSONDecodeError, sqlite3.Error) as e:
            raise RuntimeError(f"Failed to update database: {e}") from e

    def _update_db_records(
        self,
        licenses_data: list[SpdxLicenseEntry],
        root_dir: Path,
        popularity_map: dict[str, int],
        list_version: str,
        release_date: Optional[str],
        exceptions_data: list[SpdxExceptionEntry],
    ) -> None:
        """Execute database delete and insert operations."""
        license_records: list[_LicenseInsertRecord] = []
        index_records: list[_IndexInsertRecord] = []
        exception_records: list[tuple[str, str, bool, Optional[str]]] = []

        print("\nPreparing exception data...", end="", flush=True)
        # Build the superseded_by mapping at DB build time so runtime lookups
        # are O(1).
        active_ids: set[str] = {
            lic["licenseId"]
            for lic in licenses_data
            if not lic.get("isDeprecatedLicenseId", False)
        }

        name_to_exception: dict[str, str] = {}
        for exc in exceptions_data:
            if not exc.get("isDeprecatedLicenseId", False):
                name_to_exception[exc["name"].lower()] = exc["licenseExceptionId"]

        for i, lic in enumerate(licenses_data):
            # Recalculate record with superseded_by info
            is_deprecated = bool(lic.get("isDeprecatedLicenseId", False))
            superseded_by: Optional[str] = None
            if is_deprecated:
                dep_id = lic["licenseId"]
                # SPDX '+' token: GPL-2.0+ → GPL-2.0-or-later (certain).
                # Bare deprecated IDs (e.g. GPL-2.0) are left as NULL because
                # they cannot be resolved without the granting declaration.
                if dep_id.endswith("+"):
                    base_id = dep_id[:-1]  # strip the '+' operator token
                    or_later = base_id + "-or-later"
                    if or_later in active_ids:
                        superseded_by = or_later

            res = self._prepare_license_record(
                lic, root_dir, popularity_map, is_deprecated, superseded_by
            )
            if res:
                license_records.append(res[0])
                index_records.append(res[1])
            elif is_deprecated:
                # Text file absent for this deprecated ID (some SPDX releases omit
                # them).  Still store the metadata row so redirect lookups work.
                dep_name = lic.get("name", lic["licenseId"])
                license_records.append(
                    (
                        lic["licenseId"],
                        dep_name,
                        None,  # xml_template
                        True,  # is_spdx
                        False,  # is_osi_approved
                        False,  # is_fsf_libre
                        False,  # is_high_usage
                        True,  # is_deprecated
                        superseded_by,
                        1,  # pop_score
                        0,  # word_count
                        normalize_text(lic["licenseId"]),
                        normalize_text(dep_name),
                    )
                )
                # Not added to index_records — no text to index.

            if (i + 1) % 100 == 0 or (i + 1) == len(licenses_data):
                print(".", end="", flush=True)

        print("\nPreparing exception data...", end="", flush=True)
        for exc in exceptions_data:
            exc_id = exc["licenseExceptionId"]
            is_deprecated = exc.get("isDeprecatedLicenseId", False)
            superseded_by = None
            if is_deprecated:
                superseded_by = name_to_exception.get(exc["name"].lower())

            exception_records.append(
                (
                    exc_id,
                    exc["name"],
                    is_deprecated,
                    superseded_by,
                )
            )

        print(f"\nInserting {len(license_records)} records into database...")
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("DELETE FROM license_index")
                conn.execute("DELETE FROM licenses")
                conn.execute("DELETE FROM exceptions")
                conn.execute("DELETE FROM db_metadata")
                conn.execute("DELETE FROM license_fingerprints")

                now = datetime.now().isoformat()
                metadata_items: list[tuple[str, str]] = [
                    ("license_list_version", list_version),
                    ("release_date", release_date or ""),
                    ("last_check_datetime", now),
                    ("last_update_datetime", now),
                    ("normalization_version", NORMALIZATION_VERSION),
                ]
                conn.executemany(
                    "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
                    metadata_items,
                )

                conn.executemany(
                    """
                    INSERT INTO licenses (
                        license_id, name, xml_template, is_spdx,
                        is_osi_approved, is_fsf_libre, is_high_usage,
                        is_deprecated, superseded_by,
                        pop_score, word_count,
                        norm_license_id, norm_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    license_records,
                )
                conn.executemany(
                    "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
                    index_records,
                )
                conn.executemany(
                    "INSERT INTO exceptions "
                    "(exception_id, name, is_deprecated, superseded_by) "
                    "VALUES (?, ?, ?, ?)",
                    exception_records,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        # Compute fingerprints in a separate transaction so that the FTS5
        # virtual table is fully committed and readable before we scan it.
        self._compute_fingerprints()

    def _prepare_license_record(
        self,
        lic: SpdxLicenseEntry,
        root_dir: Path,
        popularity_map: dict[str, int],
        is_deprecated: bool = False,
        superseded_by: Optional[str] = None,
    ) -> Optional[tuple[_LicenseInsertRecord, _IndexInsertRecord]]:
        """Prepare license data for insertion."""
        license_id = lic["licenseId"]
        text_path = root_dir / "text" / f"{license_id}.txt"
        if not text_path.exists():
            return None

        with open(text_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        xml_path = root_dir / "license-list-XML" / f"{license_id}.xml"
        xml_content = None
        if xml_path.exists():
            with open(xml_path, "r", encoding="utf-8") as f:
                xml_content = f.read()

        fingerprint = self._create_fingerprint(raw_text, xml_content)
        word_count = len(fingerprint.split())
        is_osi = lic.get("isOsiApproved", False)
        is_fsf = lic.get("isFsfLibre", False)

        baseline = 100 if (is_osi or is_fsf) else 1
        pop_count = popularity_map.get(license_id, 0)
        pop_score = max(baseline, pop_count)

        # High usage: OSI, FSF, or significant popularity
        is_high_usage = is_osi or is_fsf or pop_score > 500

        name = lic.get("name", "")
        license_record: _LicenseInsertRecord = (
            license_id,
            name,
            xml_content,
            True,  # is_spdx
            is_osi,
            is_fsf,
            is_high_usage,
            is_deprecated,
            superseded_by,
            pop_score,
            word_count,
            normalize_text(license_id),
            normalize_text(name),
        )
        index_record: _IndexInsertRecord = (license_id, fingerprint)
        return license_record, index_record

    def _fetch_popularity_data(
        self, local_path: Optional[Path] = None
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
        """Create a search fingerprint by removing optional parts and normalizing."""
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

    def _compute_fingerprints(self) -> None:
        """Compute and store discriminative n-gram fingerprints for all licenses.

        For each license, the top ``_FINGERPRINT_TOP_N`` highest-IDF word
        n-grams (``_FINGERPRINT_N`` words each) are stored in
        ``license_fingerprints``.  IDF is computed across the whole corpus so
        that n-grams shared by many licenses score near 0 and n-grams unique
        to one license score near 1.

        Must be called after ``license_index`` has been fully populated.
        Replaces any previously stored fingerprints.
        """
        print("Computing discriminative fingerprints...", end="", flush=True)

        # Read all pre-normalised license texts.  The search_text column in
        # license_index is the canonical normalised form (see _create_fingerprint).
        with self._connect() as conn:
            rows: list[tuple[str, str]] = conn.execute(
                "SELECT license_id, search_text FROM license_index"
            ).fetchall()

        if not rows:
            print(" no data.", flush=True)
            return

        k = len(rows)
        # IDF of a 5-gram that appears in exactly one license = log(k/1) = log(k).
        # Dividing by log(k) normalises scores to [0, 1].
        max_idf = math.log(k)

        # Build 5-gram sets per license and count document frequency of each
        # n-gram (number of distinct licenses that contain it).
        license_ngrams: dict[str, set[str]] = {}
        doc_freq: Counter[str] = Counter()

        for license_id, search_text in rows:
            tokens = search_text.split()
            ngrams: set[str] = {
                " ".join(tokens[i : i + _FINGERPRINT_N])
                for i in range(len(tokens) - _FINGERPRINT_N + 1)
            }
            if ngrams:
                license_ngrams[license_id] = ngrams
                doc_freq.update(ngrams)

        # For each license keep the top-N n-grams ranked by IDF (high IDF =
        # rare across the corpus = highly discriminative).
        fp_records: list[tuple[str, str, float]] = []
        for license_id, ngrams in license_ngrams.items():
            scored = sorted(
                (
                    (ng, math.log(k / doc_freq[ng]) / max_idf)
                    for ng in ngrams
                    if doc_freq[ng] > 0
                ),
                key=lambda x: -x[1],
            )
            for ng, idf_norm in scored[:_FINGERPRINT_TOP_N]:
                if idf_norm > 0.0:
                    fp_records.append((license_id, ng, idf_norm))

        with self._connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("DELETE FROM license_fingerprints")
                conn.executemany(
                    "INSERT INTO license_fingerprints (license_id, ngram, idf_norm)"
                    " VALUES (?, ?, ?)",
                    fp_records,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        print(f" {len(fp_records)} fingerprints for {k} licenses.", flush=True)

    def find_fingerprint_hits(self, norm_input: str) -> dict[str, float]:
        """Return a map of ``license_id → max_idf_norm`` for fingerprint matches.

        Extracts ``_FINGERPRINT_N``-word n-grams from *norm_input* and queries
        the ``license_fingerprints`` index for any matching n-grams.  For each
        candidate license, the highest matching ``idf_norm`` score is returned.

        The ``idf_norm`` value is in ``[0, 1]``: 1.0 means the matching n-gram
        appears in exactly one license in the corpus (maximally discriminative).

        Returns an empty dict when the table is empty, the input is too short
        to form any n-grams, or no n-grams match.
        """
        tokens = norm_input.split()
        if len(tokens) < _FINGERPRINT_N:
            return {}

        query_ngrams = [
            " ".join(tokens[i : i + _FINGERPRINT_N])
            for i in range(len(tokens) - _FINGERPRINT_N + 1)
        ]

        placeholders = ", ".join(["?"] * len(query_ngrams))
        sql = (
            f"SELECT license_id, MAX(idf_norm) AS max_idf"
            f" FROM license_fingerprints"
            f" WHERE ngram IN ({placeholders})"
            f" GROUP BY license_id"
        )
        with self._connect() as conn:
            try:
                rows = conn.execute(sql, query_ngrams).fetchall()
            except sqlite3.OperationalError:
                # Table absent on databases built before this schema version.
                # Degrade gracefully: fingerprint boost is simply skipped.
                return {}
        return {row[0]: row[1] for row in rows}

    def search_candidates(
        self,
        text: str,
        limit: int = 50,
        already_normalized: bool = False,
    ) -> list[CandidateMatch]:
        """Tier 1: Search for candidates using trigram FTS5.

        Set already_normalized=True when the caller has already run
        normalize_text() on the full original text and is passing a slice of
        the result (e.g. a head/tail word-count window): re-normalizing a
        slice can behave differently from normalizing the full text once
        (line-anchored rules like copyright-notice removal need real line
        breaks, which a slice reconstructed by joining words with spaces no
        longer has).
        """
        norm_text = text if already_normalized else normalize_text(text)
        # Build an OR query from the first 20 normalised words.  Using OR
        # maximises recall: a candidate matches if it contains any of the
        # terms, not all of them.  FTS5 BM25 ranking still promotes documents
        # that contain more terms.  20 words (up from 10) gives enough
        # discriminating signal for licences whose preamble shares the first
        # 10 words with many other licences (e.g. HPND family: "permission to
        # use copy modify and distribute this software ...").
        words = norm_text.split()[:20]
        if not words:
            return []
        search_terms = " OR ".join(words)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT
                    li.license_id,
                    li.search_text,
                    l.word_count,
                    l.is_spdx,
                    l.is_high_usage,
                    l.is_osi_approved,
                    l.is_fsf_libre,
                    l.pop_score,
                    l.is_deprecated,
                    l.superseded_by
                FROM license_index li
                JOIN licenses l ON li.license_id = l.license_id
                WHERE li.search_text MATCH ?
                ORDER BY li.rank
                LIMIT ?
            """
            try:
                # Escape double quotes and use OR-ed keywords for recall
                match_query = search_terms.replace('"', '""')
                cursor = conn.execute(query, (match_query, limit))
                return [cast(CandidateMatch, dict(row)) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                return []

    def get_license_details(self, license_id: str) -> Optional[LicenseDetails]:
        """Get full metadata for a license (case-insensitive lookup)."""
        clean_id = license_id.strip()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM licenses WHERE license_id = ? COLLATE NOCASE",
                (clean_id,),
            ).fetchone()
            if not row:
                return None
            return self._cast_license_details(row)

    def get_license_by_name(self, name: str) -> Optional[LicenseDetails]:
        """Get full metadata for a license by its full name (case-insensitive)."""
        clean_name = name.strip()
        if not clean_name:
            return None
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM licenses WHERE name = ? COLLATE NOCASE",
                (clean_name,),
            ).fetchone()
            if not row:
                return None
            return self._cast_license_details(row)

    def get_exception_details(self, exception_id: str) -> Optional[ExceptionDetails]:
        """Get full metadata for an exception (case-insensitive lookup)."""
        clean_id = exception_id.strip()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM exceptions WHERE exception_id = ? COLLATE NOCASE",
                (clean_id,),
            ).fetchone()
            if not row:
                return None
            return self._cast_exception_details(row)

    def get_license_by_id_prefix(self, prefix: str) -> Optional[LicenseDetails]:
        """Return the best (shortest) active license whose ID starts with *prefix*.

        Used to canonicalise abbreviated IDs such as ``"Apache-2"`` →
        ``"Apache-2.0"``.  Only non-deprecated licenses are considered so that
        a bare prefix never silently resolves to a deprecated ID.  Returns
        ``None`` when no unambiguous match exists (zero or multiple candidates
        of the same length).
        """
        clean = prefix.strip()
        if not clean:
            return None
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM licenses
                WHERE license_id LIKE ? ESCAPE '\\'
                  AND is_deprecated = 0
                ORDER BY LENGTH(license_id)
                """,
                (clean.replace("%", r"\%").replace("_", r"\_") + "%",),
            ).fetchall()
        if not rows:
            return None
        # Accept only when the shortest match is unambiguous: either there is
        # exactly one row, or the shortest ID is strictly shorter than the next.
        if len(rows) == 1 or len(rows[0]["license_id"]) < len(rows[1]["license_id"]):
            return self._cast_license_details(rows[0])
        return None

    def _cast_license_details(self, row: sqlite3.Row) -> LicenseDetails:
        """Helper to cast sqlite Row to LicenseDetails with proper boolean types."""
        d = dict(row)
        bool_keys = [
            "is_spdx",
            "is_osi_approved",
            "is_fsf_libre",
            "is_high_usage",
            "is_deprecated",
        ]
        for key in bool_keys:
            if key in d:
                d[key] = bool(d[key])
        return cast(LicenseDetails, d)

    def _cast_exception_details(self, row: sqlite3.Row) -> ExceptionDetails:
        """Helper to cast sqlite Row to ExceptionDetails with proper boolean types."""
        d = dict(row)
        if "is_deprecated" in d:
            d["is_deprecated"] = bool(d["is_deprecated"])
        return cast(ExceptionDetails, d)

    def get_search_text(self, license_id: str) -> str:
        """Return the normalized search text for a license from the FTS index."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT search_text FROM license_index WHERE license_id = ?",
                (license_id,),
            ).fetchone()
            return row[0] if row else ""

    def _ensure_norm_columns(self) -> None:
        """Backfill norm_license_id/norm_name for rows that predate this
        schema addition (on-disk DBs migrated by _init_db) or bypass the
        normal insert path (e.g. a benchmark harness inserting directly
        into 'licenses').  Idempotent per instance: after the first
        successful check/backfill, later calls are a no-op.
        """
        if self._norm_cols_backfilled:
            return
        with self._connect() as conn:
            missing = conn.execute(
                "SELECT license_id, name FROM licenses WHERE norm_license_id IS NULL"
            ).fetchall()
            if missing:
                updates = [
                    (normalize_text(lid), normalize_text(name or ""), lid)
                    for lid, name in missing
                ]
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.executemany(
                        "UPDATE licenses SET norm_license_id = ?, norm_name = ?"
                        " WHERE license_id = ?",
                        updates,
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        self._norm_cols_backfilled = True

    def get_all_names_and_ids(self) -> list[LicenseNameId]:
        """Retrieve all license IDs and names for short-text matching."""
        self._ensure_norm_columns()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT license_id, name, is_deprecated,"
                " norm_license_id, norm_name FROM licenses"
            )
            return [
                LicenseNameId(
                    license_id=row["license_id"],
                    name=row["name"],
                    is_deprecated=bool(row["is_deprecated"]),
                    norm_license_id=row["norm_license_id"],
                    norm_name=row["norm_name"],
                )
                for row in cursor.fetchall()
            ]

    def get_deprecated_mappings(self) -> dict[str, str]:
        """Get a mapping of all deprecated IDs to their successors."""
        if self._deprecated_mappings_cache is not None:
            return self._deprecated_mappings_cache

        mappings: dict[str, str] = {}
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            # Licenses
            cursor = conn.execute(
                "SELECT license_id, superseded_by FROM licenses "
                "WHERE is_deprecated = 1 AND superseded_by IS NOT NULL"
            )
            for row in cursor:
                mappings[row["license_id"]] = row["superseded_by"]

            # Exceptions
            cursor = conn.execute(
                "SELECT exception_id, superseded_by FROM exceptions "
                "WHERE is_deprecated = 1 AND superseded_by IS NOT NULL"
            )
            for row in cursor:
                mappings[row["exception_id"]] = row["superseded_by"]

        self._deprecated_mappings_cache = mappings
        return mappings

    def get_metadata(self) -> DatabaseMetadata:
        """Get database metadata."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT key, value FROM db_metadata")
            return cast(DatabaseMetadata, {row[0]: row[1] for row in cursor.fetchall()})
