# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Every deprecated "-with-" license ID has its WITH expression. Roadmap
item 25: GPL-2.0-with-classpath-exception had none and answered itself.

Reads the License List bundled with py_spdx_license, so the test needs no
network, and a new deprecated ID in a later data release fails by name."""
# pylint: disable=missing-function-docstring

import json
from importlib.resources import files

import pytest

from licenseid.identifiers import DEPRECATED_WITH_IDS


def _bundled(name: str, key: str) -> list[dict[str, object]]:
    data = (files("py_spdx_license") / "data" / name).read_text("utf-8")
    entries: list[dict[str, object]] = json.loads(data)[key]
    return entries


_LICENSES = _bundled("licenses.json", "licenses")
_EXCEPTIONS = {
    e["licenseExceptionId"] for e in _bundled("exceptions.json", "exceptions")
}
_DEPRECATED_WITH = sorted(
    str(e["licenseId"])
    for e in _LICENSES
    if e.get("isDeprecatedLicenseId") and "-with-" in str(e["licenseId"])
)


def test_the_bundled_list_has_deprecated_with_ids() -> None:
    assert "GPL-2.0-with-classpath-exception" in _DEPRECATED_WITH


@pytest.mark.parametrize("deprecated", _DEPRECATED_WITH)
def test_a_deprecated_with_id_has_its_expression(deprecated: str) -> None:
    license_id, operator, exception = DEPRECATED_WITH_IDS[deprecated].split(" ")
    assert operator == "WITH"
    assert license_id in {e["licenseId"] for e in _LICENSES}
    assert exception in _EXCEPTIONS
