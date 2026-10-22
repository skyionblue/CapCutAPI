"""Full-fidelity export by driving the installed CapCut app (macOS).

NOT YET IMPLEMENTED — this is Phase 2 of docs: export-functionality-plan.md.

The Phase 0 spike (spikes/capcut_ui/) validated the whole flow end to end, including two
consecutive unattended exports. The mechanics it established, which this backend must follow:

  * Drive the home page by the accessibility ids CapCut exposes
    (`HomePageDraftTitle:<draft_id>` names each draft card by its folder name).
  * Open the dialog with `File > Export` via AXPress. AXPress works on native menus but NOT
    on CapCut's CEF-rendered buttons, which need real CGEvent clicks.
  * Hit-test every click against CGWindowList before firing it and refuse unless the target
    pixel belongs to CapCut. AX "frontmost" is NOT sufficient: with macOS Spaces, CapCut can
    be frontmost while a different Space is displayed, sending the click into another app.
  * Never send bare keystrokes — they bypass the hit-test and land in whatever is frontmost.
  * Re-read every element's coordinates immediately before clicking; CapCut's window moves
    and resizes mid-session.
  * Read the planned output path out of the dialog rather than trying to type one in. CapCut
    auto-renames on collision (1019.mp4 -> 1019(1).mp4) and the accessibility value reflects it.
  * Completion: destination file size stable across two polls, temp folders
    (`.__capcut_export_temp_folder_<epoch>__`) gone, and destination mtime newer than before.
  * Dismiss the post-export success panel (`automationcloseBtn`) — it blocks the next export.
"""

from typing import Any, Dict


def export(task_id: str, draft_id: str, options: Dict[str, Any]) -> str:
    raise NotImplementedError(
        "The 'capcut' export backend is not implemented yet (Phase 2). The approach is "
        "validated in spikes/capcut_ui/ — see FINDINGS.md. Use backend='ffmpeg' once Phase 3 "
        "lands, or export manually from CapCut in the meantime."
    )
