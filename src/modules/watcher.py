"""
Filesystem watcher — monitors data/content/ for new/modified/deleted files.
Uses watchdog for filesystem events, bridges to asyncio via a queue.
Includes debounce (300ms) and self-ignore set to prevent re-processing API writes.
"""
import asyncio
import mimetypes
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent

from config import CONTENT_DIR, WATCHER_DEBOUNCE_MS, WATCHER_IGNORE_TTL_S
from database import (
    create_item, list_items, update_item, delete_item,
    ensure_category, get_utc_now,
)


class IgnoreSet:
    """Thread-safe set of paths to ignore, with TTL-based expiry."""

    def __init__(self, ttl_seconds: float = WATCHER_IGNORE_TTL_S):
        self._ttl = ttl_seconds
        self._paths: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, path: str):
        with self._lock:
            self._paths[path] = time.monotonic()

    def should_ignore(self, path: str) -> bool:
        with self._lock:
            if path not in self._paths:
                return False
            if time.monotonic() - self._paths[path] < self._ttl:
                return True
            del self._paths[path]
            return False

    def cleanup(self):
        now = time.monotonic()
        with self._lock:
            expired = [p for p, t in self._paths.items() if now - t >= self._ttl]
            for p in expired:
                del self._paths[p]


# Global ignore set — used by upload endpoints to prevent re-processing
ignore_set = IgnoreSet()


class ContentEventHandler(FileSystemEventHandler):
    """Handles filesystem events and puts them on the async queue."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._queue = queue
        self._loop = loop

    def _enqueue(self, event_type: str, path: str):
        if ignore_set.should_ignore(path):
            return
        # Skip hidden files and directories
        p = Path(path)
        if any(part.startswith(".") for part in p.parts):
            return
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait,
            {"type": event_type, "path": path, "time": time.monotonic()}
        )

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._enqueue("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._enqueue("deleted", event.src_path)


def _path_to_category(file_path: Path) -> str:
    """Extract category from path relative to CONTENT_DIR."""
    try:
        rel = file_path.relative_to(CONTENT_DIR)
        parts = rel.parts
        if len(parts) > 1:
            return parts[0]
    except ValueError:
        pass
    return ""


def _find_item_by_filename(rel_path: str) -> Optional[dict]:
    """Find an existing item by its filename."""
    items = list_items(item_type="file", include_deleted=True)
    for item in items:
        if item.get("filename") == rel_path:
            return item
    return None


async def _process_event(event: dict, notify_callback: Optional[Callable] = None):
    """Process a single filesystem event."""
    file_path = Path(event["path"])
    event_type = event["type"]

    try:
        rel_path = str(file_path.relative_to(CONTENT_DIR))
    except ValueError:
        return

    category = _path_to_category(file_path)

    if event_type in ("created", "modified"):
        if not file_path.exists() or not file_path.is_file():
            return

        existing = _find_item_by_filename(rel_path)
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        size = file_path.stat().st_size

        if existing:
            item = update_item(
                existing["id"],
                mime_type=mime,
                size_bytes=size,
                category=category,
            )
            if notify_callback and item:
                await notify_callback("item:updated", item)
        else:
            if category:
                ensure_category(category)
            item = create_item(
                item_type="file",
                title=file_path.name,
                category=category,
                filename=rel_path,
                mime_type=mime,
                size_bytes=size,
                source="watcher",
            )
            if notify_callback and item:
                await notify_callback("item:created", item)

    elif event_type == "deleted":
        existing = _find_item_by_filename(rel_path)
        if existing and not existing.get("deleted"):
            delete_item(existing["id"])
            if notify_callback:
                await notify_callback("item:deleted", {"id": existing["id"]})


async def event_processor(
    queue: asyncio.Queue,
    notify_callback: Optional[Callable] = None,
    debounce_ms: int = WATCHER_DEBOUNCE_MS,
):
    """Background task: consume events from the queue with debouncing."""
    pending: dict[str, dict] = {}

    while True:
        try:
            # Wait for first event or timeout to process pending
            try:
                event = await asyncio.wait_for(queue.get(), timeout=debounce_ms / 1000)
                pending[event["path"]] = event
            except asyncio.TimeoutError:
                pass

            # Drain any additional events
            while not queue.empty():
                try:
                    event = queue.get_nowait()
                    pending[event["path"]] = event
                except asyncio.QueueEmpty:
                    break

            # Process debounced events
            if pending:
                now = time.monotonic()
                ready = {
                    p: e for p, e in pending.items()
                    if now - e["time"] >= debounce_ms / 1000
                }
                for path in ready:
                    await _process_event(ready[path], notify_callback)
                    del pending[path]

        except Exception as e:
            print(f"Watcher processor error: {e}")
            await asyncio.sleep(1)


def start_watcher(
    notify_callback: Optional[Callable] = None,
) -> tuple[Observer, asyncio.Task, asyncio.Queue]:
    """Start the filesystem watcher and event processor.
    Returns (observer, processor_task, queue).
    """
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    handler = ContentEventHandler(queue, loop)
    observer = Observer()
    observer.schedule(handler, str(CONTENT_DIR), recursive=True)
    observer.daemon = True
    observer.start()

    task = asyncio.create_task(event_processor(queue, notify_callback))

    return observer, task, queue
