# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Command-line interface for the licenseid tool.
"""

import os
import re
import sqlite3
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn, get_args

import click

from licenseid import __version__, console
from licenseid.clicommon import (
    LicenseIdCommand,
    echo_record,
    exit_bad_input,
    exit_usage_error,
    json_option,
    piped_input,
    reject_blank_options,
    reject_unencodable,
)
from licenseid.climatch import match_command
from licenseid.console import end_line, error, warn, write
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import (
    check_database_ready,
    delete_failed_error,
    reject_foreign_database,
    unreadable_error,
)
from licenseid.detector import LicenseDetector
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
    invalid_id_error,
    one_line,
    shown,
)
from licenseid.exprtokens import is_license_ref
from licenseid.identifiers import is_simple_expression
from licenseid.output import (
    EchoHelpCommand,
    OutputError,
    echo,
    echo_json,
    output_failed,
)
from licenseid.result import json_line, text_line
from licenseid.textinput import (
    decode_input,
    looks_like_path,
    normalize_newlines,
    read_text_file,
)
from licenseid.types import Detection, UpdateSource
from licenseid.usage import UsageLineError, UsageLineGroup


def show_diff(norm_input: str, best_window: str) -> None:
    """Show word-by-word diff between the normalised input and the window
    of the license text it matched."""
    import difflib  # pylint: disable=import-outside-toplevel

    input_words = norm_input.split()
    window_words = best_window.split()

    diff_lines = list(
        difflib.unified_diff(
            window_words, input_words, fromfile="DATABASE", tofile="INPUT", lineterm=""
        )
    )
    if not diff_lines:
        return
    # On standard error, as progress is: standard output holds only result
    # lines. Coloured only on a terminal.
    colour = _is_terminal(sys.stderr)
    console.status("\nWORD DIFF:")
    for line in diff_lines:
        fg = {"+": "green", "-": "red"}.get(line[:1])
        console.status(click.style(line, fg=fg) if colour and fg else line)
    console.status("")


def _is_terminal(stream: Any) -> bool:
    try:
        return stream is not None and bool(stream.isatty())
    except (AttributeError, OSError, ValueError):  # no stream, or closed
        return False


def check_db_staleness(database: LicenseDatabase) -> None:
    """Check if the database is older than 6 months and warn the user."""
    metadata = database.get_metadata()
    last_check = metadata.get("last_check_datetime")
    if last_check:
        try:
            last_check_dt = datetime.fromisoformat(last_check)
            if last_check_dt.tzinfo is None:
                # Databases written before this timestamp became
                # tz-aware stored a naive local-time value; treat it as
                # UTC rather than crashing on the subtraction below (this
                # is only a rough 6-month staleness check, not something
                # that needs to account for the original local offset).
                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - last_check_dt).days
            if days_old > 182:  # Approx 6 months
                warn(f"database: {days_old} days old; run 'licenseid update'")
        except (TypeError, ValueError):
            pass


def make_default_db_dir(ctx: click.Context) -> None:
    """Create the directory of the default database path, if that is the one
    in use. Reading and clearing never create it; ``update`` does, because
    ``LicenseDatabase`` opens (and so creates) the file."""
    if ctx.obj["db_is_default"]:
        Path(ctx.obj["db_path"]).parent.mkdir(parents=True, exist_ok=True)


def clear_local_cache(ctx: click.Context, db_path: str) -> None:
    """Clear the cache files beside *db_path* and the database itself.

    ``clear_cache`` refuses a file licenseid did not build (one mistyped
    ``--db`` must not destroy another program's database); the group turns
    that refusal into exit 2. A delete the system refuses is reported here,
    naming the file that actually failed, with exit 1: the command was
    understood and failed, as an update that fails does.
    """
    try:
        LicenseDatabase.clear_cache(db_path)
    except OSError as exc:
        failed = exc.filename or db_path
        error(str(delete_failed_error(str(failed), exc)))
        ctx.exit(1)


class DatabaseErrorGroup(UsageLineGroup, EchoHelpCommand):
    """A group that never lets a failure pass for an answer.

    ``detect`` and the ``is-*`` commands answer "no" with exit 1, so an unready
    database (``DatabaseNotReadyError``) must not share it. A file can also go
    bad after the readiness check (replaced or corrupted mid-run): a SQLite
    failure is then worded as an ``unreadable`` database, not a traceback.
    The detector words its own the same way (``DatabaseNotReadyError``), and
    that includes a ProgrammingError or InterfaceError: the original stays
    the ``__cause__`` for whoever debugs it.

    Click itself would exit 1 for both an interrupt (Ctrl-C) and a closed
    pipe. An interrupt exits 130 (128 + SIGINT), as the shell reports a
    killed command; a pipe whose reader has gone (``| head -1``) exits 141
    (128 + SIGPIPE) quietly, as ``cat`` and ``grep`` do; any other output
    that cannot be written exits 2 with an ``output`` error.
    """

    command_class = LicenseIdCommand

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except KeyboardInterrupt as exc:
            end_line()
            raise click.exceptions.Exit(130) from exc
        except OutputError as exc:
            raise click.exceptions.Exit(output_failed(exc)) from exc
        except DatabaseNotReadyError as exc:
            exit_usage_error(ctx, str(exc))
        except sqlite3.Error as exc:
            exit_usage_error(ctx, str(unreadable_error(ctx.obj["db_path"], exc)))


class _WithoutDatabase(dict[str, Any]):
    """The context of a run with no default database to name (no home
    directory): help and a bare run need none, so the error waits for the first
    command that reads ``db_path``."""

    def __init__(self, cause: DatabaseNotReadyError, items: dict[str, Any]) -> None:
        super().__init__(items)
        self.cause = cause

    def __missing__(self, key: str) -> Any:
        raise self.cause


def show_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """``--version``: ``licenseid <version>`` on standard output, before the
    group's own options are read, so no database path is looked up."""
    if value and not ctx.resilient_parsing:
        echo(f"licenseid {__version__}")
        ctx.exit()


@click.group(cls=DatabaseErrorGroup, invoke_without_command=True)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=show_version,
    help="Print the version and exit.",
)
@click.option("--db", help="Path to the license database.")
@click.option("--clear-cache", is_flag=True, help="Clear local cache and exit.")
@click.pass_context
def cli(ctx: click.Context, db: str | None, clear_cache: bool) -> None:
    """SPDX License ID matcher tool."""
    if db is not None and not db.strip():
        # Silently falling back to the default database would answer from a
        # file the user did not ask for. Every other blank option is a usage
        # error too (see reject_blank_options).
        exit_usage_error(ctx, "database: missing: --db; pass a path or drop --db")
    ctx.ensure_object(dict)
    ctx.obj["db_is_default"] = not db
    try:
        ctx.obj["db_path"] = db or get_default_db_path()
    except DatabaseNotReadyError as exc:
        ctx.obj = _WithoutDatabase(exc, ctx.obj)

    if clear_cache:
        clear_local_cache(ctx, ctx.obj["db_path"])
        ctx.exit()

    if ctx.invoked_subcommand is None:
        # A usage error, not a result: the help goes to standard error.
        write(ctx.get_help() + "\n")
        ctx.exit(2)


