# CapCutAPI Enhancements Plan

**Created:** 2026-10-22
**Status:** Proposed — not started
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

### Phase C1 — Add a test suite and CI

There are no automated tests. `test_mcp_client.py` is a manual connectivity script, not a suite.
Everything in the export work was verified by hand and none of it is repeatable.

The export code is unusually well suited to testing because its core is **pure**: given a draft
JSON, `draft_model.load_draft` produces a parsed model and `ffmpeg_render.build_command` produces
an argv list — no GUI, no rendering, no network.

- [ ] Add `pytest` (dev dependency) and a `tests/` package.
- [ ] Unit tests for `draft_model.load_draft`: canvas/fps/duration parsing, segment trims and
      transforms, and that each unsupported material collection produces a fidelity warning.
- [ ] Unit tests for `ffmpeg_render.build_command`: overlay count matches visible segments,
      `-ss`/`-t` match segment source ranges, `_output_size` resolution maths (including the
      "shorter side" rule in both orientations), and `_atempo_chain` outside the 0.5–2.0 range.
- [ ] Unit tests for `export_task_cache`: LRU eviction, `fidelity_warnings` accumulation,
      `not_found` for unknown ids.
- [ ] Tests for `export_impl.resolve_backend` using monkeypatched availability probes.
- [ ] Commit a small fixture draft JSON so tests need no CapCut installation.
- [ ] Mark anything requiring a GUI as `@pytest.mark.gui` and exclude it by default.
- [ ] GitHub Actions workflow running `flake8` and `pytest` on push and PR.

**Why this first among Tier C:** it protects the export work from a silent CapCut draft-format
change, which would otherwise surface as a corrupted render rather than an error.

**Completion criteria:** `pytest` passes from a clean checkout with no CapCut installed, and CI
runs on every PR.

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
C1          ── independent; prerequisite for C2
C2          ── REQUIRES C1
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
