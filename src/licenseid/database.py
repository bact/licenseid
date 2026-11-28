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
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

from licenseid.console import end_line, status
from licenseid.dbcache import TableCache, cast_license_details
from licenseid.dbcheck import (
    absolute_path,
    is_absent,
    is_memory_database,
    named_file,
    needs_writing,
    not_found_error,
    reject_blank_path,
    reject_foreign_database,
)
from licenseid.dbclear import clear_database
from licenseid.dbconnection import Connections, QueryConnection
from licenseid.dbhandle import DatabaseHandle
from licenseid.dbschema import (
    BUILD_VERSION,
    NORMALIZATION_VERSION,
    create_schema,
    has_shape,
    replace_schema,
    stamp,
    stamped_rules,
)
from licenseid.dbverdict import (
    NEWER,
    Refusal,
    connection_refusal,
    rebuild_refusal,
)
from licenseid.errors import DatabaseNotReadyError, LicenseIdError, fold, typed
from licenseid.fingerprintstore import fingerprint_hits, store_fingerprints
from licenseid.gramselect import ListFlags
from licenseid.gramstore import write_postings
from licenseid.listlookup import ListedUrl
from licenseid.records import Records, build_records
from licenseid.spdxdata import SpdxData
from licenseid.textentries import write_checks
from licenseid.textgrams import GramTable
from licenseid.types import (
    CandidateMatch,
    DatabaseMetadata,
    ExceptionDetails,
    LicenseDetails,
    LicenseNameId,
    TextParts,
    UpdateSource,
)
from licenseid.warning import warn

if TYPE_CHECKING:
    from licenseid.nameindex import NameIndex
    from licenseid.releasesource import UpdateRequest
    from licenseid.textentries import StoredTexts


def is_current_build(metadata: DatabaseMetadata) -> bool:
    """Whether a database's rows were built by this licenseid's rules
    (``dbschema.BUILD_VERSION``): not newer, as ``build vN newer`` warns (an
    older one is not ready)."""
    return stamp(metadata.get("build_version", "1")) == stamp(BUILD_VERSION)


