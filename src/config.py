import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent   # share/
DATA_DIR = PROJECT_ROOT / "data"
PUBLIC_DIR = PROJECT_ROOT / "public"
CONTENT_DIR = DATA_DIR / "content"
DB_PATH = Path(os.environ.get("SHARE_DB_PATH", str(DATA_DIR / "share.db")))

# Server
DEFAULT_PORT = 9100
TEST_PORT = 9101
BASE_PATH = "/share"  # URL prefix for reverse proxy path-based routing

# Watcher
WATCHER_DEBOUNCE_MS = 300
WATCHER_IGNORE_TTL_S = 2
