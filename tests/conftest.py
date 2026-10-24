"""Shared fixtures.

The draft builders here deliberately produce BOTH shapes of draft:

* `api_video_material` — as written by this API. `Video_material.export_json` never emits
  `has_audio`, and paths are real absolute paths.
* `capcut_video_material` — as rewritten once CapCut opens a draft. `has_audio` is set, and
  media paths become `##_draftpath_placeholder_<uuid>_##` tokens relative to the draft folder.

Both shapes are covered because testing only the CapCut-authored one is exactly how two bugs
reached main: every API-created draft rendered silently without audio, and any draft CapCut had
opened rendered empty. See commit e2a4b75.
"""

import json
import os
import shutil
import subprocess
import uuid

import pytest

from export_backends import macos_ui

US = 1_000_000


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


requires_ffmpeg = pytest.mark.skipif(
    not _have("ffmpeg") or not _have("ffprobe"),
    reason="ffmpeg/ffprobe not on PATH",
)


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    """Two tiny real media files: one with an audio stream, one without."""
    if not _have("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")
    directory = tmp_path_factory.mktemp("media")
    with_audio = directory / "with_audio.mp4"
    without_audio = directory / "silent.mp4"

    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(with_audio)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
         str(without_audio)],
        check=True,
    )
    return {"with_audio": str(with_audio), "without_audio": str(without_audio)}


def video_material(path, *, material_id="mat-1", width=320, height=240,
                   duration_us=2 * US, has_audio=None, material_type="video"):
    """One entry of materials.videos.

    `has_audio=None` omits the key entirely, which is what this API produces.
    """
    material = {
        "id": material_id,
        "path": path,
        "material_name": os.path.basename(path),
        "type": material_type,
        "width": width,
        "height": height,
        "duration": duration_us,
    }
    if has_audio is not None:
        material["has_audio"] = has_audio
    return material


def segment(material_id="mat-1", *, source_start=0, source_duration=2 * US,
            target_start=0, target_duration=2 * US, speed=1.0, volume=1.0,
            visible=True, scale=1.0, transform=(0.0, 0.0), rotation=0.0,
            alpha=1.0, flip=(False, False), extra_refs=None):
    """One entry of tracks[].segments."""
    return {
        "id": f"seg-{uuid.uuid4().hex[:8]}",
        "material_id": material_id,
        "source_timerange": {"start": source_start, "duration": source_duration},
        "target_timerange": {"start": target_start, "duration": target_duration},
        "speed": speed,
        "volume": volume,
        "visible": visible,
        "extra_material_refs": extra_refs or [],
        "clip": {
            "scale": {"x": scale, "y": scale},
            "transform": {"x": transform[0], "y": transform[1]},
            "rotation": rotation,
            "alpha": alpha,
            "flip": {"horizontal": flip[0], "vertical": flip[1]},
        },
    }


def write_draft(folder, draft_id, *, materials=None, tracks=None,
                width=1080, height=1920, fps=30.0, duration_us=2 * US,
                keyframes=None):
    """Write a draft_info.json and return the draft folder root."""
    base = {
        "ai_text_effects": [], "audios": [], "texts": [], "videos": [],
        "material_animations": [], "transitions": [], "video_effects": [],
        "effects": [], "common_mask": [], "stickers": [],
    }
    base.update(materials or {})
    payload = {
        "canvas_config": {"width": width, "height": height, "ratio": "original"},
        "fps": fps,
        "duration": duration_us,
        "materials": base,
        "tracks": tracks or [],
        "keyframes": keyframes or {},
    }
    draft_dir = os.path.join(str(folder), draft_id)
    os.makedirs(draft_dir, exist_ok=True)
    with open(os.path.join(draft_dir, "draft_info.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return str(folder)


@pytest.fixture
def draft_folder(tmp_path):
    folder = tmp_path / "drafts"
    folder.mkdir()
    return folder


REAL_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)


def _draft_entries():
    try:
        return set(os.listdir(REAL_DRAFT_FOLDER))
    except OSError:
        return set()


@pytest.fixture(scope="session", autouse=True)
def isolate_draft_folder(tmp_path_factory):
    """Keep the suite out of the real CapCut drafts folder.

    Nothing writes there today, but nothing stopped it either, and a test that
    leaves a draft behind puts it in front of a human in CapCut's project list.
    So two things happen here. CAPCUT_DRAFT_FOLDER is redirected at a temp
    directory, which pytest removes on its own, so any test that does resolve a
    draft folder cleans up after itself by construction. And the real folder is
    compared before and after the session to catch anything that bypasses the
    redirect.

    New entries are reported, not deleted. The folder holds the user's own
    projects, and guessing which of them a test created is not a guess worth
    making against real work.
    """
    before = _draft_entries()
    os.environ["CAPCUT_DRAFT_FOLDER"] = str(tmp_path_factory.mktemp("capcut_drafts"))
    yield
    os.environ.pop("CAPCUT_DRAFT_FOLDER", None)
    leaked = sorted(_draft_entries() - before)
    if leaked:
        raise AssertionError(
            "The test suite left entries in the real CapCut drafts folder: "
            + ", ".join(leaked)
            + f"\nRemove them from {REAL_DRAFT_FOLDER} and make the test write "
            "to tmp_path or to os.environ['CAPCUT_DRAFT_FOLDER'] instead."
        )


@pytest.fixture(autouse=True)
def no_real_gui(request, monkeypatch):
    """Keep the suite away from the real CapCut UI.

    Every macos_ui call funnels through `osa`, which shells out to osascript. Left alone,
    a test that forgets to stub one UI call drives the actual app: it passes on a machine
    with CapCut open and behaves differently everywhere else. Three export tests were doing
    exactly that -- with CapCut closed, ensure_foreground retried for ten seconds each and
    the suite went from 1.4s to 33s.

    Refusing here makes the leak loud and immediate. Tests of `osa` itself carry the
    `real_osa` marker and stub subprocess instead.
    """
    if request.node.get_closest_marker("real_osa"):
        return

    def refuse(*args, **kwargs):
        raise AssertionError(
            "This test reached real macOS automation (macos_ui.osa). Stub the UI calls it "
            "makes; the suite must not depend on whether CapCut is running."
        )
    monkeypatch.setattr(macos_ui, "osa", refuse)
