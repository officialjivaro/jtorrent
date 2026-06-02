from __future__ import annotations

from urllib.parse import urlparse

from .models import TorrentItem


class PolicyError(ValueError):
    pass


def host_of(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).hostname or "").lower()


def assert_not_blocked_url(url: str | None, blocked_domains: list[str]) -> None:
    host = host_of(url)
    if not host:
        return
    for blocked in blocked_domains:
        b = str(blocked).lower().strip()
        if host == b or host.endswith("." + b):
            raise PolicyError(f"Blocked domain is not allowed in this backend: {host}")


def validate_source(source: dict, policy: dict) -> None:
    if not source.get("enabled", False):
        return
    status = str(source.get("copyright_status") or "").strip().lower()
    allowed = set(policy.get("allowed_status_values") or [])
    if policy.get("require_authorized_sources", True) and status not in allowed:
        raise PolicyError(
            f"Source {source.get('id')} is enabled but copyright_status={status!r}. "
            f"Use one of: {', '.join(sorted(allowed))}"
        )
    blocked = list(policy.get("blocked_domains") or [])
    for key in ["source_homepage", "page_url", "url"]:
        assert_not_blocked_url(source.get(key), blocked)
    for key in ["page_urls", "feed_urls"]:
        for url in source.get(key) or []:
            assert_not_blocked_url(url, blocked)


def validate_item(item: TorrentItem, policy: dict) -> bool:
    status = str(item.copyright_status or "").strip().lower()
    allowed = set(policy.get("allowed_status_values") or [])
    if policy.get("require_authorized_sources", True) and status not in allowed:
        return False
    blocked = list(policy.get("blocked_domains") or [])
    for url in [item.source_url, item.source_homepage, item.details_url, item.download_page_url, item.torrent_url]:
        assert_not_blocked_url(url, blocked)
    return True
