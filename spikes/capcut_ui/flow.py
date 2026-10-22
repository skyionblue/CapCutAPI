"""Phase 0 end-to-end: open draft -> export dialog -> read path -> export -> detect completion."""
import sys, os, time, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capcut_spike as c, guarded

DRAFT = sys.argv[1] if len(sys.argv) > 1 else "1019"

def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)

def win():
    return c.main_window_index()

def sheets(w=None):
    w = w or win()
    return int(c.osa(f'tell application "System Events" to tell process "CapCut" to return (count of sheets of window {w})'))

def state():
    els = c.list_elements(win())
    tags = [(e["name"] or e["desc"]) for e in els]
    if any("MainTimeLine" in t for t in tags):
        return "editor"
    if any("HomePageDraft" in t for t in tags):
        return "home"
    return "unknown"

def planned_output_path(w):
    """The dialog defaults to <last dir>/<draft name>.mp4 — read it, don't set it."""
    s = f'''tell application "System Events" to tell process "CapCut"
    set out to ""
    repeat with k in UI elements of sheet 1 of window {w}
        try
            if (value of k) is not missing value then
                set v to (value of k) as string
                if v starts with "/" then set out to v
            end if
        end try
    end repeat
    return out
    end tell'''
    return c.osa(s)

# --- 1. get to the editor ---
guarded.ensure_front()
log("state:", state(), "| frontmost:", guarded.frontmost())

if state() == "home":
    card, els = c.find_draft_card(DRAFT)
    if not card:
        names = [e["name"] for e in c.list_elements(win()) if e["name"].startswith("HomePageDraftTitle")]
        log("ABORT draft not found. visible:", names); sys.exit(1)
    cx, cy = card["x"] + card["w"] // 2, card["y"] + card["h"] // 2
    log(f"opening draft {DRAFT} at ({cx},{cy})")
    guarded.guarded_click(cx, cy, clicks=2)
    for _ in range(30):
        time.sleep(1)
        if state() == "editor":
            break
    log("state now:", state())

if state() != "editor":
    log("ABORT: not in editor"); sys.exit(1)

def sheet_has(window, name):
    s = f'''tell application "System Events" to tell process "CapCut"
    repeat with k in UI elements of sheet 1 of window {window}
        try
            if (name of k) is "{name}" then return "yes"
        end try
    end repeat
    return "no"
    end tell'''
    try:
        return c.osa(s) == "yes"
    except Exception:
        return False

# --- 1b. dismiss a leftover post-export success panel ---
w0 = win()
if sheets(w0) > 0 and not sheet_has(w0, "ExportOkBtn"):
    if sheet_has(w0, "automationcloseBtn"):
        log("dismissing leftover post-export success panel")
        pt = guarded.sheet_element_point(w0, "automationcloseBtn")
        if pt:
            guarded.guarded_click(*pt)
            time.sleep(2)
    log("sheets after dismiss:", sheets(win()))

# --- 2. open export dialog via the menu item (element-addressed, no keystrokes) ---
if sheets() == 0:
    log("opening export dialog via File > Export")
    guarded.guarded_press('menu item "Export" of menu 1 of menu bar item "File" of menu bar 1')
    for _ in range(20):
        time.sleep(1)
        if sheets() > 0:
            break
w = win()
log("sheets:", sheets(w))
if sheets(w) == 0:
    log("ABORT: export dialog did not open"); sys.exit(1)

# --- 3. read the planned output path ---
out_path = planned_output_path(w)
log("planned output:", out_path)
out_dir = os.path.dirname(out_path)
pre_exists = os.path.exists(out_path)
pre_size = os.path.getsize(out_path) if pre_exists else -1
pre_mtime = os.path.getmtime(out_path) if pre_exists else 0
pre_listing = set(os.listdir(out_dir))
log("pre-existing:", pre_exists, "size:", pre_size)

def tmpdirs():
    return sorted(glob.glob(os.path.join(out_dir, ".__capcut_export_temp_folder_*")))

log("temp dirs before:", [os.path.basename(d) for d in tmpdirs()])

# --- 4. press Export (AXPress, element-addressed) ---
pt = guarded.sheet_element_point(w, "ExportOkBtn")
log("ExportOkBtn live center:", pt)
if not pt:
    log("ABORT: ExportOkBtn not found"); sys.exit(1)
log("clicking ExportOkBtn (real CGEvent, hit-tested)")
guarded.guarded_click(pt[0], pt[1])

# --- 5. monitor ---
t0 = time.time()
stable = 0
last = -2
for i in range(100):
    time.sleep(3)
    sz = os.path.getsize(out_path) if os.path.exists(out_path) else -1
    td = [os.path.basename(d) for d in tmpdirs()]
    try:
        sh = sheets(w)
    except Exception:
        sh = "?"
    log(f"t={time.time()-t0:5.0f}s sheets={sh} out={sz} tmp={td}")
    new_files = sorted(set(os.listdir(out_dir)) - pre_listing)
    if new_files:
        log("NEW FILES:", new_files)
    fresh = os.path.exists(out_path) and os.path.getmtime(out_path) > pre_mtime
    if sz > 0 and sz == last and (fresh or new_files):
        stable += 1
        if stable >= 2 and not td:
            log("COMPLETE — size stable and temp dirs gone"); break
    else:
        stable = 0
    last = sz
log("final:", out_path, os.path.getsize(out_path) if os.path.exists(out_path) else "MISSING")
