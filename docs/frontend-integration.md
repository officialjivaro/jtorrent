# Frontend integration notes

The backend publishes static JSON. Your Squarespace or custom frontend should not send arbitrary user searches to GitHub Actions. It should fetch the latest index, search locally in the browser, and render filtered results.

## Basic fetch

```js
const BACKEND_URL = "https://YOUR_GITHUB_USERNAME.github.io/jtorrent";
const response = await fetch(`${BACKEND_URL}/data/search-index.min.json`, {
  cache: "no-store"
});
const items = await response.json();
```

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
