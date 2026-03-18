"""
Seed test data for Personal Share test mode.
Downloads small files from the internet and creates sample items across categories.
"""
import shutil
import urllib.request
from pathlib import Path

import config
from database import (
    init_database, create_item, create_category, update_item,
    set_meta, get_utc_now,
)


CATEGORIES = [
    {"name": "recipes", "color": "#e67e22", "sort_order": 0},
    {"name": "links", "color": "#3498db", "sort_order": 1},
    {"name": "docs", "color": "#2ecc71", "sort_order": 2},
]

DOWNLOADS = [
    {
        "url": "https://picsum.photos/400/300",
        "filename": "sample-photo.jpg",
        "mime": "image/jpeg",
        "category": "",
        "title": "Sample Photo",
        "pinned": True,
    },
]

MARKDOWN_RECIPE = """\
# Simple Pasta Aglio e Olio

Serves 2 | 20 minutes

## Ingredients
- 200g spaghetti
- 4 cloves garlic, thinly sliced
- 1/4 cup olive oil
- 1/2 tsp red pepper flakes
- Fresh parsley, chopped
- Parmesan cheese
- Salt to taste

## Instructions
1. Cook pasta in salted water until al dente. Reserve 1/2 cup pasta water.
2. Heat olive oil in a pan over medium heat. Add garlic and red pepper flakes.
3. Cook until garlic is golden (not brown), about 2 minutes.
4. Add drained pasta and a splash of pasta water. Toss to coat.
5. Top with parsley and parmesan.
"""

HTML_DOC = """\
<!DOCTYPE html>
<html>
<head><title>Quick Reference</title>
<style>
body { font-family: system-ui; max-width: 600px; margin: 2rem auto; padding: 0 1rem; }
h1 { color: #2c3e50; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #f5f5f5; }
code { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; }
</style>
</head>
<body>
<h1>HTTP Status Codes</h1>
<table>
<tr><th>Code</th><th>Meaning</th></tr>
<tr><td><code>200</code></td><td>OK</td></tr>
<tr><td><code>201</code></td><td>Created</td></tr>
<tr><td><code>301</code></td><td>Moved Permanently</td></tr>
<tr><td><code>400</code></td><td>Bad Request</td></tr>
<tr><td><code>404</code></td><td>Not Found</td></tr>
<tr><td><code>500</code></td><td>Internal Server Error</td></tr>
</table>
</body>
</html>
"""


JSON_SAMPLE = """\
{
  "name": "Personal Share",
  "version": "1.0.0",
  "description": "Cross-device file and note sharing",
  "dependencies": {
    "fastapi": ">=0.100",
    "uvicorn": ">=0.20",
    "watchdog": ">=3.0"
  },
  "features": ["offline-sync", "pwa", "websocket", "file-watcher"],
  "config": {
    "port": 9100,
    "database": "data/share.db",
    "debug": false
  }
}
"""

PYTHON_SAMPLE = """\
#!/usr/bin/env python3
\"\"\"Example: Fibonacci with memoization.\"\"\"
from functools import lru_cache
from typing import Generator


@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def fib_sequence(limit: int) -> Generator[int, None, None]:
    \"\"\"Yield Fibonacci numbers up to *limit*.\"\"\"
    i = 0
    while True:
        val = fibonacci(i)
        if val > limit:
            break
        yield val
        i += 1


if __name__ == "__main__":
    for num in fib_sequence(1000):
        print(num, end=" ")
    print()
"""


