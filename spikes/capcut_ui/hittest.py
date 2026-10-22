"""Answer 'does this screen pixel actually belong to CapCut right now?'

AX frontmost is NOT sufficient: with Spaces (or an always-on-top overlay) the
frontmost app can be on a different Space than the one being displayed, so
positional clicks land in whatever IS visible. CGWindowList reports only the
windows composited on the ACTIVE space, in front-to-back order.
"""
import Quartz as Q

def onscreen_windows():
    """Windows currently composited on the active Space, front-to-back."""
    info = Q.CGWindowListCopyWindowInfo(
        Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements,
        Q.kCGNullWindowID,
    )
    out = []
    for w in info or []:
        b = w.get("kCGWindowBounds") or {}
        out.append({
            "owner": w.get("kCGWindowOwnerName", ""),
            "layer": w.get("kCGWindowLayer", 0),
            "x": b.get("X", 0), "y": b.get("Y", 0),
            "w": b.get("Width", 0), "h": b.get("Height", 0),
        })
    return out

def window_at(x, y):
    """Topmost on-screen window containing (x, y)."""
    for w in onscreen_windows():
        if w["w"] <= 1 or w["h"] <= 1:
            continue
        if w["x"] <= x < w["x"] + w["w"] and w["y"] <= y < w["y"] + w["h"]:
            return w
    return None

def owns_point(x, y, owner="CapCut"):
    w = window_at(x, y)
    return (w is not None and w["owner"] == owner), w

def assert_owns(x, y, owner="CapCut"):
    ok, w = owns_point(x, y, owner)
    if not ok:
        got = f'{w["owner"]!r} (layer {w["layer"]})' if w else "nothing"
        raise RuntimeError(
            f"REFUSING to click ({x},{y}): that pixel belongs to {got}, not {owner}. "
            f"CapCut is likely on another Space or covered."
        )
    return True
