# Personal Share

Cross-device file and note sharing system — PWA with FastAPI backend.

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
- **pytest** (unit + integration)
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
test/
  conftest.py        # Test fixtures
  unit/test_items.py # API tests
bin/
  server.sh          # start/stop/restart/status/logs
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
- Last-write-wins conflict resolution
- WebSocket at `/ws` for real-time updates from file watcher
- All API routes under `/api/`
