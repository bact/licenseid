# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Entry point for ``python -m tools.cli_matrix``."""

from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    if os.name == "nt":
        # Before the import: the runner needs pty and termios, which Windows
        # lacks, and would fail with a bare ModuleNotFoundError.
        sys.stderr.write(
            "ERROR: platform: unsupported: Windows has no POSIX shells, signals"
            " or file modes to exercise; run this tool on macOS or Linux\n"
        )
        sys.exit(2)
    from tools.cli_matrix.main import main

    sys.exit(main())
