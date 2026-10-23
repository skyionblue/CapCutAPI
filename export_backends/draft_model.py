"""Read a saved CapCut draft into a plain structure the ffmpeg renderer can compile.

This reads `draft_info.json` from the draft folder on disk — the same file CapCut itself
reads — so the headless renderer and the CapCut backend export the same thing.

Timebase throughout CapCut's draft format is MICROSECONDS.
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

US = 1_000_000.0


@dataclass
class Segment:
    """One clip placed on a track."""
    kind: str                      # "video" | "photo" | "audio" | "text" | "sticker"
    material_id: str
    path: str = ""                 # source file, for media segments
    source_start: float = 0.0      # seconds into the source
    source_duration: float = 0.0
    target_start: float = 0.0      # seconds on the timeline
    target_duration: float = 0.0
    speed: float = 1.0
    volume: float = 1.0
    visible: bool = True
    has_audio: bool = False
    width: int = 0
    height: int = 0
    # clip settings
    scale_x: float = 1.0
    scale_y: float = 1.0
    transform_x: float = 0.0       # units of HALF canvas width
    transform_y: float = 0.0       # units of HALF canvas height; positive is up
    rotation: float = 0.0          # clockwise degrees
    alpha: float = 1.0
    flip_h: bool = False
    flip_v: bool = False
    # text
    text: str = ""
    font_size: float = 0.0
    font_color: str = ""
    # anything attached that the renderer cannot reproduce
    unsupported: List[str] = field(default_factory=list)


@dataclass
class Draft:
    draft_id: str
    folder: str
    width: int
    height: int
    fps: float
    duration: float                # seconds
    segments: List[Segment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def draft_info_path(draft_id: str, draft_folder: str) -> str:
    return os.path.join(draft_folder, draft_id, "draft_info.json")


def _clip(segment: Dict[str, Any], out: Segment) -> None:
    clip = segment.get("clip") or {}
    scale = clip.get("scale") or {}
    transform = clip.get("transform") or {}
    flip = clip.get("flip") or {}
    out.scale_x = float(scale.get("x", 1.0) or 1.0)
    out.scale_y = float(scale.get("y", 1.0) or 1.0)
    out.transform_x = float(transform.get("x", 0.0) or 0.0)
    out.transform_y = float(transform.get("y", 0.0) or 0.0)
    out.rotation = float(clip.get("rotation", 0.0) or 0.0)
    out.alpha = float(clip.get("alpha", 1.0) if clip.get("alpha") is not None else 1.0)
    out.flip_h = bool(flip.get("horizontal", False))
    out.flip_v = bool(flip.get("vertical", False))


def extract_text(material: Dict[str, Any]) -> Dict[str, Any]:
    """CapCut stores text as a JSON blob in `content`. Pull out the parts callers need.

    Shared with the SRT exporter, which needs only `text`.
    """
    result = {"text": "", "size": 0.0, "color": ""}
    raw = material.get("content")
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            parsed = json.loads(raw)
            result["text"] = parsed.get("text", "") or ""
            styles = parsed.get("styles") or []
            if styles:
                style = styles[0]
                result["size"] = float(style.get("size", 0) or 0)
                fill = ((style.get("fill") or {}).get("content") or {}).get("solid") or {}
                rgb = fill.get("color")
                if isinstance(rgb, list) and len(rgb) >= 3:
                    result["color"] = "0x%02X%02X%02X" % tuple(
                        max(0, min(255, int(round(float(c) * 255)))) for c in rgb[:3]
                    )
        except (ValueError, TypeError, KeyError):
            pass
    elif isinstance(raw, str):
        result["text"] = raw
    return result


# Material collections whose presence means the timeline uses something the renderer
# cannot reproduce. These are CapCut effect IDs resolved only by CapCut's own renderer.
UNSUPPORTED_COLLECTIONS = {
    "material_animations": "clip animations (intro/outro/combo)",
    "transitions": "transitions between clips",
    "video_effects": "video effects",
    "effects": "effects",
    "common_mask": "masks",
    "stickers": "stickers",
    "chromas": "chroma key",
    "filters": "filters",
    "video_tracking": "video tracking",
    "text_templates": "text templates",
    "plugin_effects": "plugin effects",
}


# CapCut rewrites absolute media paths to a relocatable token once it opens a draft.
_DRAFT_PATH_PLACEHOLDER = re.compile(r"^##_draftpath_placeholder_[^#]*_##[/\\]?")


def resolve_path(path: str, draft_folder: str) -> str:
    """Expand CapCut's draft-relative path token into a usable absolute path.

    Shared with the draft bundler, which rewrites paths back into this form.
    """
    if not path:
        return ""
    stripped = _DRAFT_PATH_PLACEHOLDER.sub("", path)
    if stripped != path:
        return os.path.join(draft_folder, stripped)
    return path


@lru_cache(maxsize=None)
def _probe_has_audio(path: str) -> bool:
    """Ask ffprobe whether a file carries an audio stream.

    Drafts written by this API omit ``has_audio`` entirely, so its absence says nothing about
    the media; CapCut sets it only for drafts it has opened itself. Probing keeps both cases
    correct. Never raises - on any failure the caller keeps the recorded metadata.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "audio" in process.stdout


