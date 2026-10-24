"""Video export: turn a saved CapCut draft into a finished video file.

This is the step that used to require a human: save_draft puts a draft into CapCut's
drafts folder, and someone then opened CapCut and pressed Export. export_video does that
part programmatically.

Two backends, selected by `backend`:

  capcut  Drives the installed CapCut app. Full fidelity — every effect, filter, mask,
          animation, transition and sticker the API can set is a CapCut effect ID that
          only CapCut's own renderer resolves. Requires a GUI session with CapCut
          visible on the active macOS Space.

  ffmpeg  Headless render compiled from the draft timeline. Works on servers with no GUI,
          but reproduces only a subset of the timeline and reports everything it could not
          render in `fidelity_warnings`.

Exports are long-running, so this returns a task_id immediately; poll
query_export_status(task_id) for progress and the final output_path.
"""

import logging
import os
import platform
import shutil
import subprocess
import threading
import uuid
from typing import Any, Dict, List, Optional

from export_task_cache import (
    create_export_task,
    get_export_task_status,
    update_export_task,
)
from settings.local import MP4_OSS_CONFIG
from draft_cache import get_script
from save_draft_impl import save_draft_impl

logger = logging.getLogger('flask_video_generator')

# Backends that may be requested by name. "auto" picks one at dispatch time.
BACKENDS = ("capcut", "ffmpeg")

CAPCUT_APP_PATH = "/Applications/CapCut.app"

# Encoder settings the caller may override. None means "leave CapCut/ffmpeg at its default".
DEFAULT_CONTAINER = "mp4"


class ExportError(Exception):
    """Export could not be started or completed."""


class BackendUnavailable(ExportError):
    """The requested backend cannot run in this environment."""


def _which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def ffmpeg_available() -> bool:
    """ffmpeg and ffprobe are already de facto dependencies (downloader.py, get_duration_impl.py)."""
    return bool(_which("ffmpeg") and _which("ffprobe"))


