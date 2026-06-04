from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .models import TorrentItem
from .normalize import slugify

DEFAULT_MAX_JSON_FILE_BYTES = 5 * 1024 * 1024


def _write_json(path: Path, data: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def _json_bytes(data: Any, *, pretty: bool = False) -> int:
    if pretty:
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return len(text.encode("utf-8")) + 1  # _write_json adds a trailing newline.


def _record_bytes(record: dict[str, Any]) -> int:
    text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    return len(text.encode("utf-8"))


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


def _search_record(item: dict[str, Any], *, full_shard: str | None, compact_shard: str | None) -> dict[str, Any]:
    description = item.get("description")
    if isinstance(description, str) and len(description) > 280:
        description = description[:277].rstrip() + "..."
    record = {
        "id": item.get("id"),
        "slug": item.get("slug"),
        "title": item.get("title"),
        "normalized_title": item.get("normalized_title"),
        "category": item.get("category"),
        "source_id": item.get("source_id"),
        "source_name": item.get("source_name"),
        "size_bytes": item.get("size_bytes"),
        "size": item.get("size"),
        "seeders": item.get("seeders"),
        "leechers": item.get("leechers"),
        "date_added": item.get("date_added"),
        "date_published": item.get("date_published"),
        "copyright_status": item.get("copyright_status"),
        "tags": item.get("tags"),
        "description": description,
        "has_magnet": bool(item.get("magnet")),
        "has_torrent_url": bool(item.get("torrent_url")),
        "full_shard": full_shard,
        "compact_shard": compact_shard,
    }
    return {k: v for k, v in record.items() if v not in [None, "", [], {}]}


def _public_url(base_url: str, rel_path: str) -> str | None:
    if not base_url:
        return None
    return f"{base_url.rstrip('/')}/{rel_path.lstrip('/')}"


def _row_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = {str(row.get(key)) for row in rows if row.get(key) not in [None, ""]}
    return sorted(values)


def _shard_metadata(
    *,
    shard_id: str,
    rel_path: str,
    rows: list[dict[str, Any]],
    byte_size: int,
    base_url: str,
    oversized_records: int = 0,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "id": shard_id,
        "path": rel_path,
        "count": len(rows),
        "bytes": byte_size,
        "categories": _row_values(rows, "category"),
        "sources": _row_values(rows, "source_id"),
    }
    url = _public_url(base_url, rel_path)
    if url:
        metadata["url"] = url
    if oversized_records:
        metadata["oversized_records"] = oversized_records
    return metadata


def _write_record_shards(
    output_dir: Path,
    records: list[dict[str, Any]],
    *,
    rel_dir: str,
    prefix: str,
    max_file_bytes: int,
    base_url: str,
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """Write records into JSON-array shards capped near max_file_bytes.

    Returns shard metadata and an assignment list matching the input records. If a
    single record is larger than max_file_bytes it is written as its own shard and
    marked with oversized_records=1, because it cannot be split safely.
    """

    if not records:
        return [], []

    rel_dir_path = Path(rel_dir)
    target_dir = output_dir / rel_dir_path
    target_dir.mkdir(parents=True, exist_ok=True)

    shards: list[dict[str, Any]] = []
    assignments: list[str | None] = [None] * len(records)
    current_rows: list[dict[str, Any]] = []
    current_indices: list[int] = []
    current_size = 3  # [] plus trailing newline.
    shard_number = 1

    def finalize(rows: list[dict[str, Any]], indices: list[int], *, oversized_records: int = 0) -> None:
        nonlocal shard_number
        if not rows:
            return
        shard_id = f"{prefix}-{shard_number:04d}"
        rel_path = (rel_dir_path / f"{shard_id}.json").as_posix()
        path = output_dir / rel_path
        _write_json(path, rows, pretty=False)
        byte_size = path.stat().st_size
        for index in indices:
            assignments[index] = rel_path
        shards.append(
            _shard_metadata(
                shard_id=shard_id,
                rel_path=rel_path,
                rows=rows,
                byte_size=byte_size,
                base_url=base_url,
                oversized_records=oversized_records,
            )
        )
        shard_number += 1

    for index, record in enumerate(records):
        item_size = _record_bytes(record)
        item_array_size = item_size + 3  # [item]\n
        if item_array_size > max_file_bytes:
            finalize(current_rows, current_indices)
            current_rows = []
            current_indices = []
            current_size = 3
            finalize([record], [index], oversized_records=1)
            continue

        next_size = current_size + item_size + (1 if current_rows else 0)
        if current_rows and next_size > max_file_bytes:
            finalize(current_rows, current_indices)
            current_rows = []
            current_indices = []
            current_size = 3
            next_size = current_size + item_size

        current_rows.append(record)
        current_indices.append(index)
        current_size = next_size

    finalize(current_rows, current_indices)
    return shards, assignments


def _write_size_limited_json(
    path: Path,
    data: Any,
    *,
    pretty: bool,
    max_file_bytes: int,
    stub: dict[str, Any],
) -> dict[str, Any]:
    full_size = _json_bytes(data, pretty=pretty)
    if full_size <= max_file_bytes:
        _write_json(path, data, pretty=pretty)
        return {"path": path.name, "written": True, "bytes": path.stat().st_size, "mode": "inline"}

    _write_json(path, stub, pretty=True)
    return {
        "path": path.name,
        "written": False,
        "bytes": path.stat().st_size,
        "would_have_been_bytes": full_size,
        "mode": "sharded-stub",
    }


def _write_group_files(
    output_dir: Path,
    groups: dict[str, list[dict[str, Any]]],
    *,
    group_dir: str,
    group_label: str,
    max_file_bytes: int,
    base_url: str,
) -> dict[str, dict[str, Any]]:
    group_manifest: dict[str, dict[str, Any]] = {}
    for group_name, rows in sorted(groups.items()):
        group_file_rel = f"data/{group_dir}/{group_name}.json"
        group_file = output_dir / group_file_rel
        byte_size = _json_bytes(rows, pretty=False)
        if byte_size <= max_file_bytes:
            _write_json(group_file, rows, pretty=False)
            entry: dict[str, Any] = {
                group_label: group_name,
                "mode": "inline",
                "path": group_file_rel,
                "count": len(rows),
                "bytes": group_file.stat().st_size,
            }
            url = _public_url(base_url, group_file_rel)
            if url:
                entry["url"] = url
        else:
            shard_rel_dir = f"data/{group_dir}/{group_name}"
            shards, _assignments = _write_record_shards(
                output_dir,
                rows,
                rel_dir=shard_rel_dir,
                prefix="part",
                max_file_bytes=max_file_bytes,
                base_url=base_url,
            )
            stub = {
                "mode": "sharded",
                group_label: group_name,
                "count": len(rows),
                "max_file_bytes": max_file_bytes,
                "parts": shards,
            }
            _write_json(group_file, stub, pretty=True)
            entry = {
                group_label: group_name,
                "mode": "sharded",
                "path": group_file_rel,
                "count": len(rows),
                "bytes": group_file.stat().st_size,
                "parts": shards,
            }
            url = _public_url(base_url, group_file_rel)
            if url:
                entry["url"] = url
        group_manifest[group_name] = entry
    return group_manifest


def write_public(
    output_dir: Path,
    items: list[TorrentItem],
    sources: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    max_file_bytes: int = DEFAULT_MAX_JSON_FILE_BYTES,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    # Disable Jekyll processing on GitHub Pages so files and directories with
    # underscores, leading dots, or generated static names are served exactly as written.
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    max_file_bytes = max(1024, int(max_file_bytes or DEFAULT_MAX_JSON_FILE_BYTES))
    item_dicts = [i.to_dict() for i in items]
    compact = [_compact(i) for i in item_dicts]
    base_url = str(manifest.get("base_url") or "").rstrip("/")

    full_shards, full_assignments = _write_record_shards(
        output_dir,
        item_dicts,
        rel_dir="data/shards/full",
        prefix="full",
        max_file_bytes=max_file_bytes,
        base_url=base_url,
    )
    compact_shards, compact_assignments = _write_record_shards(
        output_dir,
        compact,
        rel_dir="data/shards/compact",
        prefix="compact",
        max_file_bytes=max_file_bytes,
        base_url=base_url,
    )
    search_records = [
        _search_record(item, full_shard=full_assignments[index], compact_shard=compact_assignments[index])
        for index, item in enumerate(item_dicts)
    ]
    search_shards, _search_assignments = _write_record_shards(
        output_dir,
        search_records,
        rel_dir="data/search",
        prefix="search",
        max_file_bytes=max_file_bytes,
        base_url=base_url,
    )

    search_index_stub = {
        "mode": "sharded",
        "message": "The compact index exceeded max_file_bytes. Load data/manifest.json, then load manifest.sharding.compact_shards or manifest.sharding.search_shards.",
        "manifest_path": "data/manifest.json",
        "total_results": len(compact),
        "max_file_bytes": max_file_bytes,
        "compact_shards": compact_shards,
        "search_shards": search_shards,
    }
    full_index_stub = {
        "mode": "sharded",
        "message": "The full index exceeded max_file_bytes. Load data/manifest.json, then load manifest.sharding.full_shards.",
        "manifest_path": "data/manifest.json",
        "total_results": len(item_dicts),
        "max_file_bytes": max_file_bytes,
        "full_shards": full_shards,
    }

    full_index_file = _write_size_limited_json(
        output_dir / "data" / "search-index.json",
        item_dicts,
        pretty=True,
        max_file_bytes=max_file_bytes,
        stub=full_index_stub,
    )
    compact_index_file = _write_size_limited_json(
        output_dir / "data" / "search-index.min.json",
        compact,
        pretty=False,
        max_file_bytes=max_file_bytes,
        stub=search_index_stub,
    )
    summary_index_file = _write_size_limited_json(
        output_dir / "data" / "search-index.summary.json",
        search_records,
        pretty=False,
        max_file_bytes=max_file_bytes,
        stub={
            "mode": "sharded",
            "message": "The lightweight search index exceeded max_file_bytes. Load data/manifest.json, then load manifest.sharding.search_shards.",
            "manifest_path": "data/manifest.json",
            "total_results": len(search_records),
            "max_file_bytes": max_file_bytes,
            "search_shards": search_shards,
        },
    )

    source_shards: list[dict[str, Any]] = []
    sources_size = _json_bytes(sources, pretty=True)
    if sources_size <= max_file_bytes:
        _write_json(output_dir / "data" / "sources.json", sources, pretty=True)
        sources_file = {"path": "sources.json", "written": True, "bytes": (output_dir / "data" / "sources.json").stat().st_size}
    else:
        source_shards, _source_assignments = _write_record_shards(
            output_dir,
            sources,
            rel_dir="data/sources",
            prefix="sources",
            max_file_bytes=max_file_bytes,
            base_url=base_url,
        )
        _write_json(
            output_dir / "data" / "sources.json",
            {
                "mode": "sharded",
                "message": "The source metadata exceeded max_file_bytes. Load data/manifest.json, then load manifest.sharding.source_shards.",
                "manifest_path": "data/manifest.json",
                "source_shards": source_shards,
            },
            pretty=True,
        )
        sources_file = {
            "path": "sources.json",
            "written": False,
            "bytes": (output_dir / "data" / "sources.json").stat().st_size,
            "would_have_been_bytes": sources_size,
        }

    by_category: dict[str, list[dict[str, Any]]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in compact:
        by_category.setdefault(slugify(item.get("category"), "uncategorized"), []).append(item)
        by_source.setdefault(slugify(item.get("source_id"), "unknown"), []).append(item)

    category_files = _write_group_files(
        output_dir,
        by_category,
        group_dir="by-category",
        group_label="category",
        max_file_bytes=max_file_bytes,
        base_url=base_url,
    )
    source_files = _write_group_files(
        output_dir,
        by_source,
        group_dir="by-source",
        group_label="source",
        max_file_bytes=max_file_bytes,
        base_url=base_url,
    )

    shard_index = {
        "max_file_bytes": max_file_bytes,
        "full_shards": full_shards,
        "compact_shards": compact_shards,
        "search_shards": search_shards,
        "source_shards": source_shards,
    }
    _write_json(output_dir / "data" / "shards" / "index.json", shard_index, pretty=True)

    manifest["max_json_file_bytes"] = max_file_bytes
    manifest["files"] = {
        "search_index": full_index_file,
        "search_index_min": compact_index_file,
        "search_index_summary": summary_index_file,
        "sources": sources_file,
        "shard_index": {
            "path": "shards/index.json",
            "bytes": (output_dir / "data" / "shards" / "index.json").stat().st_size,
        },
    }
    manifest["sharding"] = {
        "enabled": True,
        "strategy": "byte-size",
        "max_file_bytes": max_file_bytes,
        "full_shards": full_shards,
        "compact_shards": compact_shards,
        "search_shards": search_shards,
        "source_shards": source_shards,
        "by_category": category_files,
        "by_source": source_files,
        "notes": [
            "search-index.min.json remains the legacy full compact array only while it fits under max_file_bytes.",
            "When a legacy index is too large, it becomes a small sharded-mode stub that points frontends to manifest.json.",
            "Use search_shards for fast keyword/filter search and compact_shards or full_shards for full result data.",
        ],
    }

    _write_json(output_dir / "data" / "manifest.json", manifest, pretty=True)

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
    <div class="card"><strong>Max JSON file size</strong><br>{max_file_bytes:,} bytes</div>
  </div>
  <h2>JSON endpoints</h2>
  <ul>
    <li><a href="data/manifest.json">data/manifest.json</a></li>
    <li><a href="data/search-index.min.json">data/search-index.min.json</a> legacy compact endpoint; becomes a shard pointer if too large</li>
    <li><a href="data/search-index.summary.json">data/search-index.summary.json</a> lightweight search index; becomes a shard pointer if too large</li>
    <li><a href="data/search-index.json">data/search-index.json</a> full index; becomes a shard pointer if too large</li>
    <li><a href="data/sources.json">data/sources.json</a></li>
    <li><a href="data/shards/index.json">data/shards/index.json</a></li>
  </ul>
  <h2>Frontend example</h2>
  <pre><code>const manifest = await fetch('{base_url}/data/manifest.json').then(r =&gt; r.json());
const shardUrls = manifest.sharding.search_shards.map(s =&gt; '{base_url}/' + s.path);
const firstSearchShard = await fetch(shardUrls[0]).then(r =&gt; r.json());</code></pre>
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
