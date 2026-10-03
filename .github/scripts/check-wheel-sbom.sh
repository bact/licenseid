#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0
#
# Check the SBOM the build embeds in the wheel, and copy it out.
#
# Usage: check-wheel-sbom.sh DIST_DIR OUT_DIR
#
# The pitloom build hook ([tool.hatch.build.hooks.pitloom] in
# pyproject.toml) embeds the SBOM while the wheel is built. This script
# checks there is exactly one wheel in DIST_DIR and exactly one SBOM in it,
# at the PEP 770 location (*.dist-info/sboms/*.spdx3.json), extracts it to
# OUT_DIR under its own name, validates it with spdx3-validate, and prints
# that name, so the release can attach the very SBOM the wheel carries.
#
# Needs: unzip, spdx3-validate (pip install spdx3-validate).

set -euo pipefail
shopt -s nullglob
# "${a[*]-}" below: bash 3.2 (macOS) treats an empty array as unset.

if [ "$#" -ne 2 ]; then
  echo "usage: $0 DIST_DIR OUT_DIR" >&2
  exit 2
fi
dist_dir=$1
out_dir=$2

wheels=("${dist_dir}"/*.whl)
if [ "${#wheels[@]}" -ne 1 ]; then
  echo "::error::expected exactly one wheel in ${dist_dir}, found" \
    "${#wheels[@]}: ${wheels[*]-}" >&2
  exit 1
fi
whl=${wheels[0]}

entries=()
while IFS= read -r entry; do
  case "${entry}" in
    *.dist-info/sboms/*.spdx3.json) entries+=("${entry}") ;;
  esac
done < <(unzip -Z1 "${whl}")
if [ "${#entries[@]}" -ne 1 ]; then
  echo "::error::expected exactly one *.dist-info/sboms/*.spdx3.json in" \
    "${whl}, found ${#entries[@]}: ${entries[*]-}" >&2
  exit 1
fi
entry=${entries[0]}
echo "Found: ${entry}" >&2

mkdir -p "${out_dir}"
sbom="${out_dir}/$(basename "${entry}")"
unzip -p "${whl}" "${entry}" > "${sbom}"
spdx3-validate --json "${sbom}" >&2

basename "${sbom}"
