# Export Functionality Implementation Plan

**Project:** CapCutAPI
**Created:** 2026-10-22
**Status:** Phase 0 COMPLETE (gate passed) — see `spikes/capcut_ui/FINDINGS.md`. Phase 1 next.

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

- [ ] Create `export_impl.py` with the dispatcher, parameter validation, and task lifecycle.
- [ ] Define the export task status schema in `save_task_cache.py` style:
      `status`, `progress`, `message`, `output_path`, `video_url`, `fidelity_warnings`.
- [ ] Add `query_export_status` (or extend `query_draft_status` to recognise export tasks —
      prefer a separate tool so the two job types stay legible to the AI).
- [ ] Wire `upload_mp4_to_oss()` into the completion handler, guarded on `MP4_OSS_CONFIG` being
      populated — this finally gives the dead code a caller.
- [ ] Add a `ffmpeg`/`ffprobe` availability preflight check with a clear error message.
- [ ] Register `export_video` and `query_export_status` in `mcp_server.py` `TOOLS` and
      `execute_tool`, and add matching Flask routes in `capcut_server.py`.

**Success criterion:** `export_video` with a stub backend creates a task, reports progress, and
returns a (fake) path through both the MCP and HTTP surfaces.

---

### Phase 2 — CapCut-driven export (primary path, full fidelity)

Gated on Phase 0 succeeding.

- [ ] Implement `backends/capcut_macos.py`: launch/focus CapCut, open the target draft, trigger
      Export, fill the settings dialog from the requested parameters, confirm, wait for completion.
- [ ] Make every UI interaction retry with backoff and fail loudly with a descriptive error naming
      the step that failed — never hang silently.
- [ ] Add a configurable overall timeout proportional to timeline duration.
- [ ] Guard against concurrent exports: serialise with a lock, since there is one GUI.
- [ ] Detect and report the "CapCut not running / no GUI session / Accessibility permission
      missing" cases distinctly, each with the remediation step.
- [ ] Map export settings (resolution, framerate, bitrate, codec) onto the dialog's actual
      controls; document which requested values CapCut cannot honour.
- [ ] Pin and document the tested CapCut version; add a startup warning when the installed version
      differs from the tested one.

**Success criterion:** a draft built entirely through MCP tools — including effects, animations
and stickers — exports to MP4 with no human interaction, and the output visually matches what
CapCut's own Export produces.

---

### Phase 3 — Headless ffmpeg render (secondary path, subset fidelity)

Valuable even if Phase 2 succeeds: fast previews, CI, and any headless/server deployment where no
GUI exists.

- [ ] Walk the `script_file.py` track/segment tree and compile an ffmpeg filtergraph.
- [ ] Support: trims, cuts, concat, scale/position/rotate/opacity transforms, crossfades
      (`xfade`), audio mixing with per-segment volume and fades, subtitles via `drawtext`/`subtitles`.
- [ ] Approximate linear keyframes (`add_video_keyframe_impl.py`) with ffmpeg expressions; report
      any non-linear curve as an approximation.
- [ ] **Emit `fidelity_warnings`**: for every segment carrying a CapCut effect, filter, mask,
      animation or sticker that cannot be reproduced, record what was dropped or approximated.
      This is non-negotiable — the AI assistant must be able to tell the user what it could not
      render rather than silently delivering a degraded video.
- [ ] Stream ffmpeg progress into the task cache so long renders report real percentages.
- [ ] Add a `preview` mode: low resolution, fast preset, for quick iteration.

**Success criterion:** a draft using only cuts, transforms, audio and text renders to an MP4 that
matches the CapCut export; a draft using effects renders with an accurate, itemised warning list.

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
