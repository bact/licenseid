# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Command-line interface for the licenseid tool.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text
from licenseid.types import LicenseDetails


def get_default_db_path() -> str:
    """Get the default path for the license database."""
    home = Path.home()
    db_dir = home / ".local" / "share" / "licenseid"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "licenses.db")


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
            days_old = (datetime.now() - last_check_dt).days
            if days_old > 182:  # Approx 6 months
                click.echo(
                    f"WARNING: License database is {days_old} days old. "
                    "Run 'licenseid update' to get the latest license list.",
                    err=True,
                )
        except ValueError:
            pass


@click.group(invoke_without_command=True)
@click.option("--db", help="Path to the license database.")
@click.option("--clear-cache", is_flag=True, help="Clear local cache and exit.")
@click.pass_context
def cli(ctx: click.Context, db: Optional[str], clear_cache: bool) -> None:
    """SPDX License ID matcher tool."""
    db_path = db or get_default_db_path()
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path

    if clear_cache:
        database = LicenseDatabase(db_path)
        database.clear_cache()
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
    version: Optional[str],
    force: bool,
    use_cache: bool,
) -> None:
    """Update the license database from remote sources."""
    db_path = ctx.obj["db_path"]
    database = LicenseDatabase(db_path)
    try:
        updated = database.update_from_remote(
            version=version, force=force, use_cache=use_cache
        )
        if updated:
            click.echo(f"Database updated at {db_path}")
        else:
            metadata = database.get_metadata()
            current_version = metadata.get("license_list_version", "unknown")
            click.echo(f"Database remains at version {current_version} at {db_path}")
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        ctx.exit(1)


def unescape_text(text: str) -> str:
    """Unescape backslash-escaped characters in a string."""
    try:
        return text.encode("utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        return text


def is_sqlite_uri(path: str) -> bool:
    """Check if a path is a SQLite URI or in-memory database."""
    return path.startswith("file:") or ":memory:" in path


def get_input_content(
    input_val: Optional[str], text: Optional[str]
) -> tuple[str, bool]:
    """
    Get input content and indicate if it's likely a file path/text vs an ID.
    Returns (content, is_text_or_file).
    """
    if text:
        return unescape_text(text), True
    if input_val:
        if os.path.exists(input_val):
            with open(input_val, "r", encoding="utf-8") as f:
                return f.read(), True
        return input_val, False
    if not sys.stdin.isatty():
        return sys.stdin.read(), True
    return "", False


def resolve_license_record(
    ctx: click.Context,
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str] = None,
) -> Optional[LicenseDetails]:
    """Helper to resolve a license from CLI arguments (implements Smart Logic)."""
    db_path = ctx.obj["db_path"]
    if not os.path.exists(db_path) and not is_sqlite_uri(db_path):
        click.echo(
            f"ERROR: Database not found at {db_path}. "
            "Please run 'licenseid update' first.",
            err=True,
        )
        ctx.exit(2)

    matcher = AggregatedLicenseMatcher(db_path)
    check_db_staleness(matcher.db)

    # 1. Explicit ID
    if id_val:
        return matcher.db.get_license_details(id_val)

    # 2. Handle stdin/arguments
    content, is_text = get_input_content(input_val, text)
    if not content:
        click.echo(
            "ERROR: No input provided. Provide a file, ID, "
            "--text, --id, or pipe to stdin.",
            err=True,
        )
        ctx.exit(2)

    # 3. Smart Resolution (ID -> Text)
    if not is_text:
        # Try as ID first
        details = matcher.db.get_license_details(content)
        if details:
            return details

    # Try matching as text
    results = matcher.match(text=content)
    if results and results[0]["score"] >= 0.85:
        return matcher.db.get_license_details(results[0]["license_id"])

    return None


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
    "--java/--no-java",
    "enable_java",
    default=False,
    help="Enable/disable Tier 3 Java validation (requires tools-java).",
)
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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
    json_output: bool,
    threshold: float,
    top: int,
    enable_java: bool,
    enable_popularity: bool,
    diff: bool,
    bold: bool,
) -> None:
    """Identify license text and return the closest matched SPDX License ID."""
    db_path = ctx.obj["db_path"]

    if not os.path.exists(db_path) and not is_sqlite_uri(db_path):
        click.echo(
            f"ERROR: Database not found at {db_path}. "
            "Please run 'licenseid update' first.",
            err=True,
        )
        ctx.exit(2)

    matcher = AggregatedLicenseMatcher(
        db_path, enable_java=enable_java, enable_popularity=enable_popularity
    )
    check_db_staleness(matcher.db)

    if id_val:
        results = matcher.match(license_id=id_val)
        license_text = ""
    else:
        content, is_text = get_input_content(input_val, text)
        if not content:
            click.echo(
                "ERROR: No input provided. Provide a file, ID, "
                "--text, --id, or pipe to stdin.",
                err=True,
            )
            ctx.exit(2)

        license_text = content
        if not is_text:
            # Try as ID first (Smart Logic)
            results = matcher.match(license_id=content)
            if not results:
                # Fallback to text matching
                results = matcher.match(text=content)
        else:
            # Explicit text/file matching
            results = matcher.match(text=content)

    # Filter by threshold and limit to top N
    results = [r for r in results if r["score"] >= threshold][:top]

    if bold:
        if results:
            click.echo(results[0]["license_id"])
            ctx.exit(0)
        else:
            click.echo("ERROR: No matching license found.", err=True)
            ctx.exit(1)

    if not results:
        click.echo("ERROR: No matching license found.", err=True)
        ctx.exit(1)

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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
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
    input_val: Optional[str],
    text: Optional[str],
    id_val: Optional[str],
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
