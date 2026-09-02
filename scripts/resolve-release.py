#!/usr/bin/env python3
"""Resolve, download, and fingerprint the current official Linux package.

The download page is the source of truth.  Google does not publish a checksum
for this archive, so the workflow fingerprints the bytes it downloads and then
passes that digest to appimage-python, which verifies its own download before
building.  A release is considered unchanged only when its source digest is
available in the latest release.
"""

from __future__ import annotations

import gzip
import hashlib
import html.parser
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DOWNLOAD_PAGE = "https://antigravity.google/download?os=linux"
SECTION_ID = "antigravity-ide"
STANDALONE = True
USER_AGENT = "AntigravityIDE-AppImage"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")


class DownloadParser(html.parser.HTMLParser):
    """Collect the Linux x64 download of one section of the download page.

    The page ships every platform in the same document and lets client side
    script reveal one of them, so the platform is read from the
    ``data-os-content`` wrapper instead of from a visible heading.
    """

    def __init__(self, section_id: str, standalone: bool = False) -> None:
        super().__init__()
        self.section_id = section_id
        self.standalone = standalone
        self.section_depth = 0
        self.wrappers: list[tuple[str, bool]] = []
        self.anchor: tuple[str, str, list[str]] | None = None
        self.version_text: list[str] | None = None
        self.download_url = ""
        self.version = ""

    def platform(self) -> str:
        for platform, _ in reversed(self.wrappers):
            if platform:
                return platform
        return ""

    def in_standalone(self) -> bool:
        return any(standalone for _, standalone in self.wrappers)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Repeated attributes keep the first value, per the HTML spec.
        attributes: dict[str, str | None] = {}
        for name, value in attrs:
            attributes.setdefault(name, value)
        classes = attributes.get("class", "") or ""
        if tag == "section":
            if self.section_depth:
                self.section_depth += 1
            elif attributes.get("id") == self.section_id:
                self.section_depth = 1
            return
        if not self.section_depth:
            return
        if tag == "div":
            self.wrappers.append(
                (
                    attributes.get("data-os-content") or "",
                    "standalone-ide-wrapper" in classes,
                )
            )
        elif tag == "a":
            self.anchor = (attributes.get("href", "") or "", classes, [])
            if "nav-version-chip" in classes:
                self.version_text = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.anchor:
            self.anchor[2].append(data)
        if self.version_text is not None:
            self.version_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "section" and self.section_depth:
            self.section_depth -= 1
            self.wrappers.clear()
            return
        if tag == "div" and self.wrappers:
            self.wrappers.pop()
        if tag == "a" and self.anchor:
            href, classes, text = self.anchor
            label = " ".join("".join(text).split()).lower()
            if (
                self.platform() == "linux"
                and "button-primary" in classes
                and label == "download for x64"
                and "linux-x64" in href
                and href.endswith(".tar.gz")
            ):
                self.download_url = href
            self.anchor = None
        if tag == "a" and self.version_text is not None:
            if not self.standalone or self.in_standalone():
                match = re.search(r"v?(\d+(?:\.\d+)+)", "".join(self.version_text))
                if match:
                    self.version = match.group(1)
            self.version_text = None


def request(url: str) -> bytes:
    """Fetch bytes without changing archive contents."""
    return urlopen(
        Request(url, headers={"User-Agent": USER_AGENT}), timeout=60
    ).read()


def request_text(url: str) -> bytes:
    """Fetch a possibly gzip-compressed text response."""
    data = request(url)
    return gzip.decompress(data) if data.startswith(b"\x1f\x8b") else data


def latest_source_hash() -> str | None:
    if "/" not in REPOSITORY:
        return None
    api = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        release = json.loads(urlopen(Request(api, headers=headers), timeout=30).read())
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    for asset in release.get("assets", []):
        if asset.get("name") == "SOURCE-SHA256":
            value = request_text(asset["browser_download_url"]).decode().strip().split()
            return value[0].lower() if value else None
    return None


def output(name: str, value: str) -> None:
    print(f"{name}={value}")
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with Path(output_file).open("a", encoding="utf-8") as file:
            file.write(f"{name}={value}\n")


def main() -> int:
    parser = DownloadParser(SECTION_ID, standalone=STANDALONE)
    parser.feed(request_text(DOWNLOAD_PAGE).decode("utf-8"))
    if not parser.download_url or not parser.version:
        raise RuntimeError(
            f"Could not find the current Linux x64 package in '{SECTION_ID}' "
            "on the download page"
        )

    archive = Path.cwd() / "source" / "Antigravity.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(request(parser.download_url))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()

    output("download_url", parser.download_url)
    output("version", parser.version)
    output("sha256", digest)
    output("archive_path", str(archive))
    output("changed", str(digest.lower() != (latest_source_hash() or "").lower()).lower())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
