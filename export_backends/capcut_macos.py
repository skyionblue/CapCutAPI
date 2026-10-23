"""Full-fidelity export by driving the installed CapCut app (macOS).

CapCut is the renderer. Every effect, filter, mask, animation, transition and sticker the
API can set is stored only as a CapCut effect ID and is resolved by CapCut's own renderer,
so this backend is the only route to an export that matches what the draft actually
describes.

The flow and its constraints were validated by the Phase 0 spike; see
spikes/capcut_ui/FINDINGS.md for the evidence behind each step.

State machine:

    home ──(hit-tested double-click on the draft card)──> editor
    editor ──(AXPress File > Export)──> export dialog sheet (has ExportOkBtn)
    export dialog ──(hit-tested click on ExportOkBtn)──> encoding
    encoding ──> post-export success panel (has automationcloseBtn)
    success panel ──(hit-tested click)──> editor

The success panel persists after an export and blocks the next one, so it is dismissed both
before starting and after finishing.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from export_task_cache import add_fidelity_warning, update_export_task
from export_backends import macos_ui as ui

logger = logging.getLogger('flask_video_generator')

DEFAULT_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

# There is only one GUI, so exports must not overlap.
_EXPORT_LOCK = threading.Lock()

# Accessibility names/descriptions CapCut exposes (verified on 9.3.0).
DRAFT_TITLE_PREFIX = "HomePageDraftTitle:"
DRAFT_CARD_DESC = "HomePageDraft"
EXPORT_OK_BTN = "ExportOkBtn"
SUCCESS_CLOSE_BTN = "automationcloseBtn"
EDITOR_MARKER = "MainTimeLine"
# Present on the home page whether or not any drafts are listed. Detecting "home"
# by the draft cards alone reports an empty drafts folder as an unknown state.
HOME_MARKERS = ("HomePageStartProjectName", "HomePageDraft")

TEMP_FOLDER_PREFIX = ".__capcut_export_temp_folder_"

# CapCut version this automation was validated against.
VALIDATED_CAPCUT_VERSION = "9.3.0"


def _progress(task_id: str, percent: int, message: str) -> None:
    update_export_task(task_id, progress=percent, message=message)
    logger.info("Export %s: %s", task_id, message)


def installed_capcut_version() -> str:
    plist = "/Applications/CapCut.app/Contents/Info.plist"
    try:
        import plistlib
        with open(plist, "rb") as handle:
            return plistlib.load(handle).get("CFBundleShortVersionString", "")
    except (OSError, ValueError):
        return ""


def _warn_version(task_id: str) -> None:
    version = installed_capcut_version()
    if version and version != VALIDATED_CAPCUT_VERSION:
        add_fidelity_warning(
            task_id,
            f"CapCut {version} is installed but this automation was validated against "
            f"{VALIDATED_CAPCUT_VERSION}. UI automation is version-sensitive; verify the output."
        )


def draft_duration_seconds(draft_id: str, draft_folder: Optional[str] = None) -> Optional[float]:
    """Timeline duration from CapCut's draft registry, used to size the export timeout."""
    folder = draft_folder or DEFAULT_DRAFT_FOLDER
    registry = os.path.join(folder, "root_meta_info.json")
    try:
        with open(registry, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data.get("all_draft_store", []):
            if entry.get("draft_name") == draft_id:
                duration = entry.get("tm_duration")
                if isinstance(duration, (int, float)) and duration > 0:
                    return duration / 1_000_000.0
    except (OSError, ValueError, KeyError):
        pass
    return None


def _current_state(window: int = 0) -> str:
    """'home', 'editor' or 'unknown'.

    The File > Export menu item alone is ambiguous: it is disabled both on the home page and
    while a modal sheet is open, so the window's own elements are what decide.
    """
    # Resolve the window index inside the call: CapCut's overlay windows come and go, so an
    # index captured earlier may already be invalid.
    tags = [(element["name"] or element["desc"]) for element in ui.list_main_elements()]
    if any(EDITOR_MARKER in tag for tag in tags):
        return "editor"
    if any(marker in tag for tag in tags for marker in HOME_MARKERS):
        return "home"
    return "unknown"


def _dismiss_success_panel(window: int) -> bool:
    """Close a leftover post-export panel, which otherwise blocks the next export."""
    if ui.sheet_count(window) == 0 or ui.sheet_has(window, EXPORT_OK_BTN):
        return False
    if not ui.sheet_has(window, SUCCESS_CLOSE_BTN):
        return False
    point = ui.sheet_element_center(window, SUCCESS_CLOSE_BTN)
    if not point:
        return False
    ui.click(*point)
    time.sleep(2)
    return True


def _find_draft_card(draft_id: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Locate a draft's clickable card by its folder name, plus what else is on screen."""
    elements = ui.list_main_elements()
    title_key = DRAFT_TITLE_PREFIX + draft_id
    available = [
        element["name"][len(DRAFT_TITLE_PREFIX):]
        for element in elements
        if element["name"].startswith(DRAFT_TITLE_PREFIX)
    ]
    titles = [e for e in elements if title_key in (e["name"], e["desc"])]
    if not titles:
        return None, available

    title = titles[0]
    # The card sits directly above its title label.
    cards = [e for e in elements if e["desc"] == DRAFT_CARD_DESC and e["y"] < title["y"]]
    if not cards:
        return None, available
    card = min(
        cards,
        key=lambda c: (abs((c["x"] + c["w"] / 2) - (title["x"] + title["w"] / 2)), title["y"] - c["y"]),
    )
    return card, available


def _open_draft(task_id: str, draft_id: str, timeout: int = 60) -> int:
    """Get CapCut into the editor with the requested draft open."""
    window = ui.main_window_index()
    _dismiss_success_panel(window)

    # Always return to the home page first: an already-open editor may hold a different draft.
    if _current_state(window) == "editor":
        if ui.menu_item_enabled("CapCut", "Back to home page"):
            _progress(task_id, 12, "Returning to CapCut home page")
            ui.click_menu_item("CapCut", "Back to home page")
            deadline = time.time() + 30
            while time.time() < deadline:
                time.sleep(1)
                window = ui.main_window_index()
                if _current_state(window) == "home":
                    break

    window = ui.main_window_index()
    if _current_state(window) != "home":
        raise ui.UIAutomationError(
            "Could not reach CapCut's home page to select the draft. Close any open dialog in "
            "CapCut and retry."
        )

    card, available = _find_draft_card(draft_id)
    if not card:
        raise ui.UIAutomationError(
            f"Draft {draft_id!r} is not on CapCut's home page. Drafts visible: "
            f"{', '.join(available) if available else 'none'}. Run save_draft first, and make "
            f"sure CapCut has picked the draft up (it may need a restart to notice a new folder)."
        )

    centre_x = card["x"] + card["w"] // 2
    centre_y = card["y"] + card["h"] // 2
    _progress(task_id, 20, f"Opening draft {draft_id} in CapCut")
    ui.click(centre_x, centre_y, clicks=2)

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        window = ui.main_window_index()
        if _current_state(window) == "editor":
            return window
    raise ui.UIAutomationError(f"Draft {draft_id!r} did not open in the CapCut editor within {timeout}s")


def _open_export_dialog(task_id: str, window: int, timeout: int = 30) -> int:
    _progress(task_id, 35, "Opening CapCut's export dialog")
    if ui.sheet_count(window) == 0:
        ui.click_menu_item("File", "Export")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        window = ui.main_window_index()
        if ui.sheet_has(window, EXPORT_OK_BTN):
            return window
    raise ui.UIAutomationError("CapCut's export dialog did not open")


def _temp_folders(directory: str) -> List[str]:
    try:
        return [n for n in os.listdir(directory) if n.startswith(TEMP_FOLDER_PREFIX)]
    except OSError:
        return []


def _wait_for_export(task_id: str, out_path: str, before_mtime: float,
                     before_listing: set, timeout: int) -> str:
    """Wait for CapCut to finish writing.

    Complete when the destination size is stable across two polls, CapCut's staging folders
    are gone, and the file is genuinely new (mtime moved, or it appeared under a different
    name because CapCut auto-renamed on collision).
    """
    out_dir = os.path.dirname(out_path)
    deadline = time.time() + timeout
    last_size = -2
    stable = 0
    resolved = out_path

    while time.time() < deadline:
        time.sleep(3)
        new_files = sorted(set(os.listdir(out_dir)) - before_listing) if os.path.isdir(out_dir) else []
        if new_files and not os.path.exists(resolved):
            resolved = os.path.join(out_dir, new_files[0])

        size = os.path.getsize(resolved) if os.path.exists(resolved) else -1
        temps = _temp_folders(out_dir)
        fresh = os.path.exists(resolved) and os.path.getmtime(resolved) > before_mtime

        elapsed = int(time.time() - (deadline - timeout))
        update_export_task(
            task_id,
            progress=min(90, 50 + elapsed // 3),
            message=f"CapCut is encoding ({size if size > 0 else 0} bytes written)",
        )

        # Require two consecutive identical sizes, not one, so a brief write pause
        # mid-encode is not mistaken for completion.
        stable = stable + 1 if (size > 0 and size == last_size) else 0
        last_size = size
        if stable >= 2 and not temps and (fresh or new_files):
            return resolved

    raise ui.UIAutomationError(
        f"CapCut did not finish exporting within {timeout}s. The export may still be running; "
        f"check CapCut directly."
    )


def export(task_id: str, draft_id: str, options: Dict[str, Any]) -> str:
    """Export a draft through the CapCut app. Returns the produced file's path."""
    # One GUI: never run two exports at once.
    if not _EXPORT_LOCK.acquire(timeout=5):
        raise ui.UIAutomationError(
            "Another CapCut export is already running. Exports are serialised because they "
            "share one GUI; wait for the current one to finish."
        )
    try:
        _warn_version(task_id)

        # CapCut's export dialog settings are CEF-rendered and cannot be operated reliably,
        # so the caller's encoder preferences cannot be applied. Say so rather than pretend.
        unsupported = [name for name in ("resolution", "framerate", "bitrate") if options.get(name)]
        if unsupported:
            add_fidelity_warning(
                task_id,
                "The CapCut backend cannot set " + ", ".join(unsupported) +
                "; the export used CapCut's current export-dialog settings instead. "
                "Change them once in CapCut's export dialog and they persist for later exports."
            )

        _progress(task_id, 10, "Bringing CapCut to the foreground")
        ui.ensure_foreground()

        window = _open_draft(task_id, draft_id)
        window = _open_export_dialog(task_id, window)

        out_path = ui.sheet_path_value(window)
        if not out_path:
            raise ui.UIAutomationError(
                "Could not read the output path from CapCut's export dialog."
            )
        out_dir = os.path.dirname(out_path)
        before_mtime = os.path.getmtime(out_path) if os.path.exists(out_path) else 0.0
        before_listing = set(os.listdir(out_dir)) if os.path.isdir(out_dir) else set()
        _progress(task_id, 45, f"CapCut will write to {out_path}")

        point = ui.sheet_element_center(window, EXPORT_OK_BTN)
        if not point:
            raise ui.UIAutomationError("Could not locate CapCut's Export button")

        _progress(task_id, 50, "Starting the export")
        ui.click(*point)

        duration = draft_duration_seconds(draft_id, options.get("draft_folder"))
        # Allow generous headroom over real time, within the caller's ceiling.
        timeout = int(options.get("timeout") or 1800)
        if duration:
            timeout = min(timeout, max(180, int(duration * 20)))

        produced = _wait_for_export(task_id, out_path, before_mtime, before_listing, timeout)

        _progress(task_id, 92, "Closing CapCut's export panel")
        try:
            _dismiss_success_panel(ui.main_window_index())
        except ui.UIAutomationError as e:
            logger.warning("Export %s: could not dismiss success panel: %s", task_id, e)

        return produced
    finally:
        _EXPORT_LOCK.release()
