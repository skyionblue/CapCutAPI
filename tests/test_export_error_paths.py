"""Error paths for export: the states a user actually lands in.

Every failure here is one a person hits by doing something ordinary -- running the
export with CapCut closed, without ever granting Accessibility, before saving the
draft, or twice at once. The thing being asserted is usually not that an exception
is raised but that the message tells them what to do next, because this backend
drives someone else's GUI and a bare traceback leaves them with no move.
"""

import json
import os
import subprocess

import pytest

import export_impl
from export_backends import capcut_macos, draft_model, macos_ui
from export_impl import export_video
from export_task_cache import get_export_task_status


@pytest.fixture(autouse=True)
def draft_already_saved(monkeypatch):
    """Most tests here exercise a backend, not the save-first step export_video does.

    Tests that care about that step opt out with `no_autosave_patch`.
    """
    monkeypatch.setattr(export_impl, "_ensure_on_disk",
                        lambda task_id, draft_id, draft_folder: None)


class FakeProc:
    def __init__(self, returncode=1, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ------------------------------------------------------------------ CapCut closed

def test_capcut_closed_names_the_headless_alternative(monkeypatch):
    """With no GUI the user still has a way to render; the error has to say so."""
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: False)
    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: True)

    result = export_video("d1", backend="capcut")

    assert result["success"] is False
    assert "ffmpeg" in result["error"]


def test_capcut_closed_and_no_ffmpeg_says_both_are_missing(monkeypatch):
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: False)
    monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: False)

    error = export_video("d1", backend="auto")["error"]

    assert "CapCut" in error and "ffmpeg" in error


def test_capcut_not_on_the_home_page_lists_what_was_visible(monkeypatch):
    """The common cause is a draft CapCut has not noticed yet, so name the drafts it did see."""
    monkeypatch.setattr(capcut_macos, "_current_state", lambda window: "home")
    monkeypatch.setattr(macos_ui, "main_window_index", lambda: 1)
    monkeypatch.setattr(capcut_macos, "_find_draft_card", lambda draft_id: (None, ["1017", "1019"]))

    with pytest.raises(macos_ui.UIAutomationError) as excinfo:
        capcut_macos._open_draft("task-1", "dfd_missing")

    message = str(excinfo.value)
    assert "dfd_missing" in message
    assert "1017" in message and "1019" in message
    assert "save_draft" in message


def test_an_empty_drafts_folder_is_reported_as_none_not_as_a_blank(monkeypatch):
    monkeypatch.setattr(capcut_macos, "_current_state", lambda window: "home")
    monkeypatch.setattr(macos_ui, "main_window_index", lambda: 1)
    monkeypatch.setattr(capcut_macos, "_find_draft_card", lambda draft_id: (None, []))

    with pytest.raises(macos_ui.UIAutomationError, match="none"):
        capcut_macos._open_draft("task-1", "dfd_missing")


def test_an_unreachable_home_page_tells_the_user_to_close_the_dialog(monkeypatch):
    """A modal sheet left open in CapCut blocks everything; that is the usual cause."""
    monkeypatch.setattr(capcut_macos, "_current_state", lambda window: "unknown")
    monkeypatch.setattr(macos_ui, "main_window_index", lambda: 1)

    with pytest.raises(macos_ui.UIAutomationError, match="dialog"):
        capcut_macos._open_draft("task-1", "d1")


# -------------------------------------------------------- Accessibility permission

@pytest.mark.parametrize("stderr", [
    "osascript is not allowed assistive access. (-1719)",
    "execution error: An error of type -25211 has occurred. (-25211)",
])
def test_missing_accessibility_permission_says_where_to_grant_it(monkeypatch, stderr):
    monkeypatch.setattr(macos_ui.subprocess, "run",
                        lambda *a, **k: FakeProc(returncode=1, stderr=stderr))
    monkeypatch.setattr(macos_ui.time, "sleep", lambda s: None)

    with pytest.raises(macos_ui.AccessibilityError) as excinfo:
        macos_ui.osa("tell application \"System Events\" to return 1")

    message = str(excinfo.value)
    assert "Accessibility" in message
    assert "System Settings" in message


def test_accessibility_error_is_catchable_as_a_ui_error():
    """Callers catch UIAutomationError broadly; the permission case must not escape it."""
    assert issubclass(macos_ui.AccessibilityError, macos_ui.UIAutomationError)
    assert issubclass(macos_ui.NotVisibleError, macos_ui.UIAutomationError)


def test_a_hung_applescript_is_reported_as_a_timeout(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=60)
    monkeypatch.setattr(macos_ui.subprocess, "run", hang)

    with pytest.raises(macos_ui.UIAutomationError, match="timed out"):
        macos_ui.osa("tell application \"System Events\" to return 1")


def test_a_click_outside_capcut_is_refused_and_names_the_owner(monkeypatch):
    """The guard that stopped clicks landing in a live video call. It must stay."""
    monkeypatch.setattr(macos_ui, "window_at",
                        lambda x, y: {"owner": "Google Chrome", "x": 0, "y": 0, "w": 100, "h": 100})

    with pytest.raises(macos_ui.NotVisibleError) as excinfo:
        macos_ui.assert_capcut_owns(10, 10)

    assert "Google Chrome" in str(excinfo.value)


def test_a_click_on_no_window_at_all_is_refused(monkeypatch):
    monkeypatch.setattr(macos_ui, "window_at", lambda x, y: None)

    with pytest.raises(macos_ui.NotVisibleError, match="nothing"):
        macos_ui.assert_capcut_owns(10, 10)


