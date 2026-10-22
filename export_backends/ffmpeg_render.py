"""Headless export: compile a saved CapCut draft into an ffmpeg filtergraph and render it.

Use this where there is no GUI — servers, CI, containers. It reproduces the timeline
STRUCTURE faithfully (cuts, trims, placement, transforms, audio mixing, basic text) but it
cannot reproduce CapCut's effects, filters, masks, animations, transitions or stickers:
those are stored only as CapCut effect IDs and are resolved by CapCut's own renderer.

Everything it cannot reproduce is reported through fidelity_warnings. A caller must never be
handed a silently degraded video — if fidelity matters, use backend="capcut".

Unlike the CapCut backend, this one CAN honour resolution, framerate and bitrate.
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from export_task_cache import add_fidelity_warning, update_export_task
from export_backends.draft_model import Draft, Segment, load_draft

logger = logging.getLogger('flask_video_generator')

DEFAULT_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

# drawtext needs a real font file when fontconfig is unavailable (common on macOS builds).
FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

VISUAL_KINDS = ("video", "photo")


class RenderError(Exception):
    """The headless render could not be produced."""


def _font_file() -> Optional[str]:
    return next((path for path in FONT_CANDIDATES if os.path.exists(path)), None)


def _atempo_chain(speed: float) -> List[str]:
    """atempo accepts 0.5-2.0 only, so compose stages for anything outside that range."""
    stages: List[str] = []
    remaining = float(speed)
    if remaining <= 0:
        return []
    while remaining > 2.0:
        stages.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        stages.append("atempo=0.5")
        remaining /= 0.5
    if abs(remaining - 1.0) > 1e-6:
        stages.append(f"atempo={remaining:.6f}")
    return stages


def _escape_drawtext(text: str) -> str:
    """drawtext has its own escaping rules on top of filtergraph escaping."""
    out = text.replace("\\", r"\\\\")
    for char in (":", "'", "%", ",", "[", "]", ";"):
        out = out.replace(char, "\\" + char)
    return out.replace("\n", r"\n")


def _output_size(draft: Draft, resolution: Optional[str]) -> Tuple[int, int]:
    """Resolve the output size.

    Defaults to the draft's canvas. A resolution like "1080p" sets the SHORTER side to that
    many pixels, preserving the canvas aspect — so it means 1920x1080 for a landscape draft
    and 1080x1920 for a portrait one.
    """
    width, height = draft.width, draft.height
    if not resolution:
        return width, height

    match = re.match(r"^\s*(\d+)\s*[pP]?\s*$", str(resolution))
    if not match:
        raise RenderError(
            f"Unrecognised resolution {resolution!r}. Use a form like '1080p' or '720'."
        )
    target_short = int(match.group(1))
    if width <= 0 or height <= 0:
        raise RenderError("Draft has no usable canvas size")

    short_side = min(width, height)
    factor = target_short / float(short_side)
    out_w = max(2, int(round(width * factor)))
    out_h = max(2, int(round(height * factor)))
    # H.264 requires even dimensions.
    return out_w - (out_w % 2), out_h - (out_h % 2)


def _segment_geometry(segment: Segment, canvas_w: int, canvas_h: int) -> Tuple[int, int, str, str]:
    """Size and position for one visual segment.

    CapCut fits the source inside the canvas preserving aspect, then applies the clip's own
    scale. transform_x/transform_y are in units of HALF the canvas width/height, with
    positive y meaning UP, so the sign is flipped for ffmpeg's top-left origin.
    """
    src_w = segment.width or canvas_w
    src_h = segment.height or canvas_h
    fit = min(canvas_w / float(src_w), canvas_h / float(src_h))
    out_w = max(2, int(round(src_w * fit * segment.scale_x)))
    out_h = max(2, int(round(src_h * fit * segment.scale_y)))
    out_w -= out_w % 2
    out_h -= out_h % 2

    # Rotation grows the bounding box, so position by expression against the real overlay size.
    x_expr = f"(({canvas_w}-overlay_w)/2)+({segment.transform_x}*{canvas_w / 2.0:.4f})"
    y_expr = f"(({canvas_h}-overlay_h)/2)-({segment.transform_y}*{canvas_h / 2.0:.4f})"
    return out_w, out_h, x_expr, y_expr


def build_command(
    draft: Draft,
    out_path: str,
    resolution: Optional[str] = None,
    framerate: Optional[int] = None,
    bitrate: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Compile the draft into an ffmpeg command. Returns (argv, warnings)."""
    warnings: List[str] = list(draft.warnings)
    canvas_w, canvas_h = _output_size(draft, resolution)
    fps = float(framerate or draft.fps or 30.0)

    # Index sets, not value membership: Segment is a dataclass, so two identical clips
    # would compare equal and collide under `in`.
    visual = {i for i, s in enumerate(draft.segments) if s.kind in VISUAL_KINDS and s.visible}
    audible = {
        i for i, s in enumerate(draft.segments)
        if (s.kind == "audio" or (s.kind == "video" and s.has_audio)) and s.volume > 0
    }
    texts = [(i, s) for i, s in enumerate(draft.segments) if s.kind == "text" and s.text and s.visible]

    duration = draft.duration or max(
        [s.target_start + s.target_duration for s in draft.segments] or [0.0]
    )
    if duration <= 0:
        raise RenderError("Draft timeline has zero duration; nothing to render")

    argv: List[str] = ["ffmpeg", "-hide_banner", "-y"]
    filters: List[str] = []
    inputs_of: Dict[int, int] = {}      # index in draft.segments -> ffmpeg input index
    input_index = 0

    # Media inputs. Trim at the input with -ss/-t so ffmpeg can seek rather than decode-and-drop.
    for position, segment in enumerate(draft.segments):
        if position not in visual and position not in audible:
            continue
        if segment.kind == "photo":
            argv += ["-loop", "1", "-t", f"{max(segment.target_duration, 0.04):.6f}", "-i", segment.path]
        else:
            source_len = segment.source_duration or segment.target_duration
            argv += [
                "-ss", f"{max(segment.source_start, 0.0):.6f}",
                "-t", f"{max(source_len, 0.04):.6f}",
                "-i", segment.path,
            ]
        inputs_of[position] = input_index
        input_index += 1

    # Base canvas.
    filters.append(f"color=c=black:s={canvas_w}x{canvas_h}:r={fps}:d={duration:.6f}[base]")

    # Composite visual segments bottom-to-top in timeline order.
    current = "base"
    for position, segment in enumerate(draft.segments):
        if position not in visual:
            continue
        idx = inputs_of[position]
        out_w, out_h, x_expr, y_expr = _segment_geometry(segment, canvas_w, canvas_h)

        chain = [f"[{idx}:v]"]
        steps = [f"scale={out_w}:{out_h}"]
        if segment.flip_h:
            steps.append("hflip")
        if segment.flip_v:
            steps.append("vflip")
        if abs(segment.rotation) > 1e-6:
            # ffmpeg's rotate takes radians, counter-clockwise; CapCut stores clockwise degrees.
            steps.append(
                f"rotate={-segment.rotation}*PI/180:ow=rotw({-segment.rotation}*PI/180):"
                f"oh=roth({-segment.rotation}*PI/180):c=none"
            )
        steps.append("format=rgba")
        if segment.alpha < 1.0:
            steps.append(f"colorchannelmixer=aa={segment.alpha:.4f}")
        if segment.kind != "photo" and abs(segment.speed - 1.0) > 1e-6:
            steps.append(f"setpts=PTS/{segment.speed:.6f}")
        steps.append(f"setpts=PTS-STARTPTS+{segment.target_start:.6f}/TB")
        chain.append(",".join(steps))
        label = f"v{position}"
        chain.append(f"[{label}]")
        filters.append("".join(chain))

        end = segment.target_start + segment.target_duration
        nxt = f"ov{position}"
        filters.append(
            f"[{current}][{label}]overlay=x='{x_expr}':y='{y_expr}':"
            f"eof_action=pass:shortest=0:"
            f"enable='between(t,{segment.target_start:.6f},{end:.6f})'[{nxt}]"
        )
        current = nxt

    # Text segments, drawn over the composite.
    font = _font_file()
    if texts and not font:
        warnings.append(
            "Text segments were NOT rendered: no usable font file was found for drawtext."
        )
    elif texts:
        for position, segment in texts:
            size = int(segment.font_size * canvas_h) if 0 < segment.font_size < 1 else int(segment.font_size or 48)
            size = max(8, size)
            colour = segment.font_color or "white"
            end = segment.target_start + segment.target_duration
            x_px = f"(w-text_w)/2+({segment.transform_x}*{canvas_w / 2.0:.4f})"
            y_px = f"(h-text_h)/2-({segment.transform_y}*{canvas_h / 2.0:.4f})"
            nxt = f"t{position}"
            filters.append(
                f"[{current}]drawtext=fontfile='{font}':text='{_escape_drawtext(segment.text)}':"
                f"fontsize={size}:fontcolor={colour}:x={x_px}:y={y_px}:"
                f"enable='between(t,{segment.target_start:.6f},{end:.6f})'[{nxt}]"
            )
            current = nxt
        warnings.append(
            "Text was rendered with ffmpeg's drawtext: the font, stroke, shadow, background "
            "box and any text animation from CapCut are NOT reproduced."
        )

    filters.append(f"[{current}]format=yuv420p[vout]")

    # Audio: trim, retime, level, delay to its timeline position, then mix.
    audio_labels: List[str] = []
    for position, segment in enumerate(draft.segments):
        if position not in audible:
            continue
        idx = inputs_of[position]
        steps: List[str] = []
        steps += _atempo_chain(segment.speed)
        if abs(segment.volume - 1.0) > 1e-6:
            steps.append(f"volume={segment.volume:.4f}")
        delay_ms = int(round(segment.target_start * 1000))
        if delay_ms > 0:
            steps.append(f"adelay={delay_ms}|{delay_ms}")
        steps.append("apad")
        label = f"a{position}"
        filters.append(f"[{idx}:a]{','.join(steps) if steps else 'anull'}[{label}]")
        audio_labels.append(label)

    if audio_labels:
        if len(audio_labels) == 1:
            filters.append(f"[{audio_labels[0]}]atrim=0:{duration:.6f},asetpts=PTS-STARTPTS[aout]")
        else:
            joined = "".join(f"[{label}]" for label in audio_labels)
            filters.append(
                f"{joined}amix=inputs={len(audio_labels)}:normalize=0:dropout_transition=0,"
                f"atrim=0:{duration:.6f},asetpts=PTS-STARTPTS[aout]"
            )
    else:
        warnings.append("The rendered video has no audio: no audible segments were found.")

    argv += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio_labels:
        argv += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    argv += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", f"{fps}",
        "-t", f"{duration:.6f}",
        "-movflags", "+faststart",
    ]
    if bitrate:
        argv += ["-b:v", str(bitrate)]
    argv += ["-progress", "pipe:1", "-nostats", out_path]
    return argv, warnings


