"""Headless export by compiling the draft timeline into an ffmpeg filtergraph.

NOT YET IMPLEMENTED — this is Phase 3 of docs: export-functionality-plan.md.

Intended coverage: trims, cuts, concat, scale/position/rotate/opacity transforms, crossfades
(xfade), audio mixing with per-segment volume and fades, and subtitles.

Intended NON-coverage: CapCut effects, filters, masks, animations and stickers are stored only
as CapCut effect IDs and are resolved by CapCut's own renderer. This backend MUST report every
one it cannot reproduce through export_task_cache.add_fidelity_warning, so a caller is never
handed a silently degraded video.
"""

from typing import Any, Dict


def export(task_id: str, draft_id: str, options: Dict[str, Any]) -> str:
    raise NotImplementedError(
        "The 'ffmpeg' export backend is not implemented yet (Phase 3). Use backend='capcut' "
        "on a macOS machine with CapCut installed once Phase 2 lands."
    )
