"""
Shared fixtures for Personal Share tests.
Provides isolated temp database and test client.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC_DIR))


@pytest.fixture(scope="function")
def tmp_db(tmp_path):
    return tmp_path / "test_share.db"


@pytest.fixture(scope="function")
def tmp_content_dir(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    return content


@pytest.fixture(scope="function")
def test_app(tmp_path, tmp_db, tmp_content_dir, monkeypatch):
    # Create minimal public directory
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    (public_dir / "index.html").write_text(
        '<html><head>'
        '<link rel="stylesheet" href="/styles.css">'
        '<script src="/js/app.js"></script>'
        '</head><body>Share</body></html>'
    )
    (public_dir / "styles.css").write_text("body { margin: 0; }")
    js_dir = public_dir / "js"
    js_dir.mkdir()
    (js_dir / "app.js").write_text("console.log('test');")
    (public_dir / "manifest.json").write_text('{"name":"Share","start_url":"/","display":"standalone"}')
    (public_dir / "sw.js").write_text("// sw stub $SERVER_VERSION$")
    icons_dir = public_dir / "icons"
    icons_dir.mkdir()

    import struct
    import zlib
    def _make_png():
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = b'\x00\x00\x00\x00'
        idat_data = zlib.compress(raw)
        idat_crc = zlib.crc32(b'IDAT' + idat_data) & 0xffffffff
        idat = struct.pack('>I', len(idat_data)) + b'IDAT' + idat_data + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND') & 0xffffffff
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        return sig + ihdr + idat + iend
    (icons_dir / "icon-192.png").write_bytes(_make_png())

    import config
    monkeypatch.setattr(config, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(config, "CONTENT_DIR", tmp_content_dir)
    monkeypatch.setattr(config, "DB_PATH", tmp_db)

    import database
    database.set_db_path(tmp_db)
    database.init_database()

    import server
    monkeypatch.setattr(server, "PUBLIC_DIR", public_dir)

    # Patch CONTENT_DIR in items module (captured at import time)
    import modules.items as items_mod
    monkeypatch.setattr(items_mod, "CONTENT_DIR", tmp_content_dir)

    yield server.app


@pytest.fixture(scope="function")
def client(test_app):
    with TestClient(test_app) as c:
        yield c
