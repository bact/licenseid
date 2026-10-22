# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
The source chain of ``licenseid update``: where the target version of the SPDX
License List and its data come from.

Sources (``update --source``):

- ``bundle``: our compact bundle, ``v<version>.json.gz`` under
  ``spdx_source.BUNDLE_BASE_URL`` (raw.githubusercontent.com, about 1 MB),
  cached as ``spdx-bundle-v<version>.json.gz``. Version from our
  ``latest.json``.
- ``tarball``: SPDX's release tarball from GitHub (about 49 MB), cached as
  ``spdx-data-v<version>.tar.gz``. Version from spdx.org's ``licenses.json``.
- ``packaged``: the snapshot shipped in the wheel
  (``spdxdata.packaged_bundle``, reported as ``spdx-bundle.json.gz``), its own
  version. No network call at all, popularity data included.
- ``auto`` (the default): the version from ``latest.json``, then
  ``licenses.json``, then a stale cache, then the snapshot; the data from a
  cached bundle or tarball of that version, then the bundle, then the
  tarball, then the snapshot.

An explicit source is that source only: its failure is the error. In ``auto``
a failure prints one warning, its ACTION naming the next source
(``downloading spdx-data-v<version>.tar.gz``, ``using packaged data
v<version>``); the last failure is the error.