@cli.command()
@click.option("--version", default=None, help="SPDX License List version to download.")
@click.option("--force", is_flag=True, help="Force update even if version matches.")
@click.option(
    "--cache/--no-cache",
    "use_cache",
    default=True,
    help="Use local cache for downloads (default: true).",
)
@click.option(
    "--source",
    type=click.Choice(get_args(UpdateSource)),
    default="auto",
    show_default=True,
    help="Where to get the license list: compact (our 1 MB bundle), upstream "
    "(SPDX's tarball), packaged (the copy shipped with licenseid), or each in "
    "turn (auto).",
)
@json_option
@click.pass_context
def update(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: click.Context,
    version: str | None,
    force: bool,
    use_cache: bool,
    source: UpdateSource,
    json_output: bool,
) -> None:
    """Update the license database from remote sources.

    Prints one record: STATUS=updated or unchanged, the list VERSION the
    database now has, and its PATH.
    """
    db_path = ctx.obj["db_path"]
    # It writes the schema on open, so never into somebody else's file. Kept
    # outside the try: an unready database is a setup error (exit 2), not an
    # update that failed (exit 1).
    reject_foreign_database(db_path)
    try:
        make_default_db_dir(ctx)
        database = LicenseDatabase(db_path)
        updated = database.update_from_remote(
            version=version, force=force, use_cache=use_cache, source=source
        )
        outcome = "updated" if updated else "unchanged"
        installed = database.get_metadata().get("license_list_version")
    except InvalidInputError as e:
        exit_usage_error(ctx, str(e))
    except LicenseIdError as e:
        # Already worded "SUBJECT: CONDITION...".
        error(str(e))
        ctx.exit(1)
    except Exception as e:
        # Anything else (e.g. KeyError or RecursionError from malformed
        # release data) has no subject of its own; name the type.
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        error(f"database: update failed: {detail}")
        ctx.exit(1)
    # Outside the try: an output failure is not a failed update.
    echo_record(json_output, STATUS=outcome, VERSION=installed, PATH=db_path)


