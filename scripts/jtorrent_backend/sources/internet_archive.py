from __future__ import annotations

from typing import Iterable
from urllib.parse import urlencode

from ..models import TorrentItem
from ..timeutil import to_date
from .base import SourceAdapter


class InternetArchiveAdvancedSearchSource(SourceAdapter):
    API = "https://archive.org/advancedsearch.php"

    def fetch(self) -> Iterable[TorrentItem]:
        query = self.source.get("query")
        if not query:
            return
        rows = int(self.source.get("rows", 50))
        include_torrent = bool(self.source.get("include_torrent_url", False))
        fields = [
            "identifier",
            "title",
            "description",
            "creator",
            "mediatype",
            "date",
            "publicdate",
            "licenseurl",
            "downloads",
            "item_size",
        ]
        params: list[tuple[str, str | int]] = [("q", query), ("rows", rows), ("page", 1), ("output", "json")]
        for field in fields:
            params.append(("fl[]", field))
        url = f"{self.API}?{urlencode(params)}"
        data = self.http.get(url).json()
        docs = data.get("response", {}).get("docs", [])
        for doc in docs:
            identifier = doc.get("identifier")
            if not identifier:
                continue
            details_url = f"https://archive.org/details/{identifier}"
            torrent_url = f"https://archive.org/download/{identifier}/{identifier}_archive.torrent" if include_torrent else None
            title = doc.get("title") or identifier.replace("_", " ")
            item_data = self.base_item()
            item_data.update(
                {
                    "title": title,
                    "source_url": details_url,
                    "details_url": details_url,
                    "download_page_url": details_url,
                    "torrent_url": torrent_url,
                    "date_added": to_date(doc.get("publicdate")),
                    "date_published": to_date(doc.get("date")),
                    "license_url": doc.get("licenseurl") or self.source.get("license_url"),
                    "description": doc.get("description"),
                    "size_bytes": int(doc["item_size"]) if str(doc.get("item_size", "")).isdigit() else None,
                    "completed": int(doc["downloads"]) if str(doc.get("downloads", "")).isdigit() else None,
                    "raw": {"internet_archive": doc},
                }
            )
            yield TorrentItem.from_mapping(item_data)
