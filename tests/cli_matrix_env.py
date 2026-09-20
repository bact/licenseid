# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Helpers shared by the CLI matrix tests: cells, results and a database.

Used by ``test_cli_matrix`` and ``test_cli_matrix_judge``. Import as
``from cli_matrix_env import ...`` (tests have no ``__init__.py``).
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from licenseid.database import NORMALIZATION_VERSION, LicenseDatabase
from licenseid.normalize import normalize_text
from tools.cli_matrix.config import RunConfig, build_parser, configure_args
from tools.cli_matrix.fixtures import MIT
from tools.cli_matrix.model import Cell

_INSERT_LICENSE = (
    "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved,"
    " is_fsf_libre) VALUES (?, ?, ?, ?, ?)"
)
_INSERT_INDEX = "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)"
_INSERT_METADATA = "INSERT INTO db_metadata (key, value) VALUES (?, ?)"


def make_file_db(path: Path) -> Path:
    """Build a one-licence database file (MIT) the CLI can be pointed at.

    The database is ready (see ``licenseid.dbcheck``) and silent: it records
    the ``license_list_version`` an update writes, and the current
    normalisation version, so the CLI neither refuses it nor warns that the
    normalisation rules are out of date.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    LicenseDatabase(str(path))
    with sqlite3.connect(path) as conn:
        conn.execute(_INSERT_LICENSE, ("MIT", "MIT License", True, True, True))
        conn.execute(_INSERT_INDEX, ("MIT", normalize_text(MIT)))
        conn.executemany(
            _INSERT_METADATA,
            [
                ("last_check_datetime", _now()),
                ("license_list_version", "3.30"),
                ("normalization_version", NORMALIZATION_VERSION),
            ],
        )
    return path


def _now() -> str:
    """A timestamp recent enough that the CLI does not call the data stale."""
    return datetime.now(timezone.utc).isoformat()


def bash_available() -> bool:
    """True when bash is on PATH."""
    return shutil.which("bash") is not None


def licenseid_script() -> Path | None:
    """The ``licenseid`` script next to the running interpreter, if any."""
    script = Path(sys.executable).parent / "licenseid"
    return script if script.is_file() else None


def make_config(out: Path, db: Path, *extra: str) -> RunConfig:
    """A validated run configuration for *db*, writing under *out*."""
    argv = ["--db", str(db), "--out", str(out), *extra]
    return configure_args(build_parser().parse_args(argv))


def make_cell(**kwargs: Any) -> Cell:
    """A cell with sensible defaults, overridden by *kwargs*."""
    defaults: dict[str, Any] = {
        "id": "X1-001",
        "fam": "X1",
        "desc": "test cell",
        "cmd": "$L --db $DB match MIT",
    }
    defaults.update(kwargs)
    return Cell(**defaults)


def make_result(**kwargs: Any) -> dict[str, Any]:
    """A result row with sensible defaults, overridden by *kwargs*."""
    defaults: dict[str, Any] = {
        "id": "X1-001",
        "shell": "bash",
        "py": "310",
        "rc": 0,
        "out": "",
        "err": "",
        "dur": 0.1,
        "work": "/tmp/work",
        "files": [],
    }
    defaults.update(kwargs)
    return defaults
