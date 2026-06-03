from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_config
from .dedupe import dedupe_items
from .http import HttpClient, make_http_settings
from .models import TorrentItem
from .normalize import normalize_item
from .output import DEFAULT_MAX_JSON_FILE_BYTES, write_public
from .policy import PolicyError, validate_item, validate_source
from .sources import SOURCE_TYPES
from .timeutil import utc_now_iso


def _manual_items(config: dict[str, Any], fetched_at: str) -> list[TorrentItem]:
    items: list[TorrentItem] = []
    for raw in config.get("manual_items") or []:
        data = dict(raw)
        data.setdefault("fetched_at", fetched_at)
        items.append(normalize_item(TorrentItem.from_mapping(data)))
    return items


def build_index(config_path: Path, *, offline: bool = False, strict: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    settings = config.get("settings", {}) or {}
    policy = settings.get("policy", {}) or {}
    generated_at = utc_now_iso()
    warnings: list[str] = []
    errors: list[str] = []

    blocked_domains = list(policy.get("blocked_domains") or [])
    http = HttpClient(make_http_settings(settings, blocked_domains))

    all_items: list[TorrentItem] = _manual_items(config, generated_at)
    source_summaries: list[dict[str, Any]] = []

    enabled_sources = [s for s in config.get("sources", []) if s.get("enabled", False)]
    for source in config.get("sources", []):
        try:
            validate_source(source, policy)
        except PolicyError:
            raise

    if not offline:
        for source in enabled_sources:
            sid = source.get("id")
            stype = source.get("type")
            adapter_cls = SOURCE_TYPES.get(stype)
            summary = {
                "id": sid,
                "name": source.get("name"),
                "type": stype,
                "enabled": True,
                "category": source.get("category"),
                "source_homepage": source.get("source_homepage"),
                "copyright_status": source.get("copyright_status"),
                "license": source.get("license"),
                "item_count": 0,
                "error": None,
            }
            if adapter_cls is None:
                summary["error"] = f"Unknown source type: {stype}"
                errors.append(f"{sid}: unknown source type {stype}")
                source_summaries.append(summary)
                if strict:
                    raise ValueError(summary["error"])
                continue
            try:
                adapter = adapter_cls(source, http)
                max_items = int(settings.get("limits", {}).get("max_items_per_source", source.get("max_items", 750)))
                produced = 0
                for item in adapter.fetch():
                    item = normalize_item(item)
                    if validate_item(item, policy):
                        all_items.append(item)
                        produced += 1
                    if produced >= max_items:
                        warnings.append(f"{sid}: reached max_items_per_source={max_items}")
                        break
                summary["item_count"] = produced
            except Exception as exc:  # noqa: BLE001
                msg = f"{sid}: {exc}"
                summary["error"] = str(exc)
                errors.append(msg)
                if strict:
                    raise
            source_summaries.append(summary)
    else:
        warnings.append("Offline mode enabled; network sources were skipped.")
        for source in enabled_sources:
            source_summaries.append({
                "id": source.get("id"),
                "name": source.get("name"),
                "type": source.get("type"),
                "enabled": True,
                "category": source.get("category"),
                "source_homepage": source.get("source_homepage"),
                "copyright_status": source.get("copyright_status"),
                "license": source.get("license"),
                "item_count": 0,
                "error": "offline mode",
            })

    filtered: list[TorrentItem] = []
    for item in all_items:
        try:
            if validate_item(item, policy):
                filtered.append(item)
        except PolicyError as exc:
            errors.append(str(exc))
            if strict:
                raise

    items = dedupe_items(filtered)
    items.sort(key=lambda i: ((i.category or ""), (i.title or "").lower()))

    max_total = int(settings.get("limits", {}).get("max_items_total", 10000))
    if len(items) > max_total:
        warnings.append(f"Truncated items from {len(items)} to max_items_total={max_total}")
        items = items[:max_total]

    counts_by_category = Counter(i.category or "uncategorized" for i in items)
    counts_by_source = Counter(i.source_id or "unknown" for i in items)
    manifest = {
        "name": settings.get("name", "JTorrent Backend"),
        "generated_at": generated_at,
        "base_url": settings.get("base_url"),
        "custom_domain": settings.get("custom_domain"),
        "frontend_origin": settings.get("frontend_origin"),
        "item_count": len(items),
        "raw_item_count": len(all_items),
        "enabled_source_count": len(enabled_sources),
        "counts_by_category": dict(sorted(counts_by_category.items())),
        "counts_by_source": dict(sorted(counts_by_source.items())),
        "warnings": warnings,
        "errors": errors,
        "policy": {
            "require_authorized_sources": policy.get("require_authorized_sources", True),
            "allowed_status_values": policy.get("allowed_status_values", []),
        },
    }

    output_dir = Path(settings.get("output_dir", "public"))
    limits = settings.get("limits", {}) or {}
    max_file_bytes = int(limits.get("max_json_file_bytes", DEFAULT_MAX_JSON_FILE_BYTES))
    write_public(output_dir, items, source_summaries, manifest, max_file_bytes=max_file_bytes)
    print(f"Built {len(items)} items into {output_dir}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
    return manifest
