# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The channel sampler (``tools/licence_sample``) reads each registry's
reply as the registry writes it, with no network: every reply here is a
fake ``fetch``."""
# pylint: disable=missing-function-docstring

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from tools.licence_sample import channels, frame
from tools.licence_sample.__main__ import cut_command, main, short, tally
from tools.licence_sample.channels import ECOSYSTEMS_URL
from tools.licence_sample.urls import is_url, see_also, url_key

POM = '<project xmlns="http://maven.apache.org/POM/4.0.0">{parent}{licenses}</project>'
LICENSES = """<licenses>
  <license><name>Apache License, Version 2.0</name>
    <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url></license>
  <license><name>MIT</name></license>
</licenses>"""
PARENT = """<parent><groupId>org.x</groupId><artifactId>parent</artifactId>
  <version>7</version></parent>"""


def _fetch(replies: dict[str, str]) -> channels.Fetch:
    def fetch(url: str) -> bytes | None:
        reply = replies.get(url)
        return None if reply is None else reply.encode("utf-8")

    return fetch


def test_a_pom_gives_each_licence_name_and_url() -> None:
    url = channels.pom_url("org.x", "a", "1")
    assert url == "https://repo1.maven.org/maven2/org/x/a/1/a-1.pom"
    pom = POM.format(parent="", licenses=LICENSES)
    assert channels.maven("org.x:a", "1", _fetch({url: pom})) == [
        {"field": "name", "value": "Apache License, Version 2.0"},
        {"field": "url", "value": "https://www.apache.org/licenses/LICENSE-2.0.txt"},
        {"field": "name", "value": "MIT"},
    ]


def test_a_pom_with_no_licence_gives_its_parents() -> None:
    replies = {
        channels.pom_url("org.x", "a", "1"): POM.format(parent=PARENT, licenses=""),
        channels.pom_url("org.x", "parent", "7"): POM.format(
            parent="", licenses=LICENSES
        ),
    }
    values = channels.maven("org.x:a", "1", _fetch(replies))
    assert [v["field"] for v in values] == ["parent:name", "parent:url", "parent:name"]


def test_a_parent_loop_ends() -> None:
    url = channels.pom_url("org.x", "parent", "7")
    looping = POM.format(parent=PARENT, licenses="")
    assert channels.maven("org.x:parent", "7", _fetch({url: looping})) == []


@pytest.mark.parametrize(
    "raw",
    [
        b'<!DOCTYPE x [<!ENTITY a "aaaa">]><project>&a;</project>',
        b"<project>",  # not well formed
        None,
    ],
    ids=["entity", "broken", "missing"],
)
def test_xml_that_declares_an_entity_or_breaks_is_not_read(raw: bytes | None) -> None:
    assert channels.xml_root(raw) is None


def test_a_nuspec_gives_its_expression_and_url() -> None:
    url = "https://api.nuget.org/v3-flatcontainer/pkg/1.0.0/pkg.nuspec"
    nuspec = """<package><metadata><license type="expression">MIT</license>
      <licenseUrl>https://licenses.nuget.org/MIT</licenseUrl></metadata></package>"""
    assert channels.nuget("Pkg", "1.0.0", _fetch({url: nuspec})) == [
        {"field": "license:expression", "value": "MIT"},
        {"field": "licenseUrl", "value": "https://licenses.nuget.org/MIT"},
    ]


