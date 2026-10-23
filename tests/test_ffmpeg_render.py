"""Tests for compiling a draft into an ffmpeg command.

build_command is pure — a draft in, an argv list out — so the compilation can be checked
without rendering anything or having CapCut installed.
"""

import pytest

from export_backends.draft_model import load_draft
from export_backends.ffmpeg_render import (
    RenderError, _atempo_chain, _escape_drawtext, _output_size, build_command,
)
from tests.conftest import requires_ffmpeg, segment, video_material, write_draft

US = 1_000_000


def _filtergraph(argv):
    return argv[argv.index("-filter_complex") + 1]


def _input_paths(argv):
    return [argv[i + 1] for i, token in enumerate(argv) if token == "-i"]


@pytest.fixture
def two_cut_draft(draft_folder, media):
    """Two trimmed cuts from one source, placed back to back."""
    folder = write_draft(
        draft_folder, "cuts", duration_us=4 * US,
        materials={"videos": [video_material(media["with_audio"], has_audio=True)]},
        tracks=[{"type": "video", "segments": [
            segment(source_start=0, source_duration=2 * US,
                    target_start=0, target_duration=2 * US),
            segment(source_start=5 * US, source_duration=2 * US,
                    target_start=2 * US, target_duration=2 * US),
        ]}],
    )
    return load_draft("cuts", folder)


# --------------------------------------------------------------- structure

@requires_ffmpeg
def test_one_overlay_per_visible_segment(two_cut_draft):
    graph = _filtergraph(build_command(two_cut_draft, "/tmp/out.mp4")[0])
    assert graph.count("overlay=") == 2


@requires_ffmpeg
def test_each_segment_becomes_its_own_input(two_cut_draft):
    assert len(_input_paths(build_command(two_cut_draft, "/tmp/out.mp4")[0])) == 2


@requires_ffmpeg
def test_input_seeking_matches_each_segment_source_range(two_cut_draft):
    argv = build_command(two_cut_draft, "/tmp/out.mp4")[0]
    starts = [argv[i + 1] for i, token in enumerate(argv) if token == "-ss"]
    assert [float(value) for value in starts] == [pytest.approx(0.0), pytest.approx(5.0)]


@requires_ffmpeg
def test_invisible_segments_are_not_composited(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment(visible=False)]}],
    )
    graph = _filtergraph(build_command(load_draft("d", folder), "/tmp/out.mp4")[0])
    assert "overlay=" not in graph


@requires_ffmpeg
def test_audio_is_mapped_when_a_segment_has_audio(two_cut_draft):
    argv, _ = build_command(two_cut_draft, "/tmp/out.mp4")
    assert "[aout]" in argv, "audio-bearing segments must reach the output map"
    assert "aac" in argv


@requires_ffmpeg
def test_silent_draft_warns_and_maps_no_audio(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    argv, warnings = build_command(load_draft("d", folder), "/tmp/out.mp4")
    assert "[aout]" not in argv
    assert any("no audio" in w.lower() for w in warnings)


@requires_ffmpeg
def test_zero_duration_draft_is_rejected(draft_folder, media):
    folder = write_draft(
        draft_folder, "d", duration_us=0,
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [
            segment(target_start=0, target_duration=0, source_duration=0),
        ]}],
    )
    with pytest.raises(RenderError):
        build_command(load_draft("d", folder), "/tmp/out.mp4")


@requires_ffmpeg
def test_draft_warnings_are_carried_into_the_command_warnings(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={
            "videos": [video_material(media["without_audio"], has_audio=False)],
            "material_animations": [{"id": "a1"}],
        },
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    _, warnings = build_command(load_draft("d", folder), "/tmp/out.mp4")
    assert any("animation" in w.lower() for w in warnings)


# --------------------------------------------------------------- output size

class _Canvas:
    """Minimal stand-in: _output_size only reads width/height."""
    def __init__(self, width, height):
        self.width, self.height = width, height


@pytest.mark.parametrize("canvas,resolution,expected", [
    ((1920, 1080), "1080p", (1920, 1080)),   # already at target
    ((1920, 1080), "720p", (1280, 720)),     # landscape: shorter side is height
    ((1080, 1920), "720p", (720, 1280)),     # portrait: shorter side is width
    ((1920, 1242), "540p", (834, 540)),      # non-standard aspect preserved
    ((1080, 1920), None, (1080, 1920)),      # default is the draft canvas
])
def test_resolution_sets_the_shorter_side_preserving_aspect(canvas, resolution, expected):
    assert _output_size(_Canvas(*canvas), resolution) == expected


def test_output_dimensions_are_always_even():
    """H.264 requires even dimensions."""
    width, height = _output_size(_Canvas(1001, 1999), "333p")
    assert width % 2 == 0 and height % 2 == 0


def test_unparseable_resolution_is_rejected():
    with pytest.raises(RenderError):
        _output_size(_Canvas(1920, 1080), "huge")


# --------------------------------------------------------------- helpers

@pytest.mark.parametrize("speed,stages", [
    (1.0, 0),      # no-op
    (1.5, 1),
    (2.0, 1),
    (4.0, 2),      # outside atempo's range, must be chained
    (8.0, 3),
    (0.5, 1),
    (0.25, 2),
])
def test_atempo_chains_outside_the_supported_range(speed, stages):
    assert len(_atempo_chain(speed)) == stages


def test_atempo_stages_stay_within_ffmpeg_limits():
    for stage in _atempo_chain(8.0):
        value = float(stage.split("=")[1])
        assert 0.5 <= value <= 2.0


def test_atempo_product_reconstructs_the_requested_speed():
    product = 1.0
    for stage in _atempo_chain(6.0):
        product *= float(stage.split("=")[1])
    assert product == pytest.approx(6.0)


@pytest.mark.parametrize("raw", ["a:b", "it's", "100%", "x,y", "[a]"])
def test_drawtext_escaping_neutralises_delimiters(raw):
    escaped = _escape_drawtext(raw)
    for char in (":", "'", "%", ",", "["):
        if char in raw:
            assert "\\" + char in escaped
