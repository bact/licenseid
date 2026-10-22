# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Fetching and caching the SPDX License List (version files, the compact bundle,
the upstream tarball) and GitHub popularity data.

Kept independent of SQLite storage (see database.py) and of the order of
sources (see releasesource.py): these functions only read and write plain cache
files under a caller-supplied directory and return parsed data, so they can be
tested without a database.
"""

import contextlib
import csv
import importlib
import io
import json
import os
import re
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

import requests

from licenseid.console import status, warn
from licenseid.errors import InvalidInputError, LicenseIdError, typed
from licenseid.spdxdata import BundleError, SpdxData

LICENSES_JSON_URL = "https://spdx.org/licenses/licenses.json"
POPULARITY_DATA_URL = (
    "https://raw.githubusercontent.com/github/innovationgraph/main/data/licenses.csv"
)
TARBALL_URL_TEMPLATE = (
    "https://github.com/spdx/license-list-data/archive/refs/tags/v{version}.tar.gz"
)
# Our own compact bundles (gzipped JSON, spdxdata format 1), published on the
# `data` branch: `latest.json` (the two keys of SPDX's licenses.json, and more)
# and `v<version>.json.gz`. The format is in the path, so a later format cannot
# break an installed client; refs/heads/ stops a tag named `data` shadowing it.
BUNDLE_BASE_URL = (
    "https://raw.githubusercontent.com/bact/licenseid/refs/heads/data/spdx/format-1/"
)
LATEST_JSON_URL = f"{BUNDLE_BASE_URL}latest.json"
BUNDLE_URL_TEMPLATE = f"{BUNDLE_BASE_URL}v{{version}}.json.gz"
# Compressed size cap of a downloaded bundle: 3.29.0 is about 1 MiB.
MAX_BUNDLE_BYTES: Final = 16 * 2**20
# (connect, read) in seconds: a host that a sandbox blocks fails in seconds,
# not minutes; a small file needs less time to arrive than a release.
SMALL_FILE_TIMEOUT: Final = (10, 30)
RELEASE_TIMEOUT: Final = (10, 60)

# License list versions become part of a cache file name and a download URL, so
# reject anything that could carry a path separator or URL syntax, whether it
# comes from --version or from a third-party licenses.json.
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

CACHE_LICENSES_JSON = "licenses.json"
CACHE_LATEST_JSON = "latest.json"
CACHE_POPULARITY_CSV = "popularity.csv"
CACHE_SPDX_TARBALL_TEMPLATE = "spdx-data-v{version}.tar.gz"
CACHE_BUNDLE_TEMPLATE = "spdx-bundle-v{version}.json.gz"

# Expiration in days
EXPIRY_LICENSES_JSON = 45
# SPDX releases every 3-6 months and latest.json follows within a week, so it
# can last as long as licenses.json.
EXPIRY_LATEST_JSON = EXPIRY_LICENSES_JSON
EXPIRY_POPULARITY_CSV = 75

# A cache file may look slightly newer than "now" (clock differences on a
# network filesystem); beyond this it is treated as a bad timestamp.
_CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)


def clear_cache_files(directory: Path) -> None:
    """Remove every download cache file in *directory*, including the
    temporary files a killed download orphans."""
    for filename in (CACHE_LICENSES_JSON, CACHE_LATEST_JSON, CACHE_POPULARITY_CSV):
        path = directory / filename
        if path.exists():  # a parent that is not a directory has none
            path.unlink(missing_ok=True)
    for pattern in (
        "spdx-data-v*.tar.gz",
        f"{CACHE_LICENSES_JSON}.*.tmp",
        f"{CACHE_LATEST_JSON}.*.tmp",
        f"{CACHE_POPULARITY_CSV}.*.tmp",
        "spdx-data-v*.tar.gz.*.tmp",
        "spdx-bundle-v*.json.gz",
        "spdx-bundle-v*.json.gz.*.tmp",
    ):
        for path in directory.glob(pattern):
            path.unlink(missing_ok=True)


def user_agent() -> str:
    """User-Agent that identifies this client to third-party servers, so they
    can contact or rate-limit us instead of an anonymous python-requests.

    Resolved at call time: importing licenseid.__version__ at module level
    would make a cycle (the package __init__ imports database, which imports
    this module).
    """
    version = importlib.import_module("licenseid").__version__
    return f"licenseid/{version} (+https://github.com/bact/licenseid)"


def _http_get(
    url: str, timeout: float | tuple[float, float], stream: bool = False
) -> requests.Response:
    """GET with an identifying User-Agent, a single attempt, and a timeout.

    Deliberately no retries or backoff loops: a failing third-party server is
    hit once per run, and callers fall back to cached data.
    """
    return requests.get(
        url, headers={"User-Agent": user_agent()}, timeout=timeout, stream=stream
    )


@contextlib.contextmanager
def _atomic_path(path: Path) -> Iterator[Path]:
    """Yield a unique temporary path next to *path*; rename it onto *path* if
    the block succeeds, remove it either way.

    An interrupted write can therefore never leave a truncated file at
    *path* that looks like a valid cache, and concurrent runs cannot
    clobber each other's temporary file.
    """
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        yield tmp_path
        os.replace(tmp_path, path)
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)


def is_valid_version(version: object) -> bool:
    """True if *version* is a string safe to use in a file name and URL."""
    return isinstance(version, str) and _VERSION_RE.fullmatch(version) is not None


def is_cache_valid(path: Path, days: int) -> bool:
    """Check if the cache file exists and is not older than 'days'.

    A file dated well into the future (clock change, bad timestamp) is not
    valid, or it would never expire.
    """
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime
    return -_CLOCK_SKEW_TOLERANCE <= age < timedelta(days=days)


def _version_and_date(data: Any) -> tuple[str | None, str | None]:
    """(licenseListVersion, releaseDate) of a parsed licenses.json or
    latest.json, or (None, None) if it has no valid version. Both come from a
    third party: a release date that is not a string is dropped."""
    if not isinstance(data, dict) or not is_valid_version(
        data.get("licenseListVersion")
    ):
        return None, None
    release_date = data.get("releaseDate")
    return data["licenseListVersion"], (
        release_date if isinstance(release_date, str) else None
    )


# Each version file has a cache of its own: spdx.org can name a version our
# bundle does not have yet, so the bundle never reads spdx.org's answer.
_VERSION_CACHES: dict[str, tuple[str, int]] = {
    LICENSES_JSON_URL: (CACHE_LICENSES_JSON, EXPIRY_LICENSES_JSON),
    LATEST_JSON_URL: (CACHE_LATEST_JSON, EXPIRY_LATEST_JSON),
}


def _read_version_file(path: Path) -> tuple[str | None, str | None]:
    """(licenseListVersion, releaseDate) of a cached version file, or
    (None, None) if it is missing, unreadable, or not a usable object."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):  # incl. JSONDecodeError, UnicodeDecodeError
        return None, None
    return _version_and_date(data)