class LicenseDatabase(DatabaseHandle):
    """
    Handles SQLite database operations for storing and searching SPDX licenses.
    """

    # Whether opening without *create* judges the file (``dbverdict``); not
    # when check_database_ready has just judged it (judged_database).
    _judge = True

    def __init__(
        self,
        db_path: str | os.PathLike[str],
        create: bool = True,
    ):
        """Open the database at *db_path*. With *create* (the default) a
        file with none of licenseid's tables gets them, a file that is not
        there is made by the first write (``update_from_remote``), never by
        opening the handle or by a read, so a mistyped name leaves nothing
        behind, and any other is left to ``update``, which builds its tables
        again from nothing.

        Without *create* the handle only reads: the file must be ready to
        answer, as :func:`licenseid.dbcheck.check_database_ready` says (of
        this build's shape, its rules not older than this licenseid's), or it
        is :class:`licenseid.DatabaseNotReadyError` (``not found``, ``empty``,
        ``invalid``, ``build vN outdated``), and nothing is written. Rules
        newer than this licenseid's are warned (``database: build vN newer:
        ...``, a :class:`licenseid.LicenseIdWarning`).

        Either way a file that licenseid did not build, and that is not
        empty, is :class:`licenseid.DatabaseNotReadyError` (``invalid``):
        another program's tables are never written to. A blank *db_path* is
        :class:`licenseid.InvalidInputError`, as for ``LicenseDetector``."""
        db_path = os.fspath(db_path)
        reject_blank_path(db_path, "db_path", optional=False)
        self._create = create
        self._schema_pending = False  # a file to make by the first write
        named = named_file(db_path)  # a URI: the file it names
        self.db_path = Path(absolute_path(named) if named else db_path)
        self.use_uri = db_path.startswith("file:")  # Path() rewrites a URI
        self._source = db_path if self.use_uri else str(self.db_path)
        #: The path or ``file:`` URI this database was opened with, as
        #: :func:`licenseid.dbcheck.check_database_ready` reads it.
        self.location: str = self._source
        self._connections = Connections(
            self._source, self.use_uri, str(self.db_path), create
        )
        self._keep_alive: sqlite3.Connection | None = None

        if is_memory_database(self._source):
            # An in-memory database goes when its last connection closes.
            self._keep_alive = self._connections.connect(write=True)

        if create:
            self._init_schema()
        metadata = None if create else self._check_ready()
        self._tables = TableCache(self._connections)
        if metadata is not None:
            for condition, detail in stamped_rules(metadata, newer=True):
                warn("database", condition, detail)

    def _connection(self, write: bool = False) -> QueryConnection:
        """A connection for one query, read-only unless *write*."""
        return self._connections.connection(write)

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One connection and one rebuild check for a block's queries (one match)."""
        return self._connections.reading()

    def _check_ready(self) -> DatabaseMetadata:
        """Without *create*: raise the refusal of a file that cannot answer
        (``dbverdict.connection_refusal``, unless :func:`judged_database`
        opened it), else read its metadata, through this handle's own connection.
        Its tables are never written: a lookup never writes."""
        try:
            judged = self._judged()
        except DatabaseNotReadyError as exc:
            if needs_writing(exc.__cause__):  # a hot journal, or a WAL's -shm
                self._connections.recover()
                judged = self._judged()
            elif is_absent(str(self.db_path)):
                raise not_found_error(str(self.db_path)) from exc
            else:
                raise
        if isinstance(judged, tuple):
            raise judged[1]
        return judged

    def _judged(self) -> Refusal | DatabaseMetadata:
        """The refusal of the file, or its metadata, in one read."""
        with self._connection() as conn:
            if self._judge:
                refusal = connection_refusal(conn, str(self.db_path))
                if refusal is not None:
                    return refusal
            return _metadata(conn)

    def _refusal(self) -> Refusal | None:
        """The verdict on this file for ``update``
        (``dbverdict.rebuild_refusal``), through a read."""
        with self._connection() as conn:
            return rebuild_refusal(conn, str(self.db_path))

    def _init_schema(self) -> None:
        """With *create*: leave a missing file to the first write, and refuse
        another program's file. A file with none of licenseid's tables gets
        them now; one with some of them, of an older build or not, is left as
        it is: ``update`` replaces them whole (``dbschema.replace_schema``)."""
        try:
            with self._connection() as conn:
                shaped = has_shape(conn)
                bare = not conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = 'licenses'"
                ).fetchone()
        except DatabaseNotReadyError:
            if self._is_missing():
                self._schema_pending = True  # made by the first write
                return
            shaped, bare = False, True  # no tables that can be read: made below
        if shaped:
            return  # nothing to judge or write
        reject_foreign_database(self._source)  # never write to another's file
        if bare:
            with self._connection(write=True) as conn:
                create_schema(conn)

    def _reject_foreign(self) -> None:
        """Refuse a file that is not licenseid's to write to (an in-memory
        database has none)."""
        if not is_memory_database(self._source):
            reject_foreign_database(self._source)

    def _is_missing(self) -> bool:
        """Whether the file this database names is not there (an in-memory
        database, and a name only SQLite can resolve, are never missing)."""
        return (
            not is_memory_database(self._source)
            and named_file(self._source) is not None
            and not os.path.exists(self.db_path)
        )

    def _ensure_schema(self) -> None:
        """Judge the file before a write, and make it and its tables if
        opening left that to the first write.

        Every write path is fail-closed (a file licenseid did not build, or
        one that cannot be judged, such as a lock, is refused); a read stays
        fail-open. The file may have appeared since opening, and could be
        another program's."""
        self._reject_foreign()
        if not self._schema_pending:
            return
        with self._connection(write=True) as conn:
            create_schema(conn)
        self._schema_pending = False

    @staticmethod
    def clear_cache(db_path: str | os.PathLike[str]) -> bool:
        """Delete the database (unopened) at *db_path* and, where they are
        licenseid's, the cache files beside it (``dbclear.clear_database``);
        True if there was any of them to delete. Raises
        :class:`licenseid.DatabaseNotReadyError` for a path licenseid did not
        build a database at, as the CLI does."""
        return clear_database(db_path)

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
            self._judge_before_update()
            if not self._schema_pending:  # else there is no file to convert
                self._connections.leave_wal()  # an earlier version used WAL
            return self._update_from_remote(request)
        except DatabaseNotReadyError as e:
            # A read of this database failed: update words it as its own.
            if e.__cause__ is None:
                raise
            raise LicenseIdError(
                f"database: update failed: {typed(e.__cause__)}"
            ) from e

    def _judge_before_update(self) -> None:
        """What ``update_from_remote`` settles before it writes or downloads.

        A file made since opening (another process's update) is judged as at
        opening: refused, completed, or found current, with the rules it was
        built by (a newer licenseid's file is never written but with
        *force*: ``_update_from_remote``). A file that is not licenseid's is
        refused before ``leave_wal`` writes its journal mode. A name in a
        directory that is not there fails now, as it does when
        the file is made, not after a download."""
        if self._schema_pending and not self._is_missing():
            self._schema_pending = False
            self._init_schema()
        self._reject_foreign()
        if self._schema_pending and not (
            Path(os.path.realpath(self.db_path)).parent.is_dir()
        ):
            raise LicenseIdError(
                "database: update failed: OperationalError: "
                "unable to open database file"
            )

    def _update_from_remote(self, request: "UpdateRequest") -> bool:
        """``update_from_remote`` without the wording of a failed read."""
        from licenseid import releasesource  # see update_from_remote

        pending = self._schema_pending  # no file yet: nothing to read or skip
        current = None if pending else self.get_metadata().get("license_list_version")
        chain = releasesource.ReleaseChain(self.db_path.parent, request, current)
        target_version, release_date, ds_licenses = chain.target()
        status(f"Target SPDX License List version: {target_version}")
        # A file of older rules, or of another shape, needs the same release
        # built again. One a newer licenseid built (``newer``, readable or
        # not) is never written but with --force: left as it is at its
        # release, else refused.
        refusal = None if pending else self._refusal()
        if refusal is not None and refusal[0] == NEWER and not request.force:
            if current == target_version:
                return _skip(target_version)
            raise refusal[1]
        force = request.force or refusal is not None
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
        """Write the rows of *data*, then its fingerprints and version stamp,
        and compact the file."""
        self._write_db_records(build_records(data, popularity_map), release_date)

        # Fingerprints in a transaction of their own, read from the texts
        # the one before committed.
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
            warn("database", "compact failed", typed(exc))

    def _write_db_records(self, records: Records, release_date: str | None) -> None:
        """Replace every table, and all licence, exception, URL, metadata
        and postings rows, in a single transaction.

        ``update`` stamps ``license_list_version`` after the fingerprints: a
        run that fails before leaves a database it does not skip."""
        status(f"\nInserting {len(records.licenses)} records into database...")
        self._ensure_schema()
        with self._connection(write=True) as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                replace_schema(conn)  # whatever build made the file

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
                        norm_license_id, norm_name,
                        core_text, core_word_count, same_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    records.licenses,
                )
                conn.executemany(  # text_id: 1, 2, ... in List order
                    "INSERT INTO license_texts (license_id, search_text) VALUES (?, ?)",
                    records.index_entries,
                )
                conn.executemany(
                    "INSERT INTO exceptions "
                    "(exception_id, name, is_deprecated, superseded_by) "
                    "VALUES (?, ?, ?, ?)",
                    records.exceptions,
                )
                conn.executemany(
                    "INSERT INTO license_urls (owner_id, is_exception, url)"
                    " VALUES (?, ?, ?)",
                    records.urls,
                )
                conn.executemany(
                    "INSERT INTO text_codes (kind, owner_id, body) VALUES (?, ?, ?)",
                    records.texts,
                )
                # Read back as a lookup reads them, with the rows' time.
                write_checks(conn, now)
                # Read back from the rows just written: the postings are
                # those of the texts a lookup reads, stamped with them.
                write_postings(conn, now)
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
        """An ``exceptions`` row as ExceptionDetails, its flag made bool."""
        d = dict(row)
        if "is_deprecated" in d:
            d["is_deprecated"] = bool(d["is_deprecated"])
        return cast(ExceptionDetails, d)

    def get_search_text(self, license_id: str) -> str:
        """The normalised text of a licence (exact case), or ``""``."""
        rowid = self._tables.index_rows().get(license_id)
        if rowid is None:
            return ""
        with self._connection() as conn:
            # The ID too: a rebuild during this match may move the rows.
            row = conn.execute(
                "SELECT search_text FROM license_texts"
                " WHERE rowid = ? AND license_id = ?",
                (rowid, license_id),
            ).fetchone()
            return row[0] if row else ""

    def get_all_names_and_ids(self) -> list[LicenseNameId]:
        """Retrieve all license IDs and names for short-text matching.

        Read once per rebuild of the tables (see dbcache.TableCache): this
        is queried on every Tier-0 short-text match.
        """
        return self._tables.names_and_ids()

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> dict[str, list[LicenseNameId]]:
        """get_all_names_and_ids() by *key* of each ID (see
        dbcache.TableCache.names_by_key)."""
        return self._tables.names_by_key(key)

    def get_ids_by_url(
        self, key: Callable[[str], str | None]
    ) -> dict[str, list[ListedUrl]]:
        """The licences, then the exceptions, that list a page, by *key* of
        its URL (see dbcache.TableCache.ids_by_url)."""
        return self._tables.ids_by_url(key)

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
            return _metadata(conn)


