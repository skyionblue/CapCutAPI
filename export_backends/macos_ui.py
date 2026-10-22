"""macOS UI automation primitives for driving CapCut.

Everything here exists to satisfy constraints established by the Phase 0 spike
(spikes/capcut_ui/FINDINGS.md). The important ones:

  * CapCut is Chromium/CEF-based. `AXPress` works on native menu items but NOT on the
    CEF-rendered buttons inside windows and sheets, which need real CoreGraphics clicks
    with a genuine cursor move.
  * Accessibility "frontmost" is NOT proof that CapCut is on screen. With macOS Spaces an
    app can be frontmost in its own Space while a different Space is displayed, so a
    positional click lands in whatever is actually visible. Every click is therefore
    hit-tested against CGWindowList, which reports only windows composited on the ACTIVE
    Space. Without this guard, clicks land in unrelated applications.
  * Bare keystrokes bypass hit-testing entirely and land in whatever is frontmost, so this
    module deliberately offers no keystroke primitive.
  * CapCut's window moves and resizes mid-session, and its AX tree mutates while being
    walked, so coordinates are always re-read immediately before use and transient AX
    errors are retried.
"""

import logging
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('flask_video_generator')

APP_NAME = "CapCut"

# AX errors raised when the tree changes mid-walk; safe to retry.
_TRANSIENT_AX_ERRORS = ("-1719", "-1728", "Invalid index")


class UIAutomationError(Exception):
    """A UI automation step failed."""


class AccessibilityError(UIAutomationError):
    """Accessibility permission is missing or CapCut is not scriptable."""


class NotVisibleError(UIAutomationError):
    """CapCut is not frontmost and visible, so injecting input would hit another app."""


def _quartz():
    """Imported lazily: Quartz is macOS-only and the rest of the project is cross-platform."""
    try:
        import Quartz
        return Quartz
    except ImportError as e:
        raise UIAutomationError(
            "pyobjc-framework-Quartz is required for the CapCut export backend. "
            "Install it with: uv pip install pyobjc-framework-Quartz"
        ) from e


def osa(script: str, timeout: int = 60, retries: int = 4) -> str:
    """Run AppleScript, retrying transient accessibility errors."""
    last_error = ""
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise UIAutomationError(f"AppleScript timed out after {timeout}s") from e
        if proc.returncode == 0:
            return proc.stdout.strip()
        last_error = proc.stderr.strip()
        if not any(code in last_error for code in _TRANSIENT_AX_ERRORS):
            break
        time.sleep(0.4 * (attempt + 1))

    if "not allowed assistive access" in last_error or "-25211" in last_error:
        raise AccessibilityError(
            "Accessibility permission is missing. Grant it to the process running this server "
            "in System Settings > Privacy & Security > Accessibility, then retry."
        )
    raise UIAutomationError(last_error or "AppleScript failed with no error output")


# --------------------------------------------------------------------------- windows

def onscreen_windows() -> List[Dict[str, Any]]:
    """Windows composited on the ACTIVE Space, front to back."""
    Quartz = _quartz()
    info = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    windows = []
    for entry in info or []:
        bounds = entry.get("kCGWindowBounds") or {}
        windows.append({
            "owner": entry.get("kCGWindowOwnerName", ""),
            "layer": entry.get("kCGWindowLayer", 0),
            "x": bounds.get("X", 0), "y": bounds.get("Y", 0),
            "w": bounds.get("Width", 0), "h": bounds.get("Height", 0),
        })
    return windows


def window_at(x: float, y: float) -> Optional[Dict[str, Any]]:
    """Topmost on-screen window containing a point."""
    for window in onscreen_windows():
        if window["w"] <= 1 or window["h"] <= 1:
            continue
        if window["x"] <= x < window["x"] + window["w"] and window["y"] <= y < window["y"] + window["h"]:
            return window
    return None


def assert_capcut_owns(x: float, y: float) -> None:
    """Refuse to click a pixel that does not belong to CapCut right now."""
    window = window_at(x, y)
    if window is None or window["owner"] != APP_NAME:
        owner = f"{window['owner']!r}" if window else "nothing"
        raise NotVisibleError(
            f"Refusing to click ({int(x)},{int(y)}): that point belongs to {owner}, not {APP_NAME}. "
            f"{APP_NAME} is probably on another macOS Space or covered by another window. "
            f"Bring it to the foreground on the active Space and retry."
        )


def is_running() -> bool:
    try:
        return osa(f'tell application "System Events" to return (exists process "{APP_NAME}")') == "true"
    except UIAutomationError:
        return False


def is_frontmost() -> bool:
    return osa(f'tell application "System Events" to return frontmost of process "{APP_NAME}"') == "true"


def is_onscreen() -> bool:
    return any(w["owner"] == APP_NAME for w in onscreen_windows())


def ensure_foreground(tries: int = 4) -> None:
    """Bring CapCut forward and verify it is genuinely visible on the active Space."""
    if not is_running():
        raise UIAutomationError(
            f"{APP_NAME} is not running. Launch it and leave it on the active Space, then retry."
        )
    for _ in range(tries):
        if is_frontmost() and is_onscreen():
            return
        osa(f'tell application "{APP_NAME}" to activate')
        time.sleep(1.2)
    raise NotVisibleError(
        f"Could not bring {APP_NAME} to the foreground of the active Space. It may be on another "
        f"Space, minimised, or behind a fullscreen window. Input will not be injected."
    )