# --------------------------------------------------------------------- bad draft_id

def test_export_video_rejects_an_empty_draft_id(monkeypatch):
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)
    assert export_video("")["success"] is False


def test_an_unsaved_draft_says_to_run_save_draft(tmp_path):
    with pytest.raises(FileNotFoundError) as excinfo:
        draft_model.load_draft("dfd_never_saved", str(tmp_path))

    message = str(excinfo.value)
    assert "dfd_never_saved" in message
    assert "save_draft" in message


def test_a_corrupt_draft_info_surfaces_as_a_json_error(tmp_path):
    draft_dir = tmp_path / "dfd_corrupt"
    draft_dir.mkdir()
    (draft_dir / "draft_info.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        draft_model.load_draft("dfd_corrupt", str(tmp_path))


def test_a_bad_draft_id_fails_the_task_rather_than_the_call(monkeypatch):
    """export_video returns a task; a backend blowing up has to land on that task."""
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)

    def explode(backend, task_id, draft_id, options):
        raise FileNotFoundError(f"No draft_info.json for draft {draft_id!r}")
    monkeypatch.setattr(export_impl, "_run_backend", explode)

    result = export_video("dfd_bogus", backend="capcut", wait=True)

    assert result["success"] is True, "the call itself succeeds; the task carries the failure"
    task = get_export_task_status(result["task_id"])
    assert task["status"] == "failed"
    assert "dfd_bogus" in task["error"]


# ------------------------------------------------------------------ concurrency

def test_concurrent_exports_get_separate_tasks(monkeypatch, tmp_path):
    produced = tmp_path / "out.mp4"
    produced.write_bytes(b"\x00")
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)
    monkeypatch.setattr(export_impl, "_run_backend",
                        lambda backend, task_id, draft_id, options: str(produced))
    monkeypatch.setattr(export_impl, "_finish",
                        lambda task_id, path, requested: str(produced))

    first = export_video("d1", backend="capcut", wait=True)
    second = export_video("d2", backend="capcut", wait=True)

    assert first["task_id"] != second["task_id"]
    assert get_export_task_status(first["task_id"])["draft_id"] == "d1"
    assert get_export_task_status(second["task_id"])["draft_id"] == "d2"


def test_one_failing_export_does_not_mark_the_other_failed(monkeypatch, tmp_path):
    produced = tmp_path / "out.mp4"
    produced.write_bytes(b"\x00")
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)

    def selective(backend, task_id, draft_id, options):
        if draft_id == "bad":
            raise RuntimeError("CapCut's export dialog did not open")
        return str(produced)
    monkeypatch.setattr(export_impl, "_run_backend", selective)
    monkeypatch.setattr(export_impl, "_finish",
                        lambda task_id, path, requested: str(produced))

    good = export_video("good", backend="capcut", wait=True)
    bad = export_video("bad", backend="capcut", wait=True)

    assert get_export_task_status(good["task_id"])["status"] == "completed"
    assert get_export_task_status(bad["task_id"])["status"] == "failed"


def test_an_unknown_task_id_reports_not_found_rather_than_raising():
    status = get_export_task_status("export-nope-00000000")
    assert status["status"] == "not_found"


# ------------------------------------------- draft meta paths written on creation

def test_template_meta_paths_point_at_where_the_draft_lands(tmp_path):
    """The template ships these blank; nothing else fills them in."""
    from save_draft_impl import write_draft_meta_paths

    draft_dir = tmp_path / "dfd_new"
    draft_dir.mkdir()
    (draft_dir / "draft_meta_info.json").write_text(
        json.dumps({"draft_fold_path": "", "draft_root_path": "", "keep": 1}), encoding="utf-8")

    write_draft_meta_paths(str(draft_dir), str(tmp_path))

    meta = json.loads((draft_dir / "draft_meta_info.json").read_text(encoding="utf-8"))
    assert meta["draft_fold_path"] == str(draft_dir)
    assert meta["draft_root_path"] == str(tmp_path)
    assert meta["keep"] == 1, "unrelated fields must survive"


def test_shipped_template_has_no_foreign_path_baked_in():
    """These used to hold another person's home directory and nothing ever corrected it."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    meta_path = os.path.join(repo_root, "template", "draft_meta_info.json")
    meta = json.loads(open(meta_path, encoding="utf-8").read())

    assert meta["draft_fold_path"] == ""
    assert meta["draft_root_path"] == ""


def test_writing_meta_paths_is_a_no_op_when_the_file_is_absent(tmp_path):
    from save_draft_impl import write_draft_meta_paths
    write_draft_meta_paths(str(tmp_path), str(tmp_path))  # must not raise


def test_a_backend_that_produces_no_file_fails_the_task(monkeypatch, tmp_path):
    """Found by mutation: deleting this check left the whole suite green.

    The CapCut backend returns the path it believes CapCut wrote to, read out of the
    export dialog. If CapCut silently wrote nothing, the task has to fail here --
    otherwise it reports success and the user goes looking for a file that is not there.
    """
    monkeypatch.setattr(export_impl, "gui_session_available", lambda: True)
    monkeypatch.setattr(export_impl, "_run_backend",
                        lambda backend, task_id, draft_id, options: str(tmp_path / "never_written.mp4"))

    result = export_video("d1", backend="capcut", wait=True)

    task = get_export_task_status(result["task_id"])
    assert task["status"] == "failed"
    assert "no output file" in task["error"]
