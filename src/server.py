"""
Personal Share - FastAPI server
Serves the SPA, mounts API routes, manages WebSocket connections and file watcher.
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from config import PUBLIC_DIR, CONTENT_DIR
from database import init_database


SERVER_VERSION = uuid.uuid4().hex[:8]


# ==================== WebSocket Manager ====================

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict):
        message = json.dumps({"event": event, "data": data})
        disconnected = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


async def ws_notify(event: str, data: dict):
    """Callback for the file watcher to notify connected clients."""
    await manager.broadcast(event, data)


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app):
    init_database()
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    # Start file watcher
    observer = None
    task = None
    try:
        from modules.watcher import start_watcher
        observer, task, _ = start_watcher(notify_callback=ws_notify)
    except ImportError:
        pass  # watchdog not installed

    yield

    # Cleanup
    if observer:
        observer.stop()
        observer.join(timeout=2)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Personal Share", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API Routes ====================

from modules.items import router as items_router
app.include_router(items_router, prefix="/api")


# ==================== WebSocket ====================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ==================== Static File Serving ====================

@app.get("/")
def serve_root():
    index_path = PUBLIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")

    html = index_path.read_text()
    html = html.replace('href="/styles.css"', f'href="/styles.css?v={SERVER_VERSION}"')
    html = html.replace('src="/js/app.js"', f'src="/js/app.js?v={SERVER_VERSION}"')

    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )


@app.get("/styles.css")
def serve_css():
    css_path = PUBLIC_DIR / "styles.css"
    if css_path.exists():
        return FileResponse(
            css_path,
            media_type="text/css",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/js/{file_path:path}")
def serve_js(file_path: str):
    js_path = PUBLIC_DIR / "js" / file_path
    if js_path.exists() and js_path.is_file():
        return FileResponse(
            js_path,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail=f"JS file not found: {file_path}")


@app.get("/manifest.json")
def serve_manifest():
    manifest_path = PUBLIC_DIR / "manifest.json"
    if manifest_path.exists():
        return FileResponse(
            manifest_path,
            media_type="application/manifest+json",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/sw.js")
def serve_sw():
    sw_path = PUBLIC_DIR / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="sw.js not found")

    content = sw_path.read_text()
    content = content.replace("$SERVER_VERSION$", SERVER_VERSION)

    return Response(
        content=content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, must-revalidate",
            "Service-Worker-Allowed": "/"
        }
    )


@app.get("/icons/{file_path:path}")
def serve_icons(file_path: str):
    icon_path = PUBLIC_DIR / "icons" / file_path
    if icon_path.exists() and icon_path.is_file():
        media_type = "image/png"
        if file_path.endswith(".svg"):
            media_type = "image/svg+xml"
        elif file_path.endswith(".ico"):
            media_type = "image/x-icon"
        return FileResponse(
            icon_path,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"}
        )
    raise HTTPException(status_code=404, detail=f"Icon not found: {file_path}")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Personal Share Server")
    parser.add_argument("--port", type=int, default=9100, help="Port number (default: 9100)")
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)
