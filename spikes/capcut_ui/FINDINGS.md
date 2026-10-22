# Phase 0 Spike Findings — CapCut macOS UI Automation

**Date:** 2026-10-22
**CapCut version tested:** 9.3.0 (`com.lemon.lvoverseas`)
**macOS:** Darwin 25.6.0 (display 3456x2234 Retina)
**Verdict:** **GATE PASSED** — two consecutive unattended exports, verified with ffprobe.

---

## 1. What works

### Accessibility is available and rich

CapCut is Chromium/CEF-based (`CapCut Helper` processes), but it ships a **deliberately
instrumented accessibility tree** — element names look like internal QA automation IDs.

Home page:

| Element | Role | Notes |
|---|---|---|
| `HomePageDraftTitle:<folder>` | AXStaticText | **One per draft, named by folder name** — this is the API's `draft_id` |
| `HomePageDraft` (description) | AXStaticText | The 134x174 draft card; sits directly above its title |
| `automationrecycleBinBtn`, `automationautoUploadBtn` | AXButton | Real buttons with `AXPress` |

Editor:

| Element | Notes |
|---|---|
| `MainWindowTitleBarExportBtn` | The title-bar Export button |
| `root_Media`, `root_Text`, `root_Effects`, `root_Transitions`, … | Left panel tabs |
| `currentProgress`, `totalProgress` | Playhead / duration readouts |
| `MainTimeLineRoot`, `MTLSVideoP:<filename>` | Timeline and its segments, named by media file |

### Export dialog is fully mapped

Opened via **File → Export (Cmd+E)**. It renders as an **`AXSheet` child of the main window**
(not a separate window), description `ExportDialog`, 720x663.

| Element | Role | Actions |
|---|---|---|
| `ExportFileNameInput` | AXStaticText | none (CEF-rendered) |
| `ExportPathInput` | AXStaticText | none |
| *(sibling label)* | AXStaticText | **value = the full output path**, e.g. `/…/videos/1019.mp4` |
| `ExportFileNameInputBtn` | AXButton | AXPress, AXRaise — browse |
| `ExportSharpnessInput` (resolution), `ExportbitRateInput`, `ExportEncoderInput`, `ExportFormatInput`, `FrameRateInput`, `AudioFormatInput` | AXStaticText | none |
| `automationbackupCheckBox` | AXCheckBox | AXPress |
| `automationcancel` | AXButton | AXPress |
| `ExportOkBtn` | AXButton | AXPress |

### Reliable state probe

`enabled of menu item "Export" of menu 1 of menu bar item "File"`:

- **home page** → disabled (also `CapCut → Back to home page` disabled)
- **editor** → enabled
- **modal sheet open** → disabled again

So the Export menu item alone is ambiguous; combine it with the presence of
editor markers (`MainTimeLineRoot`) and `count of sheets` to get an unambiguous state.

### Opening a draft works

CGEvent double-click on the draft card center transitions home → editor in **~1 second**.

---

## 2. What does not work (and the fixes)

### `System Events` "click at" does nothing
CEF ignores synthetic clicks that do not move the real cursor. **Must** use CoreGraphics
(`CGEventCreateMouseEvent` + `kCGMouseEventClickState`) with a genuine cursor move.
Dependency: `pyobjc-framework-Quartz`. The venv is **uv-managed and has no pip** — use
`uv pip install --python .venv/bin/python …`.

### `AXPress` does not work on CEF buttons
`AXPress` on `ExportOkBtn` does nothing, even though it reports `enabled=true`.
**Rule:** `AXPress` works on *native* AX elements (the menu bar — `File > Export` is driven this
way reliably) but **not** on CEF-rendered buttons inside the window or sheet. Those require a real
CGEvent click.

### Window indices and geometry are both unstable
CapCut keeps 2 empty overlay windows; the editor was window 3, the home page window 1. The main
window also *moved and resized* mid-session (1708x1064 @(0,33) → 1471x981 @(129,86)).
**Rule:** select the window with the most UI elements, and **re-read every element's coordinates
immediately before clicking**. Never cache a coordinate.

### AX enumeration races with CEF re-renders
Enumerating UI elements intermittently fails with `-1719 Invalid index` when the tree mutates
mid-walk. Retry transient AX errors (`-1719`, `-1728`, "Invalid index") with a short backoff.

### Text fields cannot be focused by click
Clicking `ExportFileNameInput` does not focus it and typing does not reach it. **Do not set the
output path through the dialog** — see the design in section 4.

### Screen Recording permission
Initially denied (`screencapture`: "could not create image from display"). Granting it to the
controlling terminal is **optional** — useful for debugging, not needed by the backend.

---

## 3. ROOT CAUSE — Spaces, not focus (this cost most of the spike)

Early runs failed with no visible effect, and a screenshot revealed the clicks were landing in a
**different application entirely** (a fullscreen Google Meet window).

