from __future__ import annotations

import re
from typing import Iterable


from ..models import TorrentItem
from ..timeutil import to_date
from .base import SourceAdapter

_MAGNET_RE = re.compile(r"magnet:\?[^\s\"'<>]+", re.I)
_TORRENT_RE = re.compile(r"https?://[^\s\"'<>]+\.torrent(?:\?[^\s\"'<>]*)?", re.I)


class RssFeedSource(SourceAdapter):
    def fetch(self) -> Iterable[TorrentItem]:
        for feed_url in self.source.get("feed_urls") or []:
            text = self.http.get_text(feed_url)
            try:
                import feedparser
            except ImportError as exc:
                raise RuntimeError("feedparser is required for rss_feed sources; run `python -m pip install -r requirements.txt`") from exc
            parsed = feedparser.parse(text)
            for entry in parsed.entries:
                raw_text = " ".join(
                    str(getattr(entry, key, "") or "")
                    for key in ["summary", "description", "content", "links"]
                )
                magnet = None
                torrent_url = None
                m = _MAGNET_RE.search(raw_text)
                if m:
                    magnet = m.group(0)
                t = _TORRENT_RE.search(raw_text)
                if t:
                    torrent_url = t.group(0)
                for link in getattr(entry, "links", []) or []:
                    href = link.get("href")
                    ltype = str(link.get("type") or "").lower()
                    if href and (href.endswith(".torrent") or "bittorrent" in ltype):
                        torrent_url = href
                    if href and href.startswith("magnet:?"):
                        magnet = href

                data = self.base_item()
                data.update(
                    {
                        "title": getattr(entry, "title", None),
                        "source_url": getattr(entry, "link", feed_url),
                        "details_url": getattr(entry, "link", feed_url),
                        "download_page_url": getattr(entry, "link", feed_url),
                        "torrent_url": torrent_url,
                        "magnet": magnet,
                        "date_published": to_date(getattr(entry, "published", None) or getattr(entry, "updated", None)),
                        "description": getattr(entry, "summary", None),
                        "raw": {"feed_url": feed_url},
                    }
                )
                yield TorrentItem.from_mapping(data)
