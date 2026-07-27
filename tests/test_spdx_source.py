# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for spdx_source.is_cache_valid()."""

import os
import time
from pathlib import Path

from licenseid.spdx_source import is_cache_valid


def test_missing_file_is_invalid(tmp_path: Path) -> None:
    assert not is_cache_valid(tmp_path / "does-not-exist.json", days=45)


def test_fresh_file_is_valid(tmp_path: Path) -> None:
    cache_file = tmp_path / "licenses.json"
    cache_file.write_text("{}")
    assert is_cache_valid(cache_file, days=45)


def test_old_file_is_invalid(tmp_path: Path) -> None:
    cache_file = tmp_path / "licenses.json"
    cache_file.write_text("{}")
    old_time = time.time() - 46 * 86400
    os.utime(cache_file, (old_time, old_time))
    assert not is_cache_valid(cache_file, days=45)
