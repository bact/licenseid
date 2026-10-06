---
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Security

## Report a vulnerability

Report a vulnerability in licenseid privately: open the
[Security tab](https://github.com/bact/licenseid/security)
and choose "Report a vulnerability".
If unsure, report privately.

A vulnerability with a public advisory (a CVE or GHSA ID) in a dependency,
where the fix is an update, can go in a normal issue or pull request.
Do not describe how it can be reached through licenseid there.

## Verify release files

Releases after 0.4.0 attach these files to each
[GitHub release](https://github.com/bact/licenseid/releases) (0.4.0 has the
wheel and the sdist with their bundles and attestations, but its SBOM is
unsigned):

- the wheel and the source distribution (sdist), as published on PyPI;
- the software bill of materials (SBOM),
  `licenseid-<version>.spdx3.json`, byte-identical to the SBOM embedded in
  the wheel at `.dist-info/sboms/` ([PEP 770]);
- a [Sigstore] bundle (`<file>.sigstore.json`) for each of the three files
  above.

Each of the three files also has a GitHub artifact attestation (build
provenance).

To verify a downloaded file, put `<file>` and `<file>.sigstore.json` in the
same directory, then run:

```sh
WORKFLOW=bact/licenseid/.github/workflows/pypi-publish.yml
pip install sigstore
python -m sigstore verify github <file> \
  --cert-identity "https://github.com/${WORKFLOW}@refs/tags/v<version>"
gh attestation verify <file> -R bact/licenseid \
  --signer-workflow "${WORKFLOW}" \
  --source-ref refs/tags/v<version>
```

`<file>` is the wheel, the sdist, or the SBOM.

Versions before 0.4.0 have no signatures or attestations.

[PEP 770]: https://peps.python.org/pep-0770/
[Sigstore]: https://www.sigstore.dev/
