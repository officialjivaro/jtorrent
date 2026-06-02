# Source adapters

## `html_torrent_links`

Use this for official pages that list `.torrent` files.

```yaml
- id: example_official
  name: "Example Official Downloads"
  type: html_torrent_links
  enabled: true
  category: linux
  source_homepage: "https://example.org/downloads"
  copyright_status: open-source
  license: "Official project torrents."
  page_urls:
    - "https://example.org/downloads/torrents/"
  include_url_regexes:
    - "\\.torrent$"
  tags: [linux, official]
  fetch_torrent_metadata: true
```

## `rss_feed`

Use this for authorized feeds that include torrent or magnet links.

```yaml
- id: example_rss
  name: "Example RSS"
  type: rss_feed
  enabled: true
  category: datasets
  source_homepage: "https://example.org"
  copyright_status: open-data
  license: "Open dataset feed."
  feed_urls:
    - "https://example.org/feed.xml"
```

## `internet_archive_advancedsearch`

Disabled by default because item-level rights can vary. Enable only with a query you have reviewed.

```yaml
- id: ia_example
  name: "Internet Archive Example"
  type: internet_archive_advancedsearch
  enabled: true
  category: public-domain
  source_homepage: "https://archive.org"
  copyright_status: public-domain
  license: "Reviewed Internet Archive collection."
  query: "collection:prelinger AND mediatype:movies"
  rows: 50
  include_torrent_url: true
```

## `direct_list`

Use this for a fixed list of official torrents.

```yaml
- id: manual_project
  name: "Manual Project Torrents"
  type: direct_list
  enabled: true
  category: open-source
  source_homepage: "https://project.example"
  copyright_status: open-source
  license: "Official project torrents."
  items:
    - title: "Project ISO"
      source_url: "https://project.example/download"
      torrent_url: "https://project.example/project.iso.torrent"
```
