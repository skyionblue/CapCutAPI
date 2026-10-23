"""Tests for bundling a draft into a portable zip.

The point of the bundle is that it opens somewhere else. Zipping the draft folder alone does
not achieve that, because the media it references usually lives elsewhere on disk — so the
central test here unpacks a bundle into an unrelated directory and checks the media still
resolves.
"""

import json
import os
import shutil
import zipfile

import pytest

from export_draft_impl import export_draft_impl
from export_backends.draft_model import load_draft
from tests.conftest import requires_ffmpeg, segment, video_material, write_draft


@pytest.fixture
def saved_draft(draft_folder, media, tmp_path):
    """A draft on disk whose media sits OUTSIDE the draft folder, as CapCut writes it."""
    external = tmp_path / "elsewhere"
    external.mkdir()
    source = external / "clip.mp4"
    shutil.copy(media["with_audio"], source)

    write_draft(
        draft_folder, "d1",
        materials={"videos": [video_material(str(source), has_audio=True)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    return {"folder": str(draft_folder), "draft_id": "d1", "source": str(source)}


# --------------------------------------------------------------- the point of the feature

@requires_ffmpeg
def test_bundle_opens_in_an_unrelated_folder(saved_draft, tmp_path):
    """A bundle must work somewhere with no relationship to the original paths."""
    result = export_draft_impl(
        saved_draft["draft_id"], output_path=str(tmp_path / "out"),
        draft_folder=saved_draft["folder"],
    )
    assert result["success"] is True

    other_machine = tmp_path / "other-machine"
    other_machine.mkdir()
    with zipfile.ZipFile(result["output_path"]) as archive:
        archive.extractall(other_machine)

    draft = load_draft("d1", str(other_machine))
    assert len(draft.segments) == 1, f"media did not resolve; warnings: {draft.warnings}"
    assert os.path.exists(draft.segments[0].path)
    assert draft.warnings == []


@requires_ffmpeg
def test_bundle_still_opens_after_the_original_media_is_deleted(saved_draft, tmp_path):
    """Proves the media was copied in, not merely referenced."""
    result = export_draft_impl(
        saved_draft["draft_id"], output_path=str(tmp_path / "out"),
        draft_folder=saved_draft["folder"],
    )
    os.remove(saved_draft["source"])

    other_machine = tmp_path / "other"
    other_machine.mkdir()
    with zipfile.ZipFile(result["output_path"]) as archive:
        archive.extractall(other_machine)

    draft = load_draft("d1", str(other_machine))
    assert len(draft.segments) == 1
    assert os.path.exists(draft.segments[0].path)


# --------------------------------------------------------------- bundle contents

@requires_ffmpeg
def test_media_is_copied_into_the_bundle(saved_draft, tmp_path):
    result = export_draft_impl(saved_draft["draft_id"], output_path=str(tmp_path / "out"),
                               draft_folder=saved_draft["folder"])
    assert result["bundled_files"] == 1
    with zipfile.ZipFile(result["output_path"]) as archive:
        names = archive.namelist()
    assert any(name.startswith("d1/assets/") for name in names)


@requires_ffmpeg
def test_paths_are_rewritten_to_the_relocatable_form(saved_draft, tmp_path):
    result = export_draft_impl(saved_draft["draft_id"], output_path=str(tmp_path / "out"),
                               draft_folder=saved_draft["folder"])
    with zipfile.ZipFile(result["output_path"]) as archive:
        data = json.loads(archive.read("d1/draft_info.json"))
    path = data["materials"]["videos"][0]["path"]
    assert path.startswith("##_draftpath_placeholder_")
    assert path.endswith("/assets/clip.mp4")
    assert not os.path.isabs(path), "an absolute path would not relocate"


@requires_ffmpeg
def test_everything_is_nested_under_one_draft_folder(saved_draft, tmp_path):
    """Otherwise unzipping scatters draft_info.json across the drafts directory."""
    result = export_draft_impl(saved_draft["draft_id"], output_path=str(tmp_path / "out"),
                               draft_folder=saved_draft["folder"])
    with zipfile.ZipFile(result["output_path"]) as archive:
        tops = {name.split("/")[0] for name in archive.namelist()}
    assert tops == {"d1"}


# --------------------------------------------------------------- reporting and edges

def test_missing_media_is_reported_not_silently_dropped(draft_folder, tmp_path):
    write_draft(
        draft_folder, "d1",
        materials={"videos": [video_material("/nonexistent/gone.mp4", has_audio=True)]},
        tracks=[{"type": "video", "segments": [segment()]}],
    )
    result = export_draft_impl("d1", output_path=str(tmp_path / "out"),
                               draft_folder=str(draft_folder))
    assert result["success"] is True
    assert result["bundled_files"] == 0
    assert result["missing_media"] == ["/nonexistent/gone.mp4"]
    assert "NOT in the bundle" in result["message"]


@requires_ffmpeg
def test_output_path_accepts_a_directory(saved_draft, tmp_path):
    target = tmp_path / "bundles"
    result = export_draft_impl(saved_draft["draft_id"], output_path=str(target),
                               draft_folder=saved_draft["folder"])
    assert os.path.basename(result["output_path"]) == "d1.zip"
    assert os.path.exists(result["output_path"])


def test_unsaved_draft_tells_the_caller_to_save_first(draft_folder, tmp_path):
    result = export_draft_impl("never-saved", output_path=str(tmp_path),
                               draft_folder=str(draft_folder))
    assert result["success"] is False
    assert "save_draft" in result["error"]


def test_draft_id_is_required():
    assert export_draft_impl("")["success"] is False


# --------------------------------------------------------------- transports

@requires_ffmpeg
def test_http_route(saved_draft, tmp_path):
    import capcut_server
    client = capcut_server.app.test_client()
    body = client.post("/export_draft", json={
        "draft_id": "d1", "output_path": str(tmp_path / "http"),
        "draft_folder": saved_draft["folder"],
    }).get_json()
    assert body["success"] is True
    assert body["output"]["bundled_files"] == 1


def test_http_route_requires_a_draft_id():
    import capcut_server
    body = capcut_server.app.test_client().post("/export_draft", json={}).get_json()
    assert body["success"] is False
    assert "draft_id" in body["error"]


@requires_ffmpeg
def test_mcp_dispatch(saved_draft, tmp_path):
    import mcp_server
    out = mcp_server.execute_tool("export_draft", {
        "draft_id": "d1", "output_path": str(tmp_path / "mcp"),
        "draft_folder": saved_draft["folder"],
    })
    assert out["success"] is True
    assert out["result"]["bundled_files"] == 1