# Python's string escapes. Octal stops at \377: \400-\777 give a
# DeprecationWarning on Python 3.12+ and are to become invalid, so they are
# left unchanged on every version.
_ESCAPE_RE = re.compile(
    r"\\(?:[\\'\"abfnrtv]|[0-3][0-7]{2}|[0-7]{1,2}(?![0-7])"
    r"|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|N\{[^}]+\})"
)


def unescape_text(text: str) -> str:
    """Decode Python backslash escapes (e.g. ``\\n``) in *text*.

    Only the escape sequences are decoded, so other non-ASCII characters are
    kept as is; an unknown or invalid escape is left unchanged.
    """
    return _ESCAPE_RE.sub(_decode_escape, text)


def _decode_escape(escape: re.Match[str]) -> str:
    try:
        return escape.group(0).encode("ascii").decode("unicode_escape")
    except UnicodeDecodeError:  # e.g. \U00110000, beyond U+10FFFF
        return escape.group(0)


def exit_no_input(ctx: click.Context) -> NoReturn:
    """Exit with a usage error (2) because no input was given."""
    exit_bad_input(ctx, "missing; pass a file, an ID, --text, --id or stdin")


def read_input(ctx: click.Context, path: str | None) -> str:
    """Read the file at *path*, or standard input if None, as text.
    Exit with a usage error (2) if it cannot be read, is binary, or is a file
    with no text (empty stdin is left to the caller's "input: missing")."""
    source = path if path is not None else "stdin"
    piped_nothing = False
    try:
        if path is not None:
            text = read_text_file(path)
        else:
            if (buffer := getattr(sys.stdin, "buffer", None)) is not None:
                data = buffer.read()
            else:  # stdin replaced by a text-only stream
                data = sys.stdin.read().encode("utf-8", "surrogatepass")
            piped_nothing = not data
            text = decode_input(data, source)
    except OSError as e:
        exit_bad_input(ctx, f"unreadable: {shown(source)}: {e.strerror or e}")
    except InvalidInputError as e:  # binary data; already "input: ..."
        exit_usage_error(ctx, str(e))
    # No bytes at all on stdin means nothing was piped: "input: missing".
    if not piped_nothing and not text.strip():
        exit_bad_input(ctx, f"empty: {shown(source)}")
    return text


def reject_compound_id(ctx: click.Context, id_val: str | None) -> None:
    """Exit with a usage error (2) if --id does not name one license.

    --id is a declaration: "MIT OR Apache-2.0" declares neither license, and
    a name or an SPDX URL is not an ID. A file's tag may still hold any of
    them, so the reading of a file is unaffected.
    """
    if id_val and not is_simple_expression(id_val):
        exit_usage_error(ctx, str(invalid_id_error("--id", id_val)))


def read_text_option(ctx: click.Context, text: str) -> str:
    """Decode the escapes in --text, then treat it as file or stdin text is
    treated: LF line ends; exit 2 if binary (a NUL), blank or not encodable."""
    content = normalize_newlines(unescape_text(text))
    reject_unencodable(ctx, content, binary_source="--text")
    if not content.strip():
        exit_bad_input(ctx, "empty: --text")
    return content


