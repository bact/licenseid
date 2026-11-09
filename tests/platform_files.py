# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Test files that depend on the operating system, not only on the logic.

They get the platform marker (conftest.pytest_collection_modifyitems).
CI runs the whole suite on Linux (Python 3.10 and 3.14) and only these files
on Windows: pytest -m platform. A file that touches the file system,
streams, signals, processes, encodings or the packaging belongs here;
tests/test_platform_files.py fails when a file that does is missing.
"""

from typing import Final

PLATFORM_FILES: Final[frozenset[str]] = frozenset(
    {
        "test_build_bundle.py",
        "test_bundle_source.py",
        "test_clear_cache.py",
        "test_cli_errors.py",
        "test_cli_input.py",
        "test_cli_matrix.py",
        "test_cli_matrix_judge.py",
        "test_cli_output.py",
        "test_cli_resolve.py",
        "test_cli_resolve_corpus.py",
        "test_cli_smart.py",
        "test_cli_staleness.py",
        "test_cli_streams.py",
        "test_cli_terse.py",
        "test_cli_usage.py",
        "test_cli_version.py",
        "test_console.py",
        "test_database.py",
        "test_database_update.py",
        "test_db_connection.py",
        "test_db_lookup.py",
        "test_db_ready.py",
        "test_db_ready_adversarial.py",
        "test_dbcheck_uri.py",
        "test_dbcheck_windows.py",
        "test_default_db_path.py",
        "test_detect_function.py",
        "test_fingerprint.py",
        "test_fixd_database.py",
        "test_fixd_round2.py",
        "test_fixd_round3.py",
        "test_harness_golden_cli.py",
        "test_hatch_build.py",
        "test_housekeeping_home.py",
        "test_license_urls_build3.py",
        "test_listindex.py",
        "test_listlookup.py",
        "test_lookup_database_errors.py",
        "test_lookup_database_hardening.py",
        "test_lookup_database_pins.py",
        "test_looseid.py",
        "test_markers.py",
        "test_module_layout.py",
        "test_option_matrix.py",
        "test_output_encoding.py",
        "test_output_pattern.py",
        "test_path_argument.py",
        "test_releasebuild_dist.py",
        "test_releasebuild_pin.py",
        "test_resolver.py",
        "test_resolver_choice_cache.py",
        "test_resolver_compounds.py",
        "test_resolver_packaged.py",
        "test_shown_path.py",
        "test_slash_cli.py",
        "test_spdx_source.py",
        "test_spdx_source_cache.py",
        "test_spdxdata.py",
        "test_stray_plus_paths.py",
        "test_textinput.py",
        "test_update_characterization.py",
        "test_update_fallbacks.py",
        "test_update_matrix.py",
        "test_update_sources.py",
        "test_warning_filters.py",
    }
)