def gui_session_available() -> bool:
    """True when a CapCut-driven export could plausibly run here.

    This is a cheap precondition only. The CapCut backend re-checks, immediately before every
    synthetic click, that the target pixel actually belongs to CapCut — AX "frontmost" is not
    sufficient, because with macOS Spaces an app can be frontmost while a different Space is
    displayed and the click lands in whatever is actually on screen.
    """
    if platform.system() != "Darwin":
        return False
    if not os.path.isdir(CAPCUT_APP_PATH):
        return False
    try:
        # A window server connection is required for any UI automation.
        result = subprocess.run(
            ["launchctl", "managername"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and "Aqua" in result.stdout
    except (subprocess.SubprocessError, OSError):
        return False


def resolve_backend(backend: str = "auto") -> str:
    """Pick a backend, or validate the one the caller asked for."""
    if backend and backend != "auto":
        if backend not in BACKENDS:
            raise ExportError(f"Unknown backend {backend!r}. Valid backends: {', '.join(BACKENDS)}")
        if backend == "capcut" and not gui_session_available():
            raise BackendUnavailable(
                "The 'capcut' backend needs a macOS GUI session with CapCut installed at "
                f"{CAPCUT_APP_PATH}. Use backend='ffmpeg' for headless rendering (reduced fidelity)."
            )
        if backend == "ffmpeg" and not ffmpeg_available():
            raise BackendUnavailable("The 'ffmpeg' backend needs ffmpeg and ffprobe on PATH.")
        return backend

    # auto: prefer full fidelity, fall back to headless.
    if gui_session_available():
        return "capcut"
    if ffmpeg_available():
        return "ffmpeg"
    raise BackendUnavailable(
        "No export backend available: CapCut is not installed (or there is no GUI session) "
        "and ffmpeg/ffprobe are not on PATH."
    )


def _run_backend(backend: str, task_id: str, draft_id: str, options: Dict[str, Any]) -> str:
    """Dispatch to a backend implementation. Returns the path of the produced file."""
    if backend == "capcut":
        from export_backends.capcut_macos import export as capcut_export
        return capcut_export(task_id, draft_id, options)
    if backend == "ffmpeg":
        from export_backends.ffmpeg_render import export as ffmpeg_export
        return ffmpeg_export(task_id, draft_id, options)
    raise ExportError(f"Unknown backend {backend!r}")


def _finish(task_id: str, produced_path: str, requested_output: Optional[str]) -> str:
    """Move the produced file to the caller's requested location, then optionally upload it.

    The CapCut backend cannot reliably set the output path through its export dialog, so it
    reads where CapCut intends to write and the file is relocated here instead.
    """
    final_path = produced_path
    if requested_output:
        target = os.path.abspath(os.path.expanduser(requested_output))
        # Treat a directory (existing, or trailing separator) as "put the file in here".
        if os.path.isdir(target) or requested_output.endswith(os.sep):
            target = os.path.join(target, os.path.basename(produced_path))
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        if os.path.abspath(produced_path) != target:
            shutil.move(produced_path, target)
        final_path = target

    update_export_task(task_id, output_path=final_path)

    video_url = ""
    if MP4_OSS_CONFIG:
        try:
            update_export_task(task_id, message="Uploading video", progress=95)
            from oss import upload_mp4_to_oss
            video_url = upload_mp4_to_oss(final_path)
        except Exception as e:  # noqa: BLE001 - upload is best effort; the local file still stands
            logger.warning("Export %s: OSS upload failed: %s", task_id, e)
            update_export_task(task_id, message=f"Video exported; OSS upload failed: {e}")
    if video_url:
        update_export_task(task_id, video_url=video_url)
    return final_path


DEFAULT_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)


def _ensure_on_disk(task_id: str, draft_id: str, draft_folder: Optional[str]) -> None:
    """Save the draft first if it is not on disk yet.

    Both backends read a draft from the CapCut drafts folder, so an export of a draft that
    only exists in the cache used to fail with an error about the draft being missing --
    accurate, but it named a step the caller had every reason to think was optional.

    Already-saved drafts are left alone. Re-saving one re-downloads every remote asset it
    references, which is slow and pointless when the draft is already where it needs to be.
    """
    folder = draft_folder or DEFAULT_DRAFT_FOLDER
    if os.path.exists(os.path.join(folder, draft_id, "draft_info.json")):
        return

    if get_script(draft_id) is None:
        raise ExportError(
            f"Draft {draft_id!r} is neither saved in {folder} nor held in this server's "
            f"draft cache, so there is nothing to export. Create it with create_draft first, "
            f"or point draft_folder at the folder that holds it."
        )

    update_export_task(task_id, message="Saving the draft to disk first", progress=8)
    logger.info("Export %s: draft %s is not on disk; saving it to %s", task_id, draft_id, folder)

    # save_draft_impl builds the draft under the project root and leaves it there --
    # place_draft_locally is what moves it where CapCut looks, and save_draft runs it as
    # its on_complete. Calling save_draft_impl without it saves to the wrong place, which
    # is exactly the bug a mocked save hid in the first version of this.
    from tool_registry import place_draft_locally  # imported late: tool_registry imports this module

    result = save_draft_impl(draft_id, folder,
                             on_complete=lambda did: place_draft_locally(did, folder))
    if not result.get("success", True):
        raise ExportError(f"Could not save draft {draft_id!r} before exporting: {result.get('error')}")

    if not os.path.exists(os.path.join(folder, draft_id, "draft_info.json")):
        raise ExportError(
            f"Saved draft {draft_id!r} but it did not land in {folder}. "
            f"Export cannot continue."
        )


def _export_background(task_id: str, draft_id: str, backend: str, options: Dict[str, Any]) -> None:
    """Worker thread: run the backend and record the outcome in the task cache."""
    try:
        update_export_task(task_id, status="processing", message=f"Exporting with {backend}", progress=5)
        _ensure_on_disk(task_id, draft_id, options.get("draft_folder"))
        produced = _run_backend(backend, task_id, draft_id, options)
        if not produced or not os.path.exists(produced):
            raise ExportError("Backend reported success but produced no output file")
        final_path = _finish(task_id, produced, options.get("output_path"))
        update_export_task(
            task_id,
            status="completed",
            message=f"Export complete: {final_path}",
            progress=100,
        )
        logger.info("Export %s completed: %s", task_id, final_path)
    except Exception as e:  # noqa: BLE001 - surfaced to the caller through the task cache
        logger.error("Export %s failed: %s", task_id, e, exc_info=True)
        update_export_task(
            task_id,
            status="failed",
            message=f"Export failed: {e}",
            error=str(e),
        )


def export_video(
    draft_id: str,
    backend: str = "auto",
    output_path: Optional[str] = None,
    resolution: Optional[str] = None,
    framerate: Optional[int] = None,
    bitrate: Optional[str] = None,
    draft_folder: Optional[str] = None,
    wait: bool = False,
    timeout: int = 1800,
) -> Dict[str, Any]:
    """Start exporting a saved draft to a video file.

    :param draft_id: Draft ID. If the draft is not on disk yet it is saved first, so
        calling save_draft beforehand is optional
    :param backend: "auto", "capcut" (full fidelity, needs a GUI) or "ffmpeg" (headless, subset)
    :param output_path: Where to put the finished file. A directory is also accepted.
    :param resolution: e.g. "1080p"; None leaves the backend default
    :param framerate: e.g. 30; None leaves the backend default
    :param bitrate: e.g. "8M"; None leaves the backend default
    :param draft_folder: Override the CapCut drafts folder holding the draft
    :param wait: Block until the export finishes instead of returning a task_id immediately
    :param timeout: Seconds to allow the export before giving up
    :return: {"success": True, "task_id": ..., "backend": ...} or {"success": False, "error": ...}
    """
    if not draft_id:
        return {"success": False, "error": "draft_id is required"}

    try:
        chosen = resolve_backend(backend)
    except ExportError as e:
        return {"success": False, "error": str(e)}

    task_id = f"export-{draft_id}-{uuid.uuid4().hex[:8]}"
    create_export_task(task_id, draft_id=draft_id, backend=chosen)

    options: Dict[str, Any] = {
        "output_path": output_path,
        "resolution": resolution,
        "framerate": framerate,
        "bitrate": bitrate,
        "draft_folder": draft_folder,
        "timeout": timeout,
    }

    thread = threading.Thread(
        target=_export_background,
        args=(task_id, draft_id, chosen, options),
        name=f"export-{draft_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Export task %s started for draft %s using %s", task_id, draft_id, chosen)

    if wait:
        thread.join(timeout)
        return {"success": True, "task_id": task_id, "backend": chosen, **query_export_status(task_id)}

    return {
        "success": True,
        "task_id": task_id,
        "backend": chosen,
        "message": f"Export started with the {chosen} backend. Poll query_export_status "
                   f"with task_id={task_id!r} for progress and the final output_path.",
    }


def query_export_status(task_id: str) -> Dict[str, Any]:
    """Poll an export task started by export_video."""
    return get_export_task_status(task_id)


def _ffmpeg_can_render_text() -> bool:
    """Whether the ffmpeg backend can draw text, which needs a libfreetype build."""
    try:
        from export_backends.ffmpeg_render import has_drawtext
        return has_drawtext()
    except Exception:  # noqa: BLE001 - preflight must never raise
        return False


def export_preflight() -> Dict[str, Any]:
    """Report which backends can run here, for diagnostics and tool descriptions."""
    gui = gui_session_available()
    ff = ffmpeg_available()
    backends: List[Dict[str, Any]] = [
        {
            "name": "capcut",
            "available": gui,
            "fidelity": "full",
            "reason": "" if gui else f"needs a macOS GUI session with CapCut at {CAPCUT_APP_PATH}",
        },
        {
            "name": "ffmpeg",
            "available": ff,
            "fidelity": "subset",
            "reason": "" if ff else "needs ffmpeg and ffprobe on PATH",
            # Worth knowing before exporting rather than after: a build without drawtext
            # renders everything except the text, and the caller may prefer capcut.
            "can_render_text": _ffmpeg_can_render_text() if ff else False,
        },
    ]
    return {
        "backends": backends,
        "default": next((b["name"] for b in backends if b["available"]), None),
        "oss_upload_configured": bool(MP4_OSS_CONFIG),
    }