def _run(argv: List[str], task_id: str, duration: float, timeout: int) -> None:
    """Run ffmpeg, streaming its progress into the task cache."""
    logger.info("Export %s: %s", task_id, " ".join(argv[:12]) + " ...")
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if line.startswith("out_time_ms="):
                try:
                    seconds = int(line.split("=", 1)[1].strip()) / 1_000_000.0
                except ValueError:
                    continue
                if duration > 0:
                    percent = 10 + int(min(85.0, (seconds / duration) * 85.0))
                    update_export_task(
                        task_id, progress=percent,
                        message=f"Rendering with ffmpeg ({seconds:.1f}s of {duration:.1f}s)",
                    )
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        raise RenderError(f"ffmpeg did not finish within {timeout}s")
    finally:
        if process.poll() is None:
            process.kill()

    if process.returncode != 0:
        stderr = (process.stderr.read() if process.stderr else "") or ""
        tail = "\n".join(stderr.strip().splitlines()[-12:])
        raise RenderError(f"ffmpeg failed (exit {process.returncode}):\n{tail}")


def export(task_id: str, draft_id: str, options: Dict[str, Any]) -> str:
    """Render a saved draft headlessly. Returns the produced file's path."""
    folder = options.get("draft_folder") or DEFAULT_DRAFT_FOLDER
    update_export_task(task_id, progress=8, message="Reading draft timeline")
    draft = load_draft(draft_id, folder)

    requested = options.get("output_path")
    if requested and not os.path.isdir(requested) and not str(requested).endswith(os.sep):
        out_path = os.path.abspath(os.path.expanduser(requested))
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    else:
        out_path = os.path.join(tempfile.mkdtemp(prefix="capcut-export-"), f"{draft_id}.mp4")

    argv, warnings = build_command(
        draft, out_path,
        resolution=options.get("resolution"),
        framerate=options.get("framerate"),
        bitrate=options.get("bitrate"),
    )
    for warning in warnings:
        add_fidelity_warning(task_id, warning)

    duration = draft.duration
    timeout = int(options.get("timeout") or 1800)
    update_export_task(task_id, progress=10, message="Rendering with ffmpeg")
    _run(argv, task_id, duration, timeout)

    if not os.path.exists(out_path):
        raise RenderError("ffmpeg reported success but produced no file")
    return out_path
