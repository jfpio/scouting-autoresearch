#!/usr/bin/env python3
"""Fetch and parse approved Project Gutenberg HTML without its packaging or images."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


USER_AGENT = "scouting-autoresearch/0.1 (+https://github.com/jfpio/scouting-autoresearch)"


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    page_start: int
    page_end: int
    leading_small_caps: str | None = None


class GutenbergHtmlParser(HTMLParser):
    """Reduce Gutenberg HTML to page-aware textual blocks."""

    BLOCK_TAGS = {"p", "h3", "h4", "h5", "h6", "li", "tr"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page: int | None = None
        self.blocks: list[Block] = []
        self.capture_tag: str | None = None
        self.capture_depth = 0
        self.buffer: list[str] = []
        self.pages: list[int] = []
        self.small_caps_depth = 0
        self.small_caps_buffer: list[str] = []
        self.page_number_depth = 0
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if self.skip_depth:
            if tag not in self.VOID_TAGS:
                self.skip_depth += 1
            return
        if tag == "div" and classes.intersection({"figcenter", "figleft", "figright", "footnote"}):
            self.skip_depth = 1
            return
        if tag == "span" and "pageno" in classes:
            match = re.fullmatch(r"Page_(\d+)", attributes.get("id") or "")
            if match:
                self.page = int(match.group(1))
                if self.capture_tag:
                    self.pages.append(self.page)
                    self.page_number_depth = self.capture_depth + 1
        if self.capture_tag:
            if tag == "br":
                self.buffer.append("\n")
            elif tag in {"td", "th"} and self.buffer:
                self.buffer.append("\t")
            if tag in self.VOID_TAGS:
                return
            self.capture_depth += 1
            if tag == "span" and "sc" in classes:
                self.small_caps_depth = self.capture_depth
            return
        if tag in self.BLOCK_TAGS or (tag == "div" and "line" in classes):
            self.capture_tag = "line" if tag == "div" else tag
            self.capture_depth = 1
            self.buffer = []
            self.pages = [self.page] if self.page is not None else []
            self.small_caps_depth = 0
            self.small_caps_buffer = []

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if not self.capture_tag:
            return
        if tag == "span" and self.small_caps_depth == self.capture_depth:
            self.small_caps_depth = 0
        if tag == "span" and self.page_number_depth == self.capture_depth:
            self.page_number_depth = 0
        self.capture_depth -= 1
        if self.capture_depth:
            return
        text = normalize_block_text("".join(self.buffer))
        if text and self.pages:
            leading = normalize_block_text("".join(self.small_caps_buffer)) or None
            self.blocks.append(
                Block(
                    kind=self.capture_tag,
                    text=text,
                    page_start=min(self.pages),
                    page_end=max(self.pages),
                    leading_small_caps=leading,
                )
            )
        self.capture_tag = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth or not self.capture_tag or self.page_number_depth:
            return
        self.buffer.append(data)
        if self.small_caps_depth:
            self.small_caps_buffer.append(data)


def normalize_block_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_html(data: bytes) -> list[Block]:
    parser = GutenbergHtmlParser()
    parser.feed(data.decode("utf-8"))
    return parser.blocks


def parse_text(data: bytes) -> list[Block]:
    """Parse Gutenberg plain text into page-aware paragraphs.

    Some older Gutenberg HTML files keep running text outside semantic tags. Their UTF-8
    plain-text rendering is a more deterministic extraction source and retains the printed
    page markers in braces.
    """

    text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    page: int | None = None
    blocks: list[Block] = []
    for raw in re.split(r"\n[ \t]*\n+", text):
        markers = list(re.finditer(r"\{(\d+)(?:\s+continued)?\}", raw, flags=re.IGNORECASE))
        starts_with_marker = bool(markers and not raw[: markers[0].start()].strip())
        pages = [] if starts_with_marker or page is None else [page]
        pages.extend(int(match.group(1)) for match in markers)
        if markers:
            page = int(markers[-1].group(1))
        value = re.sub(r"\{\d+(?:\s+continued)?\}", " ", raw, flags=re.IGNORECASE)
        value = normalize_block_text(value)
        if not value or value.startswith("[Illustration:") or not pages:
            continue
        blocks.append(Block("p", value, min(pages), max(pages)))
    return blocks


def default_cache_path(ebook_id: str, suffix: str = ".htm") -> Path:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set; pass --output explicitly")
    return Path(scratch) / "scouting-autoresearch" / "sources" / f"pg-{ebook_id}" / f"{ebook_id}{suffix}"


def fetch(url: str, output: Path, expected_sha256: str) -> str:
    if output.exists():
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        if digest == expected_sha256:
            return digest
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(
            f"Downloaded source hash changed: expected {expected_sha256}, received {digest}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(output)
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ebook-id", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--outline", action="store_true")
    args = parser.parse_args()
    output = args.output or default_cache_path(args.ebook_id)
    digest = fetch(args.url, output, args.sha256)
    print(f"Source ready: {output} sha256={digest}")
    if args.outline:
        for block in parse_html(output.read_bytes()):
            if block.kind in {"h3", "h4", "h5", "h6"} or block.leading_small_caps:
                print(
                    f"{block.page_start:03d}-{block.page_end:03d}\t{block.kind}\t"
                    f"{block.leading_small_caps or block.text}"
                )


if __name__ == "__main__":
    main()
