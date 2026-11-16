# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Write ``docs/lists.md`` from the code (``python -m tools.lists_page``), or
with ``--check`` say whether it is up to date, writing nothing."""

import argparse
import sys
from pathlib import Path
from typing import Final

from tools.lists_page.measure import corpus, project_counts
from tools.lists_page.render import render

PAGE: Final = Path(__file__).resolve().parents[2] / "docs" / "lists.md"


def page_text() -> str:
    """The page as the code gives it now."""
    with corpus() as db:
        return render(db, project_counts(db))


def main(argv: list[str] | None = None) -> int:
    """Write the page, or check it; the exit status is 1 for a stale page."""
    parser = argparse.ArgumentParser(prog="python -m tools.lists_page")
    parser.add_argument(
        "--check", action="store_true", help="fail if the page is out of date"
    )
    text = page_text()
    if parser.parse_args(argv).check:
        if PAGE.read_text(encoding="utf-8") != text:
            sys.stderr.write("docs/lists.md is out of date: run the generator\n")
            return 1
        return 0
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
