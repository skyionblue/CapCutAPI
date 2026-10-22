"""LRU cache of video export task status.

Kept separate from save_task_cache.DRAFT_TASKS so that draft-save jobs and video-export
jobs stay distinguishable: they have different lifecycles, different result fields, and are
polled through different tools.
"""

from collections import OrderedDict
import threading
from typing import Any, Dict, List

# Using OrderedDict to implement LRU cache, limiting the maximum number to 1000
EXPORT_TASKS: "OrderedDict[str, dict]" = OrderedDict()
MAX_TASKS_CACHE_SIZE = 1000

# Export tasks are written from background threads and read from request handlers.
_LOCK = threading.Lock()


def _default_status(task_id: str = "", draft_id: str = "", backend: str = "") -> dict:
    """The full export task schema. Every field is always present so callers never KeyError."""
    return {
        "task_id": task_id,
        "draft_id": draft_id,
        "backend": backend,
        "status": "initialized",
        "message": "Export task initialized",
        "progress": 0,
        "output_path": "",
        "video_url": "",
        # Anything the backend could not reproduce faithfully. Never silently empty:
        # a degraded render must be reported to the caller.
        "fidelity_warnings": [],
        "error": "",
    }


def create_export_task(task_id: str, draft_id: str = "", backend: str = "") -> None:
    """Create a new export task and initialize its status."""
    with _LOCK:
        if task_id in EXPORT_TASKS:
            EXPORT_TASKS.pop(task_id)
        elif len(EXPORT_TASKS) >= MAX_TASKS_CACHE_SIZE:
            EXPORT_TASKS.popitem(last=False)
        EXPORT_TASKS[task_id] = _default_status(task_id, draft_id, backend)


def update_export_task(task_id: str, **fields: Any) -> None:
    """Update one or more fields in an export task's status."""
    with _LOCK:
        task_status = EXPORT_TASKS.pop(task_id, None)
        if task_status is None:
            task_status = _default_status(task_id)
            if len(EXPORT_TASKS) >= MAX_TASKS_CACHE_SIZE:
                EXPORT_TASKS.popitem(last=False)
        else:
            task_status = task_status.copy()
        task_status.update(fields)
        EXPORT_TASKS[task_id] = task_status


def add_fidelity_warning(task_id: str, warning: str) -> None:
    """Record something the backend could not reproduce faithfully."""
    with _LOCK:
        task_status = EXPORT_TASKS.pop(task_id, None)
        if task_status is None:
            task_status = _default_status(task_id)
        else:
            task_status = task_status.copy()
            task_status["fidelity_warnings"] = list(task_status.get("fidelity_warnings", []))
        task_status["fidelity_warnings"].append(warning)
        EXPORT_TASKS[task_id] = task_status


def get_export_task_status(task_id: str) -> Dict[str, Any]:
    """Get an export task's status, refreshing its LRU position."""
    with _LOCK:
        task_status = EXPORT_TASKS.pop(task_id, None)
        if task_status is None:
            missing = _default_status(task_id)
            missing["status"] = "not_found"
            missing["message"] = "Export task does not exist"
            return missing
        EXPORT_TASKS[task_id] = task_status
        return task_status.copy()


def list_export_tasks() -> List[Dict[str, Any]]:
    """All cached export tasks, most recently used last."""
    with _LOCK:
        return [status.copy() for status in EXPORT_TASKS.values()]
