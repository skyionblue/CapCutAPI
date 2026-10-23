"""Tests for save_draft's synchronous and background modes.

Saving downloads every remote asset a draft references, so a large project could block an HTTP
client or an MCP call until it timed out. The background path existed but was commented out
(save_draft_impl.py:277-282), which is why query_draft_status described itself as "mostly a
safety net".

`wait` defaults to True, so these tests also pin down that existing callers keep the
synchronous result they depend on.
"""

import threading
import time

import pytest

import save_draft_impl as sdi
import save_task_cache
from save_draft_impl import save_draft_impl


@pytest.fixture(autouse=True)
def clean_tasks():
    save_task_cache.DRAFT_TASKS.clear()
    yield
    save_task_cache.DRAFT_TASKS.clear()


@pytest.fixture
def fake_save(monkeypatch):
    """Stand in for the real save, which downloads assets and writes a draft folder."""
    calls = {"count": 0, "thread": None, "started": threading.Event(), "release": threading.Event()}

    def configure(succeed=True, block=False, url="https://example.invalid/draft.zip"):
        def fake(draft_id, draft_folder, task_id):
            calls["count"] += 1
            calls["thread"] = threading.current_thread().name
            calls["started"].set()
            if block:
                calls["release"].wait(timeout=5)
            if succeed:
                save_task_cache.update_task_field(task_id, "status", "completed")
                return url
            save_task_cache.update_task_field(task_id, "status", "failed")
            return ""
        monkeypatch.setattr(sdi, "save_draft_background", fake)
        return calls
    return configure


# --------------------------------------------------------------- default stays synchronous

def test_default_blocks_and_returns_the_draft_url(fake_save):
    calls = fake_save(succeed=True)
    result = save_draft_impl("d1")
    assert result["success"] is True
    assert result["draft_url"] == "https://example.invalid/draft.zip"
    assert calls["count"] == 1, "the save must have already run before returning"


def test_default_runs_on_the_calling_thread(fake_save):
    calls = fake_save(succeed=True)
    save_draft_impl("d1")
    assert calls["thread"] == threading.current_thread().name


# --------------------------------------------------------------- background mode

def test_wait_false_returns_a_task_id_without_blocking(fake_save):
    calls = fake_save(succeed=True, block=True)
    started = time.monotonic()
    result = save_draft_impl("d1", wait=False)
    elapsed = time.monotonic() - started

    assert result["success"] is True
    assert result["task_id"] == "d1"
    assert "draft_url" not in result, "an async save cannot know the url yet"
    assert elapsed < 2.0, "wait=False must not block on the save"
    assert "query_draft_status" in result["message"], "the caller must be told to poll"

    calls["release"].set()


def test_wait_false_runs_the_save_on_another_thread(fake_save):
    calls = fake_save(succeed=True)
    save_draft_impl("d1", wait=False)
    assert calls["started"].wait(timeout=5)
    assert calls["thread"] != threading.current_thread().name
    assert calls["thread"].startswith("save-draft-")


def test_background_save_reaches_completed(fake_save):
    fake_save(succeed=True)
    save_draft_impl("d1", wait=False)
    for _ in range(50):
        if save_task_cache.get_task_status("d1").get("status") == "completed":
            break
        time.sleep(0.05)
    assert save_task_cache.get_task_status("d1")["status"] == "completed"


# --------------------------------------------------------------- the post-save step

def test_on_complete_runs_after_a_successful_save_and_records_local_path(fake_save):
    fake_save(succeed=True)
    seen = []

    def place(draft_id):
        seen.append(draft_id)
        return "/drafts/d1"

    save_draft_impl("d1", on_complete=place)
    assert seen == ["d1"]
    assert save_task_cache.get_task_status("d1")["local_path"] == "/drafts/d1"


def test_on_complete_does_not_run_when_the_save_failed(fake_save):
    """Placing a draft folder that was never produced would be worse than doing nothing."""
    fake_save(succeed=False)
    seen = []
    save_draft_impl("d1", on_complete=lambda draft_id: seen.append(draft_id))
    assert seen == []


def test_on_complete_failure_does_not_fail_the_save(fake_save):
    fake_save(succeed=True)

    def boom(draft_id):
        raise RuntimeError("placement exploded")

    result = save_draft_impl("d1", on_complete=boom)
    assert result["success"] is True
    assert save_task_cache.get_task_status("d1")["status"] == "completed"


def test_on_complete_runs_in_background_mode_too(fake_save):
    fake_save(succeed=True)
    save_draft_impl("d1", wait=False, on_complete=lambda draft_id: "/drafts/d1")
    for _ in range(50):
        if save_task_cache.get_task_status("d1").get("local_path"):
            break
        time.sleep(0.05)
    assert save_task_cache.get_task_status("d1")["local_path"] == "/drafts/d1"


# --------------------------------------------------------------- failure reporting

def test_a_failed_save_is_reported_on_the_task(fake_save):
    fake_save(succeed=False)
    save_draft_impl("d1")
    assert save_task_cache.get_task_status("d1")["status"] == "failed"


# --------------------------------------------------------------- MCP dispatch ordering

@pytest.fixture
def mcp(monkeypatch, fake_save):
    """The MCP save_draft branch, with the real save and placement stubbed out."""
    import mcp_server
    placements = []

    def place(draft_id):
        # Records WHEN placement happened relative to the save completing.
        placements.append(save_task_cache.get_task_status(draft_id).get("status"))
        return f"/drafts/{draft_id}"

    monkeypatch.setattr(mcp_server, "place_draft_locally", place)
    return mcp_server, placements, fake_save


def test_mcp_sync_save_still_returns_local_path(mcp):
    mcp_server, placements, fake_save = mcp
    fake_save(succeed=True)
    out = mcp_server.execute_tool("save_draft", {"draft_id": "d1"})
    assert out["success"] is True
    assert out["result"]["local_path"] == "/drafts/d1"


def test_mcp_places_the_draft_only_after_the_save_completes(mcp):
    """The ordering bug async would otherwise introduce.

    place_draft_locally moves the rendered draft folder. Run before the save, it would move a
    folder that does not exist yet.
    """
    mcp_server, placements, fake_save = mcp
    fake_save(succeed=True)
    mcp_server.execute_tool("save_draft", {"draft_id": "d1"})
    assert placements == ["completed"], "placement must observe a completed save"


def test_mcp_async_save_returns_a_task_id_and_defers_placement(mcp):
    mcp_server, placements, fake_save = mcp
    calls = fake_save(succeed=True, block=True)

    out = mcp_server.execute_tool("save_draft", {"draft_id": "d1", "wait": False})
    assert out["result"]["task_id"] == "d1"
    assert "local_path" not in out["result"]
    assert placements == [], "placement must not happen before the save finishes"

    calls["release"].set()
    for _ in range(50):
        if placements:
            break
        time.sleep(0.05)
    assert placements == ["completed"]
