# Rename `pyJianYingDraft` to `capcut_draft`

**Status:** COMPLETE (2026-10-23)

## Objective

Remove the `pyJianYingDraft` name from the working tree. The directory is not a dependency --
it is vendored first-party source (29 tracked files) -- so this is a package rename, not a
removal. Record the code's provenance in a `NOTICE` file so the rename does not erase where it
came from.

## Scope

Repo-wide, the name appears in 25 files (excluding `.git`, `build/`, `__pycache__`, egg-info):

| Where | Count | Nature |
|---|---|---|
| `.py` import lines outside the package | 49 | `import pyJianYingDraft as draft`, `from pyJianYingDraft.metadata.… import …` |
| Absolute self-imports inside the package | 5 | `track.py`, `audio_segment.py`, `text_segment.py`, `video_segment.py` |
| Markdown docs | 10 lines | the three `*-plan.md` files and `MCP_Documentation_English.md` |
| Config | 2 lines | `pyproject.toml` `packages`, `.flake8` exclude path |

The remaining 75 intra-package imports are already relative (`from .x import y`) and need no
change.

## Non-scope / confirmed clean

- No `剪映` strings, no `JianYing` in docstrings, comments or JSON data.
- No dynamic (`importlib` / `__import__`) reference to the package name. The two `__import__`
  calls in `tests/test_dispatch_parity.py` target top-level impl modules.
- The draft JSON format itself carries no trace of the name, so no persisted draft in
  `drafts_store/` is invalidated by this change.
- `build/` and `capcut_api.egg-info/` hold stale copies of the old name but are untracked and
  gitignored. Removed locally; nothing to commit.

## Naming

`capcut_draft`. Every call site already aliases the package to `draft`
(`import pyJianYingDraft as draft`), so for most files only the import line changes. Plain
`draft` was rejected: it collides conceptually with `draft_cache.py` and `drafts_store/`.

## Tasks

- [x] `git mv pyJianYingDraft capcut_draft` (preserves history for all 29 files)
- [x] Rewrite the 49 external import lines
- [x] Rewrite the 5 absolute self-imports inside the package
- [x] `pyproject.toml` -- `packages = [...]`
- [x] `.flake8` -- exclude path
- [x] Docs: rewrite path references; leave the narrative sentences explaining *why* the code was
      vendored, which remain true
- [x] Add `NOTICE` recording provenance (see below)
- [x] Remove stale `build/` and `capcut_api.egg-info/`
- [x] Validate: `pip install -e .`, `pytest`, `flake8`

## Attribution decision

`enhancements-plan.md` Phase A2 (closed 2026-10-23) settled that this project asserts **no
licence at all** -- it is not distributed, and the upstream positions of
`sun-guannan/CapCutAPI` and `pyJianYingDraft` have never been confirmed. Renaming the directory
would otherwise remove the last in-tree trace of the code's origin.

`NOTICE` therefore records provenance as **fact only** and grants nothing. It must not name a
licence for the upstream work, because that position is still unconfirmed. This is consistent
with Phase A2, not a reversal of it: Phase A2 removed unfounded *claims of terms*; this records
*where the code came from*.

Revisit only if the project is ever published, at which point the upstream licensing positions
have to be established first.

## Risks

Low. The change is mechanical and compile-checked by the import graph: any missed reference
fails loudly at import time rather than silently. The validation step exercises every entry
point that imports the package.
