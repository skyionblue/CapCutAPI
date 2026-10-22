# Audio Detection & Path Placeholder Fix Plan

**Created:** 2026-10-22
**Status:** Complete — delivered 2026-10-22
**Scope:** `export_backends/draft_model.py` — two defects that make the ffmpeg backend render
drafts incorrectly. Does not touch the CapCut backend or the vendored `pyJianYingDraft`.

---

## 1. Summary

The headless ffmpeg backend silently drops audio for every draft this API creates, and cannot
resolve source paths for any draft CapCut has opened. Both were found while exporting eight
single-clip drafts cut from a VP9/Opus `.webm`.

| # | Defect | Symptom | Severity |
|---|---|---|---|
| **D1** | `has_audio` trusted blindly from draft metadata | **Silent video.** Every ffmpeg export of an API-created draft loses audio | High |
| **D2** | CapCut's `##_draftpath_placeholder_<uuid>_##` token not resolved | Segment skipped as "source file missing"; **empty render** | High |

Both are in the export read path, so fixing them corrects drafts already on disk.

---

## 2. Evidence

### D1 — audio dropped

`add_video` copies the source into the draft's assets and writes no `has_audio` key at all
(`pyJianYingDraft/local_materials.py:246` `Video_material.export_json` has no such field). The
draft therefore carries `has_audio: None`.

`export_backends/draft_model.py:186`:

```python
segment.has_audio = bool(material.get("has_audio"))   # bool(None) -> False
```

`export_backends/ffmpeg_render.py:139` only emits audio when `s.has_audio` is true, so the audio
is never mapped. Verified on draft `dfd_cat_1792697807_d5bbd1ad`:

| State | fidelity_warnings | audio in command |
|---|---|---|
| as-is | `The rendered video has no audio: no audible segments were found.` | none |
| `has_audio=True` | *(none)* | `[0:a]apad[a0];[a0]atrim=…[aout]` + `-map [aout]` |

The media genuinely has audio: `yeet.webm` is `V_VP9` + `A_OPUS`, and CapCut's own GUI export of
the same draft produced an `mp4` with both `vide` and `soun` tracks.

**Corroboration:** after CapCut opened draft `dfd_cat_1792697806_e9bdeb63` it wrote
`has_audio: true` into that draft itself. CapCut probes the media; this API does not.

### D2 — placeholder paths

Once CapCut opens a draft it rewrites absolute media paths to a relocatable token:

```
##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/assets/video/video_2baf…mp4
```

`draft_model` passes this to `os.path.exists()`, which fails, and the segment is dropped with
`Source file missing, segment skipped:`. A draft that CapCut has ever opened renders empty.

The token stands for the draft folder root, so it resolves by replacing it with the draft
directory.

---

## 3. Phase A — resolve path placeholders (D2)

- [x] Add `_resolve_path(path, draft_dir)` to `draft_model.py`: replace a leading
      `##_draftpath_placeholder_<anything>_##` segment with `draft_dir`.
- [x] Apply it wherever a material path is read (video/photo and audio branches).
- [x] Leave absolute paths untouched; keep the existing "source file missing" warning for paths
      that are genuinely absent after resolution.

**Validation:** `load_draft('dfd_cat_1792697806_e9bdeb63')` returns 1 segment and 0 warnings
(before the fix: 0 segments, 1 warning).

## 4. Phase B — probe for audio instead of trusting metadata (D1)

- [x] Add `_probe_has_audio(path)` using `ffprobe -select_streams a -show_entries stream=codec_type`,
      mirroring the subprocess/timeout conventions already in `get_duration_impl.py`.
- [x] Memoise per path — the same asset is read once per draft and these batches reuse one source.
- [x] At `draft_model.py:186`, probe **only when the metadata key is absent or `None`**; an
      explicit `true`/`false` from CapCut is authoritative and must still be honoured.
- [x] Fail soft: if `ffprobe` is missing or errors, fall back to the current `False` and leave the
      existing no-audio fidelity warning to inform the caller. Never raise from a probe.

**Validation:** all eight drafts report `has_audio=True`; `build_command` emits `[aout]` and
`-map [aout]`; zero fidelity warnings.

## 5. Phase C — re-render and verify

- [x] Export all 8 clips with `backend="ffmpeg"`.
- [x] Assert each output carries **both** a `vide` and a `soun` track, and that duration matches
      the draft's source timerange.
- [x] Report any `fidelity_warnings` rather than presenting a degraded render as complete.

---

## 6. Deliberately not changed

- **`pyJianYingDraft/local_materials.py`** — adding `has_audio` to `Video_material.export_json`
  would fix the metadata at write time, but diverges the vendored library from upstream for no
  additional benefit: probing in the export path already covers drafts from every writer,
  including those already on disk. Worth revisiting only if the vendored copy is forked anyway.
- **The CapCut GUI backend** — unaffected by both defects, since CapCut resolves its own
  placeholders and decodes media directly.

---

## 7. Success criteria

- [x] A draft CapCut has opened renders correctly through the ffmpeg backend.
- [x] An API-created draft from a `.webm` source renders **with audio**.
- [x] All 8 clips exported, each verified to contain an audio track.

---

## 8. Outcome

All three phases delivered and verified on 2026-10-22.

Eight clips cut from `yeet.webm` (V_VP9 + A_OPUS) rendered headlessly through the ffmpeg
backend in ~60s total, with **zero fidelity warnings**. Each output was verified by parsing its
MP4 atoms for track handlers and duration rather than trusting the task status:

| Clip | Duration | Expected | video | audio |
|---|---|---|---|---|
| clip_01 | 21.367s | 21.367 | yes | yes |
| clip_02 | 60.834s | 60.833 | yes | yes |
| clip_03 | 15.534s | 15.533 | yes | yes |
| clip_04 | 31.367s | 31.367 | yes | yes |
| clip_05 | 12.500s | 12.500 | yes | yes |
| clip_06 | 28.300s | 28.300 | yes | yes |
| clip_07 | 43.300s | 43.300 | yes | yes |
| clip_08 | 13.434s | 13.433 | yes | yes |

Clip 1 is the regression case for **D2**: CapCut had opened that draft and rewritten its media
path to a placeholder token, so before the fix it loaded as 0 segments with
`Source file missing`. All eight are the regression case for **D1** — every one rendered silent
beforehand.
