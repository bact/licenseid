# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Manual CLI matrix: every subcommand x flag x source x environment, tracked.

Why this exists
---------------
The pytest suite calls the CLI in-process, through ``click``'s test runner
and with monkeypatched I/O. That cannot see what happens when a real
process meets a real operating system: a shell that quotes differently, a
locale whose codec cannot encode the output, a closed file descriptor, a
full disk quota, a signal mid-match, a ``HOME`` that is a file, an input
larger than ``ARG_MAX``. Every FLAG this tool has produced so far was a
defect pytest could not reach.

The matrix runs each cell as a real command line, in a real shell, under
each configured interpreter, and judges the result against the invariants
in ``AGENTS.md`` ("CLI output").

Safety
------
* ``HOME`` for every cell lives inside the output directory.
* The database under test is a **copy**; the original file is never opened
  by a cell, and a path inside the real cache is refused outright.
* The real cache (``~/.local/share/licenseid``) is never opened, and the run
  fails if its entries change: cells that
  would resolve the default database path to it are skipped, not run.
* ``update`` runs only through the offline launcher, whose ``requests.get``
  is a scripted fake; a start-up self-check proves the fake is in place.
* Proxy environment variables point at a dead local port, so a request that
  somehow escaped the fake fails instead of reaching the network.

Verdicts
--------
``PASS``     all invariants and the cell's documented expectation hold.
``OBSERVE``  the behaviour is not specified; recorded for a human to judge.
``FLAG``     an invariant or a documented expectation is violated.

Usage
-----
``python -m tools.cli_matrix --db PATH [family-prefix ...]`` writes
``ledger.md``, ``coverage.md`` and ``results.json`` under ``--out``.
See ``tools/cli_matrix/README.md``.
"""
