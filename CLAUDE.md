# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`feedsmith` is a CLI that generates **Atom** feeds for blogs that publish no official RSS/Atom
feed. It fetches a blog's structured data, normalizes it to `Post` objects, and serializes
to Atom 1.0. Output is summary/excerpt-level (one HTTP request per blog; no per-post fetching).

> Note: the package and CLI are named `feedsmith`, but the working directory is `localfeed/`.
> The package lives in `src/feedsmith/`.

## Commands

All tasks go through the `Makefile` (uv-backed):

| Command | What it does |
|---------|--------------|
| `make setup` | `uv sync` — install deps (fetches Python 3.13 if needed) |
| `make test` | `uv run pytest` (coverage gate: **≥ 80%**, currently ~96%) |
| `make lint` | `uv run ruff check` + `uv run mypy src` (mypy is **strict**) |
| `make format` | `uv run ruff format` + `ruff check --fix` |
| `make run ARGS="generate boomi"` | run the CLI |

Run a single test: `uv run pytest tests/test_feed.py::test_build_atom_structure`

Run the CLI directly: `uv run feedsmith {list,generate <id>,generate-all -o DIR}`
(add `--verbose` for debug logs, `--config PATH` to override `feeds.yaml`).

### Snapshot tests

`tests/test_feed.py` uses **syrupy** snapshots. When the Atom output changes intentionally,
regenerate with `uv run pytest --snapshot-update`.

## Architecture

The core pipeline (in `src/feedsmith/`):

```
cli.py  →  config.load_config()  →  registry.get_extractor(cfg.extractor)
        →  extractor.fetch(cfg, client)  →  service sorts/truncates
        →  feed.build_atom(meta, posts)  →  stdout / file
```

Strict **presentation vs. service** separation:
- `cli.py` (Typer) is the **only** layer that catches `FeedsmithError`, logs it via structlog,
  and exits non-zero. Internal layers let domain errors propagate.
- `service.py` orchestrates config → extractor → feed; it is CLI-agnostic and holds the
  sort-by-`published`-desc + truncate-to-`max_items` logic.

### The extractor abstraction (the key extension point)

Each blog is bound to an **extractor type** via the `extractor` field in `feeds.yaml`.
Extractors are strategies implementing the `Extractor` protocol (`extractors/base.py`):
`fetch(cfg: FeedConfig, client: httpx.Client) -> list[Post]`. They must **not** sort or
truncate — the service layer does that. They map source data to the normalized `Post` model.

Two extractors exist, and they fetch **structured data, not scraped HTML**:
- `wordpress_api` (`extractors/wordpress_api.py`): WordPress REST API (`wp-json/wp/v2/posts`).
  Generic — adding another WordPress blog is a `feeds.yaml`-only change.
- `nextjs_blog` (`extractors/nextjs_blog.py`): pulls the `__NEXT_DATA__` JSON blob out of the
  page and reads `props.pageProps.cardsPaged.cards`.

`extractors/base.py` also provides `clean_text()` — a deliberately narrow regex tag-stripper
for short title/excerpt snippets. It is **not** an HTML parser; there is no BeautifulSoup/lxml
dependency. A full HTML parser is only warranted if a future source requires parsing rendered
HTML with selectors.

`extractors/registry.py` maps extractor-type name → implementation and raises `UnknownFeedError`
for unknown types.

### Config

`feeds.yaml` (repo root) is the source of truth: `feed id → {title, extractor, url, site_url,
max_items}`. `config.py` loads it into Pydantic `AppConfig`/`FeedConfig`, injecting the mapping
key as each feed's `id`. All config problems surface as `ConfigError`.

### Errors

Custom hierarchy in `exceptions.py`: `FeedsmithError` (base) → `ConfigError`, `UnknownFeedError`,
`FetchError`, `ParseError`. Extractors raise `FetchError`/`ParseError` with `raise ... from err`.

## Conventions specific to this repo

- **Tests never hit the network.** Extractor/service/CLI tests mock httpx with `respx` and feed
  recorded responses from `tests/fixtures/` (`boomi_posts.json`, `kong_blog.html`). Keep it that way.
- `Post.published` must be **timezone-aware** (a validator enforces this). WordPress `date_gmt`
  is UTC-without-offset and is stamped UTC; Next.js `publishedAt` carries a `Z`.
- structlog logging is configured with `cache_logger_on_first_use=False` on purpose, so the
  bound logger tracks the current stderr (this matters under pytest's stream capture; the
  autouse `_configure_logging` fixture in `conftest.py` rebinds per test).
