# Phase 0 Spike Findings — CapCut macOS UI Automation

**Date:** 2026-10-22
**CapCut version tested:** 9.3.0 (`com.lemon.lvoverseas`)
**macOS:** Darwin 25.6.0 (display 3456x2234 Retina)
**Verdict:** Feasible, but **blocked on a focus/safety problem that must be solved first.**

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

## 2. What does not work

### `System Events` "click at" does nothing
CEF ignores synthetic clicks that do not move the real cursor. **Must** use CoreGraphics
(`CGEventCreateMouseEvent` + `kCGMouseEventClickState`) with a genuine cursor move.
This adds a dependency: `pyobjc-framework-Quartz` (installed into the uv-managed `.venv`).

### Window indices are not stable
CapCut keeps 2 empty overlay windows alongside the real one. The editor was window **3**, the
home page window **1**. Always select the window with the most UI elements (see
`capcut_spike.main_window_index`).

### Text fields are not focusable by click
Clicking `ExportFileNameInput` does not focus it and typing does not reach it. **Do not try to
set the output path through the dialog.** See the recommended design below.

### `AXPress` on `ExportOkBtn` does nothing
Neither `AXPress` nor a correctly-positioned CGEvent click started an export, even though the
button reports `enabled=true`. The root cause is almost certainly the focus problem below.

### Screen Recording is not granted
`screencapture` fails with "could not create image from display", so screenshot-based
verification is unavailable unless the user grants it.

---

## 3. BLOCKING ISSUE — focus and stray input

**`tell application "CapCut" to activate` silently fails** when another app is frontmost. During
the spike, Google Chrome held frontmost and CapCut could not be raised.

Consequences observed:

- Positional CGEvent clicks land on whatever window is topmost at that coordinate — **not
  necessarily CapCut**.
- Keystrokes (`Return`, `Escape`, `Cmd+A`, typed text) went to the frontmost app — **Chrome** —
  not to CapCut's export dialog.

This is a **correctness and safety hazard**: an export backend that blindly injects clicks and
keystrokes can type into, and click inside, whatever application the user happens to be using.

### Required mitigations (must be built into the backend)

1. **Never inject input without first asserting frontmost.** Check
   `frontmost of process "CapCut"` immediately before *every* synthetic event; abort the export
   with a clear error if it is false. Re-assert after each step, not once at the start.
2. Prefer `AXPress` on real `AXButton` elements over positional clicks wherever a button exposes
   it, since `AXPress` is addressed to the element rather than to a screen coordinate.
3. **Never send bare keystrokes** (`Return`, `Escape`, `Cmd+…`) as part of the export flow — they
   are the most dangerous failure mode, since they land invisibly in another app. Use element
   actions only.
4. Investigate why `activate` fails (likely a fullscreen app on another Space). If CapCut cannot
   be reliably raised, the CapCut backend is only safe on a **dedicated machine or user session**
   that nobody is actively using — this should be documented as a hard operating requirement.

---

## 4. Recommended design changes (supersede parts of the plan)

### Do not set the output path in the dialog — read it, then move the file

The dialog defaults to `<last used directory>/<draft folder name>.mp4`, and that full path is
**readable** from the AX tree. Since the API already controls the draft folder name (`draft_id`),
the output filename is deterministic. So:

1. Open the export dialog.
2. **Read** the planned output path from the AX tree.
3. Press Export.
4. Poll that path for completion.
5. **Move** the finished file to the caller's requested `output_path`.

This removes all fragile text-field manipulation from the critical path.

### Completion signal

CapCut creates `<output dir>/.__capcut_export_temp_folder_<epoch>__/` and stages the encoded file
inside it. Candidate signal: temp folder disappears **and** the destination file size is stable
across two polls. This still needs confirmation once the focus problem is fixed — it was not
validated, because no export was successfully triggered.

### Dependency

`pyobjc-framework-Quartz` is required (macOS-only). The project venv is **uv-managed and has no
pip** — use `uv pip install --python .venv/bin/python …`.

---

## 5. Decision gate

The plan's Phase 0 gate asked: *does UI automation work, unattended, twice in a row?*

**Not yet proven.** The surface is far more automatable than expected (named elements, a real
Export menu item, pressable buttons), but **no export has been triggered end to end**, and the
focus problem must be solved before any further input injection is safe.

### Recommendation

Do **not** promote the CapCut backend to primary yet. Instead:

1. Resolve the focus/activation problem first (next spike session, with CapCut frontmost and no
   fullscreen app on another Space).
2. Re-attempt the `ExportOkBtn` press and validate the completion signal.
3. In parallel, begin **Phase 1 (plumbing)** and **Phase 3 (ffmpeg backend)**, which carry no GUI
   risk and are valuable regardless of how the CapCut backend lands.

---

## 6. Files

- `capcut_spike.py` — AX probing helpers: `app_state`, `list_elements`, `find_draft_card`,
  `open_draft`, `main_window_index`.
- `cgclick.py` — CoreGraphics click/move helpers.

Both are **spike code**, not production. They intentionally lack the frontmost guard described in
section 3 — do not reuse them as-is.
