# JTorrent backend

This repository is a scheduled static-data backend for `www.jtorrent.net`.

It uses GitHub Actions at 6:00 AM and 6:00 PM Japan time to fetch the enabled sources listed in `config/sources.yml`, normalize the data, deduplicate results, split large JSON outputs into about-5-MB shards, and publish the files through GitHub Pages.

## What this repo publishes

After the workflow runs, GitHub Pages serves:

```text
/data/manifest.json                    Build timestamp, counts, warnings, shard map
/data/search-index.min.json            Legacy compact index when small; shard pointer when large
/data/search-index.summary.json        Lightweight search index when small; shard pointer when large
/data/search-index.json                Full normalized index when small; shard pointer when large
/data/sources.json                     Source metadata, or a shard pointer when large
/data/shards/index.json                Shard metadata only
/data/shards/compact/*.json            Compact result shards, capped near 5 MB each
/data/shards/full/*.json               Full result shards, capped near 5 MB each
/data/search/*.json                    Lightweight search-record shards, capped near 5 MB each
/data/by-category/*.json               Category files, or shard pointers when large
/data/by-source/*.json                 Source files, or shard pointers when large
```

A minimal status page is also generated at `/` so you can verify that deployment worked. The real frontend can stay on `www.jtorrent.net` and read the JSON endpoints.

## Source allowlist model

The backend is intentionally simple: `config/sources.yml` is the source allowlist. A source with `enabled: true` is fetched, and a source with `enabled: false` is skipped. There is no separate policy block, blocked-domain list, or copyright-status filter in the builder. Source fields such as `license`, `license_url`, and `copyright_status` are optional metadata that can still be useful for the frontend.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/build_index.py --config config/sources.yml
```

Open `public/index.html` after the build. The JSON files are in `public/data/`.

## GitHub setup from zero

1. Create a new **public** GitHub repository named `jtorrent`.
2. Upload or push these files to the repo.
3. Go to **Settings → Pages**.
4. Set **Source** to **GitHub Actions**.
5. Go to **Actions → Update JTorrent Backend Index → Run workflow**.
6. After it finishes, open the Pages URL shown in the workflow output.
7. In `config/sources.yml`, change `settings.base_url` to your Pages URL, for example:

```yaml
settings:
  base_url: "https://YOUR_GITHUB_USERNAME.github.io/jtorrent"
```

8. Run the workflow again.
9. Point your `www.jtorrent.net` frontend at:

```text
https://YOUR_GITHUB_USERNAME.github.io/jtorrent/data/search-index.min.json
```


## Automatic JSON sharding

The builder reads this setting from `config/sources.yml`:

```yaml
settings:
  limits:
    max_json_file_bytes: 5242880
```

Every generated result array is split by byte size, not result count. If `search-index.min.json` still fits below the limit, it remains a normal JSON array for backward compatibility. If it grows too large, it becomes a small pointer object with `mode: "sharded"`; your frontend should then load `data/manifest.json` and read the shard paths from `manifest.sharding.search_shards`, `manifest.sharding.compact_shards`, or `manifest.sharding.full_shards`.

## Optional custom backend subdomain

You can also use something like `backend.jtorrent.net` for the GitHub Pages site. Add that domain in **Settings → Pages → Custom domain**, then update DNS according to GitHub Pages instructions. If you do this, also set:

```yaml
settings:
  base_url: "https://backend.jtorrent.net"
  custom_domain: "backend.jtorrent.net"
```

## Adding a source

Add an entry in `config/sources.yml`.

Supported adapter types:

```text
direct_list
html_torrent_links
rss_feed
internet_archive_advancedsearch
```

Every source should have at minimum:

```yaml
id: example_source
name: "Example Source"
type: html_torrent_links
enabled: true
category: example
source_homepage: "https://example.org"
```

Optional metadata fields such as `license`, `license_url`, and `copyright_status` are copied into the JSON output when present, but they are not used to filter results.

## Data shape

Each result is normalized into a rich object with useful fields when available:

```json
{
  "id": "...",
  "slug": "...",
  "title": "...",
  "category": "linux",
  "source_id": "ubuntu_official",
  "source_name": "Official Ubuntu Releases",
  "source_url": "https://releases.ubuntu.com/",
  "details_url": "https://releases.ubuntu.com/24.04/",
  "torrent_url": "https://releases.ubuntu.com/24.04/example.iso.torrent",
  "magnet": null,
  "infohash": "...",
  "trackers": [],
  "size_bytes": 123,
  "size": "123 B",
  "seeders": null,
  "leechers": null,
  "completed": null,
  "date_added": "2026-06-02",
  "date_published": null,
  "language": null,
  "license": "...",
  "license_url": "...",
  "copyright_status": "open-source",
  "description": "...",
  "tags": ["linux", "iso"],
  "files": [],
  "mirrors": [],
  "fetched_at": "2026-06-02T03:23:00Z"
}
```

## Deduplication

Dedupe priority:

1. infohash from `.torrent` metadata or magnet URI
2. normalized magnet infohash
3. normalized `.torrent` URL
4. normalized source/details URL
5. normalized title + size

When duplicates are found, metadata and mirrors are merged rather than discarded.

## Frontend integration

Example frontend fetch:

```js
const BACKEND = "https://YOUR_GITHUB_USERNAME.github.io/jtorrent";
const res = await fetch(`${BACKEND}/data/search-index.min.json`, { cache: "no-store" });
const items = await res.json();
```

Use `data/manifest.json` to display "last updated" and result counts. For large indexes, load `manifest.sharding.search_shards` first and only load `compact_shards` or `full_shards` when the user opens a result.
