# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
SQLite database management for SPDX licenses.
"""

import contextlib
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

from licenseid.console import end_line, status, warn
from licenseid.dbcache import TableCache, cast_license_details
from licenseid.dbcheck import (
    absolute_path,
    empty_error,
    is_memory_database,
    named_file,
    needs_writing,
    not_found_error,
    reject_foreign_database,
)
from licenseid.dbconnection import Connections, QueryConnection
from licenseid.dbschema import create_schema, schema_state
from licenseid.errors import DatabaseNotReadyError, LicenseIdError, fold, typed
from licenseid.fingerprintstore import fingerprint_hits, store_fingerprints
from licenseid.normalize import normalize_text
from licenseid.records import (
    BUILD_VERSION,
    ExceptionInsertRecord,
    IndexInsertRecord,
    LicenseInsertRecord,
    build_records,
)
from licenseid.spdxdata import SpdxData
from licenseid.types import (
    CandidateMatch,
    DatabaseMetadata,
    ExceptionDetails,
    LicenseDetails,
    LicenseNameId,
    UpdateSource,
)

if TYPE_CHECKING:
    from licenseid.releasesource import UpdateRequest

# Version of the normalize_text() rule set used to build the stored
# search_text and fingerprints.  Bump whenever normalization rules change so
# that databases built with the old rules can be detected and rebuilt (see
# also records.BUILD_VERSION).
# Version 2: SPDX Matching Guidelines rules (varietal words, bullets,
# copyright notices, comment prefixes, separators).
NORMALIZATION_VERSION = "2"


def _stamp(value: str) -> int:
    """A build stamp as a number to compare: -1 for one that is no short
    ASCII number, which no licenseid wrote, so it is older than any."""
    return (
        int(value)
        if isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) < 10
        else -1
    )


def is_current_build(metadata: DatabaseMetadata) -> bool:
    """Whether a database's rows were built by this licenseid's rules
    (``records.BUILD_VERSION``): not older, as ``build vN outdated`` warns,
    nor newer, as ``build vN newer`` does."""
    return _stamp(metadata.get("build_version", "1")) == _stamp(BUILD_VERSION)


class LicenseDatabase:
    """
    Handles SQLite database operations for storing and searching SPDX licenses.
    """

    def __init__(
        self,
        db_path: str | os.PathLike[str],
        create: bool = True,
        report: Callable[[str], None] | None = None,
    ):
        """Open the database at *db_path*. With *create* (the default) a
        missing file, or missing tables, are created; without it the file
        must be there, and only a schema of an older version is written to,
        so a matcher never makes a database out of one that went missing.

        Without *create*, rules older or newer than this licenseid's are
        warned (``database: build vN outdated: ...``) through *report*, by
        default ``licenseid.console.warn``; ``match()`` passes one that
        says each line once per process."""
        db_path = os.fspath(db_path)
        self._create = create
        named = named_file(db_path)  # a URI: the file it names
        self.db_path = Path(absolute_path(named) if named else db_path)
        self.use_uri = db_path.startswith("file:")  # Path() rewrites a URI
        self._source = db_path if self.use_uri else str(self.db_path)
        self._connections = Connections(
            self._source, self.use_uri, str(self.db_path), create
        )
        self._keep_alive: sqlite3.Connection | None = None

        if is_memory_database(self._source):
            # An in-memory database goes when its last connection closes.
            self._keep_alive = self._connections.connect(write=True)

        self._init_db()
        self._tables = TableCache(self._connections)
        if not create:  # update, which creates, is about to fix it
            say = report or warn
            for outdated in self._outdated_rules():
                say(f"database: {outdated}; run 'licenseid update'")
            for newer in self._stamped_rules(newer=True):
                say(f"database: {newer}")

    def _outdated_rules(self) -> list[str]:
        """The rules this database was built with that are older than this
        licenseid's, each as a condition and its detail ("normalization v1
        outdated: current v2"). ``update`` rebuilds such a database."""
        return self._stamped_rules(newer=False)

    def _stamped_rules(self, newer: bool) -> list[str]:
        """The rules this database was built with that are older than this
        licenseid's (a stamp that is no number counts as older), or with
        *newer*, the newer ones ("build v3 newer: current v2"): a later
        licenseid built it, and rebuilding would downgrade it.

        Stored search_text and fingerprints are normalised at build time; if
        the normalize_text() rules changed since, query-side normalisation no
        longer matches the index and recall degrades silently. Rows built by
        older records rules miss what those rules now record.
        """
        metadata = self.get_metadata()
        # Empty/new databases have no version yet — nothing to warn about.
        if not metadata.get("license_list_version"):
            return []
        built = (
            (
                "normalization",
                metadata.get("normalization_version", "1"),
                NORMALIZATION_VERSION,
            ),
            ("build", metadata.get("build_version", "1"), BUILD_VERSION),
        )
        ahead = [
            (rules, stored, current, _stamp(stored) - _stamp(current))
            for rules, stored, current in built
        ]
        condition = "newer" if newer else "outdated"
        return [
            f"{rules} v{stored} {condition}: current v{current}"
            for rules, stored, current, diff in ahead
            if (diff > 0 if newer else diff < 0)
        ]

    def _connection(self, write: bool = False) -> QueryConnection:
        """A connection for one query, read-only unless *write*."""
        return self._connections.connection(write)

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One connection and one rebuild check for a block's queries (one match)."""
        return self._connections.reading()

    def _init_db(self) -> None:
        """Create the tables with FTS5 (and add what an older version lacked).
        A database made without *create* is only checked: it is written to
        for an older schema, and only if it is licenseid's own file."""
        try:
            state = schema_state(self._connections)
        except DatabaseNotReadyError as exc:
            if self._create:
                state = "none"  # no file yet, or no tables: made below
            elif needs_writing(exc.__cause__):  # a hot journal, or a WAL's -shm
                self._connections.recover()
                state = schema_state(self._connections)
            elif not os.path.lexists(self.db_path):
                raise not_found_error(str(self.db_path)) from exc
            else:
                raise
        if state == "current":
            return  # nothing to write: a read-only open needs no more
        if not self._create:
            reject_foreign_database(self._source)  # never write to another's file
            if state == "none":
                raise empty_error(str(self.db_path))
        with self._connection(write=True) as conn:
            create_schema(conn)

    @staticmethod
    def clear_cache(db_path: str | Path) -> None:
        """Delete the database (unopened) at *db_path* and the cache files
        beside it. Raises :class:`licenseid.DatabaseNotReadyError` for a path
        licenseid did not build a database at, as the CLI does."""
        # Local import: spdx_source pulls in `requests` (~60ms at import),
        # unused on the match path; update_from_remote() defers it too.
        from licenseid import spdx_source

        reject_foreign_database(str(db_path))
        status("Clearing cache...")
        named = named_file(str(db_path))
        if named is None:
            return  # in-memory: no directory to clear
        db_path = Path(named)
        # The database goes first, so a refused delete leaves the cache
        # intact. Its sidecars follow, best effort: once it is gone a stale
        # -wal cannot be replayed, and reporting one would claim the delete
        # failed when it succeeded.
        if db_path.is_symlink() or db_path.exists():
            status(f"Deleting database at {db_path}...")
            db_path.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            with contextlib.suppress(OSError):
                db_path.with_name(db_path.name + suffix).unlink()
        spdx_source.clear_cache_files(db_path.parent)

    def update_from_remote(
        self,
        version: str | None = None,
        force: bool = False,
        use_cache: bool = True,
        source: UpdateSource = "auto",
    ) -> bool:
        """Install a version of the SPDX License List: *version* (default: the
        latest), from *source* (see ``licenseid.releasesource``), unless the
        database already has it and not *force*. Returns True if the database
        was updated, False if it was already up to date."""
        # Local import: releasesource pulls in `requests` (~60ms at import),
        # unused on the match path.
        from licenseid.releasesource import UpdateRequest

        request = UpdateRequest(version, use_cache, source, force)
        try:
            self._connections.leave_wal()  # a database of an earlier version used WAL
            return self._update_from_remote(request)
        except DatabaseNotReadyError as e:
            # A read of this database failed: update words it as its own.
            if e.__cause__ is None:
                raise
            raise LicenseIdError(
                f"database: update failed: {typed(e.__cause__)}"
            ) from e

    def _update_from_remote(self, request: "UpdateRequest") -> bool:
        """``update_from_remote`` without the wording of a failed read."""
        from licenseid import releasesource  # see update_from_remote

        current = self.get_metadata().get("license_list_version")
        chain = releasesource.ReleaseChain(self.db_path.parent, request, current)
        target_version, release_date, ds_licenses = chain.target()
        status(f"Target SPDX License List version: {target_version}")
        # Older build rules need the same release built again.
        force = request.force or bool(self._outdated_rules())
        if current == target_version and not force:
            return _skip(target_version)

        status(f"Updating license database to version {target_version}...")
        data, ds_data = chain.load(target_version)
        if data.version == current and not force:  # a snapshot fallback
            return _skip(data.version)
        # After the data: a skip needs none, and the chain knows by now
        # whether the network is out of reach.
        popularity_map, ds_pop = releasesource.fetch_popularity(
            self.db_path.parent, request.use_cache, chain.offline
        )

        status("Data sources:")
        status(f"  - SPDX License List metadata   : {ds_licenses}")
        status(f"  - SPDX License List data       : {ds_data}")
        status(f"  - GitHub license ranking data  : {ds_pop}")
        self._store(data, popularity_map, release_date)
        return True

    def _store(
        self,
        data: SpdxData,
        popularity_map: dict[str, int],
        release_date: str | None,
    ) -> None:
        """Replace the database's rows with *data*, from any source. Its own
        release date wins over *release_date*, the version lookup's."""
        try:
            release_date = data.release_date or release_date
            status(
                f"Processing {len(data.licenses)} licenses and "
                f"{len(data.exceptions)} exceptions "
                f"(Version: {data.version}, Released: {release_date})"
            )
            self._update_db_records(data, popularity_map, release_date)
            status("\nUpdate complete.")
        except (OSError, sqlite3.Error) as e:
            raise LicenseIdError(f"database: update failed: {fold(str(e))}") from e
        finally:
            end_line()  # a failure mid "Preparing ...": leave stderr at column 0

    def _update_db_records(
        self,
        data: SpdxData,
        popularity_map: dict[str, int],
        release_date: str | None,
    ) -> None:
        """Execute database delete and insert operations."""
        records = build_records(data, popularity_map)
        self._write_db_records(
            records.licenses, records.index_entries, records.exceptions, release_date
        )

        # Compute fingerprints in a separate transaction so that the FTS5
        # virtual table is fully committed and readable before we scan it.
        store_fingerprints(self._connections)
        with self._connection(write=True) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
                ("license_list_version", data.version),
            )
        self._compact()

    def _compact(self) -> None:
        """Return the space of deleted rows to the file (``VACUUM``). A failure
        is a warning: the data is complete and stamped, the file is only
        larger."""
        try:
            with self._connection(write=True) as conn:
                conn.execute("VACUUM")  # no transaction: nothing was written on conn
        except sqlite3.Error as exc:
            warn(f"database: compact failed: {typed(exc)}")

    def _write_db_records(
        self,
        license_records: list[LicenseInsertRecord],
        index_records: list[IndexInsertRecord],
        exception_records: list[ExceptionInsertRecord],
        release_date: str | None,
    ) -> None:
        """Replace all license/exception/metadata rows in a single transaction.

        ``update`` stamps ``license_list_version`` after the fingerprints: a
        run that fails before leaves a database it does not skip."""
        status(f"\nInserting {len(license_records)} records into database...")
        with self._connection(write=True) as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("DELETE FROM license_index")
                conn.execute("DELETE FROM licenses")
                conn.execute("DELETE FROM exceptions")
                conn.execute("DELETE FROM db_metadata")
                conn.execute("DELETE FROM license_fingerprints")

                now = datetime.now(timezone.utc).isoformat()
                metadata_items: list[tuple[str, str]] = [
                    ("release_date", release_date or ""),
                    ("last_check_datetime", now),
                    ("last_update_datetime", now),
                    ("normalization_version", NORMALIZATION_VERSION),
                    ("build_version", BUILD_VERSION),
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
            finally:
                self._tables.clear()

    def find_fingerprint_hits(self, norm_input: str) -> dict[str, float]:
        """Map each licence ID to the best idf_norm of the fingerprint n-grams it
        shares with *norm_input* (see ``fingerprintstore.fingerprint_hits``)."""
        return fingerprint_hits(self._connections, norm_input)

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
        # Each word is quoted: a word is a phrase to FTS5, never an operator,
        # so a query cannot fail for its own text and every error is the
        # database's.
        search_terms = " OR ".join(
            '"' + word.replace('"', '""') + '"' for word in words
        )

        with self._connection() as conn:
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
            cursor = conn.execute(query, (search_terms, limit))
            return [cast(CandidateMatch, dict(row)) for row in cursor.fetchall()]

    def get_license_details(self, license_id: str) -> LicenseDetails | None:
        """Get full metadata for a license (ASCII case-insensitive lookup)."""
        found = self._tables.license_id(license_id.strip())
        return None if found is None else self._license_row(found)

    def _license_row(self, license_id: str) -> LicenseDetails | None:
        """The ``licenses`` row of *license_id*, in its exact case."""
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM licenses WHERE license_id = ?", (license_id,)
            ).fetchone()
            return cast_license_details(row) if row else None

    def get_license_by_name(self, name: str) -> LicenseDetails | None:
        """Get full metadata for a license by its full name (case-insensitive)."""
        clean_name = name.strip()
        if not clean_name:
            return None
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM licenses WHERE name = ? COLLATE NOCASE",
                (clean_name,),
            ).fetchone()
            if not row:
                return None
            return cast_license_details(row)

    def get_exception_details(self, exception_id: str) -> ExceptionDetails | None:
        """Get full metadata for an exception (case-insensitive lookup)."""
        clean_id = exception_id.strip()
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM exceptions WHERE exception_id = ? COLLATE NOCASE",
                (clean_id,),
            ).fetchone()
            if not row:
                return None
            return self._cast_exception_details(row)

    def _cast_exception_details(self, row: sqlite3.Row) -> ExceptionDetails:
        """Helper to cast sqlite Row to ExceptionDetails with proper boolean types."""
        d = dict(row)
        if "is_deprecated" in d:
            d["is_deprecated"] = bool(d["is_deprecated"])
        return cast(ExceptionDetails, d)

    def get_search_text(self, license_id: str) -> str:
        """Return the normalized search text for a license from the FTS index."""
        rowid = self._tables.index_row(license_id)
        if rowid is None:
            return ""
        with self._connection() as conn:
            # The ID too: a rebuild during this match may move the rows.
            row = conn.execute(
                "SELECT search_text FROM license_index"
                " WHERE rowid = ? AND license_id = ?",
                (rowid, license_id),
            ).fetchone()
            return row[0] if row else ""

    def get_all_names_and_ids(self) -> list[LicenseNameId]:
        """Retrieve all license IDs and names for short-text matching.

        Read once per instance (see dbcache.TableCache): this is queried on
        every Tier-0 short-text match.
        """
        return self._tables.names_and_ids()

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> dict[str, list[LicenseNameId]]:
        """get_all_names_and_ids() by *key* of each ID (see
        dbcache.TableCache.names_by_key)."""
        return self._tables.names_by_key(key)

    def get_active_ids_by_name(self) -> dict[str, list[str]]:
        """The licence IDs in use by case-folded name (see
        dbcache.TableCache.active_ids_by_name)."""
        return self._tables.active_ids_by_name()

    def get_deprecated_mappings(self) -> dict[str, str]:
        """The deprecated IDs that have a successor, each with it: the licences
        in table order, then the exceptions (an exception wins a clash)."""
        return self._tables.deprecated()

    def get_metadata(self) -> DatabaseMetadata:
        """Get database metadata."""
        with self._connection() as conn:
            cursor = conn.execute("SELECT key, value FROM db_metadata")
            return cast(DatabaseMetadata, {row[0]: row[1] for row in cursor.fetchall()})


def _skip(version: str) -> bool:
    """Report that the database already has *version*; False: not updated."""
    status(f"Database is already at version {version}. Skipping update.")
    return False
