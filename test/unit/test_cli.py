"""
CLI tests for bin/share-cli.sh.

Drives the real script via subprocess against an isolated, unseeded server on an
ephemeral port (started with SHARE_TEST_* env overrides). These guard the CLI's
observable behavior — most importantly that an ambiguous `delete` aborts without
deleting anything, the safety property the personal-delete skill relies on — and
the server-location rules (--url flag > $SHARE_URL > localhost default) that let
the CLI run on a different machine from the server.
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


def base_url(port):
    return f"http://127.0.0.1:{port}"


def run_raw(argv, env_extra=None, **kwargs):
    """Run `share-cli.sh <argv...>` verbatim with an optional env overlay.

    $SHARE_URL is scrubbed from the inherited environment so a developer
    shell that exports it can't leak into the resolution-order assertions.
    """
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env.pop("SHARE_URL", None)
    env.update(env_extra or {})
    cmd = ["bash", str(CLI), *[str(a) for a in argv]]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, **kwargs)


def run_cli(port, subcmd, *args, **kwargs):
    """Run `share-cli.sh <subcmd> --url http://127.0.0.1:<port> <args...>`.

    --url is placed right after the subcommand so it precedes any positional
    content (the `share` subcommand stops option parsing at the first positional).
    """
    return run_raw([subcmd, "--url", base_url(port), *args], **kwargs)


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


# ---------------------------------------------------------------------------
# Server location: --url flag > $SHARE_URL > http://localhost:9100


def test_url_env_round_trip(cli_server, tmp_path):
    """With no --url flag the CLI follows $SHARE_URL — the remote-client setup."""
    port = cli_server
    env = {"SHARE_URL": base_url(port)}

    r = run_raw(["share", "-t", "Env Url Note", "via env"], env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "Shared:" in r.stdout

    r = run_raw(["list"], env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "Env Url Note" in r.stdout

    out = tmp_path / "env"
    r = run_raw(["fetch", "-o", str(out), "Env Url Note"], env_extra=env)
    assert r.returncode == 0, r.stderr
    assert (out / "Env Url Note.md").read_text() == "via env\n"

    r = run_raw(["delete", "Env Url Note"], env_extra=env)
    assert r.returncode == 0, r.stderr


def test_url_flag_beats_env(cli_server):
    port = cli_server
    dead = "http://127.0.0.1:1"  # nothing listens on port 1

    # env points at a dead server, flag at the live one -> flag wins
    r = run_raw(["list", "--url", base_url(port)], env_extra={"SHARE_URL": dead})
    assert r.returncode == 0, r.stderr

    # env points at the live server, flag at the dead one -> flag still wins
    r = run_raw(["list", "--url", dead], env_extra={"SHARE_URL": base_url(port)})
    assert r.returncode == 1
    assert f"cannot reach Personal Share server at {dead}" in r.stderr


def test_trailing_slash_tolerated(cli_server):
    r = run_raw(["list", "--url", base_url(cli_server) + "/"])
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("bad", [
    "127.0.0.1:9100",                 # no scheme
    "ftp://127.0.0.1:9100",           # wrong scheme
    "http://127.0.0.1:9100/share",    # path component (CLI appends /share/api itself)
    "http://127.0.0.1:9100//",        # more than one trailing slash
    "http://127.0.0.1:9100?x=y",      # query string
    "http://127.0.0.1:9100#frag",     # fragment
    "http://:9100",                   # missing host
    "http://127.0.0.1:abc",           # non-numeric port
    "http://user:pw@127.0.0.1:9100",  # credentials
])
def test_malformed_url_exits_2(bad):
    r = run_raw(["list", "--url", bad])
    assert r.returncode == 2
    assert "Invalid server URL" in r.stderr

    r = run_raw(["list"], env_extra={"SHARE_URL": bad})
    assert r.returncode == 2
    assert "Invalid server URL" in r.stderr


def test_ipv6_literal_host_accepted():
    """A bracketed IPv6 host passes validation; the run fails only because
    nothing listens on [::1]:1, which proves it got as far as curl."""
    r = run_raw(["list", "--url", "http://[::1]:1"])
    assert r.returncode == 1
    assert "Invalid server URL" not in r.stderr
    assert "cannot reach Personal Share server at http://[::1]:1" in r.stderr


def test_empty_url_flag_is_usage_error():
    """An explicit `--url ""` must not silently fall back to $SHARE_URL — that
    could send an upload or a delete to a server the user did not name."""
    r = run_raw(["list", "--url", ""], env_extra={"SHARE_URL": "http://127.0.0.1:1"})
    assert r.returncode == 1
    assert "requires a non-empty value" in r.stderr
    assert "cannot reach" not in r.stderr


@pytest.mark.parametrize("flag", ["-p", "--port"])
@pytest.mark.parametrize("subcmd", ["share", "fetch", "list", "delete"])
def test_port_flag_rejected(subcmd, flag):
    """-p/--port was removed with no shim: the port lives in the URL."""
    r = run_raw([subcmd, flag, "9100", "x"])
    assert r.returncode != 0
    assert f"Unknown option: {flag}" in r.stderr


def test_directory_argument_rejected(cli_server, tmp_path):
    """A directory is neither uploaded nor turned into a note whose body is the path."""
    port = cli_server
    d = tmp_path / "some_dir_zzz"
    d.mkdir()

    r = run_cli(port, "share", str(d))
    assert r.returncode == 1
    assert "directories cannot be shared" in r.stderr
    assert "some_dir_zzz" not in listing(port)
