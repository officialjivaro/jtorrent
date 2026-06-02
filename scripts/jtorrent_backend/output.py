from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .models import TorrentItem
from .normalize import slugify


def _write_json(path: Path, data: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def _compact(item: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "id",
        "slug",
        "title",
        "category",
        "source_id",
        "source_name",
        "source_url",
        "details_url",
        "torrent_url",
        "magnet",
        "infohash",
        "size_bytes",
        "size",
        "seeders",
        "leechers",
        "date_added",
        "date_published",
        "license",
        "license_url",
        "copyright_status",
        "description",
        "tags",
        "fetched_at",
    ]
    return {k: item.get(k) for k in keys if item.get(k) not in [None, "", [], {}]}


def write_public(output_dir: Path, items: list[TorrentItem], sources: list[dict], manifest: dict) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)

    item_dicts = [i.to_dict() for i in items]
    compact = [_compact(i) for i in item_dicts]

    _write_json(output_dir / "data" / "search-index.json", item_dicts, pretty=True)
    _write_json(output_dir / "data" / "search-index.min.json", compact, pretty=False)
    _write_json(output_dir / "data" / "sources.json", sources, pretty=True)
    _write_json(output_dir / "data" / "manifest.json", manifest, pretty=True)

    by_category: dict[str, list[dict[str, Any]]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in compact:
        by_category.setdefault(slugify(item.get("category"), "uncategorized"), []).append(item)
        by_source.setdefault(slugify(item.get("source_id"), "unknown"), []).append(item)

    for category, rows in by_category.items():
        _write_json(output_dir / "data" / "by-category" / f"{category}.json", rows, pretty=False)
    for source_id, rows in by_source.items():
        _write_json(output_dir / "data" / "by-source" / f"{source_id}.json", rows, pretty=False)

    base_url = manifest.get("base_url", "").rstrip("/")
    custom_domain = manifest.get("custom_domain")
    if custom_domain:
        (output_dir / "CNAME").write_text(str(custom_domain).strip() + "\n", encoding="utf-8")

    categories = sorted(by_category)
    sources_sorted = sorted(by_source)
    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JTorrent Backend</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.5; max-width: 900px; }}
    code, pre {{ background: #f4f4f4; padding: .15rem .3rem; border-radius: .25rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
    .card {{ border: 1px solid #ddd; border-radius: .75rem; padding: 1rem; }}
    a {{ word-break: break-word; }}
  </style>
</head>
<body>
  <h1>JTorrent backend</h1>
  <p>This is the static JSON backend for <strong>www.jtorrent.net</strong>.</p>
  <div class="grid">
    <div class="card"><strong>Items</strong><br>{manifest.get('item_count', 0)}</div>
    <div class="card"><strong>Sources enabled</strong><br>{manifest.get('enabled_source_count', 0)}</div>
    <div class="card"><strong>Generated</strong><br>{manifest.get('generated_at', '')}</div>
  </div>
  <h2>JSON endpoints</h2>
  <ul>
    <li><a href="data/search-index.json">data/search-index.json</a></li>
    <li><a href="data/search-index.min.json">data/search-index.min.json</a></li>
    <li><a href="data/sources.json">data/sources.json</a></li>
    <li><a href="data/manifest.json">data/manifest.json</a></li>
  </ul>
  <h2>Frontend example</h2>
  <pre><code>const res = await fetch('{base_url}/data/search-index.min.json');
const items = await res.json();</code></pre>
  <h2>Categories</h2>
  <ul>{''.join(f'<li><a href="data/by-category/{quote(c)}.json">{c}</a></li>' for c in categories)}</ul>
  <h2>Sources</h2>
  <ul>{''.join(f'<li><a href="data/by-source/{quote(s)}.json">{s}</a></li>' for s in sources_sorted)}</ul>
</body>
</html>
"""
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    (output_dir / "robots.txt").write_text("User-agent: *\nAllow: /data/\n", encoding="utf-8")

    sitemap_urls = [base_url + "/"] if base_url else []
    sitemap = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    for url in sitemap_urls:
        sitemap += f"  <url><loc>{url}</loc></url>\n"
    sitemap += "</urlset>\n"
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
