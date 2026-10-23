# CapCutAPI Enhancements Plan

**Created:** 2026-10-22
**Status (2026-10-23):** Tier A, Tier B and Phase C1 COMPLETE; CI deferred by decision.
C2 Group 1 defects fixed, the remaining 11 divergences BLOCKED on a behaviour decision.
C5 in progress (836 → 479 findings).
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

### Phase B2 — Make `save_draft` asynchronous — **COMPLETE (2026-10-23)**

- [x] Re-enabled the background thread that had been commented out at
      `save_draft_impl.py:277-282`, following the pattern proven by `export_impl.py`.
- [x] **No breaking change** (owner decision): `wait` defaults to `True`, so every existing
      HTTP and MCP caller keeps the synchronous result it depends on. `wait=False` returns a
      `task_id` immediately.
- [x] Progress continues to flow into `DRAFT_TASKS`; `query_draft_status` is the poll.
- [x] Rewrote the `save_draft` and `query_draft_status` tool descriptions — the latter had
      described itself as "mostly a safety net", which actively discouraged the polling the
      async path depends on.
- [x] Exposed `wait` on the HTTP route and in the MCP tool schema; documented both in the
      README and the MCP docs.

**Ordering bug caught and prevented:** `mcp_server` called `place_draft_locally(draft_id)`
immediately after `save_draft_impl`. Under an async save that would have moved a draft folder
**before it existed**. `save_draft_impl` now takes an `on_complete` callback that the worker
runs only after a *successful* save, on whichever thread did the work, recording the result as
`local_path` on the task so an async caller can still discover where the draft landed. A
failure in that step is logged and does not fail the save.

**Validated:** 13 tests (`tests/test_save_draft_async.py`) covering the synchronous default,
non-blocking return, worker-thread execution, completion, the post-save step running only on
success, its failure being contained, and — at the MCP dispatch level — that placement observes
a *completed* save in both modes.

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

### Phase C5 — Burn down the legacy lint debt — **IN PROGRESS (2026-10-23)**

Started at **836** findings; now at **479**.

#### Done

- [x] **Whitespace pass** over the project's own modules — trailing whitespace, whitespace in
      blank lines, missing final newlines, inline comment spacing, spacing around commas,
      operators and keyword defaults. Provably behaviour-free: `git diff -w` was empty, 332
      insertions against 332 deletions.
- [x] **Unused locals (F841, 8 of them) — all resolved, and one was a real bug.**
      Seven were `imported_track = script.get_imported_track(...)`, an existence probe whose
      binding was never used; the call is kept, the binding dropped. The eighth was
      `draft_folder` in `/generate_draft_url`, a parameter the route accepted and then ignored.
- [x] **Bare excepts (E722, 7 of them) narrowed to `except Exception`.** Same behaviour for
      ordinary errors, but `KeyboardInterrupt` and `SystemExit` now propagate instead of being
      swallowed by validation guards.

#### Real defect found and fixed

`/generate_draft_url` built its URL by hand as `?=<draft_id>` — **a query string with no
parameter name** — while `util.generate_draft_url`, used by the MCP tool *and* by every
`add_*` response from the same server, emits `?draft_id=<draft_id>`. The route had the helper
imported already and did not call it. Now it does, which fixes the URL and removes the
duplication. Pinned by a regression test, verified to fail against the old code.

#### Remaining

- [ ] `example.py` (212) — standalone examples, deliberately skipped this pass.
- [ ] `pyJianYingDraft` (137) — vendored library, deserves its own pass.
- [ ] `E501` line-length and `E128` continuation-indent across the project: manual wrapping,
      tedious but low risk.
- [ ] `E402` module-level imports not at top (24) — structural, matches the existing pattern in
      those files; leave unless the import blocks are restructured.

**Completion criteria:** `flake8 .` is clean from the repository root.

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
- **The MCP server advertises exactly two tools, and that is a hard constraint.** Every
  advertised tool's schema is loaded into the model's context for the whole session, and this
  toolset is large with detailed schemas, so the gateway keeps the advertised surface at
  `search_tools`/`invoke_tool` and moves discovery behind them. Any change that registers
  catalogue entries as individual MCP tools is a regression regardless of how clean the code
  looks. Enforced by `tests/test_gateway_surface.py`.
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
