---
Created: 2026-11-27
Last-Modified: 2026-11-27
SPDX-FileContributor: Arthit Suriyawongkul
SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
SPDX-FileType: DOCUMENTATION
SPDX-License-Identifier: Apache-2.0
title: "Word-gram postings of the List texts (build 8)"
---

## Word-gram postings of the List texts (build 8)

Status: task T2 of the 0.10.0 speed plan
(`working-docs/design/speed-0-10-plan.md`, sections 3.1 to 3.3), built
2026-11-27, not merged. `update` stores the postings; nothing in detection
reads them yet (task T3 will). Measurements: Apple M-series, Python 3.10,
SPDX License List 3.29.0, a machine under load (load average 6 to 11).

### 1. What is stored

- `textgrams`: the tokens of a normalised text (its words, and each Han or
  kana character alone: `split_words`, moved here from `textcorpus` so that
  the module needs the standard library only), word 3-grams, and each gram's
  hash: BLAKE2b of the three tokens joined by a space, 8 bytes, read as a
  signed little-endian integer. Never `hash()`, whose value changes with the
  process. The score of a text: `shared / min(grams of input, grams of
  text)`; equal scores keep row order.
- `text_posting_ids (k INTEGER PRIMARY KEY, id TEXT, size INTEGER)`: the
  texts by number, in table order of `license_index` (the rows that have a
  licence row; the first row of an ID wins), with each text's count of
  distinct grams. A text of fewer than three tokens holds no gram and has no
  number.
- `text_postings (h INTEGER PRIMARY KEY, ids BLOB)`: one row per gram, its
  hash and the numbers of the texts that hold it, ascending, as one blob of
  unsigned little-endian integers; a big-endian host swaps them
  (`to_blob`, `from_blobs`).
- One blob per gram, not one row per pair: a third of the size (plan 3.3),
  and one index seek per gram. Lookups bind at most 900 values a query
  (`CHUNK`).
- The width of an item is 2 bytes up to 65,536 texts, else 4. Not 1: with
  1-byte items a blob cut by one byte still reads, as a shorter list.

### 2. The stamp

`update` writes, in the transaction of the rows (`_write_db_records`, after
the texts), two `db_metadata` rows:

- `text_postings`: a JSON object with the gram size, the hash name, the
  token rule version, the width and the counts of texts and grams;
- `text_postings_update`: a copy of `last_update_datetime`.

The postings are read back from the rows just written in that transaction
(`write_postings` reads `license_index` through the writing connection), so
they are those of the texts a lookup reads.

### 3. Used only when they are those of the rows

`gramstore.load` takes the stored postings when the copy equals
`last_update_datetime` (a text, as `update` writes it), the stamp equals the
one this build writes for its counts (compared as JSON text: a JSON `true`
equals 1 in Python), `count(*)` of `text_postings` is the stamp's, and the
ids table holds exactly the stamp's texts, numbered from 0, each with a text
ID and a positive size. The width read is the one a build chooses for that
count, so another width is another stamp. Each blob is checked as it is
read: bytes, not empty, a length that is a multiple of the width, every
number under the count of texts, and no text counted more often than it has
grams (a number twice in a blob).

Anything else builds the index in memory from the texts (`build_index`,
the function `update` stores from), which gives the table the stored one
gives, and is never written back:

| Damage | Found |
| - | - |
| No stamp, no copy, a copy of an older `last_update_datetime`, a copy that is not text | at load |
| Other gram size, hash, token rule, width, count of texts or grams; an extra key; not JSON, a list, nested too deep | at load |
| Postings emptied or one row gone; ids emptied, a gap in `k`, a NULL or text `size`, a size of 0, a NULL `id` | at load |
| A blob one byte short, a number out of range, numbers twice, text or NULL in `ids` | at the read; that call and later ones use the index in memory |
| A row SQLite cannot decode as text | `DatabaseNotReadyError` (`unreadable`), as for `text_codes` |

A missing table is not damage: the file is not of this build and the
readiness gate refuses it (`empty`; `build v7 outdated` for a file of build
7). A view of one of the names, a table without its rowid (or `text_codes`
with one), or an index name held by another kind of object is a missing one
too (`dbschema.has_shape`, roadmap item 66), and `update` drops it as what it
is (`replace_schema`).

A hand-seeded test database (tables from `create_schema`, rows by SQL) has
empty postings tables and no stamp: it takes the in-memory path. Postings
rows are no condition of readiness.

### 4. State and threads

`dbcache.TableCache` owns one `gramstore.GramCache` per generation of its
reads (`_Keyed`, replaced by `clear()`), never keyed by path. A call
(`database.gram_scores`) reads `last_update_datetime`, the ids (when it
loads) and the postings in one read transaction (`BEGIN` on the shared
connection of a `reading()` block), so an `update` cannot land between them;
the state is kept for the `last_update_datetime` it was loaded at. It is
loaded under a lock and published in one assignment: eight threads on a
fresh database get one index. A blob found damaged replaces the state with
the index in memory, and the call that found it counts again from it.

`gram_scores(db, norm_text, limit=None)` gives a `GramTable`: the rows in
row order (`GramScore`: ID, shared, size, score), the grams looked up and
the input's distinct grams; `limit` looks up only the first ones (in input
order) and the table says it is `bounded` (plan 3.5; T3 owns the rule).

### 5. Measured

On List 3.29.0, built by `update` offline from the cached tarball:

| Item | Value |
| - | - |
| Texts, distinct grams, postings | 708, 142,009, 610,113 |
| `text_postings` pages | 3.40 MB; `text_posting_ids` 20 KB |
| Database file | 24.7 MB to 28.1 MB |
| `update`, three runs each | 4.48 to 4.91 s to 5.24 to 6.21 s |
| `write_postings` alone (CPU) | build 0.31 to 0.37 s, inserts 0.19 to 0.28 s |
| Index built in memory (CPU, best of five) | 0.30 s; first call 325 to 337 ms |
| `gram_scores`, MIT text, warm | 1.2 ms (memory index 0.6 ms) |
| `gram_scores`, Apache-2.0 / GPL-3.0 text, warm | 4.2 / 11.1 ms |
| First call of a process, MIT / GPL-3.0 text | 2.5 to 5.9 / 12 ms |
| `count(*)` of `text_postings` at load | 0.1 to 1.6 ms |

The plan's 0.25 to 0.5 s of `update` was the index alone; the inserts of
142,009 rows and the larger `VACUUM` add the rest. Most of a long text's
time is counting its postings (88,166 numbers for GPL-3.0): one array and
one `Counter` for all blobs costs half of a count per blob.

Equivalence: for all 708 texts and 500 fragments (start, middle, end; 30 to
300 words; 21 with every word replaced; 80 Japanese and Chinese texts and
fragments with spaces removed and wrapped at 7 to 41 characters), the stored
index, the index in memory and `gram_scores` give the same table (IDs,
shared, size, score, order), and all equal the prototype's `shingle.Index`
with `TOK=cjk`: 0 differences in 1,208 inputs.

### 6. Decisions

- Texts: the first `license_index` row of an ID that has a licence row
  (the prototype kept every row; a build has one row per ID).
- Width: 2 or 4, chosen by the count of texts and checked against it.
- Grams are posted by string, then each distinct string hashed once; a
  collision of two strings merges their postings and lowers the size of a
  text that holds both, so the index stays the one of distinct hashes.
- Not detected: a number changed to another in range inside a blob of the
  right length; checking that each blob ascends costs a pass per read.
