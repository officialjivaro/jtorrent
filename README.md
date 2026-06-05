# JTorrent backend

This repository builds the scheduled static-data backend for `www.jtorrent.net`.

It runs from GitHub Actions on push, on manual dispatch, and once every 24 hours at **1:45 AM Japan time**. The build fetches the enabled sources in `config/sources.yml`, normalizes results, deduplicates records, writes static JSON, validates the output, and deploys it through GitHub Pages.

## Important architecture note

The old frontend approach loaded every search shard into the browser before searching. That works for tens of thousands of records, but it does **not** scale to hundreds of thousands or millions. This repo now publishes a v2 static token index so the browser fetches only the token buckets needed for the user’s query and then hydrates the matching document shards.

The v2 flow is:

1. Load `data/manifest.json`.
2. Read `manifest.search_v2` or `data/v2/manifest.json`.
3. Tokenize the query.
4. Fetch only the matching `data/v2/tokens/<prefix>.json` bucket files.
5. Intersect/union `doc_id` postings.
6. Fetch only the needed `data/v2/docs/*.json` shards.

This is the correct static-site pattern for large JSON search. If the project truly needs multiple millions of rich records long-term, move the index to a real search service/database such as Meilisearch, Typesense, OpenSearch, Algolia, PostgreSQL full-text search, or Cloudflare Workers + R2/D1. GitHub Pages is useful for a static dataset, but it has size and bandwidth limits.

## What this repo publishes

After the workflow runs, GitHub Pages serves:

```text
/data/manifest.json                    Build timestamp, counts, warnings, shard map
/data/v2/manifest.json                 Scalable token-search manifest
/data/v2/tokens/*.json                 Token -> doc_id posting buckets
/data/v2/docs/*.json                   Hydratable compact document shards
/jtorrent-search-v2.js                 Browser search helper for the v2 token index
/data/search-index.min.json            Legacy compact endpoint while small; v2 pointer when too large
/data/search-index.summary.json        Legacy lightweight endpoint while small; v2 pointer when too large
/data/search-index.json                Legacy full endpoint while small; v2 pointer when too large
/data/sources.json                     Source metadata, or a shard pointer when large
/data/shards/index.json                Legacy/v2 shard metadata
```

Legacy full/compact/search shards are still written while `item_count <= settings.output.legacy_max_items`. Above that threshold, the legacy files become small `mode: "v2-only"` pointer objects so the Pages artifact does not explode in size.

## Current source reality

The Internet Archive API-backed sources are the only configured sources that can realistically produce hundreds of thousands of records in a scheduled static build. The HTML/RSS sources are best-effort: some expose only a recent page/feed, some block automated requests, and some do not expose direct torrent/magnet links on listing pages. They remain useful, but they will not produce “millions” unless the source provides a real API, paginated HTML, RSS pages, or a bulk dump.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/build_index.py --config config/sources.yml
python scripts/validate_public_backend.py --public-dir public --require-nojekyll --min-items 30000
```

For a no-network smoke test:

```bash
python scripts/build_index.py --config config/sources.yml --offline
python scripts/validate_public_backend.py --public-dir public --require-nojekyll --min-items 1
```

Open `public/index.html` after the build. The JSON files are in `public/data/`.

## GitHub setup

1. Upload or push these files to the repo.
2. Go to **Settings → Pages**.
3. Set **Source** to **GitHub Actions**.
4. Go to **Actions → Update JTorrent Backend Index → Run workflow**.
5. After it finishes, open the Pages URL shown in the workflow output.
6. In `config/sources.yml`, keep `settings.base_url` aligned to the Pages URL.

## Frontend integration

Recommended v2 usage:

```html
<script src="https://officialjivaro.github.io/jtorrent/jtorrent-search-v2.js"></script>
<script>
const results = await window.JTorrentSearchV2.search({
  baseUrl: "https://officialjivaro.github.io/jtorrent",
  query: "ubuntu iso",
  limit: 20
});
console.log(results.results);
</script>
```

The old flow that loads `manifest.sharding.search_shards` should be treated as compatibility-only. It cannot scale to very large datasets because it requires downloading the entire search corpus before each browser can search.

## Source allowlist model

`config/sources.yml` is the source allowlist. A source with `enabled: true` is fetched, and a source with `enabled: false` is skipped. There is no separate policy block, blocked-domain list, or copyright-status filter in the builder. Source fields such as `license`, `license_url`, and `copyright_status` are metadata copied into output.

## Output controls

Key settings:

```yaml
settings:
  limits:
    max_items_total: 1000000
    max_items_per_source: 50000
    max_json_file_bytes: 5242880
    min_total_items: 30000
  output:
    scalable_search:
      enabled: true
      token_bucket_prefix_chars: 2
      max_tokens_per_record: 40
      max_postings_per_token: 50000
      description_max_chars: 240
    legacy_shards: true
    legacy_max_items: 100000
    group_files: false
```

`group_files: false` avoids duplicating the whole dataset into by-category/by-source JSON files. The frontend can still filter by category/source from v2 docs.

## Adding a source

Supported adapter types:

```text
direct_list
html_torrent_links
rss_feed
internet_archive_advancedsearch
```

Large sources can set `max_items`, `rows`, and `max_pages`. Source-level `max_items` overrides the global `settings.limits.max_items_per_source`. Sources can also set `required: false`; those are best-effort and their fetch errors are reported in `sources.json` without blocking deployment.

## Deduplication

Dedupe priority:

1. infohash from `.torrent` metadata or magnet URI
2. normalized magnet infohash
3. normalized `.torrent` URL
4. normalized source/details URL
5. normalized title + size

When duplicates are found, metadata and mirrors are merged rather than discarded.
