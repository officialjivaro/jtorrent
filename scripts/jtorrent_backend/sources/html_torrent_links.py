from __future__ import annotations

import re
from collections import deque
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse


from ..models import TorrentItem
from ..normalize import parse_size_to_bytes
from ..timeutil import to_date
from ..torrent_metadata import parse_torrent_bytes
from .base import SourceAdapter

_DATE_PATTERNS = [
    re.compile(r"\b\d{4}-[A-Za-z]{3}-\d{2}\s+\d{2}:\d{2}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
]
_SIZE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:KiB|MiB|GiB|TiB|KB|MB|GB|TB|K|M|G|T)\b", re.I)


def _compile_many(patterns: list[str] | None) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns or []]


def _matches_any(url: str, patterns: list[re.Pattern], default: bool = True) -> bool:
    if not patterns:
        return default
    return any(p.search(url) for p in patterns)


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.rsplit("/", 1)[-1] or url
    name = re.sub(r"\.torrent$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip() or url


def _row_text(anchor) -> str:
    for parent_name in ["tr", "li", "p", "div"]:
        parent = anchor.find_parent(parent_name)
        if parent:
            return " ".join(parent.get_text(" ", strip=True).split())
    return " ".join(anchor.get_text(" ", strip=True).split())


def _extract_date(text: str) -> str | None:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return to_date(m.group(0))
    return None


def _extract_size(text: str) -> tuple[int | None, str | None]:
    m = _SIZE_PATTERN.search(text)
    if not m:
        return None, None
    value = m.group(0)
    return parse_size_to_bytes(value), value


class HtmlTorrentLinksSource(SourceAdapter):
    def fetch(self) -> Iterable[TorrentItem]:
        include_url = _compile_many(self.source.get("include_url_regexes") or [r"\.torrent$"])
        exclude_url = _compile_many(self.source.get("exclude_url_regexes"))
        follow_link = _compile_many(self.source.get("follow_link_regexes"))
        max_depth = int(self.source.get("max_depth", 0))
        max_items = int(self.source.get("max_items", 1000))
        collect_magnets = bool(self.source.get("collect_magnets", False))
        fetch_torrent_metadata = bool(self.source.get("fetch_torrent_metadata", False))

        queue: deque[tuple[str, int]] = deque((url, 0) for url in self.source.get("page_urls") or [])
        seen_pages: set[str] = set()
        seen_links: set[str] = set()
        produced = 0

        while queue and produced < max_items:
            page_url, depth = queue.popleft()
            page_url = urldefrag(page_url)[0]
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)

            try:
                from bs4 import BeautifulSoup
            except ImportError as exc:
                raise RuntimeError("beautifulsoup4 is required for html_torrent_links sources; run `python -m pip install -r requirements.txt`") from exc
            html = self.http.get_text(page_url)
            soup = BeautifulSoup(html, "html.parser")

            for a in soup.find_all("a", href=True):
                href = str(a.get("href") or "").strip()
                if not href:
                    continue
                absolute = urldefrag(urljoin(page_url, href))[0]

                # Follow safe in-domain pages when configured.
                if depth < max_depth and _matches_any(absolute, follow_link, default=False):
                    if urlparse(absolute).hostname == urlparse(page_url).hostname:
                        queue.append((absolute, depth + 1))

                is_magnet = absolute.startswith("magnet:?")
                is_candidate = is_magnet if collect_magnets else False
                if _matches_any(absolute, include_url, default=False):
                    is_candidate = True
                if _matches_any(absolute, exclude_url, default=False):
                    is_candidate = False
                if not is_candidate or absolute in seen_links:
                    continue
                seen_links.add(absolute)

                text = _row_text(a)
                size_bytes, size_text = _extract_size(text)
                date = _extract_date(text)
                title = a.get_text(" ", strip=True) or _title_from_url(absolute)
                if title.lower() in {"torrent", "torrent download", "64-bit", "download"}:
                    title = _title_from_url(absolute)

                data = self.base_item()
                data.update(
                    {
                        "title": title,
                        "source_url": page_url,
                        "details_url": page_url,
                        "download_page_url": page_url,
                        "torrent_url": None if is_magnet else absolute,
                        "magnet": absolute if is_magnet else None,
                        "size_bytes": size_bytes,
                        "size": size_text,
                        "date_added": date,
                        "description": text if text and text != title else self.source.get("license"),
                    }
                )
                item = TorrentItem.from_mapping(data)

                if fetch_torrent_metadata and item.torrent_url:
                    try:
                        meta = parse_torrent_bytes(self.http.get_limited_bytes(item.torrent_url))
                        item.infohash = item.infohash or meta.get("infohash")
                        item.hash_source = item.hash_source or "torrent"
                        item.trackers = item.trackers or meta.get("trackers") or []
                        item.files = item.files or meta.get("files") or []
                        item.size_bytes = item.size_bytes or meta.get("size_bytes")
                        item.title = item.title or meta.get("name")
                    except Exception as exc:  # noqa: BLE001
                        item.raw["torrent_metadata_error"] = str(exc)

                produced += 1
                yield item
