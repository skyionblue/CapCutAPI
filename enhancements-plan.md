# CapCutAPI Enhancements Plan

**Created:** 2026-10-22
**Status:** Tier A, Phase B1 and Phase C1 tests COMPLETE (2026-10-23); CI deferred by decision. B2 and remaining Tier C proposed.
**Scope:** Project-wide improvements outside the export feature (tracked separately in
`export-functionality-plan.md`, delivered in PR #1).

---

## 1. Summary

Every item below was verified against the code on 2026-10-22, with file and line references so
each can be re-checked rather than taken on trust. They fall into three tiers:

| Tier | Theme | Why it matters |
|---|---|---|
| **A** | Packaging and licensing defects | The repo currently misinstalls and mislicenses itself |
| **B** | Reliability | In-memory-only drafts are unrecoverable across a restart |
| **C** | Engineering quality | No tests, no CI, duplicated server layers |

**Recommended order:** Tier A (cheap, visibly wrong) → Phase B1 (highest value) → Phase C1
(protects everything else).

---

## Tier A — Correctness defects

Small, independent, and wrong in ways a reviewer or new user will hit immediately.

### Phase A1 — Fix packaging metadata — **COMPLETE (2026-10-23)**

- [x] Replaced `[project].dependencies` — it declared `fastapi`, `uvicorn`, `pydantic`,
      `Pillow`, `numpy`, `opencv-python`, `ffmpeg-python` and `websockets`, none of which the
      project imports — with the real set, mirroring `requirements.txt`.
- [x] Carried over the macOS-gated `pyobjc-framework-Quartz`.
- [x] `mcp` extra now mirrors `requirements-mcp.txt`; added a `dev` extra (`pytest`, `flake8`).
- [x] Noted in the file that `ffmpeg`/`ffprobe` are required at runtime but are external
      binaries that cannot be installed from here.
- [x] **Additional defect found: `pip install .` had never worked at all.** The build failed
      with *"Multiple top-level packages discovered in a flat-layout"* — setuptools cannot
      auto-discover this project's mix of top-level modules and packages. Discovery is now
      declared explicitly under `[tool.setuptools]`.

**Validated:** a clean venv (Python 3.14) installed `.[mcp]` successfully, then imported
`capcut_server`, `mcp_server` and `export_impl` — 29 url rules, 21 MCP tools, preflight
resolving a backend.

**Still open (deliberately not changed):** `psutil` is declared in `requirements.txt` but
imported nowhere, and `aiohttp`/`pydantic` arrive transitively through `mcp`. Left in place so
this phase did not silently alter anyone's environment; worth verifying before removal.

### Phase A2 — Licence — **RESOLVED (2026-10-23): claims removed, decision deferred**

Owner decision: assert nothing until the upstream position is confirmed. A derivative cannot be
licensed more permissively than what it derives from, and this project descends from
`sun-guannan/CapCutAPI` while vendoring `pyJianYingDraft`.

- [x] Removed the Apache 2.0 README badge, which linked to a `LICENSE` file that did not exist.
- [x] Replaced the README licence section — which reproduced the full Apache 2.0 notice — with
      an explicit statement that no licence is currently granted.
- [x] Removed the contradicting `License :: OSI Approved :: MIT License` classifier.
- [x] No `LICENSE` file created.
- [ ] **Follow-up:** confirm the licences of `sun-guannan/CapCutAPI` and of the vendored
      `pyJianYingDraft`, then adopt a compatible licence and restore the badge.

### Phase A3 — Remove the remaining fork references — **COMPLETE (2026-10-23)**

- [x] `pyproject.toml:43-45` `Homepage`/`Repository`/`Issues` repointed from
      `ashreo/CapCutAPI` to `skyionblue/CapCutAPI`.
- [x] Swept the tree: no references to the upstream repository remain outside git history and
      this plan.

---

## Tier B — Reliability

### Phase B1 — Persist drafts across restarts — **COMPLETE (2026-10-23)**

- [x] Every mutation writes through to `DRAFT_STORE_DIR/<draft_id>.json`, via a
      `persist_draft()` call at the end of all eight `add_*` implementations and on creation.
- [x] Writes are atomic (temp file + `os.replace`), so a crash mid-write cannot leave a
      half-written draft that would then fail to load.
- [x] `get_script()` reads cache first, then the store, and warms the cache on a restore.
      `save_draft_impl` and `query_script_impl` both go through it.
- [x] **`get_or_create_draft` now restores a known `draft_id` instead of silently creating a
      new draft under a new id** — the specific behaviour that lost work after a restart.
      A genuinely unknown id still creates a new draft.
- [x] The LRU cache keeps its semantics and stays the hot path in front of the store.
- [x] Persisting never raises: a store failure is logged, the draft stays usable in memory.
      A corrupt store file is reported rather than thrown.
- [x] `forget_draft()` clears both cache and store; `list_persisted_drafts()` reports what is
      recoverable.
- [x] Store location configurable via `draft_store_dir` in `config.json`; `drafts_store/` is
      gitignored and documented in the README.
- [x] Concurrency: all cache and store operations take a re-entrant lock, since mutations
      arrive from Flask request threads and MCP calls alike.

**Validated:**

- 14 unit tests (`tests/test_draft_persistence.py`), including corrupt-store and
  store-unwritable paths.
- **A genuine cross-process restart**, not just a cleared cache: one interpreter created and
  edited a draft, a second fresh interpreter with an empty cache restored it with its size,
  duration and tracks intact, returned the *same* id from `get_or_create_draft`, and served
  `query_script_impl` successfully.

**Known limitation (documented in the README):** a restored draft comes back on the draft
library's *imported* tracks, because `Script_file.load_template` populates
`imported_tracks`/`imported_materials` rather than the native ones. `dumps()` merges both, so
saving and querying round-trip correctly, but further edits append new tracks rather than
extending the restored ones.

**Not done:** a TTL/cleanup policy for the store, so it grows unbounded. Worth adding if drafts
accumulate.

### Phase B2 — Make `save_draft` asynchronous

The async machinery exists but is disabled — the threading block is commented out at
`save_draft_impl.py:277-282`, with the synchronous return above it. The `save_draft` MCP tool
description admits the consequence: `query_draft_status` is "mostly a safety net."

A draft with many remote assets blocks the HTTP request (and the MCP call) until every download
finishes, risking client timeouts on exactly the large projects that need it most.

- [ ] Re-enable the background thread, following the pattern now proven by `export_impl.py`.
- [ ] Return a `task_id` immediately; keep progress flowing into `DRAFT_TASKS`.
- [ ] Update the `save_draft` and `query_draft_status` tool descriptions to tell the model to poll
      — the current wording actively discourages it.
- [ ] **Backwards compatibility:** callers today receive a completed result synchronously.
      Either keep a `wait: bool = True` default, or treat this as a breaking change and say so
      in the README. **Owner decision required.**

**Validation:** a draft with several large remote assets returns promptly and reports real
progress through `query_draft_status`.

---

## Tier C — Engineering quality

### Phase C1 — Add a test suite — **COMPLETE (2026-10-23)**

Delivered on `feature/tests-and-ci`. **63 tests, running in ~0.2 s, with no CapCut installed.**

- [x] `pytest` added, with config in `pyproject.toml` (`testpaths`, `pythonpath`, a `gui`
      marker excluded by default).
- [x] `tests/conftest.py` builds draft fixtures in **both shapes**: as this API writes them
      (no `has_audio` key, real paths) and as CapCut rewrites them (`has_audio` set,
      `##_draftpath_placeholder_<uuid>_##` paths). Testing only the second shape is precisely
      how the two defects in `e2a4b75` reached main.
- [x] Tiny real media generated with ffmpeg at session scope, so audio probing is exercised
      for real rather than mocked.
- [x] `test_draft_model.py` (16) — including **regression tests for both `e2a4b75` defects**.
- [x] `test_ffmpeg_render.py` (29) — overlay count, input seeking against source ranges, audio
      mapping, the resolution "shorter side" rule in both orientations, even-dimension
      enforcement, `_atempo_chain` outside 0.5–2.0, drawtext escaping.
- [x] `test_export_task_cache.py` (11) — LRU eviction and refresh, warning accumulation,
      snapshot isolation.
- [x] `test_export_impl.py` (12) — backend resolution, validation, async contract, failure
      recording.
- [x] Documented in the README so the suite is discoverable without a pipeline.
- [~] **CI deferred.** There is no build pipeline for this project at present, by
      decision. A GitHub Actions workflow was written and removed again: with no
      runner it only produced a failed check on every push and implied a safety net
      that did not exist. The suite is fast and dependency-light precisely so it
      stays useful when run by hand.

**The regression tests were verified against the broken code**, not just the fixed code: both
fail on `e2a4b75^` and pass on `e2a4b75`. A regression test that passes either way proves nothing.

**Two defects found while writing these tests:**

1. **`export_task_cache` leaked mutable state.** `dict.copy()` is shallow, so every caller shared
   the `fidelity_warnings` list with the cache and appending to it silently rewrote recorded
   status. Fixed with a `_snapshot()` helper that copies the list.
2. **`.flake8` excluded `pyJianYingDraft\metadata\font_meta.py` using Windows separators**, so
   that exclusion never matched on macOS or Linux, and the `capcut_*` metadata tables were not
   excluded at all. Replaced with a single directory exclusion; `.venv` is now excluded too
   (linting it produced 83,566 findings).

### Phase C5 — Burn down the legacy lint debt

With `.venv` and generated metadata excluded, the pre-existing modules carry **836 flake8
findings** (`example.py` 212, `save_draft_impl.py` 102, `capcut_server.py` 88, …). CI lints the
export modules and tests **strictly**, and the whole repo **advisorily** (`continue-on-error`), so
the debt stays visible without CI being red from day one.

- [ ] Burn down per module, starting with the files Phase C2 will touch anyway.

**Completion criteria:** `flake8 .` is clean from the repository root.

### Phase C2 — Remove the duplicated server layers

`capcut_server.py` (1274 lines) and `mcp_server.py` (944 lines) wire the same implementation
functions with separately written argument handling and validation. Adding the export feature
required writing the same surface twice, which is how the two drift apart.

- [ ] Extract a shared dispatch layer: one place mapping tool name → implementation, with shared
      validation and error shaping.
- [ ] Reduce both servers to thin protocol adapters over it.
- [ ] Preserve both response shapes exactly — HTTP returns `{success, output, error}` and MCP
      returns `{success, result}`; **this refactor must not change either**.
- [ ] Do this *after* Phase C1, so the tests can prove behaviour is unchanged.

**Risk:** a large refactor with no tests is how regressions enter. Strictly gated on C1.

### Phase C3 — Harden before any non-local exposure

Not urgent for local use; required before the HTTP API is reachable from anywhere else.

- [ ] `add_video`/`add_audio`/`add_image` fetch arbitrary caller-supplied URLs server-side — an
      SSRF vector. Add host allow-listing or outbound restrictions if exposed.
- [ ] No authentication on any HTTP route.
- [ ] Review `download_file` write paths for traversal via crafted material names
      (`delete_draft` is already guarded; the download path has not been reviewed).
- [ ] Document explicitly that the server is intended for localhost use.

### Phase C4 — Finish the export plan's Tier 4

Carried over from `export-functionality-plan.md`, all optional:

- [ ] `export_draft` — portable zip of a draft with relocated asset paths.
- [ ] `export_subtitles` — SRT out, completing the round trip with `add_subtitle_impl.py`.
- [ ] `export_timeline` — OpenTimelineIO, for finishing in Resolve/Premiere/FCP.
- [ ] ffmpeg backend: crossfade transitions (`xfade`) and keyframe approximation, both currently
      reported as fidelity warnings.

---

## 2. Dependencies Between Phases

```
A1, A2, A3  ── independent, any order
B1          ── independent; highest value
B2          ── best after B1 (persistence makes async safer)
C1          ── DONE; prerequisite for C2
C2          ── REQUIRES C1 (now unblocked)
C5          ── independent; pairs naturally with C2
C3          ── only before non-local exposure
C4          ── independent, optional
```

---

## 3. Assumptions

- The project continues to target localhost / trusted-network use by default.
- Flask remains the HTTP framework (nothing in the tree uses FastAPI despite the declaration).
- Existing response shapes are a contract for current callers and must not change silently.
- `ffmpeg`/`ffprobe` remain external binary prerequisites rather than packaged dependencies.

---

## 4. Open Questions

- [ ] **Licence:** Apache 2.0 as the README asserts, or MIT as `pyproject.toml` classifies?
- [ ] **`save_draft` async:** is a breaking change to the return contract acceptable, or should
      `wait=True` preserve today's behaviour?
- [ ] **Draft persistence location:** a working directory inside the repo, a configurable path,
      or the system temp directory?
- [ ] Should `spikes/capcut_ui/` be kept long-term for its findings, or removed once the backend
      is stable?

---

## 5. Success Criteria

1. A clean-venv `pip install .` yields a working server with no manual dependency fixes.
2. One licence, asserted consistently, with the file present.
3. No draft is lost to a server restart.
4. `pytest` passes from a clean checkout with no CapCut installed, and CI enforces it on every PR.
5. Adding a new tool requires wiring it in **one** place, not two.
6. No behavioural change to existing HTTP or MCP responses as a result of any refactor.
