# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Entry point for ``python -m tools.cli_matrix``."""

from __future__ import annotations

import sys

from tools.cli_matrix.main import main

if __name__ == "__main__":
    sys.exit(main())
