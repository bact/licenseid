# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Command-line interface for the licenseid tool.
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import click

from licenseid.console import error, warn
from licenseid.database import LicenseDatabase, get_default_db_path
from licenseid.dbcheck import (
    check_database_ready,
    delete_failed_error,
    reject_foreign_database,
    unreadable_error,
)
from licenseid.errors import (
    DatabaseNotReadyError,
    InvalidInputError,
    LicenseIdError,
    invalid_id_error,
)
from licenseid.identifiers import is_simple_expression
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text
from licenseid.textinput import (
    decode_input,
    normalize_newlines,
    read_text_file,
    reject_binary,
)
from licenseid.types import LicenseDetails


def show_diff(text: str, best_window: str) -> None:
    """Show word-by-word diff between input text and matched window."""
    import difflib  # pylint: disable=import-outside-toplevel

    norm_input = normalize_text(text)
    input_words = norm_input.split()
    window_words = best_window.split()

    diff_lines = list(
        difflib.unified_diff(
            window_words, input_words, fromfile="DATABASE", tofile="INPUT", lineterm=""
        )
    )
    if diff_lines:
        click.echo("\nWORD DIFF:")
        for line in diff_lines:
            if line.startswith("+"):
                click.secho(line, fg="green")
            elif line.startswith("-"):
                click.secho(line, fg="red")
            else:
                click.echo(line)
        click.echo("")


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
    naming the file that actually failed.
    """
    try:
        LicenseDatabase.clear_cache(db_path)
    except OSError as exc:
        failed = exc.filename or db_path
        exit_usage_error(ctx, str(delete_failed_error(str(failed), exc)))


class DatabaseErrorGroup(click.Group):
    """A group that exits 2 when the database cannot answer.

    ``match`` and the ``is-*`` commands answer "no" with exit 1, so an unready
    database (``DatabaseNotReadyError``) must not share it. A file can also go
    bad after the readiness check (replaced or corrupted mid-run): a SQLite
    failure is then worded as an ``unreadable`` database, not a traceback. A
    ProgrammingError or InterfaceError is a bug in a query, not a fault in the
    file, so it still shows its traceback.
    """

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except DatabaseNotReadyError as exc:
            exit_usage_error(ctx, str(exc))
        except sqlite3.Error as exc:
            if isinstance(exc, (sqlite3.ProgrammingError, sqlite3.InterfaceError)):
                raise
            exit_usage_error(ctx, str(unreadable_error(ctx.obj["db_path"], exc)))


@click.group(cls=DatabaseErrorGroup, invoke_without_command=True)
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
    db_path = db or get_default_db_path()
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path
    ctx.obj["db_is_default"] = not db

    if clear_cache:
        clear_local_cache(ctx, db_path)
        ctx.exit()

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
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
@click.pass_context
def update(
    ctx: click.Context,
    version: str | None,
    force: bool,
    use_cache: bool,
) -> None:
    """Update the license database from remote sources."""
    db_path = ctx.obj["db_path"]
    # It writes the schema on open, so never into somebody else's file. Kept
    # outside the try: an unready database is a setup error (exit 2), not an
    # update that failed (exit 1).
    reject_foreign_database(db_path)
    try:
        make_default_db_dir(ctx)
        database = LicenseDatabase(db_path)
        updated = database.update_from_remote(
            version=version, force=force, use_cache=use_cache
        )
        if updated:
            click.echo(f"Database updated at {db_path}")
        else:
            metadata = database.get_metadata()
            current_version = metadata.get("license_list_version", "unknown")
            click.echo(f"Database remains at version {current_version} at {db_path}")
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


def exit_usage_error(ctx: click.Context, message: str) -> NoReturn:
    """Print *message* as an ERROR line and exit with a usage error (2)."""
    error(message)
    ctx.exit(2)


def exit_bad_input(ctx: click.Context, condition: str) -> NoReturn:
    """Exit with a usage error (2) for unusable input."""
    exit_usage_error(ctx, f"input: {condition}")


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
        exit_bad_input(ctx, f"unreadable: {source}: {e.strerror or e}")
    except InvalidInputError as e:  # binary data; already "input: ..."
        exit_usage_error(ctx, str(e))
    # No bytes at all on stdin means nothing was piped: "input: missing".
    if not piped_nothing and not text.strip():
        exit_bad_input(ctx, f"empty: {source}")
    return text


def reject_compound_id(ctx: click.Context, id_val: str | None) -> None:
    """Exit with a usage error (2) if --id does not name one license.

    --id is a declaration: "MIT OR Apache-2.0" declares neither license, and
    a name or an SPDX URL is not an ID. A file's tag may still hold any of
    them, so the reading of a file is unaffected.
    """
    if id_val and not is_simple_expression(id_val):
        exit_usage_error(ctx, str(invalid_id_error("--id", id_val)))


def reject_blank_options(ctx: click.Context, values: dict[str, str | None]) -> None:
    """Exit with a usage error (2) if an input given on the command line has
    no text, rather than skip it for the next input or match it as text."""
    for name, value in values.items():
        if value is not None and not value.strip():
            exit_bad_input(ctx, f"empty: {name}")


def read_text_option(ctx: click.Context, text: str) -> str:
    """Decode the escapes in --text, then treat it as file or stdin text is
    treated: LF line ends; exit 2 if binary (a NUL) or blank."""
    content = normalize_newlines(unescape_text(text))
    try:
        reject_binary(content, "--text")
    except InvalidInputError as e:
        exit_usage_error(ctx, str(e))
    if not content.strip():
        exit_bad_input(ctx, "empty: --text")
    return content


def get_input_content(
    ctx: click.Context, input_val: str | None, text: str | None
) -> tuple[str, bool]:
    """
    Get input content and indicate if it's likely a file path/text vs an ID.
    Returns (content, is_text_or_file).
    """
    if text is not None:
        return read_text_option(ctx, text), True
    if input_val:
        if os.path.exists(input_val):
            return read_input(ctx, input_val), True
        return input_val, False
    if not sys.stdin.isatty():
        return read_input(ctx, None), True
    return "", False


def reads_as_id(value: str) -> bool:
    """Whether a bare argument may be tried as a license ID.

    A bare argument is a guess between an ID and text, so only a value that
    names one license is tried as one; anything else is matched as text. A
    tag value runs to the end of its line and may trail off into prose, but
    an argument is delimited, so a tail means text ("BSD-3-Clause but
    modified heavily by us" is not BSD-3-Clause). `--id` reads the same rule
    in the other direction: it refuses what it cannot take as an ID
    (reject_compound_id).
    """
    return is_simple_expression(value)


def resolve_license_record(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None = None,
) -> LicenseDetails | None:
    """Helper to resolve a license from CLI arguments (implements Smart Logic)."""
    db_path = ctx.obj["db_path"]
    check_database_ready(db_path)  # before input handling: report the database first

    reject_blank_options(ctx, {"--id": id_val, "--text": text, "argument": input_val})
    reject_compound_id(ctx, id_val)
    matcher = AggregatedLicenseMatcher(db_path)
    check_db_staleness(matcher.db)

    # 1. Explicit ID
    if id_val:
        return matcher.resolve_record(license_id=id_val)

    # 2. Handle stdin/arguments
    content, is_text = get_input_content(ctx, input_val, text)
    if not content:
        exit_no_input(ctx)

    # 3. Smart Resolution (ID -> Text)
    if not is_text and reads_as_id(content):
        # Try as ID first, as `match` does
        record = matcher.resolve_record(license_id=content)
        if record:
            return record

    # Try matching as text
    return matcher.resolve_record(content)


@cli.command(name="match")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to match.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to lookup.")
@click.option(
    "--json", "json_output", is_flag=True, help="Output results in JSON format."
)
@click.option("--threshold", type=float, default=0.85, help="Minimum score threshold.")
@click.option("--top", type=int, default=3, help="Maximum number of results to return.")
@click.option(
    "--pop/--no-pop",
    "enable_popularity",
    default=False,
    help="Enable/disable popularity score weighting.",
)
@click.option("--diff", is_flag=True, help="Show word diff for the top match.")
@click.option("--bold", is_flag=True, help="Print only the top license ID.")
@click.pass_context
def match(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
    json_output: bool,
    threshold: float,
    top: int,
    enable_popularity: bool,
    diff: bool,
    bold: bool,
) -> None:
    """Identify license text and return the closest matched SPDX License ID."""
    db_path = ctx.obj["db_path"]

    check_database_ready(db_path)  # before input handling: report the database first
    reject_blank_options(ctx, {"--id": id_val, "--text": text, "argument": input_val})
    reject_compound_id(ctx, id_val)

    matcher = AggregatedLicenseMatcher(db_path, enable_popularity=enable_popularity)
    check_db_staleness(matcher.db)

    if id_val:
        results = matcher.match(license_id=id_val)
        license_text = ""
    else:
        content, is_text = get_input_content(ctx, input_val, text)
        if not content:
            exit_no_input(ctx)

        license_text = content
        results = []
        if not is_text and reads_as_id(content):
            results = matcher.match(license_id=content)  # try as ID first
        if not results:
            results = matcher.match(text=content)

    # Filter by threshold and limit to top N
    results = [r for r in results if r["score"] >= threshold][:top]

    if not results:
        error("match: no license found")
        ctx.exit(1)

    if bold:
        click.echo(results[0]["license_id"])
        ctx.exit(0)

    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        # Standard output: line-delimited, KEY=VALUE
        for i, r in enumerate(results):
            click.echo(
                f"LICENSE_ID={r['license_id']} "
                f"SIMILARITY={r.get('similarity', r['score']):.4f} "
                f"COVERAGE={r.get('coverage', 0.0):.4f}"
            )
            # Show diff for the top match if requested
            if diff and i == 0 and r.get("similarity", 0) < 1.0:
                show_diff(license_text, r.get("best_window", ""))

    ctx.exit(0)


@cli.command(name="is-osi")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to check.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
@click.pass_context
def is_osi(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
) -> None:
    """True if the license is OSI-approved."""
    record = resolve_license_record(ctx, input_val, text, id_val)
    if record and record.get("is_osi_approved"):
        click.echo("true")
        ctx.exit(0)
    click.echo("false")
    ctx.exit(1)


@cli.command(name="is-fsf")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to check.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
@click.pass_context
def is_fsf(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
) -> None:
    """True if the license is FSF-libre."""
    record = resolve_license_record(ctx, input_val, text, id_val)
    if record and record.get("is_fsf_libre"):
        click.echo("true")
        ctx.exit(0)
    click.echo("false")
    ctx.exit(1)


@cli.command(name="is-open")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to check.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
@click.pass_context
def is_open(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
) -> None:
    """True if the license is OSI-approved OR FSF-libre."""
    record = resolve_license_record(ctx, input_val, text, id_val)
    if record and (record.get("is_osi_approved") or record.get("is_fsf_libre")):
        click.echo("true")
        ctx.exit(0)
    click.echo("false")
    ctx.exit(1)


@cli.command(name="is-free")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to check.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
@click.pass_context
def is_free(  # pylint: disable=unused-argument
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
) -> None:
    """Alias for is-open."""
    ctx.forward(is_open)


@cli.command(name="is-spdx")
@click.argument("input_val", required=False)
@click.option("--text", help="License text to check.")
@click.option("--id", "id_val", help="Explicit SPDX License ID to check.")
@click.pass_context
def is_spdx_cmd(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None,
) -> None:
    """True if the license is in the SPDX License List."""
    record = resolve_license_record(ctx, input_val, text, id_val)
    if record and record.get("is_spdx"):
        click.echo("true")
        ctx.exit(0)
    click.echo("false")
    ctx.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
