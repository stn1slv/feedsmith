# feedsmith

Generate Atom feeds for blogs that publish no official RSS/Atom feed.

feedsmith is a small CLI. Each blog is described in `feeds.yaml` and bound to an
*extractor* that knows how to read that site's structured data, then a shared
builder serializes the posts to Atom 1.0.

## Supported sources

| Feed id | Blog | Extractor | Source |
|---------|------|-----------|--------|
| `boomi` | https://boomi.com/blog/ | `wordpress_api` | WordPress REST API (`wp-json/wp/v2/posts`) |
| `kong`  | https://konghq.com/blog/ | `nextjs_blog` | Embedded `__NEXT_DATA__` JSON |
| `bump`  | https://bump.sh/blog/ | `bump_blog` | Rendered HTML cards (BeautifulSoup) |
| `treblle` | https://treblle.com/blog/ | `sanity_blog` | Public Sanity CMS (GROQ query API) |
| `books-*` | https://books.google.com/ | `google_books` | Google Books API (English Computers & Technology books) |

The `wordpress_api` extractor is generic: adding another WordPress blog is a
config-only change in `feeds.yaml`.

The `google_books` extractor backs a family of `books-*` feeds — one per search
term (`books-mulesoft`, `books-kafka`, `books-api-management`, …), each listing
recent **English** books in the **Computers & Technology** category that match
the term. Only books published within the **last two months** are included, so the
feeds stay fresh. Adding a new query is a `feeds.yaml`-only change: copy a `books-*`
block and set its `id`, `title`, `query`, and `site_url`.

### Optional: Google Books API key

The Google Books API works **without** credentials, but anonymous requests share a
low quota and you may hit `HTTP 429`. Providing an API key raises the quota
(currently 1,000 requests/day, far more than these feeds need). The key is read from
the `GOOGLE_BOOKS_API_KEY` environment variable and sent as the `key` query
parameter; it is never stored in `feeds.yaml` (which ships inside the wheel) or logged.

To create one:

1. In the [Google Cloud Console](https://console.cloud.google.com/), select or create a project.
2. Enable the [Books API](https://console.cloud.google.com/apis/library/books.googleapis.com).
3. Under **APIs & Services → Credentials**, click **Create credentials → API key** and copy it.
4. (Recommended) Edit the key and restrict it to the **Books API**.

Then set it in the environment — feedsmith picks it up automatically:

```sh
export GOOGLE_BOOKS_API_KEY="your-api-key"
uv run feedsmith generate books-mulesoft
```

For CI / scheduled runs, store it as a secret instead of exporting it inline
(e.g. `gh secret set GOOGLE_BOOKS_API_KEY` and reference it from the workflow `env`).

## Install

Install via [Homebrew](https://brew.sh):

```bash
brew install stn1slv/tap/feedsmith
```

For development (from a checkout):

```bash
make setup        # uv sync
```

## Usage

Run the CLI with `uv run feedsmith <command>` (or via `make run ARGS="..."`).
With no command it prints help.

```bash
uv run feedsmith list                       # show configured feeds
uv run feedsmith generate boomi             # Atom to stdout
uv run feedsmith generate kong -o kong.xml  # Atom to a file
uv run feedsmith generate-all -o ./out      # write <id>.xml for every feed
```

### Commands

| Command | Argument | Description |
|---------|----------|-------------|
| `list` | — | Print each configured feed as `id<TAB>title<TAB>(extractor)`. |
| `generate` | `FEED_ID` (required) | Build the Atom feed for one blog. Writes to stdout unless `-o` is given. |
| `generate-all` | — | Build every configured feed. Requires `-o` (a directory); writes `<id>.xml` per feed. |

### Options

| Option | Applies to | Description |
|--------|------------|-------------|
| `-o`, `--output PATH` | `generate`, `generate-all` | For `generate`, a file path (default: stdout). For `generate-all`, a directory (created if missing); **required**. |
| `-c`, `--config PATH` | all | Path to a `feeds.yaml` to use instead of the bundled config. |
| `-v`, `--verbose` | all | Enable debug logging (to stderr). |
| `--help` | all | Show help for the CLI or a specific command. |

A failed run (bad config, unknown feed, fetch/parse error) logs the error and
exits with status `1`.

## Adding a blog

1. Add an entry under `feeds:` in `src/feedsmith/feeds.yaml` (id, title, extractor, url, site_url).
2. If the site needs a new extraction strategy, add an extractor in
   `src/feedsmith/extractors/` and register it in `registry.py`.

## Development

```bash
make test     # pytest with coverage (>= 80%)
make lint     # ruff + mypy --strict
make format   # ruff format + autofix
```
