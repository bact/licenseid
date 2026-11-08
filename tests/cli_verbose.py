# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``detect`` and ``resolve`` print the expression alone unless given
``--verbose``. Most tests read the full record, so the autouse fixture
``verbose_cli`` (``conftest.py``) adds ``-v`` after the subcommand of every
``CliRunner`` call. A test of the terse default carries
``@pytest.mark.terse_cli`` and sees the command line as written."""

from collections.abc import Sequence

#: The commands that print the expression alone by default.
TERSE_COMMANDS = ("detect", "resolve")

#: The words that already choose the output, so nothing is added.
VERBOSE_FLAGS = ("-v", "--verbose", "--help", "-h")


def with_verbose(args: Sequence[str]) -> list[str]:
    """*args* with ``-v`` after ``detect`` or ``resolve`` (the command is the
    first word, or the one after ``--db PATH`` or ``--db=PATH``), unless it
    has a verbose or help flag already."""
    out = list(args)
    start = 0
    if out[:1] == ["--db"]:
        start = 2
    elif out and out[0].startswith("--db="):
        start = 1
    if (
        start < len(out)
        and out[start] in TERSE_COMMANDS
        and not any(word in VERBOSE_FLAGS for word in out[start + 1 :])
    ):
        out.insert(start + 1, "-v")
    return out
