# Frontend integration notes

The backend publishes static JSON. Your frontend should not send arbitrary searches to GitHub Actions. It should fetch the static data from GitHub Pages and search in the browser.

## Use v2 for large datasets

The v2 index is designed for large static search:

```html
<script src="https://officialjivaro.github.io/jtorrent/jtorrent-search-v2.js"></script>
<script>
const response = await window.JTorrentSearchV2.search({
  baseUrl: "https://officialjivaro.github.io/jtorrent",
  query: "ubuntu iso",
  limit: 20
});
console.log(response.results);
</script>
```

This downloads only the token buckets needed for the query and then hydrates matching docs from `data/v2/docs/*.json`.

## Why not load all shards?

The legacy code path loads `manifest.sharding.search_shards` and searches them all in memory. That is fine for a small dataset, but it becomes slow and bandwidth-heavy as the item count grows. When `item_count` exceeds `settings.output.legacy_max_items`, the legacy endpoints become small `mode: "v2-only"` pointers.

## Useful endpoints

```text
/data/manifest.json
/data/v2/manifest.json
/data/v2/tokens/<prefix>.json
/data/v2/docs/*.json
/jtorrent-search-v2.js
/data/sources.json
```

## Minimal custom search without helper

```js
const BACKEND = "https://officialjivaro.github.io/jtorrent";
const manifest = await fetch(`${BACKEND}/data/manifest.json`, { cache: "no-store" }).then(r => r.json());
const v2 = manifest.search_v2;

function bucketFor(token) {
  return token.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, v2.token_bucket_prefix_chars).padEnd(v2.token_bucket_prefix_chars, "_");
}

const token = "ubuntu";
const bucket = await fetch(`${BACKEND}/data/v2/tokens/${bucketFor(token)}.json`).then(r => r.json());
const docIds = bucket.tokens[token] || [];
```

Then use `v2.doc_shards` to find which document shard contains each `doc_id`.

## Display suggestions

- Show `manifest.generated_at` and `manifest.item_count`.
- Show source/category/license metadata on each result.
- Prefer linking to the source/details page first.
- Direct torrent/magnet buttons can be shown when those fields are present.
