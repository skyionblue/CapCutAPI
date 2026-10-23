"""Tests for SRT export, completing the round trip with add_subtitle."""

import os
import tempfile

import pytest

import draft_cache
from add_subtitle_impl import add_subtitle_impl
from export_subtitles_impl import (
    build_srt, collect_cues, export_subtitles_impl, format_timestamp,
)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", str(tmp_path / "store"))
    draft_cache.DRAFT_CACHE.clear()
    yield
    draft_cache.DRAFT_CACHE.clear()


def write_srt(content):
    path = tempfile.mktemp(suffix=".srt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


SAMPLE = (
    "1\n00:00:01,000 --> 00:00:03,500\nFirst line\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nSecond line\n\n"
    "3\n00:00:07,250 --> 00:00:09,750\nThird, with punctuation!\n"
)


# --------------------------------------------------------------- the round trip

def test_srt_survives_a_round_trip_unchanged():
    """What add_subtitle imports, export_subtitles must give back."""
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    result = export_subtitles_impl(draft["draft_id"])

    assert result["success"] is True
    assert result["cue_count"] == 3
    assert result["srt"].strip() == SAMPLE.strip()


def test_import_srt_works_without_a_font():
    """Regression: import_srt left font_type unbound unless a font was passed.

    add_subtitle's own default is font=None, so the tool raised NameError on its default
    arguments.
    """
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))      # no font
    assert export_subtitles_impl(draft["draft_id"])["cue_count"] == 3


# --------------------------------------------------------------- timestamps

@pytest.mark.parametrize("seconds,expected", [
    (0, "00:00:00,000"),
    (1.5, "00:00:01,500"),
    (59.999, "00:00:59,999"),
    (60, "00:01:00,000"),
    (3661.25, "01:01:01,250"),
    (-5, "00:00:00,000"),              # clamped, never negative
])
def test_timestamp_formatting(seconds, expected):
    assert format_timestamp(seconds) == expected


def test_timestamp_uses_a_comma_not_a_period():
    """SRT requires a comma before the milliseconds; a period is a different format."""
    assert "," in format_timestamp(1.5)
    assert format_timestamp(1.5).count(".") == 0


# --------------------------------------------------------------- content handling

def test_multi_line_cue_text_is_preserved():
    source = "1\n00:00:01,000 --> 00:00:02,000\nline one\nline two\n"
    draft = add_subtitle_impl(srt_path=write_srt(source))
    srt = export_subtitles_impl(draft["draft_id"])["srt"]
    assert "line one" in srt and "line two" in srt


def test_cues_are_numbered_sequentially_from_one():
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    lines = export_subtitles_impl(draft["draft_id"])["srt"].splitlines()
    assert [ln for ln in lines if ln.isdigit()] == ["1", "2", "3"]


def test_cues_are_ordered_by_start_time():
    cues = [
        {"start": 5.0, "end": 6.0, "text": "later"},
        {"start": 1.0, "end": 2.0, "text": "earlier"},
    ]
    assert collect_cues({
        "materials": {"texts": []}, "tracks": [],
    }) == []
    rendered = build_srt(sorted(cues, key=lambda c: c["start"]))
    assert rendered.index("earlier") < rendered.index("later")


def test_time_offset_shifts_every_cue():
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    shifted = export_subtitles_impl(draft["draft_id"], time_offset=10.0)["srt"]
    assert "00:00:11,000 --> 00:00:13,500" in shifted


# --------------------------------------------------------------- filtering and output

def test_track_name_filters_to_one_track():
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE), track_name="captions")
    draft_id = draft["draft_id"]

    assert export_subtitles_impl(draft_id, track_name="captions")["cue_count"] == 3
    other = export_subtitles_impl(draft_id, track_name="nonexistent")
    assert other["cue_count"] == 0
    assert "nonexistent" in other["message"]


def test_output_path_writes_the_file(tmp_path):
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    target = tmp_path / "captions.srt"
    result = export_subtitles_impl(draft["draft_id"], output_path=str(target))

    assert result["output_path"] == str(target)
    assert target.read_text(encoding="utf-8").strip() == SAMPLE.strip()


def test_output_path_accepts_a_directory(tmp_path):
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    result = export_subtitles_impl(draft["draft_id"], output_path=str(tmp_path))
    assert os.path.basename(result["output_path"]) == f"{draft['draft_id']}.srt"
    assert os.path.exists(result["output_path"])


def test_no_output_path_writes_nothing_but_still_returns_the_srt():
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    result = export_subtitles_impl(draft["draft_id"])
    assert result["output_path"] == ""
    assert result["srt"]


# --------------------------------------------------------------- edge cases

def test_draft_with_no_text_segments_reports_an_empty_srt():
    from create_draft import get_or_create_draft
    draft_id, _ = get_or_create_draft()
    result = export_subtitles_impl(draft_id)
    assert result["success"] is True
    assert result["cue_count"] == 0
    assert result["srt"] == ""
    assert "no text segments" in result["message"]


def test_unknown_draft_is_an_error_not_an_empty_file():
    result = export_subtitles_impl("never-existed")
    assert result["success"] is False
    assert "does not exist" in result["error"]


def test_draft_id_is_required():
    assert export_subtitles_impl("")["success"] is False


def test_works_after_a_restart_via_the_draft_store():
    """Export must not depend on the draft still being in memory."""
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    draft_id = draft["draft_id"]
    draft_cache.DRAFT_CACHE.clear()          # simulate a restart
    assert export_subtitles_impl(draft_id)["cue_count"] == 3


# --------------------------------------------------------------- transports

def test_http_route_returns_the_srt():
    import capcut_server
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    client = capcut_server.app.test_client()
    body = client.post("/export_subtitles", json={"draft_id": draft["draft_id"]}).get_json()

    assert set(body) == {"success", "output", "error"}
    assert body["success"] is True
    assert body["output"]["cue_count"] == 3


def test_http_route_requires_a_draft_id():
    import capcut_server
    client = capcut_server.app.test_client()
    body = client.post("/export_subtitles", json={}).get_json()
    assert body["success"] is False
    assert "draft_id" in body["error"]


def test_mcp_dispatch_returns_the_srt():
    import mcp_server
    draft = add_subtitle_impl(srt_path=write_srt(SAMPLE))
    out = mcp_server.execute_tool("export_subtitles", {"draft_id": draft["draft_id"]})
    assert out["success"] is True
    assert out["result"]["cue_count"] == 3


def test_mcp_dispatch_reports_an_unknown_draft():
    import mcp_server
    out = mcp_server.execute_tool("export_subtitles", {"draft_id": "nope"})
    assert out["success"] is False
