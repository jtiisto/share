# Personal Share

Cross-device file and note sharing system. Drop files on the server, view them instantly on your phone or laptop.

## What It Does

- **Files** — Copy a file into `data/content/` on the server and it appears on all connected devices within a second via WebSocket.
- **Notes** — Persistent clipboard across devices. Create, edit, and sync short text snippets.
- **Categories** — Organize items with tags. Subdirectories in `data/content/` map to categories automatically.
- **Pinning** — Pin important items for quick access.
- **Offline** — Works offline with dirty tracking and background sync on reconnect.
- **Android Share Target** — Share text, URLs, or files from any Android app directly into the system.
- **Content Viewing** — Render HTML and Markdown files directly in the app.

## Devices

| Device  | Interface | Role |
|---------|-----------|------|
| Server  | File drop / API / Web UI | Primary hub, file watcher auto-syncs |
| Android | Installable PWA | View, share, upload/download |
| Laptop  | Web client | View, upload/download |

## Tech Stack

**Backend:** FastAPI, Uvicorn, SQLite, watchdog (filesystem monitoring), mistune (Markdown)

**Frontend:** Preact + HTM (ESM from CDN, no build step), Preact Signals, LocalForage, marked.js

**PWA:** Service worker with offline support, web manifest, Android share target

## Quick Start

```bash
pip install -r requirements.txt
./bin/server.sh start       # Starts on port 9100
./bin/server.sh status      # Check if running
./bin/server.sh logs        # Tail the log
```

Open `http://<server-ip>:9100` in a browser. On Android, use "Add to Home Screen" to install as a PWA.

## Project Structure

```
src/
  server.py          # FastAPI app, WebSocket, static serving
  config.py          # Paths, constants
  database.py        # SQLite schema and CRUD
  modules/
    items.py         # API routes (items, categories, sync, share)
    watcher.py       # Filesystem watcher with 300ms debounce
public/              # Frontend SPA (served as static files)
data/
  content/           # Watched directory — subdirs = categories
  share.db           # SQLite database
test/
  unit/              # 59 unit tests, 93% coverage
  e2e/               # Playwright browser tests
bin/
  server.sh          # start/stop/restart/status/logs
  deploy-prod.sh     # Safe deployment (preserves data)
plans/
  REQUIREMENTS.md    # Feature spec — source of truth
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/items` | List items (filter by `?type=` or `?category=`) |
| POST | `/api/items` | Create note |
| GET | `/api/items/{id}` | Get item |
| PUT | `/api/items/{id}` | Update item |
| DELETE | `/api/items/{id}` | Delete item |
| PATCH | `/api/items/{id}/pin` | Toggle pin |
| POST | `/api/items/upload` | Upload file (multipart) |
| GET | `/api/items/{id}/download` | Download file |
| GET | `/api/items/{id}/render` | Render HTML/MD content |
| GET/POST | `/api/categories` | List/create categories |
| PUT/DELETE | `/api/categories/{name}` | Update/delete category |
| GET | `/api/sync/status` | Last sync timestamp |
| POST | `/api/sync/pull` | Pull items since timestamp |
| POST | `/api/sync/push` | Push items (last-write-wins) |
| POST | `/api/share` | Android share target |
| WS | `/ws` | Real-time notifications |

## Testing

```bash
pytest test/unit/                # Unit tests
pytest test/e2e/                 # E2E browser tests (requires Playwright)
pytest test/unit/ --cov=src      # With coverage report
```

Git hooks run tests automatically:
- **Pre-commit:** Unit tests with coverage report
- **Pre-push:** Full suite with 90% coverage threshold

## Deployment

```bash
./bin/deploy-prod.sh /path/to/production
```

The deploy script copies application files while preserving existing `data/content/` and `*.db` files. Safe to run against both new and existing production directories.
