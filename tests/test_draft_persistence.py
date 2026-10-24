"""Tests for draft durability across a restart.

Before the draft store existed, a draft lived only in the server process: any restart made
in-progress work unrecoverable, and `get_or_create_draft` silently handed back a brand new
draft under a new id instead of the caller's. These tests pin that behaviour down.
"""

import os

import pytest

import draft_cache
import capcut_draft as draft
from draft_cache import (
    DRAFT_CACHE, forget_draft, get_script, list_persisted_drafts,
    load_persisted_draft, persist_draft, store_path, update_cache,
)
from tests.conftest import requires_ffmpeg


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Point the store at a temp directory and start from an empty cache."""
    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", str(tmp_path / "store"))
    DRAFT_CACHE.clear()
    yield
    DRAFT_CACHE.clear()


def make_draft(draft_id="d1", width=1080, height=1920):
    script = draft.Script_file(width, height)
    update_cache(draft_id, script)
    return script


def simulate_restart():
    """A restart keeps the disk store and loses the in-memory cache."""
    DRAFT_CACHE.clear()


# --------------------------------------------------------------- the core guarantee

def test_draft_survives_a_restart():
    make_draft("d1")
    assert persist_draft("d1") is True

    simulate_restart()
    assert "d1" not in DRAFT_CACHE

    restored = get_script("d1")
    assert restored is not None, "the draft must be recoverable after a restart"
    assert (restored.width, restored.height) == (1080, 1920)


def test_restored_draft_is_put_back_in_the_cache():
    make_draft("d1")
    persist_draft("d1")
    simulate_restart()

    get_script("d1")
    assert "d1" in DRAFT_CACHE, "a restore should warm the cache, not re-read every time"


def test_get_or_create_draft_restores_rather_than_creating_a_new_one():
    """The behaviour that previously lost work.

    An unknown-to-cache draft_id used to fall through to creating a fresh draft under a NEW
    id, so a caller resuming after a restart silently started over.
    """
    from create_draft import get_or_create_draft

    make_draft("d1")
    persist_draft("d1")
    simulate_restart()

    returned_id, script = get_or_create_draft("d1")
    assert returned_id == "d1", "resuming a known draft must not mint a new id"
    assert script is not None


def test_unknown_draft_id_still_creates_a_new_draft():
    """Recovery must not turn a genuinely unknown id into an error."""
    from create_draft import get_or_create_draft

    returned_id, script = get_or_create_draft("never-existed")
    assert returned_id != "never-existed"
    assert script is not None


# --------------------------------------------------------------- store mechanics

def test_persisted_content_round_trips():
    script = make_draft("d1")
    script.duration = 5_000_000
    persist_draft("d1")

    restored = load_persisted_draft("d1")
    assert restored is not None
    assert restored.duration == 5_000_000


def test_persist_writes_atomically_leaving_no_temp_file():
    make_draft("d1")
    persist_draft("d1")
    store_dir = os.path.dirname(store_path("d1"))
    assert not [n for n in os.listdir(store_dir) if n.endswith(".tmp")]


def test_persist_is_idempotent():
    make_draft("d1")
    assert persist_draft("d1") is True
    assert persist_draft("d1") is True
    assert list_persisted_drafts() == ["d1"]


def test_persist_of_an_unknown_draft_is_a_no_op_not_an_error():
    assert persist_draft("nothing-here") is False
    assert persist_draft("") is False


def test_persist_failure_does_not_raise(monkeypatch):
    """A store failure must never break the edit the caller just made."""
    make_draft("d1")
    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", "/proc/nonexistent/forbidden")
    assert persist_draft("d1") is False      # reported, not raised
    assert get_script("d1") is not None       # still usable from memory


def test_corrupt_store_file_is_reported_not_raised():
    make_draft("d1")
    persist_draft("d1")
    with open(store_path("d1"), "w", encoding="utf-8") as handle:
        handle.write("{ not valid json")
    simulate_restart()
    assert get_script("d1") is None


def test_missing_draft_returns_none():
    assert get_script("absent") is None
    assert get_script("") is None


def test_forget_draft_clears_cache_and_store():
    make_draft("d1")
    persist_draft("d1")
    forget_draft("d1")
    assert "d1" not in DRAFT_CACHE
    assert not os.path.exists(store_path("d1"))
    assert get_script("d1") is None


def test_list_persisted_drafts():
    for draft_id in ("d1", "d2"):
        make_draft(draft_id)
        persist_draft(draft_id)
    assert list_persisted_drafts() == ["d1", "d2"]


def test_list_persisted_drafts_on_a_missing_store_is_empty():
    assert list_persisted_drafts() == []


# --------------------------------------------------------------- media survives a restore

def _video_draft(draft_id, source_path):
    """A draft holding one video material, built the way add_video builds it."""
    from add_video_track import add_video_track
    result = add_video_track(video_url=source_path, duration=3.0, track_name="t")
    return result["draft_id"]


@requires_ffmpeg
def test_restored_draft_keeps_media_materials_reachable(media):
    """Regression: a restored draft had no native materials, so save_draft downloaded nothing.

    `Script_file.load_template` puts everything on `imported_materials` as plain dicts, but
    save_draft walks `script.materials.videos` -- objects carrying `remote_url` -- to decide
    what to fetch. Left as dicts, a draft saved after a restart reached CapCut with every clip
    missing, and nothing reported a problem.
    """
    draft_id = _video_draft("d-media", media["with_audio"])
    assert len(DRAFT_CACHE[draft_id].materials.videos) == 1

    simulate_restart()
    restored = get_script(draft_id)
    assert restored is not None
    assert len(restored.materials.videos) == 1, (
        "media materials must be reachable as objects after a restore, or save_draft "
        "silently produces a draft with no media"
    )


@requires_ffmpeg
def test_remote_url_survives_a_restore(media):
    """Regression: from_dict never restored remote_url, though export_json writes it.

    Without it a restored material has no source to fetch from, so even a reachable material
    downloads nothing.
    """
    draft_id = _video_draft("d-url", media["with_audio"])
    before = DRAFT_CACHE[draft_id].materials.videos[0].remote_url
    assert before

    simulate_restart()
    assert get_script(draft_id).materials.videos[0].remote_url == before


@requires_ffmpeg
def test_restore_does_not_duplicate_materials(media):
    """Promoted materials must leave imported_materials, or dumps() emits them twice."""
    import json

    draft_id = _video_draft("d-dup", media["with_audio"])
    before = json.loads(DRAFT_CACHE[draft_id].dumps())

    simulate_restart()
    after = json.loads(get_script(draft_id).dumps())

    assert len(after["materials"]["videos"]) == len(before["materials"]["videos"]) == 1
    assert (sum(len(t.get("segments", [])) for t in after["tracks"])
            == sum(len(t.get("segments", [])) for t in before["tracks"]))


@requires_ffmpeg
def test_restored_draft_round_trips_its_key_fields(media):
    import json

    draft_id = _video_draft("d-fields", media["with_audio"])
    before = json.loads(DRAFT_CACHE[draft_id].dumps())["materials"]["videos"][0]
    simulate_restart()
    after = json.loads(get_script(draft_id).dumps())["materials"]["videos"][0]

    for field in ("id", "duration", "material_name", "type", "remote_url"):
        assert after.get(field) == before.get(field), f"{field} was lost on restore"