def download_file(url: str, dest: Path) -> int:
    """Download a file, return size in bytes."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalShare/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            dest.write_bytes(data)
            return len(data)
    except Exception as e:
        print(f"  Warning: could not download {url}: {e}")
        # Write a placeholder
        placeholder = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        dest.write_bytes(placeholder)
        return len(placeholder)


def seed():
    print("Seeding test data...")

    content_dir = config.CONTENT_DIR
    db_path = config.DB_PATH

    # Clean content directory and database for fresh seed
    if content_dir.exists():
        shutil.rmtree(content_dir)
    content_dir.mkdir(parents=True)

    if db_path.exists():
        db_path.unlink()

    init_database()

    # Create categories
    for cat in CATEGORIES:
        create_category(cat["name"], cat["color"], cat["sort_order"])
        (content_dir / cat["name"]).mkdir(exist_ok=True)
        print(f"  Category: {cat['name']}")

    # Markdown recipe file
    recipe_path = content_dir / "recipes" / "pasta-aglio-e-olio.md"
    recipe_path.write_text(MARKDOWN_RECIPE)
    create_item(
        item_type="file",
        title="Pasta Aglio e Olio",
        category="recipes",
        filename="recipes/pasta-aglio-e-olio.md",
        mime_type="text/markdown",
        size_bytes=len(MARKDOWN_RECIPE.encode()),
        source="web",
    )
    print("  File: pasta-aglio-e-olio.md (recipes)")

    # HTML doc
    html_path = content_dir / "docs" / "http-status-codes.html"
    html_path.write_text(HTML_DOC)
    create_item(
        item_type="file",
        title="HTTP Status Codes",
        category="docs",
        filename="docs/http-status-codes.html",
        mime_type="text/html",
        size_bytes=len(HTML_DOC.encode()),
        source="web",
    )
    print("  File: http-status-codes.html (docs)")

    # Plain text file
    changelog = "v1.0 - Initial release\nv1.1 - Added offline sync\nv1.2 - Category management\n"
    txt_path = content_dir / "docs" / "changelog.txt"
    txt_path.write_text(changelog)
    create_item(
        item_type="file",
        title="Changelog",
        category="docs",
        filename="docs/changelog.txt",
        mime_type="text/plain",
        size_bytes=len(changelog.encode()),
        source="web",
    )
    print("  File: changelog.txt (docs)")

    # JSON sample file
    json_path = content_dir / "docs" / "sample-config.json"
    json_path.write_text(JSON_SAMPLE)
    create_item(
        item_type="file",
        title="Sample Config",
        category="docs",
        filename="docs/sample-config.json",
        mime_type="application/json",
        size_bytes=len(JSON_SAMPLE.encode()),
        source="web",
    )
    print("  File: sample-config.json (docs)")

    # Python sample file
    py_path = content_dir / "docs" / "fibonacci.py"
    py_path.write_text(PYTHON_SAMPLE)
    create_item(
        item_type="file",
        title="Fibonacci Example",
        category="docs",
        filename="docs/fibonacci.py",
        mime_type="text/x-python",
        size_bytes=len(PYTHON_SAMPLE.encode()),
        source="web",
    )
    print("  File: fibonacci.py (docs)")

    # Notes with URLs (links category)
    create_item(
        item_type="note",
        title="Python Docs",
        content="Official Python documentation\nhttps://docs.python.org/3/",
        category="links",
        source="web",
    )
    create_item(
        item_type="note",
        title="FastAPI Tutorial",
        content="Great intro to FastAPI\nhttps://fastapi.tiangolo.com/tutorial/",
        category="links",
        source="web",
    )
    create_item(
        item_type="note",
        title="MDN Web Docs",
        content="Web development reference\nhttps://developer.mozilla.org/",
        category="links",
        source="web",
    )
    print("  Notes: 3 link notes")

    # Uncategorized note
    create_item(
        item_type="note",
        title="Quick reminder",
        content="Remember to check the sync status indicator after the next deploy.",
        source="web",
    )
    print("  Note: uncategorized reminder")

    # Download image
    for dl in DOWNLOADS:
        dest_dir = content_dir / dl["category"] if dl["category"] else content_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / dl["filename"]
        rel = dl["filename"] if not dl["category"] else f"{dl['category']}/{dl['filename']}"

        print(f"  Downloading: {dl['filename']}...")
        size = download_file(dl["url"], dest)

        item = create_item(
            item_type="file",
            title=dl["title"],
            category=dl["category"],
            filename=rel,
            mime_type=dl["mime"],
            size_bytes=size,
            source="web",
        )
        if dl.get("pinned"):
            update_item(item["id"], pinned=1)
            print(f"    Pinned: {dl['title']}")

    set_meta("last_sync_time", get_utc_now())
    print("Done. Test data seeded.")


if __name__ == "__main__":
    seed()
