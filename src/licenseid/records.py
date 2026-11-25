# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rows of the ``licenses``, ``license_index``, ``exceptions`` and
``license_urls`` tables, built in memory from one :class:`licenseid.spdxdata.SpdxData`.

No database access and no network: whatever the source of the data (an
upstream tarball, a bundle), the same input gives the same rows. The text of
every licence is normalised once, here, into the search text that is indexed.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple

from licenseid.console import status
from licenseid.coretext import core_text
from licenseid.listrules import (
    active_exceptions_by_name,
    exception_successor,
    is_deprecated,
    kept_licenses,
    listed_urls,
)
from licenseid.normalize import normalize_text
from licenseid.spdxdata import SpdxData
from licenseid.textcorpus import StoredRow, TextCorpus, TextRow
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry

# Version of the rules that turn a release into rows. A database stores the
# version it was built with; `update` rebuilds one built with older rules.
# Version 2: a renamed deprecated ID records its successor (StandardML-NJ).
# Version 3: a deprecated ID without a text keeps the OSI and FSF flags the
# List gives it (wxWindows, eCos-2.0); they were both False.
# Version 4: the pages of each kept licence and every exception (``seeAlso``)
# go to ``license_urls``, so that a licence URL can be read as its licence.
# Version 5: ``core_text``, ``core_word_count`` (the template without its
# optional parts, when that is shorter) and ``same_text`` (the licences whose
# text is the same) are stored.
# Version 6: ``text_codes`` holds the List texts as word codes
# (``textcorpus.TextCorpus.stored_rows``), so the search of whole texts reads
# them instead of coding every text again at its first use.
BUILD_VERSION = "6"

# A core is kept whenever it has fewer words than the whole text, however few
# it drops (a title alone). Kept only at nine tenths of the words or less, a
# licence with a longer core competed with its whole text alone against a
# neighbour scored on its core: over the List's 708 texts, the core of
# CC-BY-SA-4.0 (0.92 of its words) became CC-BY-NC-SA-4.0 and that of
# CC-BY-SA-2.5 (0.9004) CC-BY-SA-2.0; with every shorter core kept (442, not
# 78) neither moves and no top answer is lost but among licences whose cores
# are the same text. Tier 2 scores a core only for an input of about its
# length (``similarity.CORE_MIN_SHARE``), so the cost does not grow with it.

# (license_id, name, xml_template, is_spdx, is_osi, is_fsf,
#  is_high_usage, is_deprecated, superseded_by, pop_score, word_count,
#  norm_license_id, norm_name, core_text, core_word_count, same_text)
# xml_template is always None. The column stays in the schema.
# core_text and core_word_count: None unless the core is kept (see
# ``core_of``). same_text: the IDs of the licences with the same normalised
# text, sorted and joined by one space, the licence itself included; None
# when it is alone.
LicenseInsertRecord = tuple[
    str,
    str,
    str | None,
    bool,
    bool,
    bool,
    bool,
    bool,
    str | None,
    int,
    int,
    str,
    str,
    str | None,
    int | None,
    str | None,
]
IndexInsertRecord = tuple[str, str]
# (exception_id, name, is_deprecated, superseded_by)
ExceptionInsertRecord = tuple[str, str, bool, str | None]
# (owner_id, is_exception, url): one page of a licence or an exception, the
# URL as the List writes it (a key of it is made at lookup, so a change of
# the key needs no rebuild).
UrlInsertRecord = tuple[str, bool, str]
# A kept licence with its successor (listrules.kept_licenses).
_Kept = list[tuple[SpdxLicenseEntry, str | None]]


class Records(NamedTuple):
    """The record lists of one release, ready to insert. *texts* are the
    rows of ``text_codes`` (``textcorpus.StoredRow``)."""

    licenses: list[LicenseInsertRecord]
    index_entries: list[IndexInsertRecord]
    exceptions: list[ExceptionInsertRecord]
    urls: list[UrlInsertRecord]
    texts: Sequence[StoredRow] = ()


