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

Six extractors exist. Five fetch **structured data**; one scrapes rendered HTML:
- `wordpress_api` (`extractors/wordpress_api.py`): WordPress REST API (`wp-json/wp/v2/posts`).
  Generic — adding another WordPress blog is a `feeds.yaml`-only change.
- `nextjs_blog` (`extractors/nextjs_blog.py`): pulls the `__NEXT_DATA__` JSON blob out of the
  page and reads `props.pageProps.cardsPaged.cards`.
- `sanity_blog` (`extractors/sanity_blog.py`): the Treblle blog is a Next.js App Router site
  (no `__NEXT_DATA__`) whose content lives in a **public Sanity CMS**, queried over the GROQ
  API with no auth. The GROQ projection is tuned to a `blogPost` schema; dates are ISO 8601
  with a `Z` (tz-aware as-is); Treblle's dataset exposes no author/category.
- `bump_blog` (`extractors/bump_blog.py`): the Bump.sh blog is a Bridgetown static site with no
  embedded JSON, so this extractor parses the rendered "Recent posts" cards with **BeautifulSoup**
  (CSS-class selectors over `html.parser`). Dates are `MM/DD/YYYY` and stamped UTC; no author is
  exposed by the source.
- `google_books` (`extractors/google_books.py`): backs the `books-*` feed family — recent
  **English** **Computers & Technology** books matching a per-feed search term, via the free,
  no-auth Google Books volumes API. The category (`subject:Computers`) and `langRestrict=en`
  are fixed in the extractor; the search term comes from `FeedConfig.query`, so adding a query
  is a `feeds.yaml`-only change. `publishedDate` has variable precision (`2024`, `2024-03`,
  `2024-03-15`) — padded to day 1 and stamped UTC; volumes with no usable date, a non-`en`
  language, or a publish date older than the rolling recency cutoff (`_RECENCY_MONTHS`, default
  2 calendar months before run time; `_now()` is the test seam) are skipped.
  An optional API key (raises the anonymous quota / avoids `429`) is read
  from the `GOOGLE_BOOKS_API_KEY` env var and appended as `key`; it is never put in `feeds.yaml`
  (which ships in the wheel) or logged.
- `oreilly_books` (`extractors/oreilly_books.py`): backs the `oreilly` feed — the newest
  **O'Reilly Media** books read straight from O'Reilly's own public, no-auth search API
  (`https://www.oreilly.com/api/v2/search/`). The publisher (`O'Reilly Media, Inc.`) and
  `formats=book` are fixed in the extractor and results are sorted `date_added` desc, so no
  query, key, or recency filter is needed (the service layer takes the newest `max_items`).
  `Post.published` is the `date_added` timestamp (ISO 8601, parsed via `datetime.fromisoformat`,
  stamped UTC if naive); the human link is `https://www.oreilly.com` + the result's relative
  `web_url`. Results that are not `format=book`, are non-`en`, or lack a usable id/title/link/date
  are skipped. This is the direct, structured-data source for O'Reilly books (it replaced an
  earlier Google Books `books-oreilly` config feed).

`extractors/base.py` also provides `clean_text()` — a deliberately narrow regex tag-stripper
for short title/excerpt snippets. It is **not** an HTML parser. The one real HTML parser
(`beautifulsoup4`, used by `bump_blog`) was added only because that source requires parsing
rendered HTML with selectors; prefer structured-data extraction where a source offers it.

`extractors/registry.py` maps extractor-type name → implementation and raises `UnknownFeedError`
for unknown types.

### Config

`src/feedsmith/feeds.yaml` (bundled inside the package so it ships in the wheel) is the source
of truth: `feed id → {title, extractor, url, site_url, max_items}`. `config.py` resolves it
package-relative (`Path(__file__).resolve().parent / "feeds.yaml"`) and loads it into Pydantic
`AppConfig`/`FeedConfig`, injecting the mapping key as each feed's `id`. All config problems
surface as `ConfigError`.

### Errors

Custom hierarchy in `exceptions.py`: `FeedsmithError` (base) → `ConfigError`, `UnknownFeedError`,
`FetchError`, `ParseError`. Extractors raise `FetchError`/`ParseError` with `raise ... from err`.

## Conventions specific to this repo

- **Tests never hit the network.** Extractor/service/CLI tests mock httpx with `respx` and feed
  recorded responses from `tests/fixtures/` (`boomi_posts.json`, `kong_blog.html`, `bump_blog.html`,
  `treblle_blog.json`, `google_books.json`, `oreilly_books.json`). Keep it that way.
- `Post.published` must be **timezone-aware** (a validator enforces this). WordPress `date_gmt`
  is UTC-without-offset and is stamped UTC; Next.js `publishedAt` carries a `Z`.
- structlog logging is configured with `cache_logger_on_first_use=False` on purpose, so the
  bound logger tracks the current stderr (this matters under pytest's stream capture; the
  autouse `_configure_logging` fixture in `conftest.py` rebinds per test).

## Git workflow

- **Never commit or push directly to `main`.** All changes go through a feature branch
  and a PR. Before any `git commit`/`git push`, run `git branch --show-current` and confirm
  you are **not** on `main` — a prior PR merge can leave the local checkout back on `main`.
  If you find yourself on `main` with uncommitted work, create a branch first.
- **Version bumps touch three files, keep them in sync:** `pyproject.toml` (`version`),
  `src/feedsmith/__init__.py` (`__version__`), and `uv.lock` (re-run `uv lock` after editing
  the first two). A feature (new extractor/source) is a **minor** bump; a fix is a **patch**.
- When adding a source, update **all** of: `feeds.yaml`, `registry.py`, the extractor list in
  this file, and the "Supported sources" table in `README.md`.
