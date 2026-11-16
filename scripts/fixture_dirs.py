# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Output directory handling of the licenseid fixture generator."""

import shutil
from pathlib import Path


def check_dir(dir_path: Path, force: bool) -> bool:
    """Make dir_path; return False when it exists and force is not set."""
    if dir_path.exists():
        if force:
            print(f"Removing existing directory {dir_path}")
            shutil.rmtree(dir_path)
        else:
            print(
                f"Directory {dir_path} already exists. "
                "Skipping. Use --force to overwrite."
            )
            return False
    dir_path.mkdir(parents=True, exist_ok=True)
    return True
