# Personal Share

Cross-device file and note sharing system. Drop files on your server, view them instantly on your phone or laptop.

Built as an installable PWA with a FastAPI backend. No cloud services, no accounts — runs on your own hardware.

## Features

- **Notes** — cross-device persistent clipboard for URLs, commands, text snippets
- **Files** — upload/download any file type, with in-app rendering for HTML and Markdown
- **Categories** — organize items into categories; empty categories are auto-cleaned
- **Pinning** — pin items for quick access
- **Real-time sync** — WebSocket pushes changes to all connected clients instantly
- **Offline support** — service worker caches the app; notes created offline sync when back online
- **Android share target** — share text, URLs, and files from Android's share menu
- **File watcher** — drop files into `data/content/` on the server and they appear automatically
- **CLI sharing** — `personal-share.sh` for quick notes and file uploads from the terminal
- **CLI fetching** — `personal-fetch.sh` for downloading items to any machine
- **Claude Code skills** — `/personal-share` and `/personal-fetch` for sharing and fetching from Claude Code

## Requirements

- Python 3.11+
- A modern browser (Chrome/Edge recommended for PWA install)

## Installation

```bash
git clone <repo-url> share
cd share

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# Start the server (port 9100, runs in background)
./bin/server.sh start

# Other commands
./bin/server.sh stop
./bin/server.sh restart
./bin/server.sh status
./bin/server.sh logs      # show recent logs
./bin/server.sh follow    # tail -f the log
```

The app is available at `http://localhost:9100/share/`.

## Quick Share from CLI

```bash
# Share a URL (title auto-derived from domain)
./bin/personal-share.sh "https://example.com/article"

# Share a note with explicit title
./bin/personal-share.sh -t "Deploy reminder" "remember to deploy on Friday"

# Share with a category
./bin/personal-share.sh -c "links" "https://docs.python.org/3/"

# Share a file
./bin/personal-share.sh /path/to/document.pdf

# Share a file with category and title
./bin/personal-share.sh -c "docs" -t "API Reference" /path/to/api-docs.pdf

# Pipe support (always creates a note)
echo "some text" | ./bin/personal-share.sh -t "Piped Note"
```

## Fetch from CLI

Download files or export notes from any machine with network access to the server.

```bash
# List recent items
./bin/personal-fetch.sh --list

# List only files or notes
./bin/personal-fetch.sh --list --type file
./bin/personal-fetch.sh --list --type note

# List items in a category
./bin/personal-fetch.sh --list --category "docs"

# Fetch by title (partial match, must be unique)
./bin/personal-fetch.sh "report"

# Fetch to a specific directory
./bin/personal-fetch.sh -o /tmp "cookie recipe"
```

Notes are saved as Markdown files. Files are downloaded with their original filename. If a file already exists, a number suffix is added (e.g. `report_1.pdf`).

## File Watcher

The server monitors `data/content/` for filesystem changes. Subdirectories map to categories:

```
data/content/
  recipes/
    cookies.md      -> category: recipes
    bread.html      -> category: recipes
  photo.jpg         -> no category
```

Drop files into the directory (or a subdirectory) and they appear in the app automatically. The watcher debounces events (300ms) and ignores files created by the API to prevent loops.

A special `data/content/_inbox.txt` file is also watched — each line becomes a note, and the file is truncated after processing.

## Installing as a PWA

1. Open the app in Chrome/Edge on your device
2. Tap "Install" or "Add to Home Screen"
3. The app runs standalone with offline support

On Android, the installed PWA registers as a share target — you can share text, URLs, and files from any app directly into Personal Share.

## Remote Access with Tailscale

