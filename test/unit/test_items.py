"""Unit tests for items API."""
import io
import uuid
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

    def test_update_category_color(self, client):
        client.post("/api/categories", json={"name": "design", "color": "#000000"})

        resp = client.put("/api/categories/design", json={"color": "#ff00ff"})
        assert resp.status_code == 200
        assert resp.json()["color"] == "#ff00ff"

    def test_update_category_sort_order(self, client):
        client.post("/api/categories", json={"name": "alpha"})

        resp = client.put("/api/categories/alpha", json={"sort_order": 5})
        assert resp.status_code == 200
        assert resp.json()["sort_order"] == 5

    def test_rename_category(self, client):
        client.post("/api/categories", json={"name": "old_name", "color": "#aabb00"})
        # Create an item in that category
        client.post("/api/items", json={"title": "Cat Item", "content": "x", "category": "old_name"})

        resp = client.put("/api/categories/old_name", json={"name": "new_name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new_name"

        # Item should now be in new category
        resp = client.get("/api/items?category=new_name")
        items = resp.json()
        assert any(i["title"] == "Cat Item" for i in items)

        # Old category should be gone
        resp = client.get("/api/items?category=old_name")
        assert len(resp.json()) == 0

    def test_delete_category(self, client):
        client.post("/api/categories", json={"name": "temp_cat"})
        client.post("/api/items", json={"title": "Orphan", "content": "x", "category": "temp_cat"})

        resp = client.delete("/api/categories/temp_cat")
        assert resp.status_code == 200

        # Item should be uncategorized
        resp = client.get("/api/items")
        orphan = [i for i in resp.json() if i["title"] == "Orphan"]
        assert len(orphan) == 1
        assert orphan[0]["category"] == ""

    def test_delete_nonexistent_category(self, client):
        resp = client.delete("/api/categories/nonexistent")
        assert resp.status_code == 404

    def test_update_nonexistent_category(self, client):
        resp = client.put("/api/categories/nonexistent", json={"color": "#fff"})
        assert resp.status_code == 404


class TestAutoDeleteEmptyCategory:
    """Auto-delete categories when they have zero live items."""

    def test_delete_last_item_removes_category(self, client):
        """Deleting the only item in a category auto-deletes the category."""
        client.post("/api/categories", json={"name": "solo", "color": "#111"})
        resp = client.post("/api/items", json={
            "title": "Only Item", "content": "x", "category": "solo",
        })
        item_id = resp.json()["id"]

        client.delete(f"/api/items/{item_id}")

        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "solo" not in cats

    def test_delete_item_keeps_category_with_remaining(self, client):
        """Category with remaining live items is NOT deleted."""
        client.post("/api/categories", json={"name": "shared"})
        resp1 = client.post("/api/items", json={
            "title": "Item 1", "content": "a", "category": "shared",
        })
        client.post("/api/items", json={
            "title": "Item 2", "content": "b", "category": "shared",
        })

        client.delete(f"/api/items/{resp1.json()['id']}")

        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "shared" in cats

    def test_change_category_removes_old_empty(self, client):
        """Changing an item's category auto-deletes the now-empty old category."""
        client.post("/api/categories", json={"name": "old_cat", "color": "#aaa"})
        client.post("/api/categories", json={"name": "new_cat", "color": "#bbb"})
        resp = client.post("/api/items", json={
            "title": "Mover", "content": "x", "category": "old_cat",
        })
        item_id = resp.json()["id"]

        client.put(f"/api/items/{item_id}", json={"category": "new_cat"})

        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "old_cat" not in cats
        assert "new_cat" in cats

    def test_soft_deleted_items_dont_keep_category(self, client):
        """Category with only soft-deleted items is cleaned up."""
        client.post("/api/categories", json={"name": "ghosts"})
        resp1 = client.post("/api/items", json={
            "title": "Ghost 1", "content": "a", "category": "ghosts",
        })
        resp2 = client.post("/api/items", json={
            "title": "Ghost 2", "content": "b", "category": "ghosts",
        })

        client.delete(f"/api/items/{resp1.json()['id']}")
        # After first delete, Ghost 2 still alive — category stays
        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "ghosts" in cats

        client.delete(f"/api/items/{resp2.json()['id']}")
        # Now both soft-deleted — category should be gone
        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "ghosts" not in cats

    def test_delete_removes_empty_directory(self, client, tmp_content_dir):
        """Auto-delete also removes the category subdirectory from disk."""
        cat_dir = tmp_content_dir / "cleanup"
        cat_dir.mkdir()
        client.post("/api/categories", json={"name": "cleanup"})
        resp = client.post("/api/items", json={
            "title": "Dir Item", "content": "x", "category": "cleanup",
        })
        item_id = resp.json()["id"]
        assert cat_dir.is_dir()

        client.delete(f"/api/items/{item_id}")

        assert not cat_dir.exists()

    def test_directory_kept_if_has_untracked_files(self, client, tmp_content_dir):
        """Directory is kept if it still contains files on disk."""
        cat_dir = tmp_content_dir / "hasfiles"
        cat_dir.mkdir()
        (cat_dir / "untracked.txt").write_text("not in db")
        client.post("/api/categories", json={"name": "hasfiles"})
        resp = client.post("/api/items", json={
            "title": "Tracked", "content": "x", "category": "hasfiles",
        })
        item_id = resp.json()["id"]

        client.delete(f"/api/items/{item_id}")

        # Category removed from DB but directory stays (has untracked file)
        cats = [c["name"] for c in client.get("/api/categories").json()]
        assert "hasfiles" not in cats
        assert cat_dir.is_dir()

    def test_no_cleanup_for_uncategorized(self, client):
        """Deleting an uncategorized item doesn't cause issues."""
        resp = client.post("/api/items", json={
            "title": "No Cat", "content": "x",
        })
        item_id = resp.json()["id"]

        resp = client.delete(f"/api/items/{item_id}")
        assert resp.status_code == 200


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
        assert "$BASE_PATH$" not in resp.text

    def test_serve_icon(self, client):
        resp = client.get("/icons/icon-192.png")
        assert resp.status_code == 200

    def test_serve_svg_icon(self, client, tmp_path):
        """SVG icon gets correct media type."""
        icons_dir = tmp_path / "public" / "icons"
        (icons_dir / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        resp = client.get("/icons/icon.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")

    def test_serve_ico_icon(self, client, tmp_path):
        """ICO icon gets correct media type."""
        icons_dir = tmp_path / "public" / "icons"
        (icons_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
        resp = client.get("/icons/favicon.ico")
        assert resp.status_code == 200
        assert "icon" in resp.headers["content-type"]

    def test_icon_not_found(self, client):
        resp = client.get("/icons/nonexistent.png")
        assert resp.status_code == 404

    def test_js_not_found(self, client):
        resp = client.get("/js/nonexistent.js")
        assert resp.status_code == 404


class TestNoteEdgeCases:
    def test_create_note_with_pinned(self, client):
        resp = client.post("/api/items", json={
            "title": "Pinned Note",
            "content": "pinned on create",
            "pinned": True,
        })
        assert resp.status_code == 200
        assert resp.json()["pinned"] == 1

    def test_update_note_with_new_category(self, client):
        resp = client.post("/api/items", json={"title": "Cat Note", "content": "x"})
        item_id = resp.json()["id"]

        resp = client.put(f"/api/items/{item_id}", json={"category": "newcat"})
        assert resp.status_code == 200
        assert resp.json()["category"] == "newcat"

    def test_update_nonexistent_item(self, client):
        resp = client.put("/api/items/nonexistent", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_delete_nonexistent_item(self, client):
        resp = client.delete("/api/items/nonexistent")
        assert resp.status_code == 404

    def test_toggle_pin_nonexistent(self, client):
        resp = client.patch("/api/items/nonexistent/pin")
        assert resp.status_code == 404


class TestFileEdgeCases:
    def test_upload_filename_collision(self, client, tmp_content_dir):
        """Uploading a file with the same name creates a numbered copy."""
        client.post("/api/items/upload", files={
            "file": ("dupe.txt", b"first", "text/plain"),
        })
        resp = client.post("/api/items/upload", files={
            "file": ("dupe.txt", b"second", "text/plain"),
        })
        assert resp.status_code == 200
        assert "dupe_1.txt" in resp.json()["filename"]

    def test_upload_with_pinned(self, client):
        resp = client.post("/api/items/upload", data={
            "pinned": "true",
        }, files={
            "file": ("pin.txt", b"pin me", "text/plain"),
        })
        assert resp.status_code == 200
        assert resp.json()["pinned"] == 1

    def test_download_nonexistent(self, client):
        resp = client.get("/api/items/nonexistent/download")
        assert resp.status_code == 404

    def test_download_note_item(self, client):
        """Downloading a note (not a file) returns 400."""
        resp = client.post("/api/items", json={"title": "Note", "content": "x"})
        item_id = resp.json()["id"]
        resp = client.get(f"/api/items/{item_id}/download")
        assert resp.status_code == 400

    def test_download_missing_file_on_disk(self, client, tmp_content_dir):
        """File item exists in DB but file was deleted from disk."""
        resp = client.post("/api/items/upload", files={
            "file": ("ghost.txt", b"boo", "text/plain"),
        })
        item_id = resp.json()["id"]
        filename = resp.json()["filename"]
        # Remove file from disk
        (tmp_content_dir / filename).unlink()

        resp = client.get(f"/api/items/{item_id}/download")
        assert resp.status_code == 404

    def test_share_file_collision(self, client, tmp_content_dir):
        """Sharing a file with a name that already exists creates a numbered copy."""
        # Create the first file directly on disk
        (tmp_content_dir / "collision.jpg").write_bytes(b"\xff")

        resp = client.post("/api/share", data={
            "title": "Photo",
        }, files={
            "file": ("collision.jpg", b"\xff\xd8\xff\xe0", "image/jpeg"),
        })
        assert resp.status_code == 200
        assert "collision_1.jpg" in resp.json()["filename"]


class TestRenderEndpoint:
    def test_render_note(self, client):
        resp = client.post("/api/items", json={"title": "Render Me", "content": "hello"})
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/render")
        assert resp.status_code == 200
        assert "hello" in resp.text

    def test_render_nonexistent(self, client):
        resp = client.get("/api/items/nonexistent/render")
        assert resp.status_code == 404

    def test_render_html_file(self, client, tmp_content_dir):
        (tmp_content_dir / "page.html").write_text("<h1>Hello</h1>")
        resp = client.post("/api/items/upload", files={
            "file": ("page.html", b"<h1>Hello</h1>", "text/html"),
        })
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/render")
        assert resp.status_code == 200
        assert "<h1>Hello</h1>" in resp.text

    def test_render_markdown_file(self, client, tmp_content_dir):
        (tmp_content_dir / "doc.md").write_text("# Title\n\nParagraph")
        resp = client.post("/api/items/upload", files={
            "file": ("doc.md", b"# Title\n\nParagraph", "text/markdown"),
        })
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/render")
        assert resp.status_code == 200
        # Should contain rendered HTML (either via mistune or pre-wrapped)
        assert "Title" in resp.text

    def test_render_plain_text_file(self, client, tmp_content_dir):
        (tmp_content_dir / "plain.txt").write_text("just text")
        resp = client.post("/api/items/upload", files={
            "file": ("plain.txt", b"just text", "text/plain"),
        })
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/render")
        assert resp.status_code == 200
        assert "just text" in resp.text

    def test_render_file_missing_on_disk(self, client, tmp_content_dir):
        resp = client.post("/api/items/upload", files={
            "file": ("gone.html", b"<p>gone</p>", "text/html"),
        })
        item_id = resp.json()["id"]
        filename = resp.json()["filename"]
        (tmp_content_dir / filename).unlink()

        resp = client.get(f"/api/items/{item_id}/render")
        assert resp.status_code == 404


class TestSyncEdgeCases:
    def test_sync_push_update_existing(self, client):
        """Push an update to an existing item (covers upsert update path)."""
        # Create an item first
        resp = client.post("/api/items", json={
            "title": "Original", "content": "v1",
        })
        item_id = resp.json()["id"]

        # Push an update with a newer timestamp
        resp = client.post("/api/sync/push", json={
            "items": [{
                "id": item_id,
                "type": "note",
                "title": "Updated via Sync",
                "content": "v2",
                "category": "",
                "updated_at": "2099-01-01T00:00:00Z",
            }]
        })
        assert resp.status_code == 200

        resp = client.get(f"/api/items/{item_id}")
        assert resp.json()["title"] == "Updated via Sync"
        assert resp.json()["_version"] == 2


class TestDatabaseEdgeCases:
    def test_update_item_no_valid_fields(self, client):
        """Update with no recognized fields returns the item unchanged."""
        resp = client.post("/api/items", json={"title": "Unchanged", "content": "x"})
        item_id = resp.json()["id"]

        import database
        result = database.update_item(item_id, bogus_field="nope")
        assert result is not None
        assert result["title"] == "Unchanged"
        assert result["_version"] == 1

    def test_update_nonexistent_item_db(self):
        """update_item on missing ID returns None."""
        import database
        result = database.update_item("nonexistent_id", title="nope")
        assert result is None

    def test_toggle_pin_nonexistent_db(self):
        """toggle_pin on missing ID returns None."""
        import database
        result = database.toggle_pin("nonexistent_id")
        assert result is None

    def test_update_category_no_valid_fields(self, client):
        """update_category with no recognized fields returns the category."""
        client.post("/api/categories", json={"name": "nochange", "color": "#abc"})

        import database
        result = database.update_category("nochange")
        assert result is not None
        assert result["name"] == "nochange"

    def test_rename_nonexistent_category_db(self):
        """rename_category on missing name returns None."""
        import database
        result = database.rename_category("ghost", "new_ghost")
        assert result is None


class TestImageViewing:
    """Tests for inline image viewing support."""

    def test_upload_image(self, client):
        """Image files are uploaded with correct MIME type."""
        resp = client.post("/api/items/upload", files={
            "file": ("photo.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "file"
        assert data["mime_type"] == "image/jpeg"

    def test_download_image(self, client):
        """Uploaded image can be downloaded for viewing."""
        img_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        resp = client.post("/api/items/upload", files={
            "file": ("test.png", img_data, "image/png"),
        })
        item_id = resp.json()["id"]

        resp = client.get(f"/api/items/{item_id}/download")
        assert resp.status_code == 200
        assert resp.content == img_data

    def test_image_formats(self, client):
        """Various image formats upload correctly."""
        formats = [
            ("test.jpg", "image/jpeg"),
            ("test.png", "image/png"),
            ("test.gif", "image/gif"),
            ("test.webp", "image/webp"),
            ("test.svg", "image/svg+xml"),
            ("test.bmp", "image/bmp"),
            ("test.avif", "image/avif"),
        ]
        for filename, mime in formats:
            resp = client.post("/api/items/upload", files={
                "file": (filename, b"\x00" * 10, mime),
            })
            assert resp.status_code == 200, f"Failed for {filename}"
            assert resp.json()["mime_type"] == mime

    def test_image_with_category(self, client):
        """Image upload with category works."""
        resp = client.post("/api/items/upload", data={
            "category": "photos",
        }, files={
            "file": ("sunset.jpg", b"\xff\xd8\xff\xe0", "image/jpeg"),
        })
        assert resp.status_code == 200
        assert resp.json()["category"] == "photos"


class TestWebSocket:
    def test_websocket_ping_pong(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            data = ws.receive_json()
            assert data["event"] == "pong"
