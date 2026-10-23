"""Tests for export task status tracking."""

import pytest

import export_task_cache as cache
from export_task_cache import (
    add_fidelity_warning, create_export_task, get_export_task_status,
    list_export_tasks, update_export_task,
)


@pytest.fixture(autouse=True)
def clean_cache():
    cache.EXPORT_TASKS.clear()
    yield
    cache.EXPORT_TASKS.clear()


def test_unknown_task_reports_not_found_with_a_full_schema():
    status = get_export_task_status("nope")
    assert status["status"] == "not_found"
    # Every field must always be present so callers never KeyError.
    for field in ("task_id", "draft_id", "backend", "progress",
                  "output_path", "video_url", "fidelity_warnings", "error"):
        assert field in status


def test_create_then_update():
    create_export_task("t1", draft_id="d1", backend="capcut")
    update_export_task("t1", status="processing", progress=42)
    status = get_export_task_status("t1")
    assert (status["draft_id"], status["backend"]) == ("d1", "capcut")
    assert (status["status"], status["progress"]) == ("processing", 42)


def test_fidelity_warnings_accumulate():
    create_export_task("t1")
    add_fidelity_warning("t1", "dropped animations")
    add_fidelity_warning("t1", "dropped masks")
    assert get_export_task_status("t1")["fidelity_warnings"] == [
        "dropped animations", "dropped masks",
    ]


def test_returned_status_is_a_copy():
    """A caller mutating what it got back must not corrupt the cache."""
    create_export_task("t1")
    got = get_export_task_status("t1")
    got["fidelity_warnings"].append("injected")
    got["status"] = "tampered"
    fresh = get_export_task_status("t1")
    assert fresh["fidelity_warnings"] == []
    assert fresh["status"] == "initialized"


def test_lru_evicts_the_oldest_beyond_the_cap(monkeypatch):
    monkeypatch.setattr(cache, "MAX_TASKS_CACHE_SIZE", 3)
    for n in range(4):
        create_export_task(f"t{n}")
    assert get_export_task_status("t0")["status"] == "not_found"
    assert get_export_task_status("t3")["status"] == "initialized"


def test_reading_refreshes_lru_position(monkeypatch):
    monkeypatch.setattr(cache, "MAX_TASKS_CACHE_SIZE", 3)
    for n in range(3):
        create_export_task(f"t{n}")
    get_export_task_status("t0")          # t0 becomes most recently used
    create_export_task("t3")              # evicts the now-oldest, t1
    assert get_export_task_status("t0")["status"] == "initialized"
    assert get_export_task_status("t1")["status"] == "not_found"


def test_list_export_tasks():
    create_export_task("t1")
    create_export_task("t2")
    assert {task["task_id"] for task in list_export_tasks()} == {"t1", "t2"}
