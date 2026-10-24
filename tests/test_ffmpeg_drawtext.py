"""An ffmpeg without drawtext must warn, not fail the whole export.

drawtext needs libfreetype at build time and plenty of builds omit it -- the ffmpeg on
the machine this was written on does. Before this, a draft with any text compiled a
filtergraph ffmpeg could not run, and the export died with "No such filter: 'drawtext'".
That reads like a bug in the filtergraph rather than a missing feature in the binary, and
it threw away the video that could have been rendered.
"""

import json
import subprocess

import pytest

from export_backends import ffmpeg_render
from export_backends.draft_model import load_draft
from export_backends.ffmpeg_render import build_command, has_drawtext
from tests.conftest import segment, video_material, write_draft

US = 1_000_000


def _filtergraph(argv):
    return argv[argv.index("-filter_complex") + 1]


@pytest.fixture
def draft_with_text(draft_folder, media):
    """A draft carrying one video segment and one text segment."""
    folder = write_draft(
        draft_folder, "d", duration_us=2 * US,
        materials={
            "videos": [video_material(media["with_audio"])],
            "texts": [{
                "id": "txt-1",
                "content": json.dumps({"text": "Caption here", "styles": []}),
            }],
        },
        tracks=[
            {"type": "video", "segments": [segment("mat-1")]},
            {"type": "text", "segments": [segment("txt-1")]},
        ],
    )
    return load_draft("d", folder)


# ------------------------------------------------------------------ the warning path

def test_text_is_skipped_with_a_warning_when_drawtext_is_missing(draft_with_text, monkeypatch):
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: False)

    argv, warnings = build_command(draft_with_text, "/tmp/out.mp4")

    assert "drawtext" not in _filtergraph(argv), "an unusable filter must not be compiled in"
    assert any("no 'drawtext' filter" in w for w in warnings)


def test_the_warning_names_a_way_forward(draft_with_text, monkeypatch):
    """A warning the caller cannot act on is only slightly better than a crash."""
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: False)

    warning = next(w for w in build_command(draft_with_text, "/tmp/out.mp4")[1]
                   if "drawtext" in w)

    assert "capcut" in warning
    assert "libfreetype" in warning


def test_the_rest_of_the_draft_is_still_rendered(draft_with_text, monkeypatch):
    """The point of warning rather than failing: the video still comes out."""
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: False)

    argv = build_command(draft_with_text, "/tmp/out.mp4")[0]

    assert "-filter_complex" in argv
    assert "[vout]" in _filtergraph(argv), "the video chain must still terminate"


def test_text_is_drawn_when_drawtext_is_available(draft_with_text, monkeypatch):
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: True)
    monkeypatch.setattr(ffmpeg_render, "_font_file", lambda: "/System/Library/Fonts/Helvetica.ttc")

    argv, warnings = build_command(draft_with_text, "/tmp/out.mp4")

    assert "drawtext" in _filtergraph(argv)
    assert not any("no 'drawtext' filter" in w for w in warnings)


def test_a_missing_font_still_has_its_own_warning(draft_with_text, monkeypatch):
    """The two reasons text cannot be drawn are different and must stay distinguishable."""
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: True)
    monkeypatch.setattr(ffmpeg_render, "_font_file", lambda: None)

    warnings = build_command(draft_with_text, "/tmp/out.mp4")[1]

    assert any("no usable font file" in w for w in warnings)
    assert not any("no 'drawtext' filter" in w for w in warnings)


def test_a_draft_without_text_gets_no_text_warning(draft_folder, media, monkeypatch):
    monkeypatch.setattr(ffmpeg_render, "has_drawtext", lambda: False)
    folder = write_draft(
        draft_folder, "d", duration_us=2 * US,
        materials={"videos": [video_material(media["with_audio"])]},
        tracks=[{"type": "video", "segments": [segment("mat-1")]}],
    )

    warnings = build_command(load_draft("d", folder), "/tmp/out.mp4")[1]

    assert not any("drawtext" in w for w in warnings)


# ---------------------------------------------------------------- probing the binary

@pytest.fixture
def fake_filters(monkeypatch):
    def configure(stdout):
        monkeypatch.setattr(
            ffmpeg_render.subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout=stdout, stderr=""),
        )
        has_drawtext.cache_clear()
    yield configure
    has_drawtext.cache_clear()


def test_drawtext_is_detected_in_the_filter_list(fake_filters):
    fake_filters(" T. drawbox   V->V  Draw a colored box.\n"
                 " TS drawtext  V->V  Draw text on top of video.\n")
    assert has_drawtext() is True


def test_a_build_without_drawtext_is_detected(fake_filters):
    """Exactly what the ffmpeg on this machine reports."""
    fake_filters(" T. drawbox   V->V  Draw a colored box.\n"
                 " .. drawgrid  V->V  Draw a colored grid.\n")
    assert has_drawtext() is False


def test_a_similarly_named_filter_is_not_mistaken_for_drawtext(fake_filters):
    fake_filters(" T. drawtextborder  V->V  Something else entirely.\n")
    assert has_drawtext() is False


def test_drawtext_only_mentioned_in_a_description_does_not_count(fake_filters):
    fake_filters(" T. subtitles  V->V  Render subtitles, similar to drawtext.\n")
    assert has_drawtext() is False


def test_an_ffmpeg_that_cannot_be_run_is_treated_as_lacking_drawtext(monkeypatch):
    """Safer to skip the text than to compile a filter that may not exist."""
    def boom(*args, **kwargs):
        raise OSError("ffmpeg not found")
    monkeypatch.setattr(ffmpeg_render.subprocess, "run", boom)
    has_drawtext.cache_clear()
    try:
        assert has_drawtext() is False
    finally:
        has_drawtext.cache_clear()


# ------------------------------------------------------------------------- preflight

def test_preflight_reports_whether_ffmpeg_can_render_text(monkeypatch):
    """Better found before the export than in the warnings afterwards."""
    import export_impl

    monkeypatch.setattr(export_impl, "gui_session_available", lambda: False)
    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(export_impl, "_ffmpeg_can_render_text", lambda: False)

    ffmpeg = next(b for b in export_impl.export_preflight()["backends"] if b["name"] == "ffmpeg")

    assert ffmpeg["available"] is True
    assert ffmpeg["can_render_text"] is False


def test_preflight_reports_text_support_when_drawtext_is_present(monkeypatch):
    import export_impl

    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(export_impl, "_ffmpeg_can_render_text", lambda: True)

    ffmpeg = next(b for b in export_impl.export_preflight()["backends"] if b["name"] == "ffmpeg")

    assert ffmpeg["can_render_text"] is True


def test_preflight_does_not_claim_text_support_without_ffmpeg(monkeypatch):
    import export_impl

    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: False)

    ffmpeg = next(b for b in export_impl.export_preflight()["backends"] if b["name"] == "ffmpeg")

    assert ffmpeg["available"] is False
    assert ffmpeg["can_render_text"] is False


def test_preflight_survives_a_probe_that_raises(monkeypatch):
    """Preflight is the diagnostic tool; it must not be the thing that breaks."""
    import export_impl
    from export_backends import ffmpeg_render as fr

    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(fr, "has_drawtext", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    report = export_impl.export_preflight()

    ffmpeg = next(b for b in report["backends"] if b["name"] == "ffmpeg")
    assert ffmpeg["can_render_text"] is False
