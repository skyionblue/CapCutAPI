"""Frontmost- AND visibility-guarded input.

AX 'frontmost' is not enough: with Spaces, CapCut can be frontmost in its own
Space while a different Space is displayed, so positional clicks land in
whatever is actually visible. Every click is hit-tested against CGWindowList
first, and coordinates are always re-read immediately before use.
"""
import time
import capcut_spike as c
import cgclick
import hittest

APP = "CapCut"

class FocusLost(RuntimeError):
    pass

def frontmost():
    return c.osa(f'tell application "System Events" to return frontmost of process "{APP}"') == "true"

def ensure_front(tries=3):
    for _ in range(tries):
        if frontmost() and any(w["owner"] == APP for w in hittest.onscreen_windows()):
            return True
        c.osa(f'tell application "{APP}" to activate')
        time.sleep(1.2)
    raise FocusLost(f"{APP} is not frontmost and visible on the active Space; refusing to inject input")

def guarded_click(x, y, clicks=1):
    """Click only if that exact pixel belongs to CapCut right now."""
    ensure_front()
    hittest.assert_owns(x, y, APP)
    cgclick.click(x, y, clicks=clicks)

def element_point(window, name=None, desc=None, dy=0):
    """Re-read an element's live geometry and return its center (never cache coords)."""
    for e in c.list_elements(window):
        if (name and e["name"] == name) or (desc and e["desc"] == desc):
            return e["x"] + e["w"] // 2, e["y"] + e["h"] // 2 + dy
    return None

def click_element(window, name=None, desc=None, clicks=1, dy=0):
    pt = element_point(window, name=name, desc=desc, dy=dy)
    if not pt:
        raise RuntimeError(f"element not found: name={name} desc={desc}")
    guarded_click(pt[0], pt[1], clicks=clicks)
    return pt

def sheet_element_point(window, name):
    """Live center of an element inside the export sheet. Never cache coordinates."""
    s = f'''tell application "System Events" to tell process "{APP}"
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
    r = c.osa(s).strip()
    if not r or "," not in r:
        return None
    a, b = [t.strip() for t in r.split(",")[:2]]
    return int(a), int(b)


def guarded_press(element_spec):
    """AXPress a NATIVE AX element (menus). CEF-rendered buttons ignore AXPress —
    use guarded_click for those."""
    ensure_front()
    c.osa(f'tell application "System Events" to tell process "{APP}" to click {element_spec}')
