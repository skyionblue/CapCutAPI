# CapCutAPI Enhancements Plan

**Created:** 2026-10-22
**Status:** Phase C1 tests COMPLETE (2026-10-23); CI deferred by decision. Remaining phases proposed.
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

### Phase A1 — Fix packaging metadata

`pyproject.toml` declares eight dependencies that are imported **nowhere** in the project, and
omits every dependency that is actually used. `pip install .` therefore produces a non-working
install.

Declared but unused: `fastapi`, `uvicorn[standard]`, `pydantic`, `Pillow`, `numpy`,
`opencv-python`, `ffmpeg-python`, `websockets` (verified by grepping for each import).
Actually used, but only present in `requirements.txt`: `flask`, `requests`, `oss2`, `imageio`,
`psutil`.

- [ ] Replace `[project].dependencies` with the real runtime set.
- [ ] Carry over the macOS-gated `pyobjc-framework-Quartz; sys_platform == "darwin"` already in
      `requirements.txt` (needed by the CapCut export backend).
- [ ] Reconcile `requirements.txt` / `requirements-mcp.txt` with `pyproject.toml` so there is one
      source of truth; keep the `mcp` extra for the MCP-only dependencies.
- [ ] Decide whether `ffmpeg` (the binary, not the Python package) belongs in documented
      prerequisites — it is a hard runtime dependency of `downloader.py`,
      `get_duration_impl.py` and the ffmpeg export backend, but cannot be pip-installed.

**Validation:** `pip install .` into a clean venv, then start both servers and run one
`create_draft` → `add_video` → `save_draft` cycle.

**Completion criteria:** a clean-venv install from `pyproject.toml` alone runs the servers with
no `ModuleNotFoundError`.

### Phase A2 — Resolve the licence inconsistency

Three sources disagree and the referenced file does not exist:

| Source | Says |
|---|---|
| `README.md:7` (badge) and `README.md:533` | Apache 2.0, linking to `LICENSE` |
| `pyproject.toml:14` | `License :: OSI Approved :: MIT License` |
| Repository root | **No `LICENSE` file at all** |

- [ ] Confirm the intended licence (the README asserts Apache 2.0 in two places, so that is the
      likely intent — **owner decision required**).
- [ ] Add the full licence text as `LICENSE`.
- [ ] Correct the `pyproject.toml` classifier to match.
- [ ] Check `pyJianYingDraft/` and `template/` for third-party licence obligations that need
      attribution.

**Completion criteria:** one licence asserted consistently in all three places, with the file present.

### Phase A3 — Remove the remaining fork references

Fork references were cleaned from the README in `28dec9c` and from the MCP docs in `2563d2d`, but
`pyproject.toml` was missed:

- `pyproject.toml:43` `Homepage = "https://github.com/ashreo/CapCutAPI"`
- `pyproject.toml:44` `Repository = ".../ashreo/CapCutAPI.git"`
- `pyproject.toml:45` `Issues = ".../ashreo/CapCutAPI/issues"`

- [ ] Repoint all three at `skyionblue/CapCutAPI`.
- [ ] Sweep the tree for any other stale upstream references
      (`grep -ri "ashreo\|upstream" --include=* .`).

**Completion criteria:** no references to the upstream repository remain outside git history.

---

## Tier B — Reliability

### Phase B1 — Persist drafts across restarts *(highest value)*

**The problem.** `DRAFT_CACHE` is a plain in-memory `OrderedDict` (`draft_cache.py:6`). Nothing
writes a draft to disk until `save_draft` runs. If the process restarts — a crash, a config
reload, an MCP client restart — every in-progress draft is unrecoverable:

- `save_draft_impl.py:57` → task fails with *"Draft {id} does not exist in cache"*
- `save_draft_impl.py:542` → `query_script` returns `None`

There is no path to rebuild the lost draft; the assistant must redo every edit from scratch.

This is the most consequential gap in the project for AI-driven use, where a single video may be
assembled over many tool calls spanning minutes.

- [ ] Choose a persistence point. Preferred: write the draft's script JSON to a working directory
      (e.g. `drafts/<draft_id>.json`) on every mutation, since `Script_file.dumps()` already
      produces exactly this.
- [ ] Rehydrate on cache miss: when `draft_id` is absent from `DRAFT_CACHE`, attempt to load it
      from disk before failing.
- [ ] Keep the LRU cache as a hot path in front of the store — do not change its semantics.
- [ ] Add `draft_id` existence to the error messages so a caller can distinguish "never existed"
      from "evicted/lost".
- [ ] Consider a TTL/cleanup policy so the directory does not grow unbounded.
- [ ] Verify concurrency: mutations may arrive from Flask request threads and MCP calls at once.

**Risk:** rewriting the full draft JSON on every edit could be slow for very large drafts.
Mitigate by measuring first; if needed, debounce writes or persist on a timer.

**Validation:**
- [ ] `create_draft` → `add_video` → **restart the server** → `save_draft` succeeds.
- [ ] `query_script` returns the full timeline after a restart.

**Completion criteria:** no draft is lost to a process restart, and the failure message for a
genuinely unknown `draft_id` stays clear.

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
