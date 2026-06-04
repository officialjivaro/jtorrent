# Source adapters

The source list is the allowlist. Sources with `enabled: true` are fetched; sources with `enabled: false` are skipped. Fields like `license`, `license_url`, and `copyright_status` are optional metadata only.

## `html_torrent_links`

Use this for pages that list `.torrent` files.

```yaml
- id: example_official
  name: "Example Official Downloads"
  type: html_torrent_links
  enabled: true
  category: linux
  source_homepage: "https://example.org/downloads"
  copyright_status: open-source
  license: "Optional source/license note."
  page_urls:
    - "https://example.org/downloads/torrents/"
  include_url_regexes:
    - "\\.torrent$"
  tags: [linux, official]
  fetch_torrent_metadata: true
```

## `rss_feed`

Use this for feeds that include torrent or magnet links.

```yaml
- id: example_rss
  name: "Example RSS"
  type: rss_feed
  enabled: true
  category: datasets
  source_homepage: "https://example.org"
  copyright_status: open-data
  license: "Optional source/license note."
  feed_urls:
    - "https://example.org/feed.xml"
```

## `internet_archive_advancedsearch`

Use this for Internet Archive advanced-search queries.

```yaml
- id: ia_example
  name: "Internet Archive Example"
  type: internet_archive_advancedsearch
  enabled: true
  category: public-domain
  source_homepage: "https://archive.org"
  copyright_status: public-domain
  license: "Optional source/license note."
  query: "collection:prelinger AND mediatype:movies"
  rows: 50
  include_torrent_url: true
```

## `direct_list`

Use this for a fixed list of torrent records.

```yaml
- id: manual_project
  name: "Manual Project Torrents"
  type: direct_list
  enabled: true
  category: open-source
  source_homepage: "https://project.example"
  copyright_status: open-source
  license: "Optional source/license note."
  items:
    - title: "Project ISO"
      source_url: "https://project.example/download"
      torrent_url: "https://project.example/project.iso.torrent"
```


## Large-source controls

All adapters respect the builder-level source cap. A source-level `max_items` overrides `settings.limits.max_items_per_source`; use this for large feeds or APIs that should contribute more than the global default.

`internet_archive_advancedsearch` also supports:

```yaml
rows: 1000      # rows requested per API page
max_pages: 10   # maximum API pages to fetch
max_items: 10000
min_items: 1000 # optional QC threshold for required sources
```

Set `required: false` for best-effort sources whose domains or markup are known to be volatile. Their errors stay visible in `sources.json` and manifest warnings, while required-source errors still block QC.
