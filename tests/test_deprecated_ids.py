# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Every deprecated license ID with a successor in the License List is
redirected to it. Roadmap item 25: GPL-2.0-with-classpath-exception had no
WITH expression and answered itself; GFDL-1.1 to 1.3 had no -only and
-or-later forms, so GFDL-1.3+ answered GFDL-1.3+.

Reads the License List bundled with py_spdx_license, so the test needs no
network, and a new deprecated ID in a later data release fails by name."""
# pylint: disable=missing-function-docstring

import json
from importlib.resources import files

import pytest

from licenseid.identifiers import (
    DEPRECATED_BARE_LICENSE_IDS,
    DEPRECATED_SPDX_LICENSE_IDS,
    DEPRECATED_WITH_IDS,
)


def _bundled(name: str, key: str) -> list[dict[str, object]]:
    data = (files("py_spdx_license") / "data" / name).read_text("utf-8")
    entries: list[dict[str, object]] = json.loads(data)[key]
    return entries


_LICENSES = _bundled("licenses.json", "licenses")
_EXCEPTIONS = {
    e["licenseExceptionId"] for e in _bundled("exceptions.json", "exceptions")
}
_IDS = {str(e["licenseId"]) for e in _LICENSES}
# A deprecated ID whose text is now split into -only and -or-later.
_DEPRECATED_VERSIONED = sorted(
    str(e["licenseId"])
    for e in _LICENSES
    if e.get("isDeprecatedLicenseId")
    and {f"{e['licenseId']}-only", f"{e['licenseId']}-or-later"} <= _IDS
)
_DEPRECATED_WITH = sorted(
    str(e["licenseId"])
    for e in _LICENSES
    if e.get("isDeprecatedLicenseId") and "-with-" in str(e["licenseId"])
)


def test_the_bundled_list_has_deprecated_ids() -> None:
    assert "GPL-2.0-with-classpath-exception" in _DEPRECATED_WITH
    assert {"GPL-2.0", "GFDL-1.3"} <= set(_DEPRECATED_VERSIONED)


@pytest.mark.parametrize("deprecated", _DEPRECATED_VERSIONED)
def test_a_deprecated_versioned_id_has_both_forms(deprecated: str) -> None:
    assert DEPRECATED_BARE_LICENSE_IDS[deprecated] == f"{deprecated}-only"
    assert DEPRECATED_SPDX_LICENSE_IDS[f"{deprecated}+"] == f"{deprecated}-or-later"


@pytest.mark.parametrize("deprecated", _DEPRECATED_WITH)
def test_a_deprecated_with_id_has_its_expression(deprecated: str) -> None:
    license_id, operator, exception = DEPRECATED_WITH_IDS[deprecated].split(" ")
    assert operator == "WITH"
    assert license_id in _IDS
    assert exception in _EXCEPTIONS
