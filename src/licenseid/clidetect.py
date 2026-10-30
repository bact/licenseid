# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid detect`` and the predicates ``is-osi``, ``is-fsf`` and
``is-spdx``: the commands that read the database through
:class:`licenseid.detector.LicenseDetector`.

Each prints one record per line, the answer first: ``detect`` a line per
result, or one line with every field empty when there is none (exit 1, C9
of the contract batch); a predicate the licence it judged and the flag.
``detect --id-only`` is the one exception: the top expression alone.
"""

import sys
from collections.abc import Callable
from typing import Any

import click

from licenseid import console
from licenseid.clicommon import (
    LicenseIdCommand,
    echo_record,
    exit_usage_error,
    json_option,
)
from licenseid.cliinput import (
    check_db_staleness,
    checked_inputs,
    exit_no_input,
    get_input_content,
)
from licenseid.dbcheck import check_database_ready
from licenseid.detector import LicenseDetector
from licenseid.output import echo, echo_json
from licenseid.result import (
    json_line,
    no_detection_json,
    no_detection_line,
    text_line,
)
from licenseid.types import Detection


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


def detect_license_record(
    ctx: click.Context,
    input_val: str | None,
    text: str | None,
    id_val: str | None = None,
) -> Detection | None:
    """The top match of the input of a predicate command, or None."""
    db_path = ctx.obj["db_path"]
    check_database_ready(db_path)  # before input handling: report the database first
    checked_inputs(ctx, input_val, text, id_val)
    detector = LicenseDetector(db_path)
    check_db_staleness(detector.db)
    if id_val:
        # pylint: disable-next=protected-access
        return detector._resolve_record(license_id=id_val)
    content = get_input_content(ctx, input_val, text, detector.db)
    if not content:
        exit_no_input(ctx)
    # A lone expression is read as an ID by the detector, whatever brings it.
    return detector._resolve_record(content)  # pylint: disable=protected-access


def _reject_conflicts(
    ctx: click.Context, threshold: float, top: int, outputs: dict[str, bool]
) -> None:
    """Exit 2 for an option out of range or two outputs that cannot both be
    printed (``--json`` with ``--id-only`` or ``--diff``)."""
    # A score is 0-1: a threshold outside it means nothing (above 1, or
    # nan, would keep nothing).
    if not 0.0 <= threshold <= 1.0:
        exit_usage_error(
            ctx, f"option: invalid: --threshold: {threshold}; pass a value from 0 to 1"
        )
    if top < 1:
        exit_usage_error(ctx, f"option: invalid: --top: {top}; pass 1 or more")
    for other in ("--id-only", "--diff"):
        if outputs["--json"] and outputs[other]:
            exit_usage_error(
                ctx, f"option: invalid: {other}: with --json; pass one of them"
            )


@click.command(name="detect", cls=LicenseIdCommand)
@click.argument("input_val", required=False)
@click.option("--text", help="License text to match, taken as written.")
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
@click.option(
    "--top",
    type=int,
    default=3,
    help="Maximum number of results to return (1 or more).",
)
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
@click.option("--id-only", is_flag=True, help="Print only the top expression.")
@click.pass_context
def detect_command(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
    id_only: bool,
) -> None:
    """Identify license text and return the closest matched SPDX License ID.

    INPUT_VAL is a file, a value, or - for standard input. One tab separates
    the fields of a line: read them with cut -f or awk -F'\\t'.
    """
    db_path = ctx.obj["db_path"]

    check_database_ready(db_path)  # before input handling: report the database first
    checked_inputs(ctx, input_val, text, id_val)
    _reject_conflicts(
        ctx,
        threshold,
        top,
        {"--json": json_output, "--id-only": id_only, "--diff": diff},
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

    if id_only:  # the exception to the record pattern: the expression alone
        echo(results[0]["expression"] if results else "")
    elif not results and json_output:  # "no" is an answer: an empty record
        echo_json(no_detection_json())
    elif not results:
        echo(no_detection_line())
    elif json_output:
        # JSON Lines: one canonical (RFC 8785) object per result.
        for r in results:
            echo_json(json_line(r))
    else:
        # Standard output: line-delimited, KEY=VALUE
        for r in results:
            echo(text_line(r))
    # A word diff for the top match, if it is a close text match: on
    # standard error, so beside --id-only too (--json refuses it).
    if diff and results and results[0]["method"] == "text" and not results[0]["exact"]:
        # pylint: disable-next=protected-access
        show_diff(*detector._diff_pair(license_text, results[0]["expression"]))

    ctx.exit(0 if results else 1)


def _predicate_command(
    name: str, key: str, summary: str, holds: Callable[[Detection], bool | None]
) -> click.Command:
    """The command *name*: one record, ``EXPRESSION=<id judged>`` and
    ``<key>=true|false``, exit 0 for true and 1 for false. EXPRESSION is
    empty when the input names no licence (``detector._resolve_record``);
    the flag is empty (``null``), exit 1, when an operand of the expression
    cannot be judged (``licenseid.exprflags``): never a false "no"."""

    @click.command(name=name, help=summary, cls=LicenseIdCommand)
    @click.argument("input_val", required=False)
    @click.option("--text", help="License text to check, taken as written.")
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

    return command


# Each flag is named as detect's JSON names it (is_osi_approved), by the
# organisation that certifies it; OSI-or-FSF is `is-osi X || is-fsf X`.
PREDICATE_COMMANDS: tuple[click.Command, ...] = (
    _predicate_command(
        "is-osi",
        "IS_OSI_APPROVED",
        "True if the license is OSI-approved: every operand of an AND, any of "
        "an OR. Empty, exit 1, when an operand cannot be judged.",
        lambda record: record["is_osi_approved"],
    ),
    _predicate_command(
        "is-fsf",
        "IS_FSF_LIBRE",
        "True if the license is FSF-libre, judged as is-osi judges.",
        lambda record: record["is_fsf_libre"],
    ),
    _predicate_command(
        "is-spdx",
        "IS_SPDX",
        "True if every licence and exception ID is on the SPDX License List "
        "(a LicenseRef-* is not).",
        lambda record: record["is_spdx"],
    ),
)
