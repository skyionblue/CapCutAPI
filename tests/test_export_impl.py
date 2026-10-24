"""Tests for export dispatch, backend resolution and argument validation."""

import pytest

import export_impl
from export_impl import BackendUnavailable, ExportError, export_preflight, export_video, resolve_backend


@pytest.fixture(autouse=True)
def draft_already_saved(monkeypatch):
    """These tests exercise backend dispatch, not the save-first step.

    export_video saves an unsaved draft before dispatching, so a fake draft_id would
    otherwise fail at that gate and never reach the backend being tested.
    """
    monkeypatch.setattr(export_impl, "_ensure_on_disk",
                        lambda task_id, draft_id, draft_folder: None)


@pytest.fixture
def backends(monkeypatch):
    """Control which backends appear available."""
    def configure(gui=True, ffmpeg=True):
        monkeypatch.setattr(export_impl, "gui_session_available", lambda: gui)
        monkeypatch.setattr(export_impl, "ffmpeg_available", lambda: ffmpeg)
    return configure


def test_auto_prefers_full_fidelity_capcut(backends):
    backends(gui=True, ffmpeg=True)
    assert resolve_backend("auto") == "capcut"


def test_auto_falls_back_to_ffmpeg_without_a_gui(backends):
    backends(gui=False, ffmpeg=True)
    assert resolve_backend("auto") == "ffmpeg"


def test_auto_raises_when_nothing_is_available(backends):
    backends(gui=False, ffmpeg=False)
    with pytest.raises(BackendUnavailable):
        resolve_backend("auto")


def test_explicit_capcut_without_a_gui_names_the_alternative(backends):
    backends(gui=False, ffmpeg=True)
    with pytest.raises(BackendUnavailable, match="ffmpeg"):
        resolve_backend("capcut")


def test_explicit_ffmpeg_without_ffmpeg_is_rejected(backends):
    backends(gui=True, ffmpeg=False)
    with pytest.raises(BackendUnavailable):
        resolve_backend("ffmpeg")


def test_unknown_backend_is_rejected(backends):
    backends()
    with pytest.raises(ExportError, match="Unknown backend"):
        resolve_backend("nope")


def test_export_video_requires_a_draft_id(backends):
    backends()
    result = export_video("")
    assert result["success"] is False
    assert "draft_id" in result["error"]


def test_export_video_surfaces_backend_unavailability_without_starting_a_task(backends):
    backends(gui=False, ffmpeg=False)
    result = export_video("d1")
    assert result["success"] is False
    assert "task_id" not in result


def test_export_video_returns_a_task_id_and_does_not_block(backends, monkeypatch):
    backends()
    monkeypatch.setattr(export_impl, "_run_backend",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stub")))
    result = export_video("d1", backend="ffmpeg")
    assert result["success"] is True
    assert result["task_id"].startswith("export-d1-")
    assert result["backend"] == "ffmpeg"
    # The contract is that the caller polls; the message must say so.
    assert "query_export_status" in result["message"]


def test_backend_failure_is_recorded_on_the_task(backends, monkeypatch):
    backends()
    def boom(*args, **kwargs):
        raise RuntimeError("backend exploded")
    monkeypatch.setattr(export_impl, "_run_backend", boom)
    result = export_video("d1", backend="ffmpeg", wait=True, timeout=10)
    assert result["status"] == "failed"
    assert "backend exploded" in result["error"]


def test_preflight_reports_both_backends_and_their_fidelity(backends):
    backends(gui=False, ffmpeg=True)
    report = export_preflight()
    by_name = {b["name"]: b for b in report["backends"]}
    assert by_name["capcut"]["available"] is False
    assert by_name["capcut"]["reason"]          # must explain why
    assert by_name["ffmpeg"]["fidelity"] == "subset"
    assert report["default"] == "ffmpeg"
