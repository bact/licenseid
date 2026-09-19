# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The cell catalogue, one module per family group.

``A`` ``match`` options, ``B`` predicates, ``C`` global options and help,
``D`` ``update`` outcomes, ``E`` the environment around the process
(``environment`` for its streams, ``process_env`` for its resources).
"""

from __future__ import annotations

from tools.cli_matrix.cells import (
    environment,
    global_options,
    match,
    predicate,
    process_env,
)
from tools.cli_matrix.cells import update as update_cells
from tools.cli_matrix.model import CellSet

__all__ = ["build_cells"]


def build_cells() -> CellSet:
    """The whole catalogue, in the order the families are declared."""
    cells = CellSet()
    match.add_cells(cells)
    predicate.add_cells(cells)
    global_options.add_cells(cells)
    update_cells.add_cells(cells)
    environment.add_cells(cells)
    process_env.add_cells(cells)
    return cells
