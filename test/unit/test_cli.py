"""
CLI tests for bin/share-cli.sh.

Drives the real script via subprocess against an isolated, unseeded server on an
ephemeral port (started with SHARE_TEST_* env overrides). These guard the CLI's
observable behavior — most importantly that an ambiguous `delete` aborts without
deleting anything, the safety property the personal-delete skill relies on.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
CLI = PROJECT_ROOT / "bin" / "share-cli.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or not CLI.exists(),
    reason="bash or share-cli.sh not available",
)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def cli_server(tmp_path_factory):
    """An isolated, empty Personal Share server on an ephemeral port."""
    tmp = tmp_path_factory.mktemp("cli")
    port = _free_port()
    log = open(tmp / "server.log", "wb")

    env = dict(os.environ)
    env.update({
        "SHARE_TEST_DB": str(tmp / "cli.db"),
        "SHARE_TEST_CONTENT": str(tmp / "content"),
        "SHARE_TEST_FOLDERS": str(tmp / "folders"),
        "SHARE_TEST_SEED": "0",        # start empty for deterministic counts
        "PYTHONUTF8": "1",             # locale-independent unicode handling
        "PYTHONIOENCODING": "utf-8",
    })

    proc = subprocess.Popen(
        [sys.executable, str(SRC / "server.py"), "--test", "--port", str(port)],
        cwd=str(PROJECT_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )

    base = f"http://127.0.0.1:{port}/share/api/items"
    deadline = time.time() + 30
    try:
        while True:
            if proc.poll() is not None:
                raise RuntimeError(
                    "server exited early:\n" + (tmp / "server.log").read_text(errors="replace")
                )
            try:
                with urllib.request.urlopen(base, timeout=1) as r:
                    if r.status == 200:
                        break
            except Exception:
                if time.time() > deadline:
                    raise RuntimeError("server did not become ready in time")
                time.sleep(0.3)
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def run_cli(port, subcmd, *args, **kwargs):
    """Run `share-cli.sh <subcmd> -p <port> <args...>`.

    -p is placed right after the subcommand so it precedes any positional
    content (the `share` subcommand stops option parsing at the first positional).
    """
    cmd = ["bash", str(CLI), subcmd, "-p", str(port), *[str(a) for a in args]]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, **kwargs)


def listing(port, *extra):
    r = run_cli(port, "list", *extra)
    assert r.returncode == 0, r.stderr
    return r.stdout


# ---------------------------------------------------------------------------


def test_share_list_fetch_roundtrip(cli_server, tmp_path):
    port = cli_server
    content = "hello world\nsecond line"

    r = run_cli(port, "share", "-t", "Round Trip Note", content)
    assert r.returncode == 0, r.stderr
    assert "Shared:" in r.stdout

    assert "Round Trip Note" in listing(port, "--type", "note")

    out = tmp_path / "out"
    r = run_cli(port, "fetch", "-o", str(out), "Round Trip Note")
    assert r.returncode == 0, r.stderr
    assert (out / "Round Trip Note.md").read_text() == content + "\n"

    run_cli(port, "delete", "Round Trip Note")


def test_file_fetch_preserves_name_and_dedupes(cli_server, tmp_path):
    port = cli_server
    src = tmp_path / "report.txt"
    src.write_text("FILE BODY")

    r = run_cli(port, "share", "-t", "My File", str(src))
    assert r.returncode == 0, r.stderr
    assert "Uploaded:" in r.stdout

    out = tmp_path / "dl"
    r1 = run_cli(port, "fetch", "-o", str(out), "My File")
    assert r1.returncode == 0, r1.stderr
    assert (out / "report.txt").read_text() == "FILE BODY"

    # Second fetch to the same dir must not clobber — gets a _1 suffix.
    r2 = run_cli(port, "fetch", "-o", str(out), "My File")
    assert r2.returncode == 0, r2.stderr
    assert (out / "report_1.txt").exists()

    run_cli(port, "delete", "My File")


def test_delete_unique_removes_item(cli_server):
    port = cli_server
    run_cli(port, "share", "-t", "DeleteMe Unique", "x")

    r = run_cli(port, "delete", "DeleteMe Unique")
    assert r.returncode == 0, r.stderr
    assert "Deleted:" in r.stdout
    assert "DeleteMe Unique" not in listing(port)


def test_ambiguous_delete_aborts_and_keeps_items(cli_server):
    """Safety property the personal-delete skill depends on — must never regress."""
    port = cli_server
    run_cli(port, "share", "-t", "Ambig Report One", "a")
    run_cli(port, "share", "-t", "Ambig Report Two", "b")

    r = run_cli(port, "delete", "Ambig Report")
    assert r.returncode == 1
    assert "Ambiguous" in r.stderr

    both = listing(port)
    assert "Ambig Report One" in both
    assert "Ambig Report Two" in both

    run_cli(port, "delete", "Ambig Report One")
    run_cli(port, "delete", "Ambig Report Two")


def test_zero_match_delete_and_fetch_have_no_side_effects(cli_server, tmp_path):
    port = cli_server
    # A decoy so the server is non-empty — exercises the title-no-match path
    # and lets us assert the unrelated item is untouched.
    run_cli(port, "share", "-t", "Decoy Keep Me", "keep")

    r = run_cli(port, "delete", "no-such-item-zzz")
    assert r.returncode == 1
    assert "No items matching" in r.stderr

    out = tmp_path / "z"
    r2 = run_cli(port, "fetch", "-o", str(out), "no-such-item-zzz")
    assert r2.returncode == 1
    # nothing downloaded
    assert not out.exists() or not any(out.iterdir())

    # the unrelated item was not touched
    assert "Decoy Keep Me" in listing(port)
    run_cli(port, "delete", "Decoy Keep Me")


def test_special_title_survives_escape_roundtrip(cli_server, tmp_path):
    port = cli_server
    title = 'Wéird "quote"/slash: ✓ café'
    content = "body"

    r = run_cli(port, "share", "-t", title, content)
    assert r.returncode == 0, r.stderr

    assert "Wéird" in listing(port, "--type", "note")

    out = tmp_path / "s"
    r2 = run_cli(port, "fetch", "-o", str(out), "café")
    assert r2.returncode == 0, r2.stderr
    md = list(out.glob("*.md"))
    assert len(md) == 1
    assert md[0].read_text() == content + "\n"

    run_cli(port, "delete", "café")