def load_draft(draft_id: str, draft_folder: str) -> Draft:
    """Parse a saved draft into Segments, recording what cannot be rendered."""
    info_path = draft_info_path(draft_id, draft_folder)
    if not os.path.exists(info_path):
        raise FileNotFoundError(
            f"No draft_info.json for draft {draft_id!r} at {info_path}. "
            f"Run save_draft first so the draft exists on disk."
        )
    with open(info_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    canvas = data.get("canvas_config") or {}
    draft = Draft(
        draft_id=draft_id,
        folder=os.path.join(draft_folder, draft_id),
        width=int(canvas.get("width") or 1080),
        height=int(canvas.get("height") or 1920),
        fps=float(data.get("fps") or 30.0),
        duration=float(data.get("duration") or 0) / US,
    )

    materials = data.get("materials") or {}
    videos = {m["id"]: m for m in (materials.get("videos") or []) if "id" in m}
    audios = {m["id"]: m for m in (materials.get("audios") or []) if "id" in m}
    texts = {m["id"]: m for m in (materials.get("texts") or []) if "id" in m}

    # Record timeline-wide features the renderer cannot reproduce.
    for key, label in UNSUPPORTED_COLLECTIONS.items():
        count = len(materials.get(key) or [])
        if count:
            draft.warnings.append(
                f"{count} {label} in this draft were NOT rendered: they are CapCut effect IDs "
                f"that only CapCut's renderer can resolve. Use backend='capcut' for full fidelity."
            )

    if data.get("keyframes") and any((data.get("keyframes") or {}).values()):
        draft.warnings.append(
            "Keyframe animation was NOT rendered; clips use their static transform values."
        )

    for track in data.get("tracks") or []:
        track_type = track.get("type")
        for raw in track.get("segments") or []:
            source = raw.get("source_timerange") or {}
            target = raw.get("target_timerange") or {}
            segment = Segment(
                kind=track_type,
                material_id=raw.get("material_id", ""),
                source_start=float(source.get("start", 0) or 0) / US,
                source_duration=float(source.get("duration", 0) or 0) / US,
                target_start=float(target.get("start", 0) or 0) / US,
                target_duration=float(target.get("duration", 0) or 0) / US,
                speed=float(raw.get("speed", 1.0) or 1.0),
                volume=float(raw.get("volume", 1.0) if raw.get("volume") is not None else 1.0),
                visible=bool(raw.get("visible", True)),
            )
            _clip(raw, segment)

            material: Optional[Dict[str, Any]] = None
            if segment.material_id in videos:
                material = videos[segment.material_id]
                segment.kind = material.get("type") or "video"   # "video" or "photo"
                segment.path = resolve_path(material.get("path") or "", draft.folder)
                recorded_audio = material.get("has_audio")
                segment.has_audio = (
                    bool(recorded_audio) if recorded_audio is not None
                    else _probe_has_audio(segment.path)
                )
                segment.width = int(material.get("width") or 0)
                segment.height = int(material.get("height") or 0)
            elif segment.material_id in audios:
                material = audios[segment.material_id]
                segment.kind = "audio"
                segment.path = resolve_path(material.get("path") or "", draft.folder)
                segment.has_audio = True
            elif segment.material_id in texts:
                material = texts[segment.material_id]
                segment.kind = "text"
                extracted = extract_text(material)
                segment.text = extracted["text"]
                segment.font_size = extracted["size"]
                segment.font_color = extracted["color"]
            else:
                # Sticker or some other material type the renderer has no handling for.
                segment.kind = track_type or "unknown"

            if segment.kind in ("video", "photo", "audio") and not segment.path:
                draft.warnings.append(
                    f"A {segment.kind} segment at {segment.target_start:.2f}s has no file path "
                    f"and was skipped."
                )
                continue
            if segment.path and not os.path.exists(segment.path):
                draft.warnings.append(
                    f"Source file missing, segment skipped: {segment.path}"
                )
                continue

            draft.segments.append(segment)

    return draft
