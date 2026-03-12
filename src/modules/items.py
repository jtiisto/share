"""
Items API Router — CRUD for notes and files, categories, sync, and share target.
"""
import mimetypes
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from config import CONTENT_DIR
from database import (
    create_item, get_item, list_items, update_item, delete_item, toggle_pin,
    list_categories, create_category, ensure_category,
    get_items_since, upsert_item_from_sync, get_meta, set_meta,
    get_utc_now, generate_id,
)

router = APIRouter()


# ==================== Pydantic Models ====================

class NoteCreate(BaseModel):
    title: str
    content: str = ""
    category: str = ""
    pinned: bool = False

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None

class CategoryCreate(BaseModel):
    name: str
    color: Optional[str] = None
    sort_order: int = 0

class SyncPullRequest(BaseModel):
    since: str

class SyncPushRequest(BaseModel):
    items: list[dict]


# ==================== Items CRUD ====================

@router.get("/items")
def api_list_items(type: Optional[str] = None, category: Optional[str] = None):
    return list_items(item_type=type, category=category)


@router.post("/items")
def api_create_note(note: NoteCreate):
    if note.category:
        ensure_category(note.category)
    item = create_item(
        item_type="note",
        title=note.title,
        content=note.content,
        category=note.category,
        source="web",
    )
    if note.pinned:
        item = update_item(item["id"], pinned=1)
    return item


@router.get("/items/{item_id}")
def api_get_item(item_id: str):
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/items/{item_id}")
def api_update_item(item_id: str, note: NoteUpdate):
    updates = note.model_dump(exclude_none=True)
    if "category" in updates and updates["category"]:
        ensure_category(updates["category"])
    item = update_item(item_id, **updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}")
def api_delete_item(item_id: str):
    # Also remove file if it's a file item
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item["type"] == "file" and item["filename"]:
        file_path = CONTENT_DIR / item["filename"]
        if file_path.exists():
            file_path.unlink()

    if not delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "ok"}


@router.patch("/items/{item_id}/pin")
def api_toggle_pin(item_id: str):
    item = toggle_pin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# ==================== File Upload/Download ====================

@router.post("/items/upload")
async def api_upload_file(
    file: UploadFile = File(...),
    category: str = Form(""),
    title: str = Form(""),
    pinned: bool = Form(False),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    actual_title = title or file.filename
    safe_filename = file.filename.replace("/", "_").replace("\\", "_")

    # Place in category subdirectory
    if category:
        ensure_category(category)
        dest_dir = CONTENT_DIR / category
    else:
        dest_dir = CONTENT_DIR

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Handle filename collision
    dest_path = dest_dir / safe_filename
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Write file
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Relative path from CONTENT_DIR
    rel_path = str(dest_path.relative_to(CONTENT_DIR))
    mime = file.content_type or mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"

    item = create_item(
        item_type="file",
        title=actual_title,
        category=category,
        filename=rel_path,
        mime_type=mime,
        size_bytes=len(content),
        source="web",
    )
    if pinned:
        item = update_item(item["id"], pinned=1)
    return item


@router.get("/items/{item_id}/download")
def api_download_file(item_id: str):
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["type"] != "file" or not item["filename"]:
        raise HTTPException(status_code=400, detail="Not a file item")

    file_path = CONTENT_DIR / item["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        file_path,
        filename=Path(item["filename"]).name,
        media_type=item.get("mime_type", "application/octet-stream"),
    )


@router.get("/items/{item_id}/render")
def api_render_file(item_id: str):
    """Render HTML or Markdown files inline."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Notes: render content directly
    if item["type"] == "note":
        content = item.get("content", "")
        return HTMLResponse(content=f"<pre style='white-space:pre-wrap'>{content}</pre>")

    if item["type"] != "file" or not item["filename"]:
        raise HTTPException(status_code=400, detail="Not a renderable item")

    file_path = CONTENT_DIR / item["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    mime = item.get("mime_type", "")
    text = file_path.read_text(errors="replace")

    if mime == "text/html" or file_path.suffix.lower() == ".html":
        return HTMLResponse(content=text)

    if mime == "text/markdown" or file_path.suffix.lower() in (".md", ".markdown"):
        try:
            import mistune
            html = mistune.html(text)
        except ImportError:
            html = f"<pre style='white-space:pre-wrap'>{text}</pre>"
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<pre style='white-space:pre-wrap'>{text}</pre>")


# ==================== Categories ====================

@router.get("/categories")
def api_list_categories():
    return list_categories()


@router.post("/categories")
def api_create_category(cat: CategoryCreate):
    return create_category(cat.name, cat.color, cat.sort_order)


# ==================== Sync ====================

@router.get("/sync/status")
def api_sync_status():
    last_sync = get_meta("last_sync_time")
    return {"lastModified": last_sync}


@router.post("/sync/pull")
def api_sync_pull(req: SyncPullRequest):
    items = get_items_since(req.since)
    return {"items": items, "serverTime": get_utc_now()}


@router.post("/sync/push")
def api_sync_push(req: SyncPushRequest):
    results = []
    for item_data in req.items:
        result = upsert_item_from_sync(item_data)
        results.append(result)
    now = get_utc_now()
    set_meta("last_sync_time", now)
    return {"applied": results, "serverTime": now}


# ==================== Share Target ====================

@router.post("/share")
async def api_share_target(
    title: str = Form(""),
    text: str = Form(""),
    url: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """Handle incoming share target data from Android."""
    if file and file.filename:
        # Shared file
        safe_filename = file.filename.replace("/", "_").replace("\\", "_")
        dest_dir = CONTENT_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / safe_filename

        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)

        rel_path = str(dest_path.relative_to(CONTENT_DIR))
        mime = file.content_type or mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"

        item = create_item(
            item_type="file",
            title=title or file.filename,
            filename=rel_path,
            mime_type=mime,
            size_bytes=len(content),
            source="share",
        )
        return item

    # Shared text/URL
    combined = ""
    if text:
        combined += text
    if url:
        combined += ("\n" + url) if combined else url

    item = create_item(
        item_type="note",
        title=title or combined[:50] or "Shared item",
        content=combined,
        source="share",
    )
    return item
