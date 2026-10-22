# Export Functionality Implementation Plan

**Project:** CapCutAPI
**Created:** 2026-10-22
**Status:** Phases 0-3 COMPLETE — both export backends work. Phase 4 (interchange formats) next.

---

## 1. Objective

Make the project end-to-end autonomous: a user describes the video they want in natural
language, the AI assistant builds it through the MCP tools, **and the AI delivers a finished
video file** — without the user opening CapCut and pressing Export.

Today the pipeline stops one step short. `save_draft` writes a CapCut draft folder and moves it
into `~/Movies/CapCut/User Data/Projects/com.lveditor.draft` (`mcp_server.py:548`
`place_draft_locally`). From there a human must finish the job manually. This plan closes that
gap.

### Guiding principle

CapCut is the rendering engine. Every effect, filter, mask, animation, transition and sticker the
API can set (`add_effect_impl.py`, `add_sticker_impl.py`, `pyJianYingDraft/animation.py`) is
stored as a CapCut effect ID and is resolved only by CapCut's own renderer. Any export path that
bypasses CapCut loses them. Therefore:

- **Primary path:** drive the installed CapCut app to export. Full fidelity.
- **Secondary path:** headless ffmpeg render. Fast, server-friendly, documented subset of
  fidelity. Used for previews, CI, and headless deployments.
- **Tertiary paths:** interchange and bundle formats, for handing work to other tools.

---

## 2. Current State

| Item | Location | Notes |
|---|---|---|
| Draft assembly | `save_draft_impl.py` | Downloads assets, rewrites paths, writes draft folder |
| Local placement | `mcp_server.py:548` | Moves draft into CapCut's Projects directory |
| Async job pattern | `save_task_cache.py`, `query_draft_status` | LRU task cache with status/progress/message — reusable for long renders |
| ffmpeg already used | `downloader.py`, `get_duration_impl.py` | ffmpeg/ffprobe are de facto dependencies already |
| **Dead code** | `oss.py:23` `upload_mp4_to_oss()` | Fully implemented, never called |
| **Dead config** | `config.json.example` → `settings/local.py:60` `MP4_OSS_CONFIG` | Loaded, never used |
| MCP tool surface | `mcp_server.py` `TOOLS` + `execute_tool` | 18 tools; none export media |
| HTTP surface | `capcut_server.py` | Flask routes mirror the MCP tools |

The dead `upload_mp4_to_oss` and `mp4_oss_config` show that video export was always the intended
destination — the delivery half exists, the render half does not.

### Environment facts (verified 2026-10-22)

- `/Applications/CapCut.app` is installed; bundle id `com.lemon.lvoverseas`.
- No `.sdef` in the app bundle → **CapCut is not AppleScript-scriptable**. Automation must go
  through System Events / the macOS Accessibility API, which requires granting Accessibility
  permission to the controlling process.
- The drafts directory exists and contains drafts.

---

## 3. Target Architecture

A new `export_impl.py` module exposing one entry point per backend behind a shared interface,
plus a single `export_video` MCP tool that selects a backend.

```
export_video(draft_id, backend="capcut"|"ffmpeg", resolution, framerate, bitrate, output_path)
  -> {"task_id": ...}            # async, returns immediately
query_export_status(task_id)     # reuses save_task_cache
  -> {"status", "progress", "message", "output_path", "video_url", "fidelity_warnings"}
```

Both backends write to the same task-cache contract so the AI assistant polls one way regardless
of backend. On completion, if `mp4_oss_config` is configured, the finished file is uploaded via
the existing `upload_mp4_to_oss()` and a signed URL is returned alongside the local path.

```
export_impl.py
├── export_video()            # dispatcher, task creation
├── backends/capcut_macos.py  # System Events UI automation
├── backends/ffmpeg_render.py # filtergraph compiler
└── backends/interchange.py   # OTIO / FCPXML / SRT writers
```

---

## 4. Phases

### Phase 0 — Spike: can we drive CapCut's export on macOS? (BLOCKING)

Everything in Phase 2 depends on the answer. Timebox this before committing to the approach.

- [ ] Confirm Accessibility permission can be granted to the process running the MCP server
      (Terminal / the MCP host app) and document the exact steps for the user.
