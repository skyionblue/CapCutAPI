"""export_video saves the draft first when it is not on disk yet.

Both backends read the draft from the CapCut drafts folder, so exporting a draft that
only existed in the cache used to fail with an error about the draft being missing.
Accurate, but it named a step the caller had every reason to think was optional --
especially an AI driving this through the gateway, which has no reason to know that
save_draft is a prerequisite rather than a convenience.
"""

import json
import os

import pytest

import export_impl
from export_impl import export_video
from export_task_cache import get_export_task_status


@pytest.fixture
def saved_draft(tmp_path):
    """A draft that is already on disk, as save_draft would leave it."""
    def make(draft_id="d_saved"):
        folder = tmp_path / "drafts"
        (folder / draft_id).mkdir(parents=True)
        (folder / draft_id / "draft_info.json").write_text(json.dumps({"tracks": []}),
                                                           encoding="utf-8")
        return str(folder)
    return make


@pytest.fixture
def ran(monkeypatch, tmp_path):
    """Record what the export did, with a backend that produces a real file."""
    calls = {"saved": [], "backend": []}

    produced = tmp_path / "out.mp4"
    produced.write_bytes(b"\x00")

    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)
    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: True)

    def fake_save(draft_id, folder, on_complete=None):
        """Stands in for save_draft_impl, including that it is on_complete that places
        the draft. The first version of this fake wrote the file itself and so hid a real
        bug: the production call was saving to the project root, not to CapCut's folder."""
        calls["saved"].append((draft_id, folder))
        src = os.path.join(export_impl.__file__, "..", draft_id)
        os.makedirs(os.path.abspath(src), exist_ok=True)
        with open(os.path.join(os.path.abspath(src), "draft_info.json"), "w", encoding="utf-8") as f:
            json.dump({"tracks": []}, f)
        if on_complete:
            on_complete(draft_id)
        return {"success": True}

    monkeypatch.setattr(export_impl, "save_draft_impl", fake_save)
    monkeypatch.setattr(export_impl, "get_script", lambda draft_id: object())

    def fake_backend(backend, task_id, draft_id, options):
        calls["backend"].append(draft_id)
        return str(produced)

    monkeypatch.setattr(export_impl, "_run_backend", fake_backend)
    monkeypatch.setattr(export_impl, "_finish",
                        lambda task_id, path, requested: str(produced))
    return calls


def test_an_unsaved_draft_is_saved_before_the_backend_runs(ran, tmp_path):
    folder = str(tmp_path / "drafts")
    result = export_video("d_new", backend="ffmpeg", draft_folder=folder, wait=True)

    assert ran["saved"] == [("d_new", folder)]
    assert ran["backend"] == ["d_new"], "the backend must still run after the save"
    assert get_export_task_status(result["task_id"])["status"] == "completed"


def test_an_already_saved_draft_is_not_saved_again(ran, saved_draft):
    """Re-saving re-downloads every remote asset, so it must not happen needlessly."""
    folder = saved_draft("d_saved")
    export_video("d_saved", backend="ffmpeg", draft_folder=folder, wait=True)

    assert ran["saved"] == []
    assert ran["backend"] == ["d_saved"]


def test_a_draft_that_exists_nowhere_says_so_without_calling_save(ran, monkeypatch, tmp_path):
    monkeypatch.setattr(export_impl, "get_script", lambda draft_id: None)

    result = export_video("d_ghost", backend="ffmpeg",
                          draft_folder=str(tmp_path / "drafts"), wait=True)

    assert ran["saved"] == [], "nothing to save; do not try"
    assert ran["backend"] == [], "and do not dispatch either"
    task = get_export_task_status(result["task_id"])
    assert task["status"] == "failed"
    assert "d_ghost" in task["error"]
    assert "create_draft" in task["error"], "the error must name the step that was missed"


def test_a_failing_save_fails_the_task_rather_than_exporting_anyway(ran, monkeypatch, tmp_path):
    monkeypatch.setattr(export_impl, "save_draft_impl",
                        lambda draft_id, folder, on_complete=None:
                        {"success": False, "error": "disk full"})

    result = export_video("d_new", backend="ffmpeg",
                          draft_folder=str(tmp_path / "drafts"), wait=True)

    assert ran["backend"] == [], "a draft that did not save must not be exported"
    task = get_export_task_status(result["task_id"])
    assert task["status"] == "failed"
    assert "disk full" in task["error"]


def test_a_save_that_does_not_place_the_draft_is_caught(ran, monkeypatch, tmp_path):
    """The bug this feature shipped with on the first attempt.

    save_draft_impl builds the draft under the project root and leaves it there; it is
    on_complete that moves it where CapCut looks. Calling save without that placement
    reported success while the draft was in the wrong directory, and the export then failed
    with a confusing "run save_draft first" -- after having just run it.
    """
    monkeypatch.setattr(export_impl, "save_draft_impl",
                        lambda draft_id, folder, on_complete=None: {"success": True})

    result = export_video("d_new", backend="ffmpeg",
                          draft_folder=str(tmp_path / "drafts"), wait=True)

    assert ran["backend"] == [], "nothing landed, so nothing should be exported"
    task = get_export_task_status(result["task_id"])
    assert task["status"] == "failed"
    assert "did not land" in task["error"]


def _placing_save(record):
    """A save_draft_impl stand-in that behaves like the real one: it places via on_complete."""
    def fake(draft_id, folder, on_complete=None):
        record["folder"] = folder
        record["on_complete"] = on_complete
        os.makedirs(os.path.join(folder, draft_id), exist_ok=True)
        with open(os.path.join(folder, draft_id, "draft_info.json"), "w", encoding="utf-8") as f:
            json.dump({"tracks": []}, f)
        return {"success": True}
    return fake


def test_the_save_is_given_a_placement_callback(monkeypatch, tmp_path):
    """on_complete is not optional here -- without it the draft never reaches the folder."""
    record = {}
    monkeypatch.setattr(export_impl, "get_script", lambda draft_id: object())
    monkeypatch.setattr(export_impl, "save_draft_impl", _placing_save(record))

    export_impl._ensure_on_disk("task-1", "d_new", str(tmp_path))

    assert callable(record["on_complete"]), "save must be told how to place the draft"


def test_the_default_folder_points_at_capcut():
    """A relative or wrong default would scatter drafts somewhere CapCut never looks."""
    assert os.path.isabs(export_impl.DEFAULT_DRAFT_FOLDER)
    assert export_impl.DEFAULT_DRAFT_FOLDER.endswith("com.lveditor.draft")
    assert "CapCut" in export_impl.DEFAULT_DRAFT_FOLDER


def test_the_default_folder_is_used_when_none_is_given(monkeypatch, tmp_path):
    """Redirected to tmp, so the assertion is about which constant is consulted."""
    record = {}
    monkeypatch.setattr(export_impl, "DEFAULT_DRAFT_FOLDER", str(tmp_path / "capcut"))
    monkeypatch.setattr(export_impl, "get_script", lambda draft_id: object())
    monkeypatch.setattr(export_impl, "save_draft_impl", _placing_save(record))

    export_impl._ensure_on_disk("task-1", "d_new", None)

    assert record["folder"] == str(tmp_path / "capcut")


def test_an_explicit_folder_overrides_the_default(monkeypatch, tmp_path):
    record = {}
    monkeypatch.setattr(export_impl, "get_script", lambda draft_id: object())
    monkeypatch.setattr(export_impl, "save_draft_impl", _placing_save(record))

    export_impl._ensure_on_disk("task-1", "d_new", str(tmp_path))

    assert record["folder"] == str(tmp_path)