To access the app from your phone and laptop outside your local network, use [Tailscale](https://tailscale.com/) with HTTPS serving.

### Setup

1. Install Tailscale on your server and all client devices
2. Configure HTTPS serving with a path prefix:

```bash
sudo tailscale serve --https 9443 --set-path /share --bg http://localhost:9100
```

3. Verify:

```bash
sudo tailscale serve status
```

4. Access the app at `https://<your-tailscale-hostname>:9443/share/`

The app's path-based routing handles this automatically. Tailscale strips the `/share` prefix before forwarding, and the server's `StripPrefixMiddleware` handles direct access at `localhost:9100/share/`. No additional configuration needed.

### Multiple apps on one port

You can serve multiple apps on the same Tailscale HTTPS port using different path prefixes:

```bash
sudo tailscale serve --https 9443 --set-path /share --bg http://localhost:9100
sudo tailscale serve --https 9443 --set-path /other-app --bg http://localhost:9200
```

Each app gets its own PWA scope, so Chrome on Android treats them as separate installable apps.

### Without Tailscale

The app works fine without Tailscale for local network use:

```
http://localhost:9100/share/
http://<your-server-ip>:9100/share/
```

## Deployment

Deploy to a production directory (separate from development):

```bash
./bin/deploy-prod.sh /path/to/production/share
```

This syncs application files without touching `data/` — your database and content files are preserved. It also deploys the Claude Code skill with paths rewritten for the production location.

First-time production setup:

```bash
cd /path/to/production/share
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./bin/server.sh start
```

## Testing

```bash
# All tests (unit + E2E)
pytest test/

# Unit tests only (66 tests, 95% coverage)
pytest test/unit/

# E2E browser tests (requires: pip install pytest-playwright && playwright install chromium)
pytest test/e2e/

# With coverage report
pytest test/ --cov=src --cov-report=term-missing
```

### Test mode

Run an isolated instance with seeded sample data for manual testing:

```bash
python3 src/server.py --test
```

This starts on port 9101 with a separate database and content directory. Production data is never touched.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/items` | List items (filter by `?type=` or `?category=`) |
| POST | `/api/items` | Create note |
| GET | `/api/items/{id}` | Get item |
| PUT | `/api/items/{id}` | Update item |
| DELETE | `/api/items/{id}` | Delete item (auto-cleans empty category) |
| PATCH | `/api/items/{id}/pin` | Toggle pin |
| POST | `/api/items/upload` | Upload file (multipart) |
| GET | `/api/items/{id}/download` | Download file |
| GET | `/api/items/{id}/render` | Render HTML/MD content |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Create category |
| PUT | `/api/categories/{name}` | Update/rename category |
| DELETE | `/api/categories/{name}` | Delete category |
| GET | `/api/sync/status` | Last sync timestamp |
| POST | `/api/sync/pull` | Pull items since timestamp |
| POST | `/api/sync/push` | Push items (last-write-wins) |
| POST | `/api/share` | Share target endpoint (multipart) |
| WS | `/ws` | Real-time notifications |

All endpoints are accessed via the `/share` prefix from the browser (e.g., `/share/api/items`). The server middleware strips this prefix so route handlers use unprefixed paths.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, SQLite, watchdog, mistune
- **Frontend:** Preact + HTM (ESM from CDN, no build step), Preact Signals, LocalForage, marked.js
- **Testing:** pytest (unit), Playwright (E2E), httpx

## Project Structure

```
src/
  server.py          # FastAPI app, WebSocket, static serving
  config.py          # Paths, constants
  database.py        # SQLite schema, CRUD operations
  modules/
    items.py         # API routes: items, categories, sync, share
    watcher.py       # Filesystem watcher with debounce
public/              # Frontend SPA (served as static files)
data/
  share.db           # SQLite database (created on first run)
  content/           # Watched directory (subdirs = categories)
skills/
  personal-share/    # Claude Code skill for sharing
  personal-fetch/    # Claude Code skill for fetching
plans/
  REQUIREMENTS.md    # Feature spec and status
test/
  unit/              # Unit/API tests
  e2e/               # Playwright browser tests
bin/
  server.sh          # Server control (start/stop/restart/status/logs)
  personal-share.sh  # CLI for sharing notes and files
  personal-fetch.sh  # CLI for fetching items to local directory
  deploy-prod.sh     # Production deployment
```