def _download_version_file(url: str, path: Path) -> tuple[str | None, str | None]:
    """Download the version file at *url* (spdx.org's licenses.json or our
    latest.json) and cache it at *path* if usable.

    Returns (licenseListVersion, releaseDate), or (None, None) if the
    response has no license list version (and is then not cached). Raises
    requests.RequestException on a network, HTTP or JSON-decoding failure.
    """
    status(f"Fetching latest license list info from {url}...")
    resp = _http_get(url, timeout=SMALL_FILE_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    version, release_date = _version_and_date(data)
    if version is None:
        return None, None
    try:
        with _atomic_path(path) as tmp_path, open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        warn(f"{path.name}: cache write failed: {typed(e)}")
    return version, release_date


def _fresh_version(
    cache_dir: Path, urls: tuple[str, ...]
) -> tuple[str | None, str | None]:
    """The version in the first valid cache of *urls* that holds one; a
    valid cache that holds none is reported."""
    for url in urls:
        name, days = _VERSION_CACHES[url]
        path = cache_dir / name
        if not is_cache_valid(path, days):
            continue
        version, release_date = _read_version_file(path)
        if version:
            return version, release_date
        warn(f"{name}: cache unusable; downloading")
    return None, None


def _download_version(
    cache_dir: Path, urls: tuple[str, ...]
) -> tuple[str | None, str | None, str]:
    """The version of the first of *urls* whose download gives one, as
    ``(version, release_date, "")``, or ``(None, None, failure)``: *failure*
    is the ``SUBJECT: CONDITION: DETAIL`` of the last one. A URL that fails
    with another to try warns, naming the next."""
    failure = ""
    for url in urls:
        name = _VERSION_CACHES[url][0]
        if failure:
            warn(f"{failure}; downloading {name}")
        try:
            version, release_date = _download_version_file(url, cache_dir / name)
        except requests.RequestException as e:
            failure = f"{name}: download failed: {typed(e)}"
            continue
        if version:
            return version, release_date, ""
        failure = f"{name}: download unusable: no valid license list version"
    return None, None, failure


def _stale_version(
    cache_dir: Path, urls: tuple[str, ...], failure: str
) -> tuple[str | None, str | None]:
    """The version in the first cache of *urls* that has one, whatever its
    age, with the warning that *failure* falls back to it."""
    for url in urls:
        name = _VERSION_CACHES[url][0]
        version, release_date = _read_version_file(cache_dir / name)
        if version:
            own = failure.startswith(f"{name}:")
            warn(f"{failure}; using stale {'cache' if own else name}")
            return version, release_date
    return None, None


def get_version_info(
    cache_dir: Path,
    version: str | None,
    use_cache: bool,
    urls: tuple[str, ...] = (LICENSES_JSON_URL,),
) -> tuple[str, str | None, str]:
    """Determine target version and fetch version info.

    Returns ``(version, release_date, source)`` where source is ``"cache"``,
    ``"remote"``, ``"stale cache"`` or ``"unavailable"``.

    *urls* (not empty; ``LICENSES_JSON_URL``, ``LATEST_JSON_URL``) are the
    version files to trust, each with a cache file of its own. Only their
    caches are read: spdx.org's licenses.json can name a version our
    latest.json does not have yet. Order: the first valid cache (if
    *use_cache*), then one download of each in turn until one gives a version,
    then (only if *use_cache*) the first stale cache. If all fail, an explicit
    *version* is used as is; otherwise LicenseIdError is raised, worded
    ``SUBJECT: CONDITION: DETAIL`` with no ACTION, so a caller can add the
    fallback it takes.
    """
    if version is not None and not is_valid_version(version):
        raise InvalidInputError(f"version: invalid: {version!r}")

    if use_cache:
        latest_version, release_date = _fresh_version(cache_dir, urls)
        if latest_version:
            return version or latest_version, release_date, "cache"
    latest_version, release_date, failure = _download_version(cache_dir, urls)
    if latest_version:
        return version or latest_version, release_date, "remote"

    if use_cache:  # --no-cache means never fall back to cached data
        latest_version, release_date = _stale_version(cache_dir, urls, failure)
        if latest_version:
            return version or latest_version, release_date, "stale cache"
    if not version:
        raise LicenseIdError(failure)
    warn(f"{failure}; using version {version}")
    return version, None, "unavailable"


def get_tarball_path(
    cache_dir: Path, version: str, use_cache: bool
) -> tuple[Path, str]:
    """Download or retrieve the SPDX License List tarball path."""
    if not is_valid_version(version):
        raise InvalidInputError(f"version: invalid: {version!r}")
    tar_filename = CACHE_SPDX_TARBALL_TEMPLATE.format(version=version)
    tar_cache_path = cache_dir / tar_filename
    data_source = "remote"

    if not (use_cache and tar_cache_path.exists()):
        tar_url = TARBALL_URL_TEMPLATE.format(version=version)
        status(f"Downloading release: {tar_url}")
        try:
            resp = _http_get(tar_url, timeout=RELEASE_TIMEOUT, stream=True)
            resp.raise_for_status()
            with _atomic_path(tar_cache_path) as tmp_path, open(tmp_path, "wb") as f:
                f.writelines(resp.iter_content(chunk_size=8192))
        except requests.RequestException as e:
            raise LicenseIdError(f"{tar_filename}: download failed: {typed(e)}") from e
        except OSError as e:  # a full disk; on Windows, a file held open
            raise LicenseIdError(
                f"{tar_filename}: cache write failed: {typed(e)}"
            ) from e
    else:
        data_source = "cache"

    return tar_cache_path, data_source


def get_bundle(cache_dir: Path, version: str, use_cache: bool) -> tuple[SpdxData, str]:
    """The bundle of *version*, from the cache (if *use_cache*) or one
    download; returns ``(data, source)``, source ``"cache"`` or ``"remote"``.

    A cached bundle that cannot be read is removed and downloaded again, with
    a warning. Integrity is gzip's CRC, checked as the whole stream is read; a
    bundle is cached only once it parses, atomically, and never expires. A
    cache that cannot be written is a warning: the data is in memory.
    Raises LicenseIdError (``download failed`` or ``download unusable``,
    no ACTION) when the download gives no usable bundle, a 404 included.
    """
    if not is_valid_version(version):
        raise InvalidInputError(f"version: invalid: {version!r}")
    name = CACHE_BUNDLE_TEMPLATE.format(version=version)
    path = cache_dir / name
    if use_cache and path.exists():
        try:
            return SpdxData.from_bundle(path.read_bytes(), version), "cache"
        except (BundleError, OSError) as e:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
            detail = str(e) if isinstance(e, BundleError) else typed(e)
            warn(f"{name}: cache unusable: {detail}; downloading")
    raw = _download_bundle(name, BUNDLE_URL_TEMPLATE.format(version=version))
    try:
        data = SpdxData.from_bundle(raw, version)
    except BundleError as e:
        raise LicenseIdError(f"{name}: download unusable: {e}") from e
    try:
        with _atomic_path(path) as tmp_path:
            tmp_path.write_bytes(raw)
    except OSError as e:
        warn(f"{name}: cache write failed: {typed(e)}")
    return data, "remote"


def _download_bundle(name: str, url: str) -> bytes:
    """The bytes at *url*, at most MAX_BUNDLE_BYTES of them: counted as they
    arrive, as a Content-Length header can lie or be absent."""
    status(f"Downloading bundle: {url}")
    chunks: list[bytes] = []
    size = 0
    try:
        resp = _http_get(url, timeout=RELEASE_TIMEOUT, stream=True)
        try:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > MAX_BUNDLE_BYTES:
                    raise LicenseIdError(
                        f"{name}: download unusable: "
                        f"larger than {MAX_BUNDLE_BYTES} bytes"
                    )
                chunks.append(chunk)
        finally:
            resp.close()  # a stream given up early still holds its connection
    except requests.RequestException as e:
        raise LicenseIdError(f"{name}: download failed: {typed(e)}") from e
    return b"".join(chunks)


def _read_local_csv(path: Path) -> str | None:
    """Read a local popularity CSV; None (with a warning) on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        warn(f"{CACHE_POPULARITY_CSV}: cache read failed: {e}")
        return None


def _download_popularity_csv() -> tuple[str, str]:
    """Download the popularity CSV. Returns ``(text, failure)``: text is empty
    and *failure* is a ``download failed: ...`` condition on failure."""
    status(f"Downloading popularity data: {POPULARITY_DATA_URL}")
    try:
        resp = _http_get(POPULARITY_DATA_URL, timeout=SMALL_FILE_TIMEOUT)
        resp.raise_for_status()
        return resp.text, ""
    except requests.RequestException as e:
        return "", f"download failed: {typed(e)}"


def _write_popularity_cache(path: Path, csv_content: str) -> None:
    """Cache the CSV atomically; a write failure only costs a re-download."""
    try:
        with _atomic_path(path) as tmp_path:
            tmp_path.write_text(csv_content, encoding="utf-8")
    except OSError as e:
        warn(f"{CACHE_POPULARITY_CSV}: cache write failed: {e}")


def _parse_count(value: str | None) -> int | None:
    """Parse a pusher count; None if it is missing or not an integer."""
    try:
        return int(value or "")
    except ValueError:
        return None


def _aggregate_popularity(csv_content: str) -> dict[str, int]:
    """Sum pushers per SPDX license ID, skipping blank and NOASSERTION rows.

    A row with a missing or non-numeric count still lists the license, with 0
    pushers; the number of such rows is reported. On a CSV parse error
    nothing is returned, so partial data is never used or cached.
    """
    popularity_map: dict[str, int] = {}
    bad_counts = 0
    try:
        for row in csv.DictReader(io.StringIO(csv_content)):
            spdx_id = row.get("spdx_license")
            if not spdx_id or spdx_id == "NOASSERTION":
                continue
            count = _parse_count(row.get("num_pushers"))
            if count is None:
                bad_counts += 1
                count = 0
            popularity_map[spdx_id] = popularity_map.get(spdx_id, 0) + count
    except (csv.Error, ValueError) as e:
        warn(f"{CACHE_POPULARITY_CSV}: parse failed: {e}")
        return {}

    if bad_counts:
        warn(
            f"{CACHE_POPULARITY_CSV}: {bad_counts} rows with missing or non-numeric "
            "num_pushers; counted as 0"
        )
    if popularity_map:
        status(f"Aggregated popularity data for {len(popularity_map)} licenses.")
    return popularity_map


def fetch_popularity_data(
    cache_dir: Path, local_path: Path | None = None, allow_stale: bool = True
) -> tuple[dict[str, int], str]:
    """Fetch and aggregate popularity data from GitHub Innovation Graph.

    Returns ``(popularity_map, source)`` where source is ``"cache"``,
    ``"remote"``, ``"stale cache"`` or ``"unavailable"``. Order: usable
    *local_path* data, then one download (cached only if it parses), then, if
    *allow_stale*, a stale cache file. Every fallback prints a warning.
    """
    local_csv = _read_local_csv(local_path) if local_path else None
    popularity_map = _aggregate_popularity(local_csv) if local_csv else {}
    if popularity_map:
        return popularity_map, "cache"
    if local_csv is not None:  # read, even if empty; a read failure has warned
        warn(f"{CACHE_POPULARITY_CSV}: cache unusable; downloading")

    cache_path = cache_dir / CACHE_POPULARITY_CSV
    downloaded, failure = _download_popularity_csv()
    popularity_map = _aggregate_popularity(downloaded) if downloaded else {}
    if popularity_map:
        _write_popularity_cache(cache_path, downloaded)
        return popularity_map, "remote"
    failure = failure or "download unusable"  # never cached

    # A cache file already tried above as *local_path* is not read again.
    try_stale = allow_stale and cache_path.exists() and local_path != cache_path
    if try_stale:
        popularity_map = _aggregate_popularity(_read_local_csv(cache_path) or "")
        if popularity_map:
            warn(f"{CACHE_POPULARITY_CSV}: {failure}; using stale cache")
            return popularity_map, "stale cache"
    warn(f"{CACHE_POPULARITY_CSV}: {failure}")
    if try_stale:
        warn(f"{CACHE_POPULARITY_CSV}: stale cache unusable")
    return {}, "unavailable"


def cached_popularity_data(
    cache_dir: Path, use_cache: bool
) -> tuple[dict[str, int], str]:
    """Popularity data with no download, for an update that makes no network
    call: the cache file only, and only if *use_cache*. An expired file is
    still used, with a warning, as nothing fresher can be had; a missing or
    unusable one gives baseline scores, with a warning. Returns
    ``(popularity_map, source)`` as fetch_popularity_data does."""
    path = cache_dir / CACHE_POPULARITY_CSV
    if not (use_cache and path.exists()):
        warn(f"{CACHE_POPULARITY_CSV}: missing")
        return {}, "unavailable"
    popularity_map = _aggregate_popularity(_read_local_csv(path) or "")
    if not popularity_map:
        warn(f"{CACHE_POPULARITY_CSV}: cache unusable")
        return {}, "unavailable"
    if is_cache_valid(path, EXPIRY_POPULARITY_CSV):
        return popularity_map, "cache"
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    days = max((datetime.now(timezone.utc) - mtime).days, 0)
    warn(f"{CACHE_POPULARITY_CSV}: {days} days old; using stale cache")
    return popularity_map, "stale cache"
