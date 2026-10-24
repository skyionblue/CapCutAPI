"""Long text must wrap inside the frame rather than run off both edges.

These expectations are not deduced from the format -- they were measured by rendering
one draft through real CapCut with four captions carrying the same string and differing
only in these two fields:

    force_apply_line_max_width=False, fixed_width=648  -> wraps, full text
    force_apply_line_max_width=True,  fixed_width=648  -> wraps, full text (identical)
    force_apply_line_max_width=True,  fixed_width=-1   -> wraps, full text
    force_apply_line_max_width=False, fixed_width=-1   -> CLIPPED at both frame edges

So fixed_width is what drives the break, and the flag only matters when nothing else
constrains the width. That last row is exactly what add_text used to produce.
"""

import json

import pytest

from capcut_draft.text_segment import Text_segment
from capcut_draft.time_util import Timerange

US = 1_000_000
LONG = "Second clip running with a deliberately long caption"


def material(**kwargs):
    return Text_segment(LONG, Timerange(0, 4 * US), **kwargs).export_material()


def test_unconstrained_text_wraps_by_default():
    """The measured clipping case must not be reachable without asking for it."""
    m = material()
    assert m["fixed_width"] == -1, "this is the case the flag has to cover"
    assert m["force_apply_line_max_width"] is True


def test_wrapping_can_be_turned_off_for_text_meant_to_overflow():
    assert material(wrap_lines=False)["force_apply_line_max_width"] is False


def test_a_fixed_width_still_constrains_the_text():
    m = material(fixed_width=648)
    assert m["fixed_width"] == 648


def test_the_wrap_width_is_a_fraction_of_the_frame():
    assert material()["line_max_width"] == 0.82


@pytest.mark.parametrize("width,height,expected", [
    (1080, 1920, int(1080 * 0.6)),
    (720, 1280, int(720 * 0.6)),
    (1920, 1080, int(1920 * 0.7)),
    (3840, 2160, int(3840 * 0.7)),
])
def test_subtitle_width_follows_the_draft_canvas(width, height, expected, tmp_path):
    """import_srt used to hardcode 1080/1920, so every other canvas got the wrong width."""
    import capcut_draft as draft

    srt = tmp_path / "s.srt"
    srt.write_text(f"1\n00:00:00,000 --> 00:00:04,000\n{LONG}\n", encoding="utf-8")

    script = draft.Script_file(width, height)
    script.import_srt(str(srt), track_name="subs")

    texts = json.loads(script.dumps())["materials"]["texts"]
    assert len(texts) == 1
    assert texts[0]["fixed_width"] == expected


def test_add_text_produces_the_combination_that_renders_wrapped():
    """Pins the end-to-end result: add_text's output must match the measured good case."""
    from tool_registry import execute_tool
    from draft_cache import get_script

    draft_id = execute_tool("create_draft", {"width": 1080, "height": 1920})["result"]["draft_id"]
    execute_tool("add_text", {"draft_id": draft_id, "text": LONG, "start": 0, "end": 4})

    text = json.loads(get_script(draft_id).dumps())["materials"]["texts"][0]
    assert text["fixed_width"] == -1
    assert text["force_apply_line_max_width"] is True
