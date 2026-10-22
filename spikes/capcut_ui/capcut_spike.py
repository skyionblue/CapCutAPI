#!/usr/bin/env python3
"""Phase 0 spike: probe CapCut 9.3.0 macOS UI automation surface."""
import subprocess, json, sys, time

APP = "CapCut"

def osa(script, timeout=60):
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()

def menu_item_enabled(menu, item):
    s = f'''tell application "System Events" to tell process "{APP}"
    return enabled of menu item "{item}" of menu 1 of menu bar item "{menu}" of menu bar 1
    end tell'''
    return osa(s) == "true"

def app_state():
    """home | editor — Export enabled only in the editor."""
    try:
        return "editor" if menu_item_enabled("File", "Export") else "home"
    except RuntimeError as e:
        return f"error: {e}"

def list_elements(win=1):
    """Return [{role,name,desc,x,y,w,h,actions}] for window `win`, coords parsed cleanly."""
    s = f'''tell application "System Events" to tell process "{APP}"
    set out to ""
    repeat with k in UI elements of window {win}
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
            set px to item 1 of p
            set py to item 2 of p
            set z to size of k
            set pw to item 1 of z
            set ph to item 2 of z
        end try
        set act to ""
        try
            set act to (name of actions of k) as string
        end try
        set out to out & (role of k) & tab & kn & tab & kd & tab & px & tab & py & tab & pw & tab & ph & tab & act & linefeed
    end repeat
    return out
    end tell'''
    rows = []
    for line in osa(s).splitlines():
        f = line.split("\t")
        if len(f) < 8:
            continue
        rows.append({"role": f[0], "name": f[1], "desc": f[2],
                     "x": int(f[3]), "y": int(f[4]), "w": int(f[5]), "h": int(f[6]),
                     "actions": f[7]})
    return rows

def find_draft_card(draft_name):
    """Locate the clickable card for a draft by its folder name."""
    els = list_elements()
    title_key = f"HomePageDraftTitle:{draft_name}"
    titles = [e for e in els if e["name"] == title_key or e["desc"] == title_key]
    if not titles:
        return None, els
    t = titles[0]
    cards = [e for e in els if e["desc"] == "HomePageDraft" and e["y"] < t["y"]]
    if not cards:
        return None, els
    card = min(cards, key=lambda c: (abs((c["x"] + c["w"] / 2) - (t["x"] + t["w"] / 2)), t["y"] - c["y"]))
    return card, els

def click_at(x, y):
    osa(f'tell application "System Events" to click at {{{x}, {y}}}')

def focus():
    osa(f'tell application "{APP}" to activate')
    time.sleep(1.0)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "state"
    if cmd == "state":
        print("state:", app_state())
    elif cmd == "elements":
        for e in list_elements():
            print(f'{e["role"]:15} n=[{e["name"]}] d=[{e["desc"]}] @({e["x"]},{e["y"]}) {e["w"]}x{e["h"]} acts={e["actions"]}')
    elif cmd == "card":
        card, _ = find_draft_card(sys.argv[2])
        print("card:", json.dumps(card))

def open_draft(draft_name, timeout=60, double=True):
    focus()
    card, els = find_draft_card(draft_name)
    if not card:
        names = [e["name"] for e in els if e["name"].startswith("HomePageDraftTitle")]
        raise RuntimeError(f"draft {draft_name!r} not on home page; visible: {names}")
    cx, cy = card["x"] + card["w"] // 2, card["y"] + card["h"] // 2
    click_at(cx, cy)
    if double:
        time.sleep(0.15)
        click_at(cx, cy)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app_state() == "editor":
            return {"opened": draft_name, "clicked": [cx, cy], "secs": round(time.time() - (deadline - timeout), 1)}
        time.sleep(1.0)
    return {"opened": None, "clicked": [cx, cy], "state": app_state()}

def main_window_index():
    """Window indices are NOT stable: CapCut keeps empty overlay windows.
    Pick the window with the most UI elements."""
    s = f'''tell application "System Events" to tell process "{APP}"
    set out to ""
    set i to 0
    repeat with w in windows
        set i to i + 1
        set out to out & i & tab & (count of UI elements of w) & linefeed
    end repeat
    return out
    end tell'''
    best, best_n = 1, -1
    for line in osa(s).splitlines():
        f = line.split("\t")
        if len(f) == 2 and int(f[1]) > best_n:
            best, best_n = int(f[0]), int(f[1])
    return best