def _metadata(conn: sqlite3.Connection) -> DatabaseMetadata:
    """The rows of ``db_metadata``, by key."""
    cursor = conn.execute("SELECT key, value FROM db_metadata")
    return cast(DatabaseMetadata, {row[0]: row[1] for row in cursor.fetchall()})


class _JudgedDatabase(LicenseDatabase):
    """A handle opened right after ``check_database_ready`` judged its file
    (:func:`judged_database`): opening reads the metadata, never the verdict
    again. A file gone since is ``not found``, a hot journal is rolled back,
    as for a handle that judges."""

    _judge = False


def judged_database(db_path: str | os.PathLike[str]) -> LicenseDatabase:
    """The handle a lookup reads *db_path* through, right after
    :func:`licenseid.dbcheck.check_database_ready` passed it: the verdict is
    made once (``LicenseDatabase(db_path, create=False)`` makes it again)."""
    return _JudgedDatabase(db_path, create=False)


def _skip(version: str) -> bool:
    """Report that the database already has *version*; False: not updated."""
    status(f"Database is already at version {version}. Skipping update.")
    return False


def exception_words(db: LicenseDatabase) -> list[frozenset[str]]:
    """The normalised words of each exception's name and ID of *db* (see
    dbcache.TableCache.exception_words): a function, not a method, so the
    class keeps its public methods."""
    return db._tables.exception_words()  # pylint: disable=protected-access


