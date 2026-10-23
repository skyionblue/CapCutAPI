"""Tests for parsing a saved draft.

The regression tests at the top cover the two defects fixed in e2a4b75, both of which reached
main because every manual check used a draft CapCut had authored.
"""

import os
import shutil

import pytest

from export_backends.draft_model import load_draft
from tests.conftest import requires_ffmpeg, segment, video_material, write_draft

US = 1_000_000


# --------------------------------------------------------------- regressions (e2a4b75)

@requires_ffmpeg
def test_api_authored_draft_detects_audio_without_the_metadata_key(draft_folder, media):
    """Drafts from this API omit has_audio entirely; it must be probed, not assumed False.

    Regression: bool(None) disabled audio, so every API-created draft rendered silently.
    """
    folder = write_draft(
        draft_folder, "api-draft",
        materials={"videos": [video_material(media["with_audio"], has_audio=None)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("api-draft", folder)

    assert len(draft.segments) == 1
    assert draft.segments[0].has_audio is True, "audio must be probed when the key is absent"


@requires_ffmpeg
def test_probe_reports_no_audio_for_a_silent_file(draft_folder, media):
    folder = write_draft(
        draft_folder, "silent-draft",
        materials={"videos": [video_material(media["without_audio"], has_audio=None)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("silent-draft", folder)
    assert draft.segments[0].has_audio is False


@requires_ffmpeg
def test_explicit_has_audio_is_honoured_without_probing(draft_folder, media):
    """An explicit false from CapCut must win over what the file actually contains."""
    folder = write_draft(
        draft_folder, "explicit",
        materials={"videos": [video_material(media["with_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("explicit", folder)
    assert draft.segments[0].has_audio is False


@requires_ffmpeg
def test_capcut_path_placeholder_resolves_against_the_draft_folder(draft_folder, media):
    """Once CapCut opens a draft it rewrites paths to a relocatable token.

    Regression: the token hit os.path.exists() verbatim, the segment was dropped as
    "source file missing", and the draft rendered empty.
    """
    draft_dir = os.path.join(str(draft_folder), "capcut-draft")
    os.makedirs(draft_dir, exist_ok=True)
    local_name = "clip.mp4"
    shutil.copy(media["with_audio"], os.path.join(draft_dir, local_name))

    token = f"##_draftpath_placeholder_{'a' * 8}-dead-beef_##/{local_name}"
    folder = write_draft(
        draft_folder, "capcut-draft",
        materials={"videos": [video_material(token, has_audio=True)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("capcut-draft", folder)

    assert len(draft.segments) == 1, f"segment was dropped; warnings: {draft.warnings}"
    assert draft.segments[0].path.endswith(local_name)
    assert os.path.exists(draft.segments[0].path)


# --------------------------------------------------------------- parsing

def test_canvas_fps_and_duration(draft_folder, media):
    folder = write_draft(
        draft_folder, "d", width=1920, height=1080, fps=24.0, duration_us=5 * US,
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("d", folder)
    assert (draft.width, draft.height) == (1920, 1080)
    assert draft.fps == 24.0
    assert draft.duration == pytest.approx(5.0)


def test_timeranges_convert_microseconds_to_seconds(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [
            segment(source_start=3 * US, source_duration=2 * US,
                    target_start=10 * US, target_duration=2 * US),
        ]}],
    )
    seg = load_draft("d", folder).segments[0]
    assert seg.source_start == pytest.approx(3.0)
    assert seg.source_duration == pytest.approx(2.0)
    assert seg.target_start == pytest.approx(10.0)
    assert seg.target_duration == pytest.approx(2.0)


def test_clip_transform_is_parsed(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [
            segment(scale=1.5, transform=(0.25, -0.5), rotation=90.0,
                    alpha=0.5, flip=(True, False)),
        ]}],
    )
    seg = load_draft("d", folder).segments[0]
    assert seg.scale_x == pytest.approx(1.5)
    assert (seg.transform_x, seg.transform_y) == (pytest.approx(0.25), pytest.approx(-0.5))
    assert seg.rotation == pytest.approx(90.0)
    assert seg.alpha == pytest.approx(0.5)
    assert seg.flip_h is True and seg.flip_v is False


def test_missing_source_file_is_skipped_with_a_warning(draft_folder):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material("/nonexistent/none.mp4", has_audio=True)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("d", folder)
    assert draft.segments == []
    assert any("missing" in w.lower() for w in draft.warnings)


def test_absent_draft_raises(draft_folder):
    with pytest.raises(FileNotFoundError):
        load_draft("never-created", str(draft_folder))


# --------------------------------------------------------------- fidelity reporting

@pytest.mark.parametrize("collection,phrase", [
    ("material_animations", "animation"),
    ("transitions", "transition"),
    ("video_effects", "effect"),
    ("common_mask", "mask"),
    ("stickers", "sticker"),
])
def test_unsupported_materials_produce_a_fidelity_warning(draft_folder, media, collection, phrase):
    """A degraded render must always be declared, never silent."""
    folder = write_draft(
        draft_folder, "d",
        materials={
            "videos": [video_material(media["without_audio"], has_audio=False)],
            collection: [{"id": "x1"}, {"id": "x2"}],
        },
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    draft = load_draft("d", folder)
    assert any(phrase in w.lower() for w in draft.warnings), draft.warnings


def test_keyframes_produce_a_fidelity_warning(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment()]}],
        keyframes={"video": [{"id": "k"}]},
    )
    draft = load_draft("d", folder)
    assert any("keyframe" in w.lower() for w in draft.warnings)


def test_clean_draft_has_no_warnings(draft_folder, media):
    folder = write_draft(
        draft_folder, "d",
        materials={"videos": [video_material(media["without_audio"], has_audio=False)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    assert load_draft("d", folder).warnings == []
