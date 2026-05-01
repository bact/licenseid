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
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text


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
@click.option("--timed", is_flag=True, help="Print wall time used for the command.")
@click.pass_context
def cli(ctx: click.Context, db: Optional[str], clear_cache: bool, timed: bool) -> None:
    """SPDX License ID matcher tool."""
    if timed:
        start_time = time.monotonic()

        def print_wall_time() -> None:
            duration = time.monotonic() - start_time
            click.echo(f"WALL_TIME={duration:.4f}s", err=True)

        ctx.call_on_close(print_wall_time)

    db_path = db or get_default_db_path()
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path

    if clear_cache:
        database = LicenseDatabase(db_path)
        database.clear_cache()
        ctx.exit()

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


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
    updated = database.update_from_remote(
        version=version, force=force, use_cache=use_cache
    )
    if updated:
        click.echo(f"Database updated at {db_path}")
    else:
        metadata = database.get_metadata()
        current_version = metadata.get("license_list_version", "unknown")
        click.echo(f"Database remains at version {current_version} at {db_path}")


def unescape_text(text: str) -> str:
    """Unescape backslash-escaped characters in a string."""
    try:
        return text.encode("utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        return text


@cli.command()
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option("--text", help="License text to match.")
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
def match(
    ctx: click.Context,
    input_file: Optional[str],
    text: Optional[str],
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

    if not os.path.exists(db_path):
        click.echo(
            f"Error: Database not found at {db_path}. "
            "Please run 'licenseid update' first.",
            err=True,
        )
        sys.exit(1)

    db_obj = LicenseDatabase(db_path)
    check_db_staleness(db_obj)

    license_text = ""
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            license_text = f.read()
    elif text:
        license_text = unescape_text(text)
    else:
        # Try reading from stdin
        if not sys.stdin.isatty():
            license_text = sys.stdin.read()
        else:
            click.echo(
                "Error: No input text provided. "
                "Provide a file, --text, or pipe to stdin.",
                err=True,
            )
            sys.exit(1)

    matcher = AggregatedLicenseMatcher(
        db_path, enable_java=enable_java, enable_popularity=enable_popularity
    )
    results = matcher.match(license_text)

    # Filter by threshold and limit to top N
    results = [r for r in results if r["score"] >= threshold][:top]

    if bold:
        if results:
            click.echo(results[0]["license_id"])
        else:
            click.echo("ERROR: No matching license found.", err=True)
            sys.exit(1)
        return

    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        if not results:
            click.echo("ERROR: No matching license found.", err=True)
            sys.exit(1)

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


def main() -> None:
    """Main entry point for the CLI."""
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
