"""Export a draft's text segments back out as an SRT file.

`add_subtitle` reads SRT in; this completes the round trip. Captions written or adjusted in a
draft can be pulled back out for upload alongside the exported video, which is what the major
platforms want as a separate file rather than burned into the frame.

Reads the live draft (cache, falling back to the persisted store), so it works before
`save_draft` as well as after.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from draft_cache import get_script
from export_backends.draft_model import extract_text

logger = logging.getLogger('flask_video_generator')

US = 1_000_000.0


def format_timestamp(seconds: float) -> str:
    """SRT timestamps are HH:MM:SS,mmm — comma for the decimal separator, not a period."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def collect_cues(draft_data: Dict[str, Any], track_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Text segments as cues, ordered by start time."""
    texts = {m["id"]: m for m in (draft_data.get("materials") or {}).get("texts") or [] if "id" in m}
    cues: List[Dict[str, Any]] = []

    for track in draft_data.get("tracks") or []:
        if track.get("type") != "text":
            continue
        if track_name is not None and track.get("name") != track_name:
            continue
        for segment in track.get("segments") or []:
            material = texts.get(segment.get("material_id"))
            if material is None:
                continue
            content = extract_text(material).get("text", "").strip()
            if not content:
                continue
            timerange = segment.get("target_timerange") or {}
            start = float(timerange.get("start", 0) or 0) / US
            duration = float(timerange.get("duration", 0) or 0) / US
            cues.append({"start": start, "end": start + duration, "text": content})

    cues.sort(key=lambda cue: (cue["start"], cue["end"]))
    return cues


def build_srt(cues: List[Dict[str, Any]], time_offset: float = 0.0) -> str:
    """Render cues as SRT. Numbering is sequential over the sorted cues, as the format expects."""
    blocks = []
    for index, cue in enumerate(cues, start=1):
        start = format_timestamp(cue["start"] + time_offset)
        end = format_timestamp(cue["end"] + time_offset)
        blocks.append(f"{index}\n{start} --> {end}\n{cue['text']}\n")
    return "\n".join(blocks)


def export_subtitles_impl(draft_id: str, output_path: Optional[str] = None,
                          track_name: Optional[str] = None,
                          time_offset: float = 0.0) -> Dict[str, Any]:
    """Write a draft's text segments out as SRT.

    :param draft_id: Draft to read
    :param output_path: Where to write the .srt. Omit to get the content back inline only.
    :param track_name: Limit to one text track; omit to include every text track
    :param time_offset: Seconds to shift every cue, for syncing against a trimmed export
    :return: {"success", "srt", "cue_count", "output_path"} or {"success": False, "error"}
    """
    if not draft_id:
        return {"success": False, "error": "draft_id is required"}

    script = get_script(draft_id)
    if script is None:
        return {
            "success": False,
            "error": f"Draft {draft_id!r} does not exist in cache or the draft store.",
        }

    try:
        draft_data = json.loads(script.dumps())
    except (ValueError, TypeError) as e:
        return {"success": False, "error": f"Could not read draft {draft_id}: {e}"}

    cues = collect_cues(draft_data, track_name=track_name)
    srt = build_srt(cues, time_offset=time_offset)

    written = ""
    if output_path:
        target = os.path.abspath(os.path.expanduser(output_path))
        if os.path.isdir(target) or output_path.endswith(os.sep):
            target = os.path.join(target, f"{draft_id}.srt")
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(srt)
        written = target
        logger.info("Wrote %d subtitle cues for draft %s to %s", len(cues), draft_id, target)

    result: Dict[str, Any] = {
        "success": True,
        "srt": srt,
        "cue_count": len(cues),
        "output_path": written,
    }
    if not cues:
        result["message"] = (
            f"Draft {draft_id} has no text segments"
            + (f" on track {track_name!r}" if track_name else "")
            + ", so the SRT is empty."
        )
    return result
