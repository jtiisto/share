"""
Shared Folders API Router — browse server directories shared via symlinks.
"""
import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from config import FOLDERS_DIR
from database import (
    create_shared_folder, get_shared_folder, list_shared_folders,
    update_shared_folder, delete_shared_folder, shared_folder_exists_by_target,
)

router = APIRouter()

# Image extensions the browser can render natively
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif'}

# Extensions viewable in ContentViewer
VIEWABLE_EXTS = (
    IMAGE_EXTS |
    {'.html', '.htm', '.md', '.markdown', '.txt'} |
    {'.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.css', '.scss', '.sass', '.less',
     '.json', '.yaml', '.yml', '.toml', '.xml', '.csv', '.ini', '.cfg', '.conf',
     '.properties', '.env', '.graphql', '.gql', '.proto',
     '.py', '.rb', '.go', '.rs', '.java', '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx',
     '.cs', '.swift', '.kt', '.kts', '.scala', '.dart', '.zig', '.nim', '.v',
     '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.lua', '.perl', '.pl',
     '.r', '.php',
     '.hs', '.elm', '.clj', '.cljs', '.ex', '.exs', '.erl', '.ml', '.fs', '.fsx',
     '.lisp', '.scm',
     '.sql',
     '.dockerfile', '.tf', '.hcl', '.nix', '.cmake', '.gradle', '.makefile',
     '.diff', '.patch', '.log',
     '.asm', '.wasm', '.vhdl', '.verilog'}
)


class FolderShare(BaseModel):
    target_path: str


def _deduplicate_name(basename: str, target: Path) -> str:
    """Generate a unique symlink name by prepending parent path segments."""
    name = basename
    if not (FOLDERS_DIR / name).exists():
        return name

    parts = target.parts
    # Walk up parent dirs, prepending segments until unique
    for i in range(len(parts) - 2, -1, -1):
        segment = parts[i].replace("/", "_").lstrip("_")
        name = f"{segment}_{name}"
        if not (FOLDERS_DIR / name).exists():
            return name

    # Last resort: append number
    counter = 1
    base = basename
    while (FOLDERS_DIR / name).exists():
        name = f"{base}_{counter}"
        counter += 1
    return name


def _safe_filename(filename: str) -> bool:
    """Reject path traversal attempts."""
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    return True


def _count_files(folder_path: Path) -> int:
    """Count top-level files in a directory."""
    if not folder_path.is_dir():
        return 0
    return sum(1 for f in folder_path.iterdir() if f.is_file())


def _resolve_folder(name: str) -> Path:
    """Resolve a shared folder name to its target path, with validation."""
    folder = get_shared_folder(name)
    if not folder:
        raise HTTPException(status_code=404, detail="Shared folder not found")

    target = Path(folder["target_path"])
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Folder target no longer exists")

    return target


# ==================== Endpoints ====================

@router.post("/folders")
def api_share_folder(req: FolderShare):
    target = Path(req.target_path).resolve()

    if not target.exists():
        raise HTTPException(status_code=400, detail="Directory does not exist")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    if not os.access(str(target), os.R_OK):
        raise HTTPException(status_code=400, detail="Directory is not readable")
    if shared_folder_exists_by_target(str(target)):
        raise HTTPException(status_code=409, detail="Directory is already shared")

    FOLDERS_DIR.mkdir(parents=True, exist_ok=True)

    basename = target.name
    name = _deduplicate_name(basename, target)

    # Create symlink
    link_path = FOLDERS_DIR / name
    link_path.symlink_to(target)

    file_count = _count_files(target)
    folder = create_shared_folder(name, str(target), file_count)
    return folder


@router.get("/folders")
def api_list_folders():
    folders = list_shared_folders()
    # Update file counts
    for f in folders:
        target = Path(f["target_path"])
        if target.is_dir():
            f["file_count"] = _count_files(target)
    return folders


@router.get("/folders/{name}")
def api_list_folder_files(name: str):
    target = _resolve_folder(name)

    files = []
    for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
        if not entry.is_file():
            continue
        if entry.name.startswith('.'):
            continue
        stat = entry.stat()
        ext = entry.suffix.lower()
        mime = mimetypes.guess_type(entry.name)[0] or "application/octet-stream"
        files.append({
            "name": entry.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "mime_type": mime,
            "viewable": ext in VIEWABLE_EXTS,
        })

    # Update cached file count
    update_shared_folder(name, file_count=len(files))

    return files


@router.get("/folders/{name}/files/{filename}")
def api_download_folder_file(name: str, filename: str):
    if not _safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = _resolve_folder(name)
    file_path = target / filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Extra safety: ensure resolved path is still within target
    if not str(file_path.resolve()).startswith(str(target.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")

    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(file_path, filename=filename, media_type=mime)


@router.get("/folders/{name}/files/{filename}/render")
def api_render_folder_file(name: str, filename: str):
    if not _safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = _resolve_folder(name)
    file_path = target / filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if not str(file_path.resolve()).startswith(str(target.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")

    ext = file_path.suffix.lower()

    # Images: redirect to download (browser renders natively)
    if ext in IMAGE_EXTS:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return FileResponse(file_path, media_type=mime)

    # Text-based files: read and render
    text = file_path.read_text(errors="replace")

    if ext in ('.html', '.htm'):
        return HTMLResponse(content=text)

    if ext in ('.md', '.markdown'):
        try:
            import mistune
            html = mistune.html(text)
        except ImportError:
            html = f"<pre style='white-space:pre-wrap'>{text}</pre>"
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<pre style='white-space:pre-wrap'>{text}</pre>")


@router.delete("/folders/{name}")
def api_unshare_folder(name: str):
    folder = get_shared_folder(name)
    if not folder:
        raise HTTPException(status_code=404, detail="Shared folder not found")

    # Remove symlink
    link_path = FOLDERS_DIR / name
    if link_path.is_symlink():
        link_path.unlink()
    elif link_path.exists():
        link_path.unlink()

    delete_shared_folder(name)
    return {"status": "ok"}
