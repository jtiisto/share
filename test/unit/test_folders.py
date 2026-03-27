"""Unit tests for shared folders API."""
import os
import pytest


class TestShareFolder:
    def test_share_folder(self, client, tmp_path):
        """Share a directory creates symlink and DB entry."""
        target = tmp_path / "mydir"
        target.mkdir()
        (target / "file1.txt").write_text("hello")
        (target / "file2.py").write_text("print('hi')")

        resp = client.post("/api/folders", json={"target_path": str(target)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "mydir"
        assert data["target_path"] == str(target)
        assert data["file_count"] == 2

    def test_share_nonexistent_directory(self, client):
        resp = client.post("/api/folders", json={"target_path": "/nonexistent/path"})
        assert resp.status_code == 400

    def test_share_file_not_directory(self, client, tmp_path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("nope")
        resp = client.post("/api/folders", json={"target_path": str(f)})
        assert resp.status_code == 400

    def test_share_already_shared(self, client, tmp_path):
        target = tmp_path / "shared_once"
        target.mkdir()
        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.post("/api/folders", json={"target_path": str(target)})
        assert resp.status_code == 409

    def test_list_folders(self, client, tmp_path):
        d1 = tmp_path / "dir1"
        d1.mkdir()
        d2 = tmp_path / "dir2"
        d2.mkdir()

        client.post("/api/folders", json={"target_path": str(d1)})
        client.post("/api/folders", json={"target_path": str(d2)})

        resp = client.get("/api/folders")
        assert resp.status_code == 200
        folders = resp.json()
        names = [f["name"] for f in folders]
        assert "dir1" in names
        assert "dir2" in names

    def test_unshare_folder(self, client, tmp_path, tmp_folders_dir):
        target = tmp_path / "removeme"
        target.mkdir()
        resp = client.post("/api/folders", json={"target_path": str(target)})
        name = resp.json()["name"]

        # Symlink should exist
        assert (tmp_folders_dir / name).is_symlink()

        resp = client.delete(f"/api/folders/{name}")
        assert resp.status_code == 200

        # Symlink should be gone
        assert not (tmp_folders_dir / name).exists()

        # Original directory should still exist
        assert target.is_dir()

        # Should be gone from list
        resp = client.get("/api/folders")
        names = [f["name"] for f in resp.json()]
        assert name not in names

    def test_unshare_nonexistent(self, client):
        resp = client.delete("/api/folders/nonexistent")
        assert resp.status_code == 404


class TestNameDeduplication:
    def test_no_conflict(self, client, tmp_path):
        target = tmp_path / "unique_name"
        target.mkdir()
        resp = client.post("/api/folders", json={"target_path": str(target)})
        assert resp.json()["name"] == "unique_name"

    def test_conflict_prepends_parent(self, client, tmp_path, tmp_folders_dir):
        # Create first "projects"
        t1 = tmp_path / "dev" / "projects"
        t1.mkdir(parents=True)
        resp = client.post("/api/folders", json={"target_path": str(t1)})
        assert resp.json()["name"] == "projects"

        # Create second "projects" — should prepend parent
        t2 = tmp_path / "backup" / "projects"
        t2.mkdir(parents=True)
        resp = client.post("/api/folders", json={"target_path": str(t2)})
        name = resp.json()["name"]
        assert name != "projects"
        assert "projects" in name


class TestFolderContents:
    def test_list_files(self, client, tmp_path):
        target = tmp_path / "filedir"
        target.mkdir()
        (target / "readme.md").write_text("# Hello")
        (target / "script.py").write_text("print('hi')")
        (target / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (target / ".hidden").write_text("hidden file")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/filedir")
        assert resp.status_code == 200
        files = resp.json()
        names = [f["name"] for f in files]
        # Should include visible files, not hidden
        assert "readme.md" in names
        assert "script.py" in names
        assert "photo.jpg" in names
        assert ".hidden" not in names

    def test_list_files_nonexistent_folder(self, client):
        resp = client.get("/api/folders/nonexistent")
        assert resp.status_code == 404

    def test_file_viewable_flag(self, client, tmp_path):
        target = tmp_path / "typedir"
        target.mkdir()
        (target / "code.py").write_text("pass")
        (target / "image.png").write_bytes(b"\x89PNG")
        (target / "binary.exe").write_bytes(b"\x00\x00")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/typedir")
        files = {f["name"]: f for f in resp.json()}
        assert files["code.py"]["viewable"] is True
        assert files["image.png"]["viewable"] is True
        assert files["binary.exe"]["viewable"] is False

    def test_download_file(self, client, tmp_path):
        target = tmp_path / "dldir"
        target.mkdir()
        (target / "data.txt").write_text("file content")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/dldir/files/data.txt")
        assert resp.status_code == 200
        assert resp.content == b"file content"

    def test_download_nonexistent_file(self, client, tmp_path):
        target = tmp_path / "emptydir"
        target.mkdir()
        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/emptydir/files/nope.txt")
        assert resp.status_code == 404

    def test_render_markdown_file(self, client, tmp_path):
        target = tmp_path / "renderdir"
        target.mkdir()
        (target / "doc.md").write_text("# Hello\n\nWorld")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/renderdir/files/doc.md/render")
        assert resp.status_code == 200
        assert "Hello" in resp.text

    def test_render_html_file(self, client, tmp_path):
        target = tmp_path / "htmldir"
        target.mkdir()
        (target / "page.html").write_text("<h1>Test</h1>")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/htmldir/files/page.html/render")
        assert resp.status_code == 200
        assert "<h1>Test</h1>" in resp.text

    def test_render_code_file(self, client, tmp_path):
        target = tmp_path / "codedir"
        target.mkdir()
        (target / "app.py").write_text("print('hello')")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/codedir/files/app.py/render")
        assert resp.status_code == 200
        assert "print" in resp.text

    def test_render_image_file(self, client, tmp_path):
        target = tmp_path / "imgdir"
        target.mkdir()
        (target / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/imgdir/files/photo.jpg/render")
        assert resp.status_code == 200


class TestPathTraversal:
    def test_reject_dotdot_in_filename(self, client, tmp_path):
        """Path traversal via encoded slashes is rejected (404 from routing or 400 from validation)."""
        target = tmp_path / "safedir"
        target.mkdir()
        (target / "ok.txt").write_text("fine")

        client.post("/api/folders", json={"target_path": str(target)})

        # FastAPI path routing rejects encoded slashes with 404
        resp = client.get("/api/folders/safedir/files/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)

    def test_reject_slash_in_filename(self, client, tmp_path):
        target = tmp_path / "safedir2"
        target.mkdir()

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/safedir2/files/sub%2Ffile.txt")
        assert resp.status_code in (400, 404)

    def test_reject_dotdot_in_render(self, client, tmp_path):
        target = tmp_path / "safedir3"
        target.mkdir()

        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/safedir3/files/..%2F..%2Fetc%2Fpasswd/render")
        assert resp.status_code in (400, 404)

    def test_reject_dotdot_plain(self, client, tmp_path):
        """Direct dotdot in filename is caught by validation."""
        target = tmp_path / "safedir4"
        target.mkdir()
        client.post("/api/folders", json={"target_path": str(target)})

        resp = client.get("/api/folders/safedir4/files/..passwd")
        assert resp.status_code in (400, 404)


class TestDatabaseFolderCRUD:
    def test_create_and_get(self, client, tmp_path):
        """Direct database operations for shared folders."""
        import database
        target = tmp_path / "dbtest"
        target.mkdir()

        folder = database.create_shared_folder("testfolder", str(target), 5)
        assert folder["name"] == "testfolder"
        assert folder["file_count"] == 5

        got = database.get_shared_folder("testfolder")
        assert got is not None
        assert got["target_path"] == str(target)

    def test_update_file_count(self, client, tmp_path):
        import database
        target = tmp_path / "updatetest"
        target.mkdir()

        database.create_shared_folder("countfolder", str(target), 0)
        updated = database.update_shared_folder("countfolder", file_count=10)
        assert updated["file_count"] == 10

    def test_delete_folder(self, client, tmp_path):
        import database
        target = tmp_path / "deltest"
        target.mkdir()

        database.create_shared_folder("delfolder", str(target))
        assert database.delete_shared_folder("delfolder") is True
        assert database.get_shared_folder("delfolder") is None

    def test_exists_by_target(self, client, tmp_path):
        import database
        target = tmp_path / "existtest"
        target.mkdir()

        assert database.shared_folder_exists_by_target(str(target)) is False
        database.create_shared_folder("existfolder", str(target))
        assert database.shared_folder_exists_by_target(str(target)) is True

    def test_list_shared_folders(self, client, tmp_path):
        import database
        t1 = tmp_path / "list1"
        t1.mkdir()
        t2 = tmp_path / "list2"
        t2.mkdir()

        database.create_shared_folder("folder_a", str(t1))
        database.create_shared_folder("folder_b", str(t2))
        folders = database.list_shared_folders()
        names = [f["name"] for f in folders]
        assert "folder_a" in names
        assert "folder_b" in names
