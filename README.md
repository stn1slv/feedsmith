# LocalFeed

Generate Atom feeds for blogs that publish no official RSS/Atom feed.

LocalFeed is a small CLI. Each blog is described in `feeds.yaml` and bound to an
*extractor* that knows how to read that site's structured data, then a shared
builder serializes the posts to Atom 1.0.

## Supported sources

| Feed id | Blog | Extractor | Source |
|---------|------|-----------|--------|
| `boomi` | https://boomi.com/blog/ | `wordpress_api` | WordPress REST API (`wp-json/wp/v2/posts`) |
| `kong`  | https://konghq.com/blog/ | `nextjs_blog` | Embedded `__NEXT_DATA__` JSON |

The `wordpress_api` extractor is generic: adding another WordPress blog is a
config-only change in `feeds.yaml`.

## Install

```bash
make setup        # uv sync
```

## Usage

```bash
uv run feedsmith list                       # show configured feeds
uv run feedsmith generate boomi             # Atom to stdout
uv run feedsmith generate kong -o kong.xml  # Atom to a file
uv run feedsmith generate-all -o ./out      # write <id>.xml for every feed
```

Add `--verbose` for debug logging, or `--config path/to/feeds.yaml` to use a
different config.

## Adding a blog

1. Add an entry under `feeds:` in `feeds.yaml` (id, title, extractor, url, site_url).
2. If the site needs a new extraction strategy, add an extractor in
   `src/feedsmith/extractors/` and register it in `registry.py`.

## Development

```bash
make test     # pytest with coverage (>= 80%)
make lint     # ruff + mypy --strict
make format   # ruff format + autofix
```
