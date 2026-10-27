---
Created: 2026-10-27
Last-Modified: 2026-10-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
---

# Resolving a declared value (PR #97 and the 0.6.0 review)

`licenseid.resolve(value)` (`resolver.py`, types in `resolvertypes.py`)
answers which SPDX expression a declared licence value stands for, and
lists each step taken. `match` answers which licence a text is. The two
differ on purpose in one place: `resolve` never narrows a bare deprecated ID
(`GPL-3.0` is category `assumed_only`, both variants offered), while `match`
narrows it to `-only` and warns.

## Decisions from the pre-release review

The review before 0.6.0 found nine issues. What was decided:

- **WITH.** `X WITH exception` names one licence. `_with` reads `X` as a
  value of its own (a "+", a grant, a loose ID, a `LicenseRef-*`) and the
  exception by its ID, with its case and deprecation read as a licence's.
  Only AND and OR make an `expression` of several licences. An unknown
  exception gives `unresolved`. A grant written after the exception
  (`GPL-2.0 WITH Classpath-exception-2.0 or later`) is also `unresolved`:
  `match` gives that grant to the licence, but `resolve` does not move
  words.
- **LicenseRef.** A whole `LicenseRef-*` (with `DocumentRef-*:`, idstrings
  as SPDX defines them, so no "_") names itself, as written: category
  `exact`. It takes no "+" (`malformed`) and has no `-or-later`
  (`unresolved`). The predicate is `identifiers.is_license_ref`.
- **A qualifier stated twice** is `malformed` on every path: "+" twice,
  a grant twice, a "+" and then a grant (`GPLv3+ or later`), and
  `-only`/`-or-later` with either. A value that names no licence stays
  `unresolved`.
- **"+" after a bracket.** SPDX gives "+" to a licence ID only, so
  `(GPL-2.0)+` is `malformed`. PR #97 had pinned it as accepted.
- **Hidden characters.** A format character (category Cf: a zero-width
  space, a bidi override, a soft hyphen, a BOM) makes a value `unresolved`,
  as a control character does. The loose-ID key used to fold one away as a
  separator, so `MIT​` resolved to MIT. White space such as a
  no-break space is still trimmed.
- **Names** come from `TableCache.active_ids_by_name`, built once per
  database generation, not from a scan of every row on each call. The
  comparison is still the exact case-folded name, the List's own name.
  `match` compares normalised names: a value that only normalises to a
  name is `match`'s to guess, not a `listed_name` step.
- **The declared "or later" reader.** `looseid.declared_grant_id_text` no
  longer has a regex of its own. It finds the last "or" after white space
  or a bracket and lets `classify.OR_LATER_PHRASE` judge the rest. That
  reader wants a number before a bare "or later" (prose says "sooner or
  later"), so the declared reader reads the phrase as if after one, unless
  `classify.is_negated`. `tests/test_resolver_shapes.py` holds it and
  `granted_id_text` to `PHRASES` (`tests/ordering_helpers.py`), the table
  the tie-breaker and the ID path already follow. The shared grant tail now
  takes "]", so `[or later]` is a grant on both paths, as the table said.
- **Older databases.** The rename successor is written at build time.
  Before, a database already at the release `update` found was skipped,
  and nothing told the user to rebuild. Each build now stores
  `build_version` (`records.BUILD_VERSION`) beside `normalization_version`.
  An older stamp, or none, warns
  `database: build v1 outdated: current v2; run 'licenseid update'`, and
  `update` rebuilds such a database at the release it has. The
  normalisation stamp works the same way now, so neither needs `--force`.
- **Version number.** The release was first planned as a patch. A new
  public API makes it a minor release under SemVer, so it is 0.6.0.

## Traps

- `Pattern.match(text, pos)` lets a lookbehind see the text before `pos`,
  which slicing does not: the declared reader uses it so that "not" before
  the grant still takes it back.
- A test seeder that writes `db_metadata` by hand must write both stamps,
  or every database it makes warns.