def build_records(data: SpdxData, popularity_map: dict[str, int]) -> Records:
    """Build the record lists for insertion (no DB access)."""
    status("\nPreparing license data...", end="")
    # The superseded_by mapping is built at DB build time so runtime
    # lookups are O(1).
    kept = kept_licenses(
        data.licenses, lambda license_id: data.texts.get(license_id) is not None
    )
    licenses, index = _license_records(data, kept, popularity_map)
    licenses = _with_same_text(licenses, index)
    return Records(
        licenses,
        index,
        _exception_records(data.exceptions),
        _url_records(kept, data.exceptions),
        text_rows(licenses, index),
    )


def text_rows(
    licenses: Iterable[LicenseInsertRecord], index: Iterable[IndexInsertRecord]
) -> list[StoredRow]:
    """The rows of ``text_codes`` of the licence rows *licenses* with their
    *index* entries: the corpus the search of whole texts reads, built from
    the same rows it would read back (``dbcache.TableCache.text_corpus``)."""
    parts = {record[0]: record for record in licenses}
    rows = []
    for license_id, text in index:
        record = parts[license_id]
        same = record[15]
        core = record[13] if record[14] else None
        rows.append(
            TextRow(
                license_id, text, core, tuple(same.split()) if same else (license_id,)
            )
        )
    return TextCorpus.build(rows).stored_rows()


def _url_records(
    kept: _Kept, exceptions: tuple[SpdxExceptionEntry, ...]
) -> list[UrlInsertRecord]:
    """The pages of the kept licences in List order, then those of every
    exception: the licences that the database keeps, and no other."""
    records: list[UrlInsertRecord] = [
        (lic["licenseId"], False, url) for lic, _ in kept for url in listed_urls(lic)
    ]
    records.extend(
        (exc["licenseExceptionId"], True, url)
        for exc in exceptions
        for url in listed_urls(exc)
    )
    return records


def _license_records(
    data: SpdxData, kept: _Kept, popularity_map: dict[str, int]
) -> tuple[list[LicenseInsertRecord], list[IndexInsertRecord]]:
    """Licence rows and index rows of the *kept* licences. A licence without
    a text is dropped, unless it is deprecated: that one keeps a metadata row
    (no index entry), so that a lookup of its ID can still be redirected."""
    license_records: list[LicenseInsertRecord] = []
    index_records: list[IndexInsertRecord] = []
    for i, (lic, superseded_by) in enumerate(kept):
        res = _prepare_license_record(
            lic,
            data.texts.get(lic["licenseId"]),
            popularity_map,
            superseded_by,
            data.templates.get(lic["licenseId"]),
        )
        if res:
            license_records.append(res[0])
            index_records.append(res[1])
        else:
            # Text absent for this deprecated ID (some SPDX releases omit
            # them).  Still store the metadata row so redirect lookups work.
            license_records.append(_metadata_only_record(lic, superseded_by))

        if (i + 1) % 100 == 0 or (i + 1) == len(kept):
            status(".", end="")
    return license_records, index_records


def _metadata_only_record(
    lic: SpdxLicenseEntry, superseded_by: str | None
) -> LicenseInsertRecord:
    """The row of a deprecated licence that has no text: its flags as the
    List gives them, as for a row with a text, with no text to count or
    rank by."""
    dep_name = lic.get("name", lic["licenseId"])
    return (
        lic["licenseId"],
        dep_name,
        None,  # xml_template
        True,  # is_spdx
        lic.get("isOsiApproved", False),
        lic.get("isFsfLibre", False),
        False,  # is_high_usage
        True,  # is_deprecated
        superseded_by,
        1,  # pop_score
        0,  # word_count
        normalize_text(lic["licenseId"]),
        normalize_text(dep_name),
        None,  # core_text
        None,  # core_word_count
        None,  # same_text
    )


def _exception_records(
    exceptions_data: tuple[SpdxExceptionEntry, ...],
) -> list[ExceptionInsertRecord]:
    """Exception rows; a deprecated one points to the active exception that
    has the same name (lower-cased)."""
    status("\nPreparing exception data...", end="")
    by_name = active_exceptions_by_name(exceptions_data)
    return [
        (
            exc["licenseExceptionId"],
            exc["name"],
            # The raw flag, not is_deprecated(): the row keeps what the file says.
            exc.get("isDeprecatedLicenseId", False),
            exception_successor(exc, by_name),
        )
        for exc in exceptions_data
    ]