**`frontmost of process "CapCut"` returned `true` while CapCut was not on screen at all.**

macOS focus and screen compositing are independent. With Spaces, CapCut can be frontmost *within
its own Space* while a different Space is displayed. `screencapture` and CGEvent clicks both act
on the **visible** Space, so every positional click went to the meeting window. Keystrokes
(`Return`, `Escape`, `Cmd+A`, typed text) also went there.

### The fix — hit-test every click against `CGWindowList`

`CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly)` returns only the windows composited
on the **active** Space, front-to-back. Before each click, resolve the topmost window containing
the target pixel and assert its owner is CapCut (`hittest.assert_owns`).

Validated in both directions:

- **Negative:** with the terminal in front, `(1162,870)` resolved to `iTerm2` → click refused.
- **Positive:** with CapCut visible, the draft card point resolved to `CapCut` → click allowed.

This guard is what made the export work *and* made it safe. An AX-frontmost check alone is
**not sufficient** and must never be relied on by itself.

### Operating requirement

The CapCut backend is safe to run **while other apps (including a screen-recorded video call) are
open**, provided CapCut is the visible app on the active Space when the export runs. If it is not,
the guard aborts with a clear error instead of clicking into whatever is on screen. Never send
bare keystrokes as part of the flow — they bypass the hit-test and land invisibly in another app.

---

## 4. Validated design

### Do not set the output path — read it, then move the file

The dialog defaults to `<last used directory>/<draft folder name>.mp4` and that full path is
**readable** from the AX tree. On a name collision **CapCut auto-renames** (`1019.mp4` →
`1019(1).mp4`) and the AX-read path **reflects the adjusted name**, so reading is always correct
where guessing would not be. Flow:

1. Open the export dialog (`File > Export` via `AXPress` — native menu, reliable).
2. **Read** the planned output path from the AX tree.
3. Click `ExportOkBtn` with a hit-tested CGEvent click at its freshly-read center.
4. Poll for completion.
5. **Move** the finished file to the caller's requested `output_path`.

### Export state machine

```
home ──(hit-tested double-click on HomePageDraftTitle:<draft_id> card)──> editor
editor ──(AXPress File > Export)──> export dialog sheet (has ExportOkBtn)
export dialog ──(hit-tested click ExportOkBtn)──> encoding
encoding ──> post-export SUCCESS PANEL  (automationopenFolderBtn, publish_pc_btn, automationcloseBtn)
success panel ──(hit-tested click automationcloseBtn)──> editor   # REQUIRED before next export
```

**The success panel persists after export and blocks the next one.** Distinguish the two sheets by
probing for `ExportOkBtn` (settings dialog) vs `automationcloseBtn` (success panel); always dismiss
a leftover panel before starting.

### Completion signal (validated)

CapCut stages into `<output dir>/.__capcut_export_temp_folder_<epoch>__/`. Export is complete when
the destination file size is **stable across two polls** AND the temp folders are **gone**. Also
require the destination mtime to be newer than before the run, so a pre-existing file at the same
path is not mistaken for a finished export.

---

## 5. Results — GATE PASSED

Two consecutive unattended exports of draft `1019`, no human interaction:

| Run | Output | Size | Elapsed |
|---|---|---|---|
| 1 | `…/videos/1019.mp4` | 15,954,816 B | ~3 s |
| 2 | `…/videos/1019(1).mp4` | 15,942,603 B | ~3 s |

Both verified with `ffprobe`: **H.264 720x1280 @ 30 fps, AAC audio, duration 15.066667 s** —
matching draft 1019's registry `tm_duration` of 15,066,666 µs exactly.

### Required permissions

| Permission | For | Required? |
|---|---|---|
| Accessibility | reading the AX tree, menu `AXPress` | **yes** |
| Automation → CapCut | `tell application "CapCut" to activate` | **yes** |
| Screen Recording | `screencapture` debugging only | no |

### Recommendation

Promote the CapCut backend to **primary**, as the plan intended. It preserves full fidelity of
every effect the API can set. Phase 1 (plumbing) and Phase 3 (ffmpeg) remain worth building — the
latter for headless/server use where no GUI exists.

---

## 6. Files

- `capcut_spike.py` — AX probing helpers: `app_state`, `list_elements`, `find_draft_card`,
  `open_draft`, `main_window_index`.
- `cgclick.py` — CoreGraphics click/move helpers.

- `hittest.py` — **the critical piece**: `CGWindowList` hit-testing (`owns_point`, `assert_owns`).
- `guarded.py` — input that refuses to fire unless the target pixel belongs to CapCut.
- `flow.py` — the validated end-to-end flow.

Spike code, not production, but `hittest.py` and the guard pattern in `guarded.py` should carry
over to `export_impl.py` essentially as-is.
