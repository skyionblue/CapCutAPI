"""In-memory draft cache backed by a disk store.

The cache alone is not enough: before this module persisted anything, a draft existed only in
the server process. Any restart — a crash, a config reload, an MCP client restart — made every
in-progress draft unrecoverable, because `save_draft` and `query_script` both look the draft up
by id and fail outright when it is missing. There was no way to rebuild the lost work.

So every mutation is written through to `DRAFT_STORE_DIR/<draft_id>.json`, and a cache miss
falls back to reading it. The LRU cache stays in front as the hot path; the store is the
durable record.
"""

import logging
import os
import threading
from collections import OrderedDict
from typing import Dict, Optional

import capcut_draft as draft
from settings.local import DRAFT_STORE_DIR

logger = logging.getLogger('flask_video_generator')

# Modify global variable, use OrderedDict to implement LRU cache, limit the maximum number to 10000
DRAFT_CACHE: Dict[str, 'draft.Script_file'] = OrderedDict()  # Use Dict for type hinting
MAX_CACHE_SIZE = 10000

# Mutations arrive from Flask request threads and MCP calls alike.
_LOCK = threading.RLock()


def store_path(draft_id: str) -> str:
    return os.path.join(DRAFT_STORE_DIR, f"{draft_id}.json")


def update_cache(key: str, value: draft.Script_file) -> None:
    """Update LRU cache"""
    with _LOCK:
        if key in DRAFT_CACHE:
            # If the key exists, delete the old item
            DRAFT_CACHE.pop(key)
        elif len(DRAFT_CACHE) >= MAX_CACHE_SIZE:
            print(f"{key}, Cache is full, deleting the least recently used item")
            # If the cache is full, delete the least recently used item (the first item)
            DRAFT_CACHE.popitem(last=False)
        # Add new item to the end (most recently used)
        DRAFT_CACHE[key] = value


def persist_draft(draft_id: str, script: Optional[draft.Script_file] = None) -> bool:
    """Write a draft to the durable store. Returns True when it reached disk.

    Never raises: a failure to persist must not break the edit the caller just made. The draft
    stays in memory and the failure is logged.
    """
    if not draft_id:
        return False
    with _LOCK:
        script = script if script is not None else DRAFT_CACHE.get(draft_id)
        if script is None:
            return False
        try:
            os.makedirs(DRAFT_STORE_DIR, exist_ok=True)
            # Write to a temporary file and replace, so a crash mid-write cannot leave a
            # half-written draft behind that would then fail to load.
            temp_path = store_path(draft_id) + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                handle.write(script.dumps())
            os.replace(temp_path, store_path(draft_id))
            return True
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Could not persist draft %s: %s", draft_id, e)
            return False


def load_persisted_draft(draft_id: str) -> Optional[draft.Script_file]:
    """Rebuild a draft from the store, or None if it is not there or unreadable.

    Content comes back on the Script_file's *imported* tracks and materials rather than its
    native ones. `dumps()` merges both, so saving and querying round-trip correctly; further
    edits append new tracks rather than extending the restored ones.
    """
    path = store_path(draft_id)
    if not os.path.exists(path):
        return None
    try:
        script = draft.Script_file.load_template(path)
        _promote_media_materials(script)
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning("Could not restore draft %s from %s: %s", draft_id, path, e)
        return None
    logger.info("Restored draft %s from the draft store", draft_id)
    return script


def _promote_media_materials(script: draft.Script_file) -> None:
    """Rebuild video and audio materials as objects on the restored draft.

    `load_template` puts everything on `imported_materials` as plain dicts. That is fine for
    dumping, but save_draft walks `script.materials.videos` / `.audios` -- objects with
    `remote_url` and `replace_path` -- to decide what to download. Left as dicts, a draft
    saved after a restart downloads nothing and lands in CapCut with every clip missing.

    Promoted entries are removed from `imported_materials` so `dumps()` does not emit them
    twice; the imported tracks still reference them by material id, which `from_dict`
    preserves.
    """
    for key, cls, bucket in (
        ("videos", draft.Video_material, script.materials.videos),
        ("audios", draft.Audio_material, script.materials.audios),
    ):
        entries = (script.imported_materials or {}).get(key) or []
        if not entries:
            continue
        promoted = []
        for entry in list(entries):
            try:
                bucket.append(cls.from_dict(entry))
                promoted.append(entry)
            except Exception as e:  # noqa: BLE001 - one bad entry must not lose the draft
                logger.warning("Could not rebuild %s material %s: %s", key, entry.get("id"), e)
        for entry in promoted:
            entries.remove(entry)


def get_script(draft_id: str) -> Optional[draft.Script_file]:
    """The draft for an id: from cache, else restored from the store, else None."""
    if not draft_id:
        return None
    with _LOCK:
        script = DRAFT_CACHE.get(draft_id)
        if script is not None:
            update_cache(draft_id, script)       # refresh LRU position
            return script
        script = load_persisted_draft(draft_id)
        if script is not None:
            update_cache(draft_id, script)
        return script


def forget_draft(draft_id: str) -> None:
    """Drop a draft from both cache and store."""
    with _LOCK:
        DRAFT_CACHE.pop(draft_id, None)
        try:
            os.remove(store_path(draft_id))
        except OSError:
            pass


def list_persisted_drafts() -> list:
    """Draft ids currently recoverable from the store."""
    try:
        return sorted(
            name[:-5] for name in os.listdir(DRAFT_STORE_DIR) if name.endswith(".json")
        )
    except OSError:
        return []