def names_licences(db: LicenseDatabase, value: str) -> bool:
    """Whether every part of a "/"-joined *value* is a licence ID or a
    ``LicenseRef-*`` ("MIT/Apache-2.0", Cargo's old way to write OR): a
    declared value, not a path, whatever its shape."""
    return all(
        is_license_ref(part) or db.get_license_details(part)
        for part in value.split("/")
    )


def get_input_content(
    ctx: click.Context, input_val: str | None, text: str | None, db: LicenseDatabase
) -> str:
    """The input to match: --text, else the argument (a file if one exists by
    that name, a usage error if it is shaped like a path and names no
    licence, else the value itself), else stdin; "" if there is none."""
    if text is not None:
        return read_text_option(ctx, text)
    if input_val:
        if os.path.exists(input_val):
            return read_input(ctx, input_val)
        reject_unencodable(ctx, input_val)
        if looks_like_path(input_val) and not names_licences(db, input_val):
            # a mistyped path is no text to match
            exit_bad_input(ctx, f"not found: {one_line(input_val)}; pass --text")
        return input_val
    if piped_input():  # a closed one is no input, not a crash
        return read_input(ctx, None)
    return ""


def detect_license_record(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None = None,
) -> Detection | None:
    """Helper to detect a license from CLI arguments (implements Smart Logic)."""
    db_path = ctx.obj["db_path"]
    check_database_ready(db_path)  # before input handling: report the database first

    reject_blank_options(ctx, {"--id": id_val, "--text": text, "argument": input_val})
    reject_compound_id(ctx, id_val)
    detector = LicenseDetector(db_path)
    check_db_staleness(detector.db)

    # 1. Explicit ID
    if id_val:
        return detector.resolve_record(license_id=id_val)

    # 2. Handle stdin/arguments
    content = get_input_content(ctx, input_val, text, detector.db)
    if not content:
        exit_no_input(ctx)

    # A lone expression is read as an ID by the detector, whatever brings it.
    return detector.resolve_record(content)


@cli.command(name="detect")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to match.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to lookup.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON Lines, one RFC 8785 object per result.",
)
@click.option(
    "--threshold", type=float, default=0.85, help="Minimum score, from 0 to 1."
)
@click.option(
    "--exact",
    "exact_only",
    is_flag=True,
    help="Keep only exact matches: declared, an exact ID or name, a whole text.",
)
@click.option("--top", type=int, default=3, help="Maximum number of results to return.")
@click.option(
    "--pop/--no-pop",
    "enable_popularity",
    default=False,
    help="Enable/disable popularity score weighting.",
)
@click.option(
    "--diff",
    is_flag=True,
    help="Show a word diff for the top match when it is a close text match, "
    "on standard error.",
)
@click.option("--bold", is_flag=True, help="Print only the top license ID.")
@click.pass_context
def detect(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
    json_output: bool,
    threshold: float,
    exact_only: bool,
    top: int,
    enable_popularity: bool,
    diff: bool,
    bold: bool,
) -> None:
    """Identify license text and return the closest matched SPDX License ID.

    One tab separates the fields of a line: read them with cut -f or
    awk -F'\\t'.
    """
    db_path = ctx.obj["db_path"]

    check_database_ready(db_path)  # before input handling: report the database first
    reject_blank_options(ctx, {"--id": id_val, "--text": text, "argument": input_val})
    reject_compound_id(ctx, id_val)
    # A score is 0-1: a threshold outside it means nothing (above 1, or
    # nan, would keep nothing).
    if not 0.0 <= threshold <= 1.0:
        exit_usage_error(
            ctx, f"option: invalid: --threshold: {threshold}; pass a value from 0 to 1"
        )

    detector = LicenseDetector(db_path, enable_popularity=enable_popularity)
    check_db_staleness(detector.db)

    if id_val:
        results = detector.detect(license_id=id_val)
        license_text = ""
    else:
        content = get_input_content(ctx, input_val, text, detector.db)
        if not content:
            exit_no_input(ctx)

        license_text = content
        # A lone expression is read as an ID by the detector, whatever brings it.
        results = detector.detect(text=content)

    # Filter by threshold (and exactness), then limit to top N
    results = [
        r for r in results if r["score"] >= threshold and (r["exact"] or not exact_only)
    ][:top]

    if not results:  # "no" is an answer, as is-* prints false: no ERROR line
        ctx.exit(1)

    if bold:
        echo(results[0]["expression"])
        ctx.exit(0)

    if json_output:
        # JSON Lines: one canonical (RFC 8785) object per result.
        for r in results:
            echo_json(json_line(r))
    else:
        # Standard output: line-delimited, KEY=VALUE
        for i, r in enumerate(results):
            echo(text_line(r))
            # A word diff for the top match, if it is a close text match.
            if diff and i == 0 and r["method"] == "text" and not r["exact"]:
                show_diff(*detector.diff_pair(license_text, r["expression"]))

    ctx.exit(0)


