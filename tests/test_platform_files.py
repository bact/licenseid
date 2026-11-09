# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CI runs only ``platform`` files on Windows: keep the list honest."""

import re
from pathlib import Path

from platform_files import PLATFORM_FILES

# pylint: disable=missing-function-docstring
TESTS = Path(__file__).parent
# What ties a test to the operating system, not to the matching logic.
_OS_USE = re.compile(
    r"posix_only|subprocess|Path\.home|TextIOWrapper|tarfile|signal\.|"
    r"os\.(?:chmod|symlink|mkfifo|getuid|utime)|\.chmod\(|"
    r"monkeypatch\.setenv\(\"HOME\"|get_default_db_path|"
    r"\bresolve_states\b"
)


def test_listed_files_exist() -> None:
    assert not [n for n in PLATFORM_FILES if not (TESTS / n).is_file()]


def test_os_dependent_files_are_listed() -> None:
    missing = sorted(
        path.name
        for path in TESTS.glob("test_*.py")
        if path.name != Path(__file__).name
        and path.name not in PLATFORM_FILES
        and _OS_USE.search(path.read_text(encoding="utf-8"))
    )
    assert not missing, f"add to tests/platform_files.py: {missing}"
