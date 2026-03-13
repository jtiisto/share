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

## Installation

### Prerequisites

- Python 3.11+
- pip

### Development Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./bin/server.sh start       # Starts on port 9100
```

Access the app at `http://localhost:9100/share/`. The `/share` prefix is baked into all frontend paths and handled by the `StripPrefixMiddleware` in the server, so it works with or without a reverse proxy.

### Production Setup with Tailscale

Share and [Wellness](https://github.com/jtiisto/wellness) are designed to run side-by-side on the same Tailscale hostname using path-based routing. Both PWAs get non-overlapping scopes (`/share/` and `/wellness/`) so Chrome on Android treats them as separate installable apps.

**1. Start both servers:**

```bash
# Share — port 9100
./bin/server.sh start

# Wellness — port 9000 (separate project)
```

**2. Configure Tailscale path-based routing:**

```bash
sudo ./bin/setup-tailscale.sh
```

This runs:

```bash
tailscale serve --https 9443 --set-path /share --bg http://localhost:9100
tailscale serve --https 9443 --set-path /wellness --bg http://localhost:9000
```

**3. Access the apps:**

```
https://<tailscale-hostname>:9443/share/
https://<tailscale-hostname>:9443/wellness/
```

On Android, "Add to Home Screen" installs each as an independent PWA.

### Without Tailscale

The app works without Tailscale for local development and testing:

```
http://localhost:9100/share/
```

The `StripPrefixMiddleware` in `server.py` strips the `/share` prefix from incoming requests so backend routes stay at root (`/api/items`, `/ws`, etc.) while the frontend uses prefixed paths (`/share/api/items`, `/share/ws`). This means the same server works both behind Tailscale (which also strips the prefix) and via direct access.

### systemd Service

For production, install as a systemd service:

```bash
sudo cp share.service /etc/systemd/system/share.service
sudo systemctl daemon-reload
sudo systemctl enable --now share
```

## Server Control

```bash
./bin/server.sh start       # Start on port 9100
./bin/server.sh stop        # Stop the server
./bin/server.sh restart     # Restart
./bin/server.sh status      # Check if running
./bin/server.sh logs        # Tail the log
```

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

All API endpoints are accessed via the `/share` prefix from the browser (e.g., `/share/api/items`). The server's `StripPrefixMiddleware` strips this prefix, so backend route handlers use unprefixed paths.

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
