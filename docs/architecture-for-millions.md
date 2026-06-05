# Scaling JTorrent to hundreds of thousands or millions of records

The old static backend shape was acceptable for a small catalogue, but it does not scale to millions of records because the browser had to download every search shard before it could answer a query. At 34,110 indexed records the generated compact/search arrays were already tens of megabytes, and the full legacy index would have exceeded 100 MB. At millions of records, that design would be slow, expensive, and unreliable.

## Current scalable static design

The backend now emits two families of files:

1. **Record shards** under `data/v2/docs/`.
   These contain the actual searchable result records, split into byte-size-limited JSON files.

2. **Token buckets** under `data/v2/tokens/`.
   Each token bucket maps search terms to `doc_id` postings lists. The browser fetches only the bucket files needed by the user's query, intersects/unions the matching doc IDs, then hydrates only the small set of result records from the relevant doc shard files.

The generated manifest is:

```text
data/v2/manifest.json
```

The generated browser helper is:

```text
jtorrent-search-v2.js
```

A frontend can use it like this:

```html
<script src="https://officialjivaro.github.io/jtorrent/jtorrent-search-v2.js"></script>
<script>
const response = await window.JTorrentSearchV2.search({
  baseUrl: 'https://officialjivaro.github.io/jtorrent',
  query: 'ubuntu',
  limit: 20
});
console.log(response.results);
</script>
```

## GitHub Pages reality check

GitHub Pages is fine for a static prototype or a catalogue in the tens/hundreds of thousands, but it has practical limits. For a true multi-million-record public search engine, use GitHub Pages only as the frontend host and put the index on a real search/data layer.

Recommended long-term architecture:

```text
Crawler workflow / worker
  -> object storage for raw snapshots
  -> database/search index, e.g. Meilisearch, Typesense, OpenSearch, Postgres FTS, or SQLite/DuckDB artifacts
  -> small API endpoint for queries
  -> Squarespace/GitHub Pages frontend calls the API
```

Static JSON can still work as a low-cost phase if the index remains below the Pages size/deploy/bandwidth limits, but the frontend must never load the entire catalogue into memory.

## Important knobs

In `config/sources.yml`:

```yaml
settings:
  limits:
    max_items_total: 1000000
    max_items_per_source: 50000
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

For larger builds, raise `max_items_total` and source-level `max_items`, but watch the size of `public/` and the GitHub Pages deployment limits. If the generated `public/` directory approaches hundreds of megabytes, move storage/search off GitHub Pages.