The snapshot is shipped, not cached, so ``--no-cache`` allows it. ``auto``
falls back to it only if it holds the ``--version`` asked for and is not
older than the database: a failed download must not downgrade the database.
When the version itself comes from the snapshot (every lookup failed), the
network is not tried again: the data is the snapshot's too.
"""

import contextlib
import functools
import re
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from licenseid import spdx_source, spdxdata
from licenseid.console import warn
from licenseid.errors import InvalidInputError, LicenseIdError, typed
from licenseid.spdxdata import BundleError, SpdxData
from licenseid.types import UpdateSource

SOURCES: tuple[UpdateSource, ...] = get_args(UpdateSource)
# The version files each source trusts; the packaged source reads none.
_LOOKUPS: dict[UpdateSource, tuple[str, ...]] = {
    "auto": (spdx_source.LATEST_JSON_URL, spdx_source.LICENSES_JSON_URL),
    "bundle": (spdx_source.LATEST_JSON_URL,),
    "tarball": (spdx_source.LICENSES_JSON_URL,),
}
# What makes a tarball unusable when it is read (OSError: it cannot be read).
_BAD_TARBALL = (tarfile.TarError, EOFError, zlib.error, ValueError, RecursionError)
_NUMERIC_VERSION = re.compile(r"\d+(?:\.\d+)*")


@dataclass(frozen=True)
class UpdateRequest:
    """What ``update`` was asked for: ``--version``, ``--cache/--no-cache``,
    ``--source`` and ``--force``."""

    version: str | None = None
    use_cache: bool = True
    source: UpdateSource = "auto"
    force: bool = False


class _StepError(LicenseIdError):
    """A source failed; *final_action* is the ACTION of the error when no
    source follows (a fallback's ACTION takes its place otherwise)."""

    def __init__(self, message: str, final_action: str) -> None:
        super().__init__(message)
        self.final_action = final_action


def check_request(request: UpdateRequest) -> None:
    """Raise InvalidInputError for a source or version no chain can use."""
    if request.source not in SOURCES:
        raise InvalidInputError(
            f"option: invalid: source: {request.source!r}; "
            f"pass one of {', '.join(SOURCES)}"
        )
    version = request.version
    if version is not None and not spdx_source.is_valid_version(version):
        raise InvalidInputError(f"version: invalid: {version!r}")


class ReleaseChain:
    """The sources of one update, tried in turn (see the module docstring).

    *current* is the version of the database being updated, if any.
    """

    def __init__(
        self, cache_dir: Path, request: UpdateRequest, current: str | None
    ) -> None:
        check_request(request)
        self.cache_dir = cache_dir
        self.request = request
        self.current = current
        # No network call from here on: the packaged source, or a version
        # that came from the snapshot because every lookup failed.
        self.offline = request.source == "packaged"

    def target(self) -> tuple[str, str | None, str]:
        """``(version, release_date, source)`` of the version to install, as
        ``spdx_source.get_version_info`` returns it; source ``"packaged"``
        when it is the snapshot's."""
        request = self.request
        if request.source == "packaged":
            snapshot = self._packaged()
            self._refuse_downgrade(snapshot.version)
            return snapshot.version, snapshot.release_date, "packaged"
        try:
            return spdx_source.get_version_info(
                self.cache_dir,
                request.version,
                request.use_cache,
                _LOOKUPS[request.source],
            )
        except LicenseIdError as exc:  # never InvalidInputError: checked above
            fallback = self._fallback if request.source == "auto" else None
            if fallback is None:
                raise
            warn(f"{exc}; using packaged data v{fallback.version}")
            self.offline = True
            return fallback.version, fallback.release_date, "packaged"

    def _refuse_downgrade(self, version: str) -> None:
        """Refuse a snapshot older than the database unless ``--force``, or
        ``--version`` names it: a database is not made older by default."""
        current, request = self.current, self.request
        if request.force or request.version is not None or current is None:
            return
        if is_older(version, current):
            raise LicenseIdError(
                f"{spdxdata.PACKAGED_NAME}: older than the database: "
                f"v{version} < v{current}; "
                "run 'licenseid update --source packaged --force'"
            )

    def load(self, target: str) -> tuple[SpdxData, str]:
        """The data of *target* from the first source that has it, and how
        it was got (``bundle (cache)``, ``tarball (remote)``, ``packaged``
        and so on), for the ``Data sources:`` report."""
        steps = self._steps(target)
        kind = steps.pop(0)
        while True:
            try:
                return self._load(kind, target)
            except LicenseIdError as exc:
                following = steps.pop(0) if steps else None
                if following == "packaged" and self._fallback is None:
                    following = None
                if following is None:
                    if isinstance(exc, _StepError):
                        raise LicenseIdError(f"{exc}; {exc.final_action}") from exc
                    raise
                warn(f"{exc}; {self._action(following, target)}")
                kind = following

    def _steps(self, target: str) -> list[UpdateSource]:
        """The sources to try for *target*, in order: in ``auto``, a cached
        bundle or tarball first, as the cache comes before a download."""
        if self.offline:
            return ["packaged"]
        if self.request.source != "auto":
            return [self.request.source]
        network: list[UpdateSource] = ["bundle", "tarball"]
        cached = [kind for kind in network if self._cached(kind, target)]
        return [*cached, *(k for k in network if k not in cached), "packaged"]

    def _cached(self, kind: UpdateSource, target: str) -> bool:
        """Whether *kind* would read its cache for *target*."""
        return (
            self.request.use_cache
            and (self.cache_dir / _cache_name(kind, target)).exists()
        )

    def _action(self, kind: UpdateSource, target: str) -> str:
        """The ACTION of a warning whose fallback is *kind*."""
        if kind == "packaged":
            return f"using packaged data v{self._packaged().version}"
        name = _cache_name(kind, target)
        return (
            f"using cached {name}"
            if self._cached(kind, target)
            else f"downloading {name}"
        )

    def _load(self, kind: UpdateSource, target: str) -> tuple[SpdxData, str]:
        """The data of *target* from *kind*; LicenseIdError if it has none."""
        if kind == "packaged":
            return self._packaged(), "packaged"
        if kind == "bundle":
            data, origin = spdx_source.get_bundle(
                self.cache_dir, target, self.request.use_cache
            )
            return data, f"bundle ({origin})"
        return self._tarball(target)

    def _tarball(self, target: str) -> tuple[SpdxData, str]:
        """The tarball of *target*, cached or downloaded. One that cannot be
        read is removed; a cached one is then downloaded again."""
        path, origin = spdx_source.get_tarball_path(
            self.cache_dir, target, self.request.use_cache
        )
        if origin == "cache":
            try:
                return _read_tarball(path, "cache unusable"), "tarball (cache)"
            except LicenseIdError as exc:
                if path.exists():  # not removed: a download cannot replace it
                    raise _StepError(
                        str(exc), "remove it and run 'licenseid update' again"
                    ) from exc
                warn(f"{exc}; downloading")
            path, origin = spdx_source.get_tarball_path(self.cache_dir, target, False)
        return _read_tarball(path, "download unusable"), f"tarball ({origin})"

    @functools.cached_property
    def _snapshot(self) -> SpdxData | str:
        """The packaged snapshot, read once, or the CONDITION of why there is
        none (``not found``, ``invalid: <detail>``)."""
        raw = spdxdata.packaged_bundle()
        if raw is None:
            return "not found"
        try:
            return SpdxData.from_bundle(raw, None)
        except BundleError as exc:
            return f"invalid: {exc}"

    def _packaged(self) -> SpdxData:
        """The snapshot, if it holds the version asked for; else raise
        LicenseIdError."""
        snapshot = self._snapshot
        if isinstance(snapshot, str):
            raise LicenseIdError(f"{spdxdata.PACKAGED_NAME}: {snapshot}")
        wanted = self.request.version
        if wanted is not None and snapshot.version != wanted:
            raise LicenseIdError(
                f"{spdxdata.PACKAGED_NAME}: not found: version {wanted} "
                f"(packaged: {snapshot.version})"
            )
        return snapshot

    @functools.cached_property
    def _fallback(self) -> SpdxData | None:
        """The snapshot, if ``auto`` may fall back to it: absent, of another
        version than ``--version``, or older than the database, it may not.
        An unreadable one is reported, once."""
        snapshot = self._snapshot
        if isinstance(snapshot, str):
            if snapshot != "not found":
                warn(f"{spdxdata.PACKAGED_NAME}: {snapshot}")
            return None
        wanted, current = self.request.version, self.current
        if wanted is not None and snapshot.version != wanted:
            return None
        if current is not None and is_older(snapshot.version, current):
            return None
        return snapshot


def _cache_name(kind: UpdateSource, version: str) -> str:
    """The cache file name of *kind* (bundle or tarball) for *version*."""
    template = (
        spdx_source.CACHE_BUNDLE_TEMPLATE
        if kind == "bundle"
        else spdx_source.CACHE_SPDX_TARBALL_TEMPLATE
    )
    return template.format(version=version)


def _read_tarball(path: Path, condition: str) -> SpdxData:
    """The data in the tarball at *path*. One that cannot be read is removed,
    best effort, and LicenseIdError ``<name>: <condition>: <detail>`` raised."""
    try:
        return SpdxData.from_tarball(path)
    except (*_BAD_TARBALL, OSError) as exc:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        raise LicenseIdError(f"{path.name}: {condition}: {typed(exc)}") from exc


def _numbers(version: str) -> tuple[int, ...] | None:
    """*version* as numbers without trailing zeros (``3.29.0`` is ``3.29``),
    or None if it is not all numbers (``3.0rc1``)."""
    if not _NUMERIC_VERSION.fullmatch(version):
        return None
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_older(version: str, than: str) -> bool:
    """Whether release *version* is older than *than*. Versions that are not
    all numbers are not compared: never older."""
    mine, theirs = _numbers(version), _numbers(than)
    return mine is not None and theirs is not None and mine < theirs


def fetch_popularity(
    cache_dir: Path, use_cache: bool, offline: bool
) -> tuple[dict[str, int], str]:
    """Popularity data for an update, as ``(popularity_map, source)``: the
    cache only when *offline*, else a valid cache (if *use_cache*), then one
    download, then a stale cache (if *use_cache*)."""
    if offline:
        return spdx_source.cached_popularity_data(cache_dir, use_cache)
    cache_path = cache_dir / spdx_source.CACHE_POPULARITY_CSV
    fresh = use_cache and spdx_source.is_cache_valid(
        cache_path, spdx_source.EXPIRY_POPULARITY_CSV
    )
    return spdx_source.fetch_popularity_data(
        cache_dir, cache_path if fresh else None, allow_stale=use_cache
    )
