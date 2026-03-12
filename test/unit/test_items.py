"""Unit tests for items API."""
import io
import pytest


class TestNotes:
    def test_create_note(self, client):
        resp = client.post("/api/items", json={
            "title": "Test Note",
            "content": "Hello world",
            "category": "general",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "note"
        assert data["title"] == "Test Note"
        assert data["content"] == "Hello world"
        assert data["category"] == "general"
        assert data["deleted"] == 0

    def test_list_notes(self, client):
        client.post("/api/items", json={"title": "Note 1", "content": "a"})
        client.post("/api/items", json={"title": "Note 2", "content": "b"})

        resp = client.get("/api/items?type=note")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2

    def test_get_note(self, client):
        resp = client.post("/api/items", json={"title": "Get Me", "content": "body"})
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Me"

    def test_update_note(self, client):
        resp = client.post("/api/items", json={"title": "Old Title", "content": "old"})
        item_id = resp.json()["id"]

        resp = client.put(f"/api/items/{item_id}", json={"title": "New Title", "content": "new"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        assert resp.json()["content"] == "new"
        assert resp.json()["_version"] == 2

    def test_delete_note(self, client):
        resp = client.post("/api/items", json={"title": "Delete Me", "content": "x"})
        item_id = resp.json()["id"]

        resp = client.delete(f"/api/items/{item_id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/items/{item_id}")
        assert resp.status_code == 404

    def test_pin_toggle(self, client):
        resp = client.post("/api/items", json={"title": "Pin Me", "content": "x"})
        item_id = resp.json()["id"]
        assert resp.json()["pinned"] == 0

        resp = client.patch(f"/api/items/{item_id}/pin")
        assert resp.status_code == 200
        assert resp.json()["pinned"] == 1

        resp = client.patch(f"/api/items/{item_id}/pin")
        assert resp.json()["pinned"] == 0

    def test_pinned_items_first(self, client):
        client.post("/api/items", json={"title": "Unpinned", "content": "a"})
        resp = client.post("/api/items", json={"title": "Pinned", "content": "b"})
        item_id = resp.json()["id"]
        client.patch(f"/api/items/{item_id}/pin")

        resp = client.get("/api/items")
        items = resp.json()
        assert items[0]["title"] == "Pinned"

    def test_filter_by_category(self, client):
        client.post("/api/items", json={"title": "Work", "content": "a", "category": "work"})
        client.post("/api/items", json={"title": "Home", "content": "b", "category": "home"})

        resp = client.get("/api/items?category=work")
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "Work"

    def test_not_found(self, client):
        resp = client.get("/api/items/nonexistent")
        assert resp.status_code == 404


class TestFiles:
    def test_upload_file(self, client):
        resp = client.post("/api/items/upload", data={
            "title": "test.txt",
            "category": "",
        }, files={
            "file": ("test.txt", b"hello world", "text/plain"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "file"
        assert data["title"] == "test.txt"
        assert data["mime_type"] == "text/plain"
        assert data["size_bytes"] == 11

    def test_download_file(self, client):
        resp = client.post("/api/items/upload", files={
            "file": ("download.txt", b"download me", "text/plain"),
        })
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/download")
        assert resp.status_code == 200
        assert resp.content == b"download me"

    def test_upload_with_category(self, client):
        resp = client.post("/api/items/upload", data={
            "category": "docs",
        }, files={
            "file": ("readme.md", b"# Hello", "text/markdown"),
        })
        data = resp.json()
        assert data["category"] == "docs"
        assert "docs/" in data["filename"]

    def test_delete_file_removes_from_disk(self, client, tmp_content_dir):
        resp = client.post("/api/items/upload", files={
            "file": ("todelete.txt", b"bye", "text/plain"),
        })
        item_id = resp.json()["id"]
        filename = resp.json()["filename"]

        assert (tmp_content_dir / filename).exists()

        client.delete(f"/api/items/{item_id}")
        assert not (tmp_content_dir / filename).exists()


class TestCategories:
    def test_create_and_list(self, client):
        client.post("/api/categories", json={"name": "work", "color": "#ff0000"})
        client.post("/api/categories", json={"name": "personal", "color": "#00ff00"})

        resp = client.get("/api/categories")
        assert resp.status_code == 200
        cats = resp.json()
        names = [c["name"] for c in cats]
        assert "work" in names
        assert "personal" in names


class TestSync:
    def test_sync_status(self, client):
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        assert "lastModified" in resp.json()

    def test_sync_pull(self, client):
        client.post("/api/items", json={"title": "Sync Me", "content": "x"})

        resp = client.post("/api/sync/pull", json={"since": "2000-01-01T00:00:00Z"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert "serverTime" in data

    def test_sync_push(self, client):
        import uuid
        item_id = uuid.uuid4().hex
        resp = client.post("/api/sync/push", json={
            "items": [{
                "id": item_id,
                "type": "note",
                "title": "Pushed Note",
                "content": "from client",
                "category": "",
                "updated_at": "2099-01-01T00:00:00Z",
            }]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applied"]) == 1

        # Verify it exists
        resp = client.get(f"/api/items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Pushed Note"


class TestShareTarget:
    def test_share_text(self, client):
        resp = client.post("/api/share", data={
            "title": "Shared Link",
            "text": "Check this out",
            "url": "https://example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "note"
        assert data["source"] == "share"
        assert "https://example.com" in data["content"]

    def test_share_file(self, client):
        resp = client.post("/api/share", data={
            "title": "Photo",
        }, files={
            "file": ("photo.jpg", b"\xff\xd8\xff\xe0", "image/jpeg"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "file"
        assert data["source"] == "share"


class TestStaticFiles:
    def test_serve_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Share" in resp.text

    def test_serve_css(self, client):
        resp = client.get("/styles.css")
        assert resp.status_code == 200

    def test_serve_js(self, client):
        resp = client.get("/js/app.js")
        assert resp.status_code == 200

    def test_serve_manifest(self, client):
        resp = client.get("/manifest.json")
        assert resp.status_code == 200

    def test_serve_sw(self, client):
        resp = client.get("/sw.js")
        assert resp.status_code == 200
        assert "$SERVER_VERSION$" not in resp.text

    def test_serve_icon(self, client):
        resp = client.get("/icons/icon-192.png")
        assert resp.status_code == 200
