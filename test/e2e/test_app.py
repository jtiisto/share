"""
E2E tests for Personal Share using Playwright.
Tests the full app lifecycle: create notes, upload files, browse, pin, categories.

Requires: pip install pytest-playwright && playwright install chromium
Run: pytest test/e2e/ -v
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Check if playwright is available
try:
    from playwright.sync_api import sync_playwright, expect
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed"),
]

_SRC_DIR = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(_SRC_DIR))

SERVER_PORT = 9199
BASE_URL = f"http://localhost:{SERVER_PORT}/share"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Start a real server instance for E2E testing."""
    tmp = tmp_path_factory.mktemp("e2e")
    db_path = tmp / "test.db"
    content_dir = tmp / "content"
    content_dir.mkdir()

    import os
    env = os.environ.copy()
    env["SHARE_DB_PATH"] = str(db_path)

    proc = subprocess.Popen(
        [sys.executable, str(_SRC_DIR / "server.py"), "--port", str(SERVER_PORT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    for _ in range(20):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{SERVER_PORT}/share/manifest.json", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("Server did not start in time")

    yield proc

    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def browser_context(server):
    """Create a browser context for tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},  # Mobile viewport
        )
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Create a fresh page for each test."""
    p = browser_context.new_page()
    p.goto(BASE_URL)
    p.wait_for_load_state("networkidle")
    yield p
    p.close()


class TestAppShell:
    def test_page_loads(self, page):
        expect(page).to_have_title("Share")

    def test_has_bottom_nav(self, page):
        nav = page.locator(".nav-bar")
        expect(nav).to_be_visible()
        expect(page.locator(".nav-btn")).to_have_count(2)

    def test_nav_switching(self, page):
        # Start on files
        expect(page.locator(".header-title")).to_have_text("Files")

        # Switch to notes
        page.locator(".nav-btn", has_text="Notes").click()
        expect(page.locator(".header-title")).to_have_text("Notes")

        # Switch back to files
        page.locator(".nav-btn", has_text="Files").click()
        expect(page.locator(".header-title")).to_have_text("Files")

    def test_fab_opens_add_sheet(self, page):
        page.locator(".fab").click()
        expect(page.locator(".sheet")).to_be_visible()
        expect(page.locator(".sheet-title")).to_contain_text("Add")

    def test_sync_indicator_visible(self, page):
        expect(page.locator(".sync-btn")).to_be_visible()


class TestNotes:
    def test_create_note(self, page):
        # Switch to notes view
        page.locator(".nav-btn", has_text="Notes").click()

        # Open add sheet
        page.locator(".fab").click()
        page.wait_for_selector(".sheet")

        # Ensure note tab is selected
        page.locator(".category-chip", has_text="Note").click()

        # Fill in note
        page.locator("input.form-input").first.fill("Test Note")
        page.locator("textarea.form-textarea").fill("Hello from E2E test")

        # Create
        page.locator("button.btn-primary", has_text="Create").click()

        # Sheet should close and note should appear
        page.wait_for_selector(".sheet", state="hidden")
        expect(page.locator(".item-card-title", has_text="Test Note")).to_be_visible()

    def test_note_shows_preview(self, page):
        # Create a note first
        page.locator(".nav-btn", has_text="Notes").click()
        page.locator(".fab").click()
        page.wait_for_selector(".sheet")
        page.locator(".category-chip", has_text="Note").click()
        page.locator("input.form-input").first.fill("Preview Note")
        page.locator("textarea.form-textarea").fill("This content should show as preview")
        page.locator("button.btn-primary", has_text="Create").click()
        page.wait_for_selector(".sheet", state="hidden")

        expect(page.locator(".item-card-preview", has_text="This content")).to_be_visible()


class TestFiles:
    def test_upload_file(self, page):
        # Open add sheet
        page.locator(".fab").click()
        page.wait_for_selector(".sheet")

        # Switch to file tab
        page.locator(".category-chip", has_text="File").click()

        # Upload a file
        page.locator("input[type='file']").set_input_files({
            "name": "test.txt",
            "mimeType": "text/plain",
            "buffer": b"Hello from E2E",
        })

        # Should close and file should appear
        page.wait_for_selector(".sheet", state="hidden", timeout=5000)
        expect(page.locator(".item-card-title", has_text="test.txt")).to_be_visible()


class TestCategories:
    def test_category_filter_visible(self, page):
        expect(page.locator(".category-filter")).to_be_visible()
        expect(page.locator(".category-chip", has_text="All")).to_be_visible()

    def test_manage_categories_opens(self, page):
        page.locator(".category-chip", has_text="Manage").click()
        expect(page.locator(".sheet-title", has_text="Manage Categories")).to_be_visible()
