"""
Database layer for Personal Share.
SQLite schema, connection helper, and CRUD operations for items and categories.
"""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import DB_PATH


_db_path: Path = DB_PATH


def set_db_path(path: Path):
    global _db_path
    _db_path = path


@contextmanager
def get_db():
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id              TEXT PRIMARY KEY,
                type            TEXT NOT NULL,
                title           TEXT NOT NULL,
                category        TEXT DEFAULT '',
                content         TEXT,
                filename        TEXT,
                mime_type       TEXT,
                size_bytes      INTEGER DEFAULT 0,
                pinned          INTEGER DEFAULT 0,
                source          TEXT DEFAULT 'web',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                deleted         INTEGER DEFAULT 0,
                _version        INTEGER DEFAULT 1,
                _lastModifiedBy TEXT DEFAULT ''
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_type ON items(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_updated ON items(updated_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_pinned ON items(pinned)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_deleted ON items(deleted)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                name        TEXT PRIMARY KEY,
                color       TEXT,
                sort_order  INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_id() -> str:
    return uuid.uuid4().hex


# ==================== Item CRUD ====================

def create_item(
    item_type: str,
    title: str,
    category: str = "",
    content: Optional[str] = None,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
    size_bytes: int = 0,
    source: str = "web",
    item_id: Optional[str] = None,
) -> dict:
    item_id = item_id or generate_id()
    now = get_utc_now()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO items (id, type, title, category, content, filename,
                              mime_type, size_bytes, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, item_type, title, category, content, filename,
              mime_type, size_bytes, source, now, now))
        conn.commit()

    return get_item(item_id)


def get_item(item_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE id = ? AND deleted = 0", (item_id,)
        ).fetchone()
        return dict(row) if row else None


def list_items(
    item_type: Optional[str] = None,
    category: Optional[str] = None,
    include_deleted: bool = False,
) -> list[dict]:
    with get_db() as conn:
        query = "SELECT * FROM items"
        conditions = []
        params = []

        if not include_deleted:
            conditions.append("deleted = 0")
        if item_type:
            conditions.append("type = ?")
            params.append(item_type)
        if category is not None:
            conditions.append("category = ?")
            params.append(category)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY pinned DESC, updated_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_item(item_id: str, **fields) -> Optional[dict]:
    allowed = {"title", "category", "content", "filename", "mime_type",
               "size_bytes", "pinned", "source", "type"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_item(item_id)

    updates["updated_at"] = get_utc_now()

    with get_db() as conn:
        # Increment version
        row = conn.execute("SELECT _version FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return None
        updates["_version"] = row["_version"] + 1

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [item_id]
        conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", params)
        conn.commit()

    return get_item(item_id)


def delete_item(item_id: str) -> bool:
    with get_db() as conn:
        now = get_utc_now()
        result = conn.execute(
            "UPDATE items SET deleted = 1, updated_at = ?, _version = _version + 1 WHERE id = ? AND deleted = 0",
            (now, item_id)
        )
        conn.commit()
        return result.rowcount > 0


def toggle_pin(item_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT pinned FROM items WHERE id = ? AND deleted = 0", (item_id,)).fetchone()
        if not row:
            return None
        new_pinned = 0 if row["pinned"] else 1
    return update_item(item_id, pinned=new_pinned)


# ==================== Category CRUD ====================

def list_categories() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY sort_order, name"
        ).fetchall()
        return [dict(r) for r in rows]


def create_category(name: str, color: Optional[str] = None, sort_order: int = 0) -> dict:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, color, sort_order) VALUES (?, ?, ?)",
            (name, color, sort_order)
        )
        conn.commit()
    return {"name": name, "color": color, "sort_order": sort_order}


def update_category(name: str, **fields) -> Optional[dict]:
    allowed = {"color", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_category(name)

    with get_db() as conn:
        row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [name]
        conn.execute(f"UPDATE categories SET {set_clause} WHERE name = ?", params)
        conn.commit()
    return get_category(name)


def rename_category(old_name: str, new_name: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM categories WHERE name = ?", (old_name,)).fetchone()
        if not row:
            return None
        # Update items that reference this category
        conn.execute("UPDATE items SET category = ? WHERE category = ?", (new_name, old_name))
        # Update the category itself
        conn.execute(
            "INSERT OR REPLACE INTO categories (name, color, sort_order) VALUES (?, ?, ?)",
            (new_name, row["color"], row["sort_order"])
        )
        if old_name != new_name:
            conn.execute("DELETE FROM categories WHERE name = ?", (old_name,))
        conn.commit()
    return get_category(new_name)


def delete_category(name: str) -> bool:
    with get_db() as conn:
        # Clear category from items (don't delete the items)
        conn.execute("UPDATE items SET category = '' WHERE category = ?", (name,))
        result = conn.execute("DELETE FROM categories WHERE name = ?", (name,))
        conn.commit()
        return result.rowcount > 0


def get_category(name: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def ensure_category(name: str):
    if name:
        create_category(name)


# ==================== Sync helpers ====================

def get_items_since(since: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE updated_at > ? ORDER BY updated_at",
            (since,)
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_item_from_sync(item_data: dict) -> dict:
    """Insert or update an item from sync data (last-write-wins)."""
    item_id = item_data["id"]
    now = get_utc_now()

    with get_db() as conn:
        existing = conn.execute("SELECT _version, updated_at FROM items WHERE id = ?", (item_id,)).fetchone()

        if existing:
            # Last-write-wins: only apply if incoming is newer
            if item_data.get("updated_at", "") >= existing["updated_at"]:
                fields = {k: v for k, v in item_data.items() if k not in ("id", "created_at")}
                fields["_version"] = existing["_version"] + 1
                set_clause = ", ".join(f"{k} = ?" for k in fields)
                params = list(fields.values()) + [item_id]
                conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", params)
                conn.commit()
        else:
            item_data.setdefault("created_at", now)
            item_data.setdefault("updated_at", now)
            cols = ", ".join(item_data.keys())
            placeholders = ", ".join("?" * len(item_data))
            conn.execute(
                f"INSERT INTO items ({cols}) VALUES ({placeholders})",
                list(item_data.values())
            )
            conn.commit()

    return get_item(item_id) or item_data


def get_meta(key: str) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
