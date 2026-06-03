from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .models import TorrentItem

_SIZE_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[KMGTPE]?i?B|[KMGTPE])\b", re.I)
_INFOHASH_RE = re.compile(r"^[a-fA-F0-9]{40}$|^[a-zA-Z2-7]{32}$")


def slugify(value: str | None, fallback: str = "item") -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:90] or fallback


def normalize_title(value: str | None) -> str:
    text = (value or "").lower()
    text = re.sub(r"\.torrent$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_size_to_bytes(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    m = _SIZE_RE.search(text)
    if not m:
        return None
    num = float(m.group("num"))
    unit = m.group("unit").lower().replace("ib", "b")
    powers = {"b": 0, "k": 1, "kb": 1, "m": 2, "mb": 2, "g": 3, "gb": 3, "t": 4, "tb": 4, "p": 5, "pb": 5, "e": 6, "eb": 6}
    power = powers.get(unit)
    if power is None:
        return None
    return int(num * (1024 ** power))


def format_size(size_bytes: int | None) -> str | None:
    if size_bytes is None:
        return None
    value = float(size_bytes)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if value < 1024 or unit == "PiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return str(size_bytes)


def extract_infohash_from_magnet(magnet: str | None) -> str | None:
    if not magnet:
        return None
    try:
        parsed = urlparse(magnet)
        if parsed.scheme != "magnet":
            return None
        xt_values = parse_qs(parsed.query).get("xt", [])
        for xt in xt_values:
            xt = unquote(xt)
            if xt.startswith("urn:btih:"):
                candidate = xt.rsplit(":", 1)[-1]
                if _INFOHASH_RE.match(candidate):
                    return candidate.lower()
    except Exception:
        return None
    return None


def clean_tags(tags: list[Any] | None) -> list[str]:
    result: list[str] = []
    for tag in tags or []:
        value = slugify(str(tag), fallback="")
        if value and value not in result:
            result.append(value)
    return result


def stable_id(*parts: str | None) -> str:
    key = "|".join([p or "" for p in parts])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def normalize_item(item: TorrentItem | dict[str, Any]) -> TorrentItem:
    if isinstance(item, dict):
        item = TorrentItem.from_mapping(item)

    if item.magnet and not item.infohash:
        ih = extract_infohash_from_magnet(item.magnet)
        if ih:
            item.infohash = ih
            item.hash_source = item.hash_source or "magnet"

    item.normalized_title = normalize_title(item.title)
    if item.size_bytes is None and item.size:
        item.size_bytes = parse_size_to_bytes(item.size)
    if item.size is None and item.size_bytes is not None:
        item.size = format_size(item.size_bytes)

    item.tags = clean_tags(item.tags)

    if not item.slug:
        basis = item.title or item.infohash or item.torrent_url or item.source_url or "item"
        item.slug = slugify(basis)
    if not item.id:
        basis = item.infohash or item.magnet or item.torrent_url or item.details_url or item.source_url or item.title
        item.id = f"{slugify(item.source_id or item.source_name or 'src')}-{stable_id(basis, item.title, item.size)}"

    if not item.source_url:
        item.source_url = item.details_url or item.download_page_url or item.source_homepage
    if not item.details_url:
        item.details_url = item.source_url or item.source_homepage
    return item