def _predicate_command(
    name: str, key: str, summary: str, holds: Callable[[Detection], bool | None]
) -> None:
    """Add the command *name*: one record, ``EXPRESSION=<id judged>`` and
    ``<key>=true|false``, exit 0 for true and 1 for false. EXPRESSION is
    empty when the input names no licence (``detector.resolve_record``);
    the flag is empty (``null``), exit 1, when an operand of the expression
    cannot be judged (``licenseid.exprflags``): never a false "no"."""

    @cli.command(name=name, help=summary)
    @click.argument("input_val", required=False)
    @click.option("--text", help="License text to check.")
    @click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
    @json_option
    @click.pass_context
    def command(
        ctx: click.Context,
        input_val: str | None,
        text: str | None,
        id_val: str | None,
        json_output: bool,
    ) -> None:
        record = detect_license_record(ctx, input_val, text, id_val)
        answer = False if record is None else holds(record)
        expression = None if record is None else record["expression"]
        echo_record(json_output, EXPRESSION=expression, **{key: answer})
        ctx.exit(0 if answer is True else 1)


def _is_open(record: Detection) -> bool:
    return bool(record["is_osi_approved"] or record["is_fsf_libre"])


# The key of each flag is that of detect's JSON (is_osi_approved), or the
# command's own name for a flag detect has not (is-open, is-free).
_predicate_command(
    "is-osi",
    "IS_OSI_APPROVED",
    "True if the license is OSI-approved: every operand of an AND, any of an "
    "OR. Empty, exit 1, when an operand cannot be judged.",
    lambda record: record["is_osi_approved"],
)
_predicate_command(
    "is-fsf",
    "IS_FSF_LIBRE",
    "True if the license is FSF-libre, judged as is-osi judges.",
    lambda record: record["is_fsf_libre"],
)
_predicate_command(
    "is-open", "IS_OPEN", "True if the license is OSI-approved OR FSF-libre.", _is_open
)
_predicate_command("is-free", "IS_FREE", "Alias for is-open.", _is_open)
_predicate_command(
    "is-spdx",
    "IS_SPDX",
    "True if every licence and exception ID is on the SPDX License List "
    "(a LicenseRef-* is not).",
    lambda record: record["is_spdx"],
)


cli.add_command(match_command)


def main() -> None:
    """Main entry point for the CLI.

    Click's own handling (standalone mode) would exit 1 on Ctrl-C, the code
    for "no", and print a ClickException with no regard for a failing
    standard error, which then turned the exit status into 120 at the flush
    on exit.
    """
    try:
        status = cli.main(standalone_mode=False)
    except click.exceptions.Abort:  # Ctrl-C before a command runs
        end_line()
        status = 130
    except click.ClickException as exc:  # a usage error, through the console
        UsageLineError(exc).show()
        status = exc.exit_code
    except OutputError as exc:  # `licenseid --help`, before any command runs
        status = output_failed(exc)
    sys.exit(status if isinstance(status, int) else 0)


if __name__ == "__main__":
    main()
