"""Bundle a saved draft, with its media, into a portable zip.

`save_draft` writes a draft CapCut can open *on this machine*: the media it references is
usually somewhere else on disk entirely, so zipping the folder alone produces a bundle that
opens with every clip missing.

This collects the referenced media as well and rewrites each path into CapCut's own relocatable
form — `##_draftpath_placeholder_<uuid>_##/assets/...` — which CapCut resolves relative to
whichever folder the draft ends up in. The result can be unzipped into a drafts folder on
another machine and opened.
"""

import json
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from export_backends.draft_model import resolve_path

logger = logging.getLogger('flask_video_generator')

DEFAULT_DRAFT_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

# Material collections that carry a file path.
PATH_COLLECTIONS = ("videos", "audios", "images")

BUNDLED_ASSETS_DIR = "assets"


def _placeholder(relative_path: str, token: str) -> str:
    """CapCut's relocatable path form, resolved against whatever folder the draft sits in."""
    return f"##_draftpath_placeholder_{token}_##/{relative_path}"


def _bundle_media(draft_data: Dict[str, Any], source_folder: str, staging: str,
                  token: str) -> Tuple[int, List[str]]:
    """Copy every referenced file into the bundle and rewrite its path. Returns (count, missing)."""
    assets_root = os.path.join(staging, BUNDLED_ASSETS_DIR)
    os.makedirs(assets_root, exist_ok=True)

    bundled: Dict[str, str] = {}      # absolute source path -> relative path in the bundle
    missing: List[str] = []
    materials = draft_data.get("materials") or {}

    for collection in PATH_COLLECTIONS:
        for material in materials.get(collection) or []:
            raw = material.get("path")
            if not raw:
                continue
            absolute = resolve_path(raw, source_folder)
            if not os.path.exists(absolute):
                missing.append(raw)
                continue

            relative = bundled.get(absolute)
            if relative is None:
                name = os.path.basename(absolute)
                target = os.path.join(assets_root, name)
                # Two different sources can share a basename; keep both.
                stem, extension = os.path.splitext(name)
                counter = 1
                while os.path.exists(target):
                    name = f"{stem}_{counter}{extension}"
                    target = os.path.join(assets_root, name)
                    counter += 1
                shutil.copy2(absolute, target)
                relative = f"{BUNDLED_ASSETS_DIR}/{name}"
                bundled[absolute] = relative

            material["path"] = _placeholder(relative, token)

    return len(bundled), missing


def export_draft_impl(draft_id: str, output_path: Optional[str] = None,
                      draft_folder: Optional[str] = None) -> Dict[str, Any]:
    """Zip a saved draft together with its media.

    :param draft_id: Draft to bundle. It must already have been saved with save_draft.
    :param output_path: Where to write the .zip. A directory is also accepted.
    :param draft_folder: Folder holding the draft; defaults to CapCut's drafts folder.
    :return: {"success", "output_path", "bundled_files", "size_bytes", "missing_media"}
    """
    if not draft_id:
        return {"success": False, "error": "draft_id is required"}

    folder = draft_folder or DEFAULT_DRAFT_FOLDER
    source_folder = os.path.join(folder, draft_id)
    info_path = os.path.join(source_folder, "draft_info.json")
    if not os.path.exists(info_path):
        return {
            "success": False,
            "error": (f"No saved draft at {source_folder}. Run save_draft first — this bundles "
                      f"what is on disk, not what is only in memory."),
        }

    staging = tempfile.mkdtemp(prefix=f"draft-bundle-{draft_id}-")
    try:
        bundle_root = os.path.join(staging, draft_id)
        # Skip any assets directory already present: media is re-collected below, so copying
        # it first would duplicate every file in the zip.
        shutil.copytree(
            source_folder, bundle_root,
            ignore=shutil.ignore_patterns(BUNDLED_ASSETS_DIR),
        )

        with open(os.path.join(bundle_root, "draft_info.json"), "r", encoding="utf-8") as handle:
            draft_data = json.load(handle)

        token = uuid.uuid4().hex[:12]
        bundled_count, missing = _bundle_media(draft_data, source_folder, bundle_root, token)

        with open(os.path.join(bundle_root, "draft_info.json"), "w", encoding="utf-8") as handle:
            json.dump(draft_data, handle, ensure_ascii=False, indent=4)

        target = _resolve_output(draft_id, output_path, staging)
        _zip_tree(bundle_root, target, draft_id)

        result: Dict[str, Any] = {
            "success": True,
            "output_path": target,
            "bundled_files": bundled_count,
            "size_bytes": os.path.getsize(target),
            "missing_media": missing,
        }
        if missing:
            result["message"] = (
                f"{len(missing)} referenced file(s) were not found on disk and are NOT in the "
                f"bundle; those clips will be missing when it is opened elsewhere."
            )
        logger.info("Bundled draft %s to %s (%d media files, %d missing)",
                    draft_id, target, bundled_count, len(missing))
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _resolve_output(draft_id: str, output_path: Optional[str], staging: str) -> str:
    if not output_path:
        return os.path.join(os.getcwd(), f"{draft_id}.zip")
    target = os.path.abspath(os.path.expanduser(output_path))
    # Anything that is not explicitly a .zip is taken as a directory to put the bundle in,
    # including one that does not exist yet — checking isdir() alone would silently write a
    # file named after the intended folder.
    if not target.lower().endswith(".zip"):
        os.makedirs(target, exist_ok=True)
        target = os.path.join(target, f"{draft_id}.zip")
    else:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    return target


def _zip_tree(root: str, target: str, arc_prefix: str) -> None:
    """Write the tree under `root` into a zip, nested beneath `arc_prefix`.

    Nesting matters: unzipping then yields a single draft folder rather than scattering
    draft_info.json and assets across the drafts directory.
    """
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory, _subdirs, files in os.walk(root):
            for name in files:
                absolute = os.path.join(directory, name)
                relative = os.path.relpath(absolute, root)
                archive.write(absolute, os.path.join(arc_prefix, relative))
