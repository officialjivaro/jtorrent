# Frontend integration notes

The backend publishes static JSON. Your Squarespace or custom frontend should not send arbitrary user searches to GitHub Actions. It should fetch the latest JSON from GitHub Pages, search locally in the browser, and render filtered results.

## Recommended fetch flow

Always load the manifest first. It tells the frontend whether the legacy one-file index is still small enough, or whether the data has been split into shards.

```js
const BACKEND_URL = "https://officialjivaro.github.io/jtorrent";
const manifest = await fetch(`${BACKEND_URL}/data/manifest.json`, {
  cache: "no-store"
}).then(r => r.json());
```

## Simple mode: one compact index still fits

When `manifest.files.search_index_min.mode === "inline"`, the compact index is still below the configured file-size limit, so the frontend can keep using the old one-file flow.

```js
async function loadCompactIndex() {
  const manifest = await fetch(`${BACKEND_URL}/data/manifest.json`, { cache: "no-store" }).then(r => r.json());

  if (manifest.files.search_index_min.mode === "inline") {
    return fetch(`${BACKEND_URL}/data/search-index.min.json`, { cache: "no-store" }).then(r => r.json());
  }

  const chunks = await Promise.all(
    manifest.sharding.compact_shards.map(shard =>
      fetch(`${BACKEND_URL}/${shard.path}`, { cache: "no-store" }).then(r => r.json())
    )
  );
  return chunks.flat();
}
```

## Large mode: use search shards first

When the index grows, use `manifest.sharding.search_shards` for fast searching/filtering. Search shards contain lightweight records plus the shard path for the full result.

```js
async function loadSearchRecords() {
  const manifest = await fetch(`${BACKEND_URL}/data/manifest.json`, { cache: "no-store" }).then(r => r.json());
  const chunks = await Promise.all(
    manifest.sharding.search_shards.map(shard =>
      fetch(`${BACKEND_URL}/${shard.path}`, { cache: "no-store" }).then(r => r.json())
    )
  );
  return chunks.flat();
}
```

When the user clicks a result, load the matching `compact_shard` or `full_shard` listed on that search record and find the item by `id`.

## Search example

```js
function search(items, query) {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter(item => [
    item.title,
    item.description,
    item.category,
    item.source_name,
    ...(item.tags || [])
  ].filter(Boolean).join(" ").toLowerCase().includes(q));
}
```

## Useful frontend filters

- keyword
- category
- source
- copyright/license status
- torrent available
- magnet available
- size range
- published/added date
- tags

## Display safety

Show the official source page prominently. Only show direct torrent/magnet buttons when the item has an authorized/open status in the JSON.