def _prepare_license_record(
    lic: SpdxLicenseEntry,
    text: str | None,
    popularity_map: dict[str, int],
    superseded_by: str | None = None,
    template: str | None = None,
) -> tuple[LicenseInsertRecord, IndexInsertRecord] | None:
    """The row and the index entry of one licence, or ``None`` when it has no
    *text* (an empty text is a text). ``same_text`` is left empty: it needs
    every licence (:func:`_with_same_text`)."""
    if text is None:
        return None

    license_id = lic["licenseId"]
    fingerprint = normalize_text(text)
    word_count = len(fingerprint.split())
    core, core_words = core_of(template, word_count)
    is_osi = lic.get("isOsiApproved", False)
    is_fsf = lic.get("isFsfLibre", False)

    baseline = 100 if (is_osi or is_fsf) else 1
    pop_count = popularity_map.get(license_id, 0)
    pop_score = max(baseline, pop_count)

    is_high_usage = is_osi or is_fsf or pop_score > 500

    name = lic.get("name", "")
    license_record: LicenseInsertRecord = (
        license_id,
        name,
        None,  # xml_template
        True,  # is_spdx
        is_osi,
        is_fsf,
        is_high_usage,
        is_deprecated(lic),
        superseded_by,
        pop_score,
        word_count,
        normalize_text(license_id),
        normalize_text(name),
        core,
        core_words,
        None,  # same_text
    )
    return license_record, (license_id, fingerprint)


def core_of(template: str | None, word_count: int) -> tuple[str | None, int | None]:
    """The normalised core of *template* and its word count, or ``(None,
    None)`` when there is none to keep: no template, a malformed one
    (``coretext.core_text``), a core with no word, or a core with no fewer
    words than the whole text (*word_count*). The core is normalised
    by ``normalize_text``, as the whole text is, so that their words compare."""
    if template is None:
        return None, None
    core = core_text(template)
    if core is None:
        return None, None
    normalised = normalize_text(core)
    words = len(normalised.split())
    if words == 0 or words >= word_count:
        return None, None
    return normalised, words


def _with_same_text(
    licenses: list[LicenseInsertRecord], index: list[IndexInsertRecord]
) -> list[LicenseInsertRecord]:
    """*licenses* with ``same_text`` set (:func:`same_text_of`) and the cores
    of a group that :func:`uneven_cores` names dropped."""
    of_id = same_text_of(index)
    dropped = uneven_cores(of_id, {record[0]: record[13] for record in licenses})
    return [
        (
            *record[:13],
            None if record[0] in dropped else record[13],
            None if record[0] in dropped else record[14],
            of_id.get(record[0]),
        )
        for record in licenses
    ]


def same_text_of(index: Iterable[IndexInsertRecord]) -> dict[str, str]:
    """The ``same_text`` of each licence of *index* that shares its normalised
    text (the ``search_text`` of the index, the whole text the match reads)
    with another: the IDs of its group, sorted, joined by one space, its own
    ID in it. A text with no word is no evidence of one licence and groups
    nothing. A licence alone is not a key."""
    groups: dict[str, list[str]] = {}
    for license_id, fingerprint in index:
        if fingerprint:
            groups.setdefault(fingerprint, []).append(license_id)
    return {
        license_id: " ".join(sorted(ids))
        for ids in groups.values()
        if len(ids) > 1
        for license_id in ids
    }


def uneven_cores(
    same_text: Mapping[str, str], cores: Mapping[str, str | None]
) -> frozenset[str]:
    """The IDs, of *same_text* (:func:`same_text_of`), whose core is not kept:
    every licence of a group whose members' *cores* are not all one text (or
    all none: where some have a core and some none, none keeps one).

    Licences with the same text are told apart by the tie-breaker of their
    equal scores (``ranking``). Uneven cores would score them apart instead,
    on the parts of their templates the text does not show: OFL-1.1 and
    OFL-1.1-RFN have the same text, but their copyright lines name a Reserved
    Font Name, so their cores are not shorter than the text and are not kept,
    while OFL-1.1-no-RFN's is, and an OFL-1.1 copy without its title read as
    OFL-1.1-no-RFN. Without a core, each scores on the text they share."""
    of_group: dict[str, set[str | None]] = {}
    for license_id, group in same_text.items():
        of_group.setdefault(group, set()).add(cores.get(license_id))
    return frozenset(
        license_id
        for license_id, group in same_text.items()
        if len(of_group[group]) > 1
    )