def text_parts(db: LicenseDatabase) -> dict[str, TextParts]:
    """The core and the same-text group of each licence that has one (see
    ``dbcache.TableCache.text_parts``): a function, not a method, as the
    class has as many public ones as the linter allows."""
    return db._tables.text_parts()  # pylint: disable=protected-access


def gram_scores(
    db: LicenseDatabase, norm_text: str, limit: int | None = None
) -> GramTable:
    """The List texts that share a word 3-gram with *norm_text* (normalised),
    each with its shared grams, size and score, in row order (see
    ``licenseid.gramstore``): from the stored postings when they are those of
    the rows, else from an index built in memory. Only the first *limit* of
    its distinct grams are looked up when given; the table says so
    (``bounded``)."""
    texts = db._tables.texts()  # pylint: disable=protected-access
    return texts.gram_scores(norm_text, limit)


def list_flags(db: LicenseDatabase) -> dict[str, ListFlags]:
    """What the filters of ``detect()`` read of each licence, by ID (see
    ``dbcache.TableCache.list_flags``)."""
    return db._tables.list_flags()  # pylint: disable=protected-access


# The columns of a candidate: its text, the rest from its licence row.
_CANDIDATE_ROWS = """
    SELECT
        t.license_id,
        t.search_text,
        l.word_count,
        l.is_spdx,
        l.is_high_usage,
        l.is_osi_approved,
        l.is_fsf_libre,
        l.pop_score,
        l.is_deprecated,
        l.superseded_by
    FROM license_texts t
    JOIN licenses l ON t.license_id = l.license_id
    WHERE t.rowid IN ({})
"""


def candidate_rows(db: LicenseDatabase, ids: Sequence[str]) -> list[CandidateMatch]:
    """The candidates of Tier 2 for the licences *ids* (exact case), in that
    order, each with its text: one query, by the rowid of each text (the
    first row of an ID, as ``text_posting_ids`` numbers them). An ID with no
    text or no row is left out. At most ``gramselect.MOST`` IDs are asked,
    well under SQLite's limit of bound values."""
    tables = db._tables  # pylint: disable=protected-access
    index = tables.index_rows()
    rowids = [index[license_id] for license_id in ids if license_id in index]
    if not rowids:
        return []
    with db._connection() as conn:  # pylint: disable=protected-access
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            _CANDIDATE_ROWS.format(", ".join("?" * len(rowids))), rowids
        ).fetchall()
    found = {row["license_id"]: cast(CandidateMatch, dict(row)) for row in rows}
    return [found[i] for i in dict.fromkeys(ids) if i in found]


def text_source(db: LicenseDatabase) -> "StoredTexts":
    """The coded texts of the List one call reads for the search of the
    texts an input holds whole and for Tier 2, entry by entry (see
    ``licenseid.textentries``)."""
    return db._tables.texts().source()  # pylint: disable=protected-access


def snapshot(db: LicenseDatabase) -> contextlib.AbstractContextManager[None]:
    """One read transaction for the queries of a block (see
    ``dbcache.TableCache.snapshot``): the postings, ids and coded texts of
    one call are read in it."""
    return db._tables.snapshot()  # pylint: disable=protected-access


def name_index(db: LicenseDatabase) -> "NameIndex":
    """What the name tier reads from the names of *db*, worked out once per
    rebuild of its tables (see ``dbcache.TableCache.name_index``); its
    ``rows`` are ``db.get_all_names_and_ids()``."""
    return db._tables.name_index()  # pylint: disable=protected-access