@pytest.mark.parametrize(
    ("doc", "values"),
    [
        ({"license": "MIT"}, [("license", "MIT")]),
        (
            {"license": {"type": "BSD", "url": "http://x/LICENSE"}},
            [("license.type", "BSD"), ("license.url", "http://x/LICENSE")],
        ),
        (
            {"licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}]},
            [("licenses.type", "MIT"), ("licenses.type", "Apache-2.0")],
        ),
        ({"license": "  "}, []),
    ],
)
def test_npm_reads_every_form_of_its_field(
    doc: dict[str, object], values: list[tuple[str, str]]
) -> None:
    url = "https://registry.npmjs.org/@s%2Fp/1.0"
    found = channels.npm("@s/p", "1.0", _fetch({url: json.dumps(doc)}))
    assert [(v["field"], v["value"]) for v in found] == values


def test_pypi_reads_its_three_fields() -> None:
    info = {
        "license_expression": "MIT",
        "license": "MIT License",
        "classifiers": ["License :: OSI Approved :: MIT License", "Topic :: X"],
    }
    url = "https://pypi.org/pypi/p/1.0/json"
    found = channels.pypi("p", "1.0", _fetch({url: json.dumps({"info": info})}))
    assert [v["field"] for v in found] == [
        "License-Expression",
        "License",
        "Classifier",
    ]


def test_a_model_card_gives_each_licence_and_its_link() -> None:
    card = {"license": ["mit", "apache-2.0"], "license_link": "https://x/LICENSE"}
    url = "https://huggingface.co/api/models/o/m/revision/abc"
    found = channels.huggingface(
        "o/m", "abc", _fetch({url: json.dumps({"cardData": card})})
    )
    assert [(v["field"], v["value"]) for v in found] == [
        ("license", "mit"),
        ("license", "apache-2.0"),
        ("license_link", "https://x/LICENSE"),
    ]


def test_a_crate_reads_the_listed_value() -> None:
    assert channels.cargo("c", "1", _fetch({}), "MIT OR Apache-2.0") == [
        {"field": "license", "value": "MIT OR Apache-2.0"}
    ]


@pytest.mark.parametrize(
    ("value", "url"),
    [
        ("https://opensource.org/licenses/MIT", True),
        ("www.apache.org/licenses/LICENSE-2.0", True),
        ("<http://x.org/l>", False),  # angle brackets: not read
        ("MIT (https://opensource.org/licenses/MIT)", False),  # in prose
        ("MIT", False),
    ],
)
def test_a_url_is_the_whole_value(value: str, url: bool) -> None:
    assert is_url(value) is url


@pytest.mark.parametrize(
    "spelling",
    [
        "https://www.apache.org/licenses/LICENSE-2.0",
        "http://apache.org/licenses/LICENSE-2.0/",
        "HTTPS://WWW.APACHE.ORG/licenses/LICENSE-2.0/index.html#x",
    ],
)
def test_spellings_of_one_page_have_one_key(spelling: str) -> None:
    assert url_key(spelling) == "apache.org/licenses/license-2.0"


def test_the_query_is_part_of_the_key() -> None:
    page = "www.apache.org/licenses/LICENSE-2.0"
    assert url_key(page + "?y=1") != url_key(page)
    assert url_key(page + "?y=1") == url_key("https://" + page + "?y=1")


def test_see_also_maps_each_url_to_its_licences(tmp_path: Path) -> None:
    path = tmp_path / "licenses.json"
    page = "https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html"
    path.write_text(
        json.dumps(
            {
                "licenses": [
                    {"licenseId": "GPL-2.0-only", "seeAlso": [page]},
                    {"licenseId": "GPL-2.0-or-later", "seeAlso": [page]},
                    {"licenseId": "MIT", "seeAlso": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    table = see_also(path)
    assert table[url_key(page) or ""] == {"GPL-2.0-only", "GPL-2.0-or-later"}
    assert table["spdx.org/licenses/mit"] == {"MIT"}


def test_see_also_skips_a_url_with_a_fragment(tmp_path: Path) -> None:
    path = tmp_path / "licenses.json"
    path.write_text(
        json.dumps(
            {"licenses": [{"licenseId": "MIT", "seeAlso": ["https://x.org/faq#MIT"]}]}
        ),
        encoding="utf-8",
    )
    assert not any(key.startswith("x.org") for key in see_also(path))


def test_tally_counts_values_and_urls(corpus_db: LicenseDatabase) -> None:
    table = {"spdx.org/licenses/mit": {"MIT"}, "x.org/gpl": {"GPL-2.0-only", "GPL-2.0"}}
    packages: list[dict[str, Any]] = [
        {"values": [{"field": "name", "value": "MIT"}]},
        {"values": [{"field": "url", "value": "https://spdx.org/licenses/MIT"}]},
        {"values": [{"field": "url", "value": "http://x.org/gpl"}]},
        {"values": [{"field": "url", "value": "https://aka.ms/eula"}]},
        {"values": [{"field": "name", "value": "x" * 300}]},  # licence text
        {"values": [{"field": "name", "value": "Some Licence"}]},
        {"values": []},
    ]
    counts = tally(packages, table, corpus_db)
    assert counts["packages"] == {"with a value": 5, "none": 2}
    assert counts["packages stating a URL"] == {"with a URL": 3}
    assert counts["categories"] == {"exact": 1, "unresolved": 1}
    assert counts["unresolved values"] == {"Some Licence": 1}
    assert counts["urls"] == {"one licence": 1, "several": 1, "none": 1}
    assert counts["unlisted hosts"] == {"aka.ms": 1}


def test_licence_text_is_no_declared_value() -> None:
    assert short("MIT")
    assert not short("Permission is hereby granted\nto any person")


def test_a_frame_keeps_its_criteria_and_packages(tmp_path: Path) -> None:
    rows = [{"name": "p", "latest_release_number": "1.0", "downloads": 9}]
    pages = {
        ECOSYSTEMS_URL.format(registry="npmjs.org", sort="downloads", page=1): rows
    }

    def get(url: str) -> bytes | None:
        return json.dumps(pages[url]).encode() if url in pages else b"[]"

    packages = frame.rank("npm", 5, get)
    assert packages == [
        {
            "rank": 1,
            "name": "p",
            "version": "1.0",
            "downloads": 9,
            "downloads_period": None,
            "dependents": None,
            "listed": None,
        }
    ]
    header = frame.criteria("npm", 5, "2026-11-05T00:00:00+00:00")
    path = tmp_path / "frame.jsonl"
    frame.write_frame(path, header, packages)
    assert frame.read_frame(path) == (header, packages)
    assert header["population"].startswith("packages of npmjs.org")


@pytest.mark.parametrize(
    "first", ['{"name": "p"}', '{"frame": {"format": 0}}', ""], ids=str
)
def test_a_file_that_is_no_frame_is_refused(tmp_path: Path, first: str) -> None:
    path = tmp_path / "frame.jsonl"
    path.write_text(first + "\n", encoding="utf-8")
    with pytest.raises(frame.FrameError):
        frame.read_frame(path)


def test_a_package_records_each_reply_at_its_version() -> None:
    url = "https://registry.npmjs.org/p/1.0"
    body = b'{"license": "MIT"}'
    package = {"rank": 1, "name": "p", "version": "1.0"}
    read = frame.read_package("npm", package, lambda u: body if u == url else None)
    assert read["replies"] == [{"url": url, "sha256": hashlib.sha256(body).hexdigest()}]
    assert read["values"] == [{"field": "license", "value": "MIT"}]
    missing = frame.read_package("npm", package, lambda _: None)
    assert (missing["replies"][0]["sha256"], missing["values"]) == (None, [])


def _page(n: int) -> str:
    return ECOSYSTEMS_URL.format(registry="npmjs.org", sort="downloads", page=n)


@pytest.mark.parametrize(
    "second", [None, b"<html>busy</html>", b'{"error": 1}'], ids=str
)
def test_a_failed_ranking_page_refuses_the_frame(second: bytes | None) -> None:
    pages = {_page(1): json.dumps([{"name": "p"}]).encode(), _page(2): second}
    with pytest.raises(frame.FrameError, match="1 packages read"):
        frame.rank("npm", 5, pages.get)


def test_an_empty_ranking_page_ends_the_registry() -> None:
    pages = {_page(1): json.dumps([{"name": "p"}]).encode(), _page(2): b"[]"}
    assert [p["name"] for p in frame.rank("npm", 5, pages.get)] == ["p"]


def _ranked(count: int) -> list[dict[str, Any]]:
    return [{"rank": n, "name": f"p{n}", "version": "1"} for n in range(1, count + 1)]


def test_a_cut_keeps_the_top_and_says_what_it_was_cut_from() -> None:
    header = frame.criteria("npm", 4, "2026-11-05T00:00:00+00:00")
    smaller, kept = frame.cut(header, _ranked(4), 2)
    assert [p["rank"] for p in kept] == [1, 2]
    assert (smaller["count"], smaller["cut_from"]) == (2, 4)
    assert "top 2;" in smaller["population"]
    assert smaller["taken"] == header["taken"]


def test_a_cut_beyond_the_frame_is_refused() -> None:
    header = frame.criteria("npm", 4, "2026-11-05T00:00:00+00:00")
    with pytest.raises(frame.FrameError):
        frame.cut(header, _ranked(3), 4)


def _write_run(tmp_path: Path, read: list[int]) -> tuple[Path, Path]:
    paths = (tmp_path / "frame.jsonl", tmp_path / "sample.jsonl")
    frame.write_frame(paths[0], frame.criteria("npm", 4, "t"), _ranked(4))
    lines = [json.dumps({"rank": n, "values": []}) for n in read]
    paths[1].write_text("".join(line + "\n" for line in lines), "utf-8")
    return paths


def test_a_cut_sample_is_in_rank_order(tmp_path: Path) -> None:
    paths = _write_run(tmp_path, [3, 1, 2])  # threads finish out of order
    outs = (tmp_path / "f2.jsonl", tmp_path / "s2.jsonl")
    cut_command(paths, 2, outs)
    assert frame.read_frame(outs[0])[0]["count"] == 2
    lines = outs[1].read_text("utf-8").splitlines()
    assert [json.loads(line)["rank"] for line in lines] == [1, 2]


def test_a_sample_missing_a_ranked_package_is_not_cut(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frame_path, sample = _write_run(tmp_path, [1, 3])
    argv = ["cut", str(frame_path), str(sample), "--count", "2"]
    argv += ["--out-frame", str(tmp_path / "f"), "--out-sample", str(tmp_path / "s")]
    assert main(argv) == 1
    assert capsys.readouterr().err.startswith("ERROR: frame: ")
    assert not (tmp_path / "f").exists()


def test_a_failed_reply_is_recorded_as_failed_not_as_no_licence(
    corpus_db: LicenseDatabase,
) -> None:
    def failing(_url: str) -> bytes | None:
        raise frame.FetchError("HTTP 503")

    package = {"rank": 1, "name": "p", "version": "1.0"}
    read = frame.read_package("npm", package, failing)
    assert read["replies"][0]["error"] == "HTTP 503"
    counts = tally([read, {"values": [], "replies": []}], {}, corpus_db)
    assert counts["packages"] == {"failed": 1, "none": 1}