def main_window_index() -> int:
    """CapCut keeps empty overlay windows, so indices are not stable.

    Pick the window with the most UI elements.
    """
    script = f'''tell application "System Events" to tell process "{APP_NAME}"
    set out to ""
    set i to 0
    repeat with w in windows
        set i to i + 1
        set out to out & i & tab & (count of UI elements of w) & linefeed
    end repeat
    return out
    end tell'''
    best_index, best_count = 1, -1
    for line in osa(script).splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip().isdigit() and int(parts[1]) > best_count:
            best_index, best_count = int(parts[0]), int(parts[1])
    return best_index


# --------------------------------------------------------------------------- elements

def list_elements(window: int) -> List[Dict[str, Any]]:
    """Direct children of a window, with live geometry."""
    script = f'''tell application "System Events" to tell process "{APP_NAME}"
    set out to ""
    repeat with k in UI elements of window {window}
        set kn to ""
        try
            if (name of k) is not missing value then set kn to (name of k) as string
        end try
        set kd to ""
        try
            if (description of k) is not missing value then set kd to (description of k) as string
        end try
        set px to -1
        set py to -1
        set pw to -1
        set ph to -1
        try
            set p to position of k
            set z to size of k
            set px to item 1 of p
            set py to item 2 of p
            set pw to item 1 of z
            set ph to item 2 of z
        end try
        set out to out & (role of k) & tab & kn & tab & kd & tab & px & tab & py & tab & pw & tab & ph & linefeed
    end repeat
    return out
    end tell'''
    elements = []
    for line in osa(script).splitlines():
        fields = line.split("\t")
        if len(fields) < 7:
            continue
        try:
            elements.append({
                "role": fields[0], "name": fields[1], "desc": fields[2],
                "x": int(fields[3]), "y": int(fields[4]),
                "w": int(fields[5]), "h": int(fields[6]),
            })
        except ValueError:
            continue
    return elements


def sheet_count(window: int) -> int:
    try:
        return int(osa(f'tell application "System Events" to tell process "{APP_NAME}" '
                       f'to return (count of sheets of window {window})'))
    except (UIAutomationError, ValueError):
        return 0


def sheet_has(window: int, name: str) -> bool:
    """Is an element with this accessibility name present in the window's sheet?"""
    script = f'''tell application "System Events" to tell process "{APP_NAME}"
    repeat with k in UI elements of sheet 1 of window {window}
        try
            if (name of k) is "{name}" then return "yes"
        end try
    end repeat
    return "no"
    end tell'''
    try:
        return osa(script) == "yes"
    except UIAutomationError:
        return False


def sheet_element_center(window: int, name: str) -> Optional[Tuple[int, int]]:
    """Live centre of a sheet element. Never cache this — CapCut's window moves."""
    script = f'''tell application "System Events" to tell process "{APP_NAME}"
    repeat with k in UI elements of sheet 1 of window {window}
        try
            if (name of k) is "{name}" then
                set p to position of k
                set z to size of k
                set cx to ((item 1 of p) + ((item 1 of z) div 2)) as integer
                set cy to ((item 2 of p) + ((item 2 of z) div 2)) as integer
                return (cx as string) & "," & (cy as string)
            end if
        end try
    end repeat
    return ""
    end tell'''
    raw = osa(script).strip()
    if "," not in raw:
        return None
    try:
        x_text, y_text = [part.strip() for part in raw.split(",")[:2]]
        return int(x_text), int(y_text)
    except ValueError:
        return None


def sheet_path_value(window: int) -> str:
    """The output path CapCut intends to write, read from the dialog.

    Read rather than set: CapCut auto-renames on collision (1019.mp4 -> 1019(1).mp4) and the
    accessibility value reflects the adjusted name, so reading is correct where guessing is not.
    """
    script = f'''tell application "System Events" to tell process "{APP_NAME}"
    set out to ""
    repeat with k in UI elements of sheet 1 of window {window}
        try
            if (value of k) is not missing value then
                set v to (value of k) as string
                if v starts with "/" then set out to v
            end if
        end try
    end repeat
    return out
    end tell'''
    return osa(script).strip()


# --------------------------------------------------------------------------- menus

def menu_item_enabled(menu: str, item: str) -> bool:
    script = (f'tell application "System Events" to tell process "{APP_NAME}" to return enabled of '
              f'menu item "{item}" of menu 1 of menu bar item "{menu}" of menu bar 1')
    try:
        return osa(script) == "true"
    except UIAutomationError:
        return False


def click_menu_item(menu: str, item: str) -> None:
    """AXPress a native menu item. Reliable — unlike AXPress on CEF buttons."""
    ensure_foreground()
    osa(f'tell application "System Events" to tell process "{APP_NAME}" to click '
        f'menu item "{item}" of menu 1 of menu bar item "{menu}" of menu bar 1')


# --------------------------------------------------------------------------- input

def _post(event) -> None:
    Quartz = _quartz()
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def click(x: int, y: int, clicks: int = 1) -> None:
    """A real CoreGraphics click, hit-tested first.

    CEF ignores System Events 'click at', which posts no cursor movement, so the cursor is
    genuinely moved. The hit-test is what keeps a misplaced click from landing in another app.
    """
    ensure_foreground()
    assert_capcut_owns(x, y)

    Quartz = _quartz()
    _post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft))
    time.sleep(0.06)
    for n in range(1, clicks + 1):
        for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
            event = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, n)
            _post(event)
            time.sleep(0.02)
        time.sleep(0.04)
