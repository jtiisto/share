# Personal Share

Cross-device file and note sharing system — PWA with FastAPI backend.

## Development Process

**Spec-driven development.** All work follows this flow:

1. **Spec first** — Write or update requirements in `plans/REQUIREMENTS.md` before any code changes. New features, changes, and bug fixes all start as spec updates.
2. **Separation of status** — Requirements are clearly marked as `[DONE]` (implemented) or unmarked (pending). This is the source of truth for what exists vs. what's planned.
3. **Implement** — Build against the spec. Tests are written alongside code.
4. **Mark done** — Update `plans/REQUIREMENTS.md` to reflect the new implementation status.

When proposing new work, always update the requirements file first and confirm with the user before implementing.

## Tech Stack

### Backend
- **FastAPI** (Python 3.11+)
- **Uvicorn** server
- **SQLite** database (`data/share.db`)
- **watchdog** for filesystem monitoring
- **mistune** for server-side Markdown rendering

### Frontend
- **Preact** + **HTM** (ESM from CDN, no build step)
- **Preact Signals** for state management
- **LocalForage** (IndexedDB) for offline storage
- **marked** for client-side Markdown rendering

### Testing
- **pytest** (unit — 66 tests, 95% coverage)
- **Playwright** (E2E browser tests — 10 tests)
- **httpx** for async test client

## Project Structure

```
src/
  server.py          # FastAPI app, lifespan, static serving, WebSocket
  config.py          # Paths, constants
  database.py        # Schema, CRUD operations
  modules/
    items.py         # API routes: items, categories, sync, share
    watcher.py       # Filesystem watcher with debounce
public/
  index.html         # SPA entry point
  styles.css         # Dark theme, mobile-first
  manifest.json      # PWA + share target
  sw.js              # Service worker
  js/
    app.js           # App shell, navigation
    store.js         # State management, API helpers, WebSocket
    items/           # View components
data/
  content/           # Watched directory (subdirs = categories)
plans/
  REQUIREMENTS.md    # Spec — source of truth for features and status
skills/
  share-note/        # Claude Code skill (source of truth, deployed to ~/.claude/skills/)
test/
  conftest.py        # Test fixtures
  unit/test_items.py # Unit/API tests (66 tests)
  e2e/test_app.py    # Playwright E2E tests (10 tests)
bin/
  server.sh          # start/stop/restart/status/logs
  share.sh           # CLI for sharing notes and files
  deploy-prod.sh     # Deploy to production (syncs skill + symlinks)
```

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
./bin/server.sh start    # Port 9100

# Run tests
pytest test/
```

## Key Conventions
- Port 9100 (wellness uses 9000)
- Database at `data/share.db`
- Content files at `data/content/` — subdirectories map to categories
- Empty categories are auto-deleted when their last live item is removed or recategorized
- Last-write-wins conflict resolution
- WebSocket at `/ws` for real-time updates from file watcher
- All API routes under `/api/`
- Visual design matches the wellness project (`../health/wellness`)

## Deployment

```bash
./bin/deploy-prod.sh /path/to/production/directory
```

The deploy script:
- Syncs `src/`, `public/`, `bin/` (excluding deploy script itself), and `requirements.txt`
- Copies the `share-note` skill with paths rewritten to the production directory
- Symlinks `~/.claude/skills/share-note` to the production copy
- Preserves `data/` (database and content files are never overwritten)

## Path-Based Routing

The app uses a `/share` URL prefix for all frontend paths (`BASE_PATH` in `config.py`). Backend routes stay at root (`/api/items`, `/ws`). The `StripPrefixMiddleware` in `server.py` bridges the gap by stripping `/share` from incoming requests.

This enables:
- **Tailscale `serve --set-path /share`** — Tailscale strips the prefix before forwarding; the middleware is a no-op
- **Direct access at `localhost:9100/share/`** — The middleware strips the prefix so backend routes match

Frontend files (`index.html`, `manifest.json`, `sw.js`, `store.js`, all component JS) use `/share/` prefixed paths. The server injects `$BASE_PATH$` into `sw.js` at serve time.