- [ ] Dump CapCut's UI element tree with System Events while a draft is open; record the element
      paths for: draft list entry, Export button, export settings dialog (resolution, framerate,
      bitrate, output path fields), the confirm button, and the completion state.
- [ ] Determine whether CapCut can be launched directly into a specific draft (URL scheme,
      command-line argument, or `root_meta_info.json` manipulation) or whether the automation must
      navigate the draft list by name.
- [ ] Identify a reliable **completion signal**: a UI state change, the output file reaching a
      stable size, or a CapCut log file. Polling the output file for size stability is the most
      robust fallback.
- [ ] Record the CapCut version tested (automation is version-fragile).
- [ ] **Decision gate:** if UI automation proves unworkable, Phase 2 is dropped and Phase 3
      (ffmpeg) becomes the primary path, with the fidelity limits documented as a hard constraint.

**Success criterion:** a throwaway script exports one existing draft to a known MP4 path,
unattended, twice in a row.


#### Phase 0 Outcome (2026-10-22) — GATE PASSED

Full results: **`spikes/capcut_ui/FINDINGS.md`**.

**Two consecutive unattended exports of draft `1019` succeeded**, verified with `ffprobe`
(H.264 720x1280 @30fps, AAC, 15.066667 s — matching the draft's registry duration exactly).

Key results:

- CapCut 9.3.0 exposes named automation elements (`HomePageDraftTitle:<draft_id>`,
  `ExportOkBtn`, `automationcloseBtn`, …). `File > Export` is a real menu item (Cmd+E).
- **Root cause of early failures was macOS Spaces, not permissions.** `frontmost` returned
  `true` while CapCut was on a non-visible Space, so positional clicks landed in another
  application. **AX frontmost alone is unsafe and must never be relied on.**
- **Fix:** hit-test every click against `CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly)`
  and refuse to click unless the target pixel belongs to CapCut. Validated both directions.
  This makes the backend safe to run alongside other apps, including a screen-recorded call.
- `AXPress` works on native menus but **not** on CEF buttons — those need real CGEvent clicks
  (`pyobjc-framework-Quartz`). Window geometry changes mid-session, so coordinates must be
  re-read immediately before every click.
- A **post-export success panel** persists and blocks the next export; it must be dismissed via
  `automationcloseBtn`.
- **Design confirmed:** read the planned output path from the AX tree rather than setting it —
  CapCut auto-renames on collision (`1019(1).mp4`) and the AX value reflects that.

**Gate decision:** CapCut backend is **promoted to primary**, as originally intended. Phase 1
(plumbing) is next; Phase 3 (ffmpeg) remains valuable for headless/server use.

---

### Phase 1 — Foundation: export plumbing (no renderer yet)

Independent of the Phase 0 outcome; build it first so either backend can plug in.

- [x] Create `export_impl.py` with the dispatcher, parameter validation, and task lifecycle.
- [x] Define the export task status schema — `export_task_cache.py`, mirroring
      `save_task_cache.py`'s LRU pattern but kept separate so save jobs and export jobs stay
      distinguishable. Fields: `status`, `progress`, `message`, `output_path`, `video_url`,
      `fidelity_warnings`, `error`, `backend`, `draft_id`.
- [x] Add `query_export_status` as its own tool (not folded into `query_draft_status`).
- [x] Wire `upload_mp4_to_oss()` into the completion handler, guarded on `MP4_OSS_CONFIG` —
      the dead code finally has a caller. Upload failure is non-fatal; the local file stands.
- [x] Add a `ffmpeg`/`ffprobe` and GUI-session preflight, exposed as its own `export_preflight`
      tool so the assistant can explain what is possible before trying.
- [x] Register `export_video`, `query_export_status` and `export_preflight` in `mcp_server.py`
      `TOOLS` + `execute_tool` (18 -> 21 tools) and add matching Flask routes.
- [x] Backend package `export_backends/` with `capcut_macos.py` (Phase 2) and
      `ffmpeg_render.py` (Phase 3) raising clear not-implemented errors that name the phase.
- [x] Update `README.md` endpoint/tool lists and `MCP_Documentation_English.md` tool table.
- [x] Add macOS-gated `pyobjc-framework-Quartz` to `requirements.txt`.

**Success criterion — MET.** `export_video` creates a task, dispatches to a backend on a worker
thread, and records failure cleanly in the task cache; verified through both the MCP
(`execute_tool`) and HTTP (Flask test client) surfaces. New files are flake8-clean and the
changed files gained no new lint findings beyond one `E402`, matching the 23 pre-existing ones
in that import block.

---

### Phase 2 — CapCut-driven export (primary path, full fidelity)

Gated on Phase 0 succeeding.

- [x] Implement `export_backends/capcut_macos.py` — returns to the home page, opens the target
      draft, triggers Export, confirms, waits for completion, and dismisses the success panel.
      UI primitives live in `export_backends/macos_ui.py`.
- [x] Retry transient accessibility errors with backoff; every failure names the step and the
      remediation rather than hanging.
- [x] Timeout proportional to timeline duration, read from CapCut's draft registry
      (`tm_duration`), capped by the caller's `timeout`.
- [x] Serialise exports behind a module-level lock — there is only one GUI.
- [x] Distinct, actionable errors for: CapCut not running, not visible on the active Space,
      Accessibility permission missing, draft not on the home page, dialog did not open.
- [x] **Could not** map resolution/framerate/bitrate onto the dialog: those controls are
      CEF-rendered and cannot be operated reliably. Requesting them now emits a
      `fidelity_warning` saying CapCut's current dialog settings were used instead, rather
      than silently ignoring the request.
- [x] Pin the validated CapCut version (9.3.0) and emit a `fidelity_warning` when the installed
      version differs.

**Success criterion — MET.** Three consecutive exports through the production `export_video`
API with no human interaction, each verified with `ffprobe` (H.264 720x1280 @30fps, AAC,
15.066667 s). Includes the repeat path, where the leftover success panel is dismissed
automatically, and the relocation of the finished file to the caller's `output_path`.

**Known limitation:** encoder settings must be changed once by hand in CapCut's export dialog;
they then persist for subsequent exports. Lifting this would need reliable operation of the
CEF dropdowns, which the spike could not achieve.

---

### Phase 3 — Headless ffmpeg render (secondary path, subset fidelity)

Valuable even if Phase 2 succeeds: fast previews, CI, and any headless/server deployment where no
GUI exists.

- [x] Parse the saved `draft_info.json` into a plain model (`export_backends/draft_model.py`) —
      reading what is on disk, the same file CapCut reads, so both backends export the same thing.
- [x] Compile an ffmpeg filtergraph (`export_backends/ffmpeg_render.py`): trims, cuts, timeline
      placement, scale/position/rotate/flip/opacity transforms, per-segment speed, audio mixing
      with volume and delay, and basic text via `drawtext`.
- [x] **Emit `fidelity_warnings`** for animations, transitions, effects, masks, stickers, chroma,
      filters, text templates, plugin effects, keyframes, missing source files, and text styling
      that `drawtext` cannot reproduce.
- [x] Stream ffmpeg `-progress` into the task cache for real percentages on long renders.
- [x] Honour `resolution`, `framerate` and `bitrate` — the ffmpeg backend CAN do what the CapCut
      backend cannot. `resolution` sets the shorter side, preserving the draft's aspect.
- [ ] Crossfade transitions (`xfade`) — deferred; currently reported as a fidelity warning.
- [ ] Keyframe approximation — deferred; currently reported as a fidelity warning.
- [ ] A dedicated `preview` mode (low resolution, fast preset) — `resolution` already covers most
      of this need.

**Success criterion — MET.**

| Check | Result |
|---|---|
| Simple draft (1019) vs the CapCut export of the same draft | **SSIM ~0.99** across frames |
| Complex draft (1021): 8 trimmed cuts, 249 s, zoom transform, at `resolution='540p'` | rendered 834x540, 249.233333 s, 8 overlays |
| Trim + transform correctness (differential test) | **0.835** against the correct source moment vs **0.434** against a deliberately wrong one |
| Fidelity reporting on 1021 | correctly warned about 8 clip animations and the absence of audio |

**Known limitations (all reported, never silent):** CapCut effects/filters/masks/animations/
transitions/stickers are not reproduced; text is rendered with `drawtext` so CapCut's font,
stroke, shadow, background box and text animation are lost; keyframes use static values.

---

### Phase 4 — Interchange and bundle exports (quick wins)

- [ ] `export_draft`: zip the draft folder with assets and relative paths so a draft is portable
      between machines (today `place_draft_locally` only handles the local case).
- [ ] `export_subtitles`: write SRT from the draft's text/subtitle segments — `add_subtitle_impl.py`
      already parses SRT in, so this closes the round trip.
- [ ] `export_timeline`: OpenTimelineIO and/or FCPXML. Timeline structure (cuts, timings,
      transforms, audio levels) converts losslessly; the user finishes in Resolve/Premiere/FCP.
      Scope to OTIO first — one well-supported format beats two half-done ones.

**Success criterion:** each format opens correctly in its target application.

---

### Phase 5 — Documentation and AI ergonomics

The AI assistant is the primary consumer of this surface, so tool descriptions are part of the
feature, not an afterthought.

- [ ] Write `export_video`'s tool description so the model chooses the right backend unprompted:
      state plainly that `capcut` is full-fidelity but needs a GUI session, and `ffmpeg` is
      headless but drops CapCut-specific effects.
- [ ] Document the async contract in the description — the model must know to poll
      `query_export_status` rather than assume the file exists on return.
- [ ] Update `README.md`'s feature matrix and HTTP endpoint list.
- [ ] Update `MCP_Documentation_English.md` with the new tools and its changelog.
- [ ] Document the macOS Accessibility permission setup as a prerequisite.
- [ ] Add `mp4_oss_config` usage notes — it is finally live.

---

## 5. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| CapCut UI automation breaks on app update | Primary path dies | Pin tested version, warn on mismatch, keep ffmpeg backend as fallback |
| No GUI session (server/headless deploy) | CapCut backend unusable | ffmpeg backend; detect and report the condition clearly |
| Accessibility permission not granted | Silent automation failure | Preflight check with explicit remediation message |
| ffmpeg output silently lower fidelity | User receives a degraded video believing it correct | Mandatory `fidelity_warnings` in every export result |
| Long renders exceed MCP client timeouts | Tool call appears to hang | Async task pattern — return `task_id` immediately, poll for status |
| Concurrent exports collide over one GUI | Corrupt or wrong output | Serialise CapCut exports behind a lock |

---

## 6. Assumptions

- CapCut remains installed and logged in on the machine running the MCP server for the
  CapCut-driven path.
- `ffmpeg`/`ffprobe` are on `PATH` — already true in practice given `downloader.py`.
- Existing behaviour is preserved: `save_draft` keeps working exactly as it does today; export is
  strictly additive.
- Backwards compatibility: no changes to existing tool signatures or HTTP routes.

---

## 7. Validation

- [ ] Existing flows unchanged: `create_draft` → adds → `save_draft` still produces a draft CapCut
      opens correctly.
- [ ] End-to-end natural-language test: describe a video, let the AI build and export it, confirm
      the MP4 matches the description without human intervention.
- [ ] Both backends exercised against the same draft; differences match the declared fidelity
      warnings.
- [ ] Error paths tested: CapCut closed, permission missing, ffmpeg absent, bad `draft_id`,
      concurrent export requests.
- [ ] `flake8` clean per `.flake8`.

---

## 8. Success Criteria

1. A user states what they want in natural language and receives a finished video file, with no
   manual CapCut interaction.
2. Full-fidelity export preserves every effect, animation, transition and sticker the API can set.
3. A headless export path exists for server deployments, and it never misrepresents its fidelity.
4. Long exports are observable through progress reporting rather than opaque waits.
5. `upload_mp4_to_oss()` and `mp4_oss_config` are live code.
6. No existing functionality is changed or removed.

---

## 9. Open Questions

- [ ] Should `export_video` auto-call `save_draft` when the draft isn't yet on disk, or require it
      first? (Leaning: auto-save, since it removes a step the AI could forget.)
- [ ] Default backend when the caller doesn't specify: `capcut` when a GUI session is detected,
      else `ffmpeg`?
- [ ] Is OSS upload wanted at all here, or is a local path sufficient for your workflow?
