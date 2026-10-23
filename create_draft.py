import uuid
import pyJianYingDraft as draft
import time
from draft_cache import get_script, persist_draft, update_cache

def create_draft(width=1080, height=1920):
    """
    Create new CapCut draft
    :param width: Video width, default 1080
    :param height: Video height, default 1920
    :return: (draft_name, draft_path, draft_id, draft_url)
    """
    # Generate timestamp and draft_id
    unix_time = int(time.time())
    unique_id = uuid.uuid4().hex[:8]  # Take the first 8 digits of UUID
    draft_id = f"dfd_cat_{unix_time}_{unique_id}"  # Use Unix timestamp and UUID combination

    # Create CapCut draft with specified resolution
    script = draft.Script_file(width, height)

    # Store in global cache and write through to the durable store
    update_cache(draft_id, script)
    persist_draft(draft_id, script)

    return script, draft_id

def get_or_create_draft(draft_id=None, width=1080, height=1920):
    """
    Get or create CapCut draft
    :param draft_id: Draft ID, if None or corresponding zip file not found, create new draft
    :param width: Video width, default 1080
    :param height: Video height, default 1920
    :return: (draft_name, draft_path, draft_id, draft_dir, script)
    """
    if draft_id is not None:
        # Cache first, then the durable store: after a restart the draft is no longer in
        # memory, and silently creating a new one would lose the caller's work.
        script = get_script(draft_id)
        if script is not None:
            print(f"Getting draft: {draft_id}")
            return draft_id, script

    # Create new draft logic
    print("Creating new draft")
    script, generate_draft_id = create_draft(
        width=width,
        height=height,
    )
    return generate_draft_id, script
