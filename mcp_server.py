#!/usr/bin/env python3
"""
CapCut API MCP Server (2-tool gateway)

Exposes the full CapCut editing toolset (draft creation, video/audio/image/text/
subtitle/effect/sticker/keyframe operations) behind two MCP tools instead of one
per capability, so the tool list stays small:

  - search_tools(query): discover available editing tools and their input schemas
  - invoke_tool(name, arguments): execute one of them by name

Runs over stdio using the official `mcp` SDK (FastMCP).
"""

import sys
import os
import shutil
import io
import json
import contextlib
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.mcpserver import MCPServer

from create_draft import get_or_create_draft
from add_text_impl import add_text_impl
from add_video_track import add_video_track
from add_audio_track import add_audio_track
from add_image_impl import add_image_impl
from add_subtitle_impl import add_subtitle_impl
from add_effect_impl import add_effect_impl
from add_sticker_impl import add_sticker_impl
from add_video_keyframe_impl import add_video_keyframe_impl
from get_duration_impl import get_video_duration
from save_draft_impl import save_draft_impl, query_script_impl, query_task_status, build_asset_path
from util import generate_draft_url as util_generate_draft_url
from pyJianYingDraft.text_segment import TextStyleRange
from pyJianYingDraft import Text_style, Video_material, Audio_material

from pyJianYingDraft.metadata.capcut_animation_meta import (
    CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type,
)
from pyJianYingDraft.metadata.capcut_transition_meta import CapCut_Transition_type
from pyJianYingDraft.metadata.capcut_mask_meta import CapCut_Mask_type
from pyJianYingDraft.metadata.capcut_audio_effect_meta import (
    CapCut_Voice_filters_effect_type, CapCut_Voice_characters_effect_type, CapCut_Speech_to_song_effect_type,
)
from pyJianYingDraft.metadata.font_meta import Font_type
from pyJianYingDraft.metadata.capcut_text_animation_meta import (
    CapCut_Text_intro, CapCut_Text_outro, CapCut_Text_loop_anim,
)
from pyJianYingDraft.metadata.capcut_effect_meta import (
    CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type,
)
from util import hex_to_rgb, url_to_hash

# category -> enum, for list_option_values.
# "audio_effect" isn't here — it merges three enums and carries param info, so it's
# handled separately in execute_tool.
OPTION_CATEGORIES = {
    "transition": CapCut_Transition_type,
    "mask": CapCut_Mask_type,
    "font": Font_type,
    "text_intro": CapCut_Text_intro,
    "text_outro": CapCut_Text_outro,
    "text_loop_anim": CapCut_Text_loop_anim,
    "video_scene_effect": CapCut_Video_scene_effect_type,
    "video_character_effect": CapCut_Video_character_effect_type,
    "intro_animation": CapCut_Intro_type,
    "outro_animation": CapCut_Outro_type,
    "combo_animation": CapCut_Group_animation_type,
}
ALL_OPTION_CATEGORIES = sorted(OPTION_CATEGORIES) + ["audio_effect"]

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Where CapCut actually looks for local drafts on this machine.
DEFAULT_DRAFT_FOLDER = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")

# Full tool registry. This is what search_tools searches and invoke_tool dispatches to.
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "create_draft",
        "description": "Create a new CapCut draft (project). Returns a draft_id to pass to every other tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
            },
        },
    },
    {
        "name": "add_video",
        "description": "Add a video clip to the draft's timeline. Supports transitions, masks, background blur.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "Local file path or URL of the video"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "start": {"type": "number", "default": 0, "description": "Trim start within the source clip (seconds)"},
                "end": {"type": "number", "description": "Trim end within the source clip (seconds)"},
                "target_start": {"type": "number", "default": 0, "description": "Placement start on the timeline (seconds)"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
                "transform_x": {"type": "number", "default": 0, "description": "X position"},
                "transform_y": {"type": "number", "default": 0, "description": "Y position"},
                "scale_x": {"type": "number", "default": 1, "description": "X scale"},
                "scale_y": {"type": "number", "default": 1, "description": "Y scale"},
                "speed": {"type": "number", "default": 1.0, "description": "Playback speed"},
                "track_name": {"type": "string", "default": "main", "description": "Track name"},
                "volume": {"type": "number", "default": 1.0, "description": "Volume (0.0-1.0+)"},
                "transition": {"type": "string", "description": "Transition type — see list_option_values('transition')"},
                "transition_duration": {"type": "number", "default": 0.5, "description": "Transition duration (seconds)"},
                "relative_index": {"type": "integer", "default": 0, "description": "Stacking order among tracks of the same type (higher = closer to foreground)"},
                "duration": {"type": "number", "description": "Override detected clip duration (seconds); skips duration probing"},
                "mask_type": {"type": "string", "description": "Mask type — see list_option_values('mask')"},
                "mask_center_x": {"type": "number", "default": 0.5, "description": "Mask center X (0-1)"},
                "mask_center_y": {"type": "number", "default": 0.5, "description": "Mask center Y (0-1)"},
                "mask_size": {"type": "number", "default": 1.0, "description": "Mask size (0-1)"},
                "mask_rotation": {"type": "number", "default": 0.0, "description": "Mask rotation angle (degrees)"},
                "mask_feather": {"type": "number", "default": 0.0, "description": "Mask feather amount (0-1)"},
                "mask_invert": {"type": "boolean", "default": False, "description": "Invert the mask"},
                "mask_rect_width": {"type": "number", "description": "Rectangle mask width, fraction of material width (rectangle mask only)"},
                "mask_round_corner": {"type": "number", "description": "Rectangle mask corner radius, 0-100 (rectangle mask only)"},
                "background_blur": {"type": "integer", "description": "Background blur level (1-4)"},
                "draft_folder": {"type": "string", "description": "Local draft folder path override (rarely needed)"},
            },
            "required": ["video_url"],
        },
    },
    {
        "name": "add_audio",
        "description": "Add an audio clip to the draft (music, VO, SFX). Supports volume and speed control.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_url": {"type": "string", "description": "Local file path or URL of the audio"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "start": {"type": "number", "default": 0, "description": "Trim start within the source clip (seconds)"},
                "end": {"type": "number", "description": "Trim end within the source clip (seconds)"},
                "target_start": {"type": "number", "default": 0, "description": "Placement start on the timeline (seconds)"},
                "volume": {"type": "number", "default": 1.0, "description": "Volume (0.0-1.0+)"},
                "speed": {"type": "number", "default": 1.0, "description": "Playback speed"},
                "track_name": {"type": "string", "default": "audio_main", "description": "Track name"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
                "duration": {"type": "number", "description": "Override detected clip duration (seconds); skips duration probing"},
                "sound_effects": {
                    "type": "array",
                    "description": "List of [effect_name, param_list] pairs — effect names from list_option_values('audio_effect')",
                },
                "draft_folder": {"type": "string", "description": "Local draft folder path override (rarely needed)"},
            },
            "required": ["audio_url"],
        },
    },
    {
        "name": "add_image",
        "description": "Add an image to the draft. Supports intro/outro animation, transitions, masks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Local file path or URL of the image"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "start": {"type": "number", "default": 0, "description": "Placement start on the timeline (seconds)"},
                "end": {"type": "number", "default": 3.0, "description": "Placement end on the timeline (seconds)"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
                "transform_x": {"type": "number", "default": 0, "description": "X position"},
                "transform_y": {"type": "number", "default": 0, "description": "Y position"},
                "scale_x": {"type": "number", "default": 1, "description": "X scale"},
                "scale_y": {"type": "number", "default": 1, "description": "Y scale"},
                "track_name": {"type": "string", "default": "main", "description": "Track name"},
                "relative_index": {"type": "integer", "default": 0, "description": "Stacking order among tracks of the same type (higher = closer to foreground)"},
                "intro_animation": {"type": "string", "description": "Intro animation type — see list_option_values('intro_animation'); mutually exclusive with combo_animation"},
                "intro_animation_duration": {"type": "number", "default": 0.5, "description": "Intro animation duration (seconds)"},
                "outro_animation": {"type": "string", "description": "Outro animation type — see list_option_values('outro_animation')"},
                "outro_animation_duration": {"type": "number", "default": 0.5, "description": "Outro animation duration (seconds)"},
                "combo_animation": {"type": "string", "description": "Combo animation type — see list_option_values('combo_animation'); mutually exclusive with intro_animation"},
                "combo_animation_duration": {"type": "number", "default": 0.5, "description": "Combo animation duration (seconds)"},
                "transition": {"type": "string", "description": "Transition type — see list_option_values('transition')"},
                "transition_duration": {"type": "number", "default": 0.5, "description": "Transition duration (seconds)"},
                "mask_type": {"type": "string", "description": "Mask type — see list_option_values('mask')"},
                "mask_center_x": {"type": "number", "default": 0.0, "description": "Mask center X (material pixels; default is material center)"},
                "mask_center_y": {"type": "number", "default": 0.0, "description": "Mask center Y (material pixels; default is material center)"},
                "mask_size": {"type": "number", "default": 0.5, "description": "Mask size, fraction of material height"},
                "mask_rotation": {"type": "number", "default": 0.0, "description": "Mask rotation angle (degrees, clockwise)"},
                "mask_feather": {"type": "number", "default": 0.0, "description": "Mask feather amount (0-100)"},
                "mask_invert": {"type": "boolean", "default": False, "description": "Invert the mask"},
                "mask_rect_width": {"type": "number", "description": "Rectangle mask width, fraction of material width (rectangle mask only)"},
                "mask_round_corner": {"type": "number", "description": "Rectangle mask corner radius, 0-100 (rectangle mask only)"},
                "background_blur": {"type": "integer", "description": "Background blur level (1-4)"},
                "draft_folder": {"type": "string", "description": "Local draft folder path override (rarely needed)"},
            },
            "required": ["image_url"],
        },
    },
    {
        "name": "add_text",
        "description": "Add text to the draft. Supports multi-style runs, shadow, and background box.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content"},
                "start": {"type": "number", "description": "Placement start on the timeline (seconds)"},
                "end": {"type": "number", "description": "Placement end on the timeline (seconds)"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "track_name": {"type": "string", "default": "text_main", "description": "Track name"},
                "transform_x": {"type": "number", "default": 0, "description": "X position"},
                "transform_y": {"type": "number", "default": -0.8, "description": "Y position"},
                "vertical": {"type": "boolean", "default": False, "description": "Display text vertically"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
                "fixed_width": {"type": "number", "default": -1, "description": "Fixed text box width (-1 = not fixed)"},
                "fixed_height": {"type": "number", "default": -1, "description": "Fixed text box height (-1 = not fixed)"},
                "font": {"type": "string", "description": "Font name — see list_option_values('font')"},
                "font_color": {"type": "string", "default": "#ffffff", "description": "Font color"},
                "font_size": {"type": "integer", "default": 24, "description": "Font size"},
                "font_alpha": {"type": "number", "default": 1.0, "description": "Font opacity"},
                "border_width": {"type": "number", "default": 0.0, "description": "Outline width (0 = no outline)"},
                "border_color": {"type": "string", "default": "#000000", "description": "Outline color"},
                "border_alpha": {"type": "number", "default": 1.0, "description": "Outline opacity"},
                "shadow_enabled": {"type": "boolean", "default": False, "description": "Enable text shadow"},
                "shadow_color": {"type": "string", "default": "#000000", "description": "Shadow color"},
                "shadow_alpha": {"type": "number", "default": 0.8, "description": "Shadow opacity"},
                "shadow_angle": {"type": "number", "default": 315.0, "description": "Shadow angle"},
                "shadow_distance": {"type": "number", "default": 5.0, "description": "Shadow distance"},
                "shadow_smoothing": {"type": "number", "default": 0.0, "description": "Shadow smoothing"},
                "background_color": {"type": "string", "description": "Background box color"},
                "background_alpha": {"type": "number", "default": 1.0, "description": "Background box opacity"},
                "background_style": {"type": "integer", "default": 0, "description": "Background box style"},
                "background_round_radius": {"type": "number", "default": 0.0, "description": "Background box corner radius"},
                "background_height": {"type": "number", "default": 0.14, "description": "Background box height (fraction of frame)"},
                "background_width": {"type": "number", "default": 0.14, "description": "Background box width (fraction of frame)"},
                "background_horizontal_offset": {"type": "number", "default": 0.5, "description": "Background box horizontal offset"},
                "background_vertical_offset": {"type": "number", "default": 0.5, "description": "Background box vertical offset"},
                "bubble_effect_id": {"type": "string", "description": "Text bubble effect ID"},
                "bubble_resource_id": {"type": "string", "description": "Text bubble resource ID"},
                "effect_effect_id": {"type": "string", "description": "Text visual effect ID"},
                "intro_animation": {"type": "string", "description": "Text entrance animation — see list_option_values('text_intro')"},
                "intro_duration": {"type": "number", "default": 0.5, "description": "Intro animation duration (seconds)"},
                "outro_animation": {"type": "string", "description": "Text exit animation — see list_option_values('text_outro')"},
                "outro_duration": {"type": "number", "default": 0.5, "description": "Outro animation duration (seconds)"},
                "text_styles": {
                    "type": "array",
                    "description": "Per-range style overrides: list of {start, end, font_size, font_color, bold, italic, underline}",
                },
            },
            "required": ["text", "start", "end"],
        },
    },
    {
        "name": "add_subtitle",
        "description": "Import an SRT subtitle file into the draft, with styling.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "srt_path": {"type": "string", "description": "Local file path or URL of the SRT file"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "track_name": {"type": "string", "default": "subtitle", "description": "Track name"},
                "time_offset": {"type": "number", "default": 0, "description": "Time offset (seconds)"},
                "font": {"type": "string", "description": "Font"},
                "font_size": {"type": "number", "default": 8.0, "description": "Font size"},
                "font_color": {"type": "string", "default": "#FFFFFF", "description": "Font color"},
                "bold": {"type": "boolean", "default": False, "description": "Bold"},
                "italic": {"type": "boolean", "default": False, "description": "Italic"},
                "underline": {"type": "boolean", "default": False, "description": "Underline"},
                "border_width": {"type": "number", "default": 0.0, "description": "Outline width"},
                "border_color": {"type": "string", "default": "#000000", "description": "Outline color"},
                "border_alpha": {"type": "number", "default": 1.0, "description": "Outline opacity"},
                "background_color": {"type": "string", "default": "#000000", "description": "Background color"},
                "background_style": {"type": "integer", "default": 1, "description": "Background box style"},
                "background_alpha": {"type": "number", "default": 0.0, "description": "Background opacity"},
                "bubble_effect_id": {"type": "string", "description": "Text bubble effect ID"},
                "bubble_resource_id": {"type": "string", "description": "Text bubble resource ID"},
                "effect_effect_id": {"type": "string", "description": "Text visual effect ID"},
                "transform_x": {"type": "number", "default": 0.0, "description": "X position"},
                "transform_y": {"type": "number", "default": -0.8, "description": "Y position"},
                "scale_x": {"type": "number", "default": 1.0, "description": "X scale"},
                "scale_y": {"type": "number", "default": 1.0, "description": "Y scale"},
                "rotation": {"type": "number", "default": 0.0, "description": "Rotation angle"},
                "vertical": {"type": "boolean", "default": True, "description": "Display subtitle vertically"},
                "alpha": {"type": "number", "default": 0.4, "description": "Overall opacity"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
            },
            "required": ["srt_path"],
        },
    },
    {
        "name": "add_effect",
        "description": "Add a visual effect to the draft on its own effect track.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "effect_type": {"type": "string", "description": "Effect type name"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "start": {"type": "number", "default": 0, "description": "Placement start on the timeline (seconds)"},
                "end": {"type": "number", "default": 3.0, "description": "Placement end on the timeline (seconds)"},
                "track_name": {"type": "string", "default": "effect_01", "description": "Track name"},
                "params": {"type": "array", "description": "Effect parameter list"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
            },
            "required": ["effect_type"],
        },
    },
    {
        "name": "add_sticker",
        "description": "Add a sticker to the draft.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Sticker resource ID"},
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "start": {"type": "number", "description": "Placement start on the timeline (seconds)"},
                "end": {"type": "number", "description": "Placement end on the timeline (seconds)"},
                "transform_x": {"type": "number", "default": 0, "description": "X position"},
                "transform_y": {"type": "number", "default": 0, "description": "Y position"},
                "scale_x": {"type": "number", "default": 1.0, "description": "X scale"},
                "scale_y": {"type": "number", "default": 1.0, "description": "Y scale"},
                "alpha": {"type": "number", "default": 1.0, "description": "Opacity"},
                "rotation": {"type": "number", "default": 0.0, "description": "Rotation angle"},
                "flip_horizontal": {"type": "boolean", "default": False, "description": "Flip horizontally"},
                "flip_vertical": {"type": "boolean", "default": False, "description": "Flip vertically"},
                "track_name": {"type": "string", "default": "sticker_main", "description": "Track name"},
                "relative_index": {"type": "integer", "default": 0, "description": "Stacking order among tracks of the same type (higher = closer to foreground)"},
                "width": {"type": "integer", "default": 1080, "description": "Video width in pixels"},
                "height": {"type": "integer", "default": 1920, "description": "Video height in pixels"},
            },
            "required": ["resource_id", "start", "end"],
        },
    },
    {
        "name": "add_video_keyframe",
        "description": "Add keyframe(s) animating a property (position, scale, rotation, opacity, ...) over time. Use property_type/time/value for one keyframe, or the plural property_types/times/values for several at once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "track_name": {"type": "string", "default": "main", "description": "Track name"},
                "property_type": {
                    "type": "string",
                    "description": "Keyframe property (position_x, position_y, rotation, scale_x, scale_y, uniform_scale, alpha, saturation, contrast, brightness, volume)",
                },
                "time": {"type": "number", "default": 0.0, "description": "Keyframe time (seconds)"},
                "value": {"type": "string", "description": "Keyframe value"},
                "property_types": {"type": "array", "description": "Batch mode: list of property types"},
                "times": {"type": "array", "description": "Batch mode: list of keyframe times"},
                "values": {"type": "array", "description": "Batch mode: list of keyframe values"},
            },
        },
    },
    {
        "name": "get_video_duration",
        "description": "Get the duration of a video file (local path or URL).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "Local file path or URL of the video"},
            },
            "required": ["video_url"],
        },
    },
    {
        "name": "save_draft",
        "description": (
            "Render the draft to disk and place it in CapCut's local drafts folder so it appears in the "
            "CapCut app. Returns local_path, the final on-disk location of the draft."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "draft_folder": {
                    "type": "string",
                    "description": f"Target CapCut drafts folder. Defaults to {DEFAULT_DRAFT_FOLDER}",
                },
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "list_option_values",
        "description": (
            "List the valid string values for an enum-typed parameter used by other tools "
            "(e.g. add_video/add_image's transition or mask_type, add_effect's effect_type, "
            "add_subtitle's font, add_sticker's animation-adjacent params). Call this before "
            "guessing a value for any such parameter — invalid strings fail silently or error "
            "deep in the underlying draft library."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ALL_OPTION_CATEGORIES,
                    "description": "Which set of option values to list.",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "query_script",
        "description": (
            "Get a draft's full current timeline as JSON (tracks, segments, materials, durations). "
            "Use it to inspect what's already on a draft before adding more (e.g. to find where the "
            "last clip ends) or to verify an edit landed as expected."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "force_update": {
                    "type": "boolean",
                    "default": True,
                    "description": "Re-derive computed fields (like total duration) before returning",
                },
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "query_draft_status",
        "description": (
            "Poll the status/progress of a save_draft task by its task_id (the draft_id used for "
            "save_draft). Only useful if a save is slow enough to need polling — the gateway's "
            "save_draft currently returns synchronously, so this is mostly a safety net."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID — same value as the draft_id passed to save_draft"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "generate_draft_url",
        "description": (
            "Format the cloud preview/download URL for a draft_id. Only meaningful if the cloud OSS/"
            "preview flow in config.json is actually configured — otherwise this returns a URL that "
            "won't resolve to anything real. save_draft's local_path is what matters for local use."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
            },
            "required": ["draft_id"],
        },
    },
    {
        "name": "replace_material",
        "description": (
            "Swap the underlying video/audio/image file on an existing material without touching "
            "any segment's transforms, masks, effects, or keyframes — unlike add_video/add_image/"
            "add_audio, which always create a new segment. Use this to drop final footage into a "
            "shot that was already built out around a placeholder clip. Find the exact material_name "
            "first via query_script (materials.videos[].material_name for video/image, "
            "materials.audios[].name for audio)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID from create_draft"},
                "material_name": {"type": "string", "description": "Exact name of the existing material to replace, from query_script"},
                "new_url": {"type": "string", "description": "Local file path or URL of the replacement file"},
                "material_type": {"type": "string", "enum": ["video", "audio"], "default": "video", "description": "'video' also covers images; 'audio' for audio materials"},
                "duration": {"type": "number", "description": "Duration of the new file (seconds). Rarely needed — replacing a material doesn't change the segment's timerange."},
                "replace_crop": {"type": "boolean", "default": False, "description": "Also replace the original material's crop settings (video only)"},
                "draft_folder": {"type": "string", "description": "Local draft folder path override (rarely needed)"},
            },
            "required": ["draft_id", "material_name", "new_url"],
        },
    },
    {
        "name": "list_drafts",
        "description": (
            "List drafts currently sitting in the local CapCut drafts folder, so you can resume or "
            "reference existing work instead of only ever creating new drafts."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_draft",
        "description": (
            "Permanently delete a draft folder from the local CapCut drafts folder. Irreversible — "
            "the draft will no longer appear in CapCut. Use list_drafts first to confirm the draft_id."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID (folder name) to delete"},
            },
            "required": ["draft_id"],
        },
    },
]


@contextlib.contextmanager
def capture_stdout():
    """Capture stdout so CapCut API debug prints don't corrupt the MCP stdio channel."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = old_stdout


def convert_text_styles(text_styles_data):
    """Convert dict-form text_styles into TextStyleRange objects."""
    if not text_styles_data:
        return None
    try:
        ranges = []
        for style_dict in text_styles_data:
            style_kwargs = {}
            if style_dict.get("font_size") is not None:
                style_kwargs["size"] = style_dict["font_size"]
            if style_dict.get("font_color") is not None:
                style_kwargs["color"] = hex_to_rgb(style_dict["font_color"])
            style_kwargs["bold"] = style_dict.get("bold", False)
            style_kwargs["italic"] = style_dict.get("italic", False)
            style_kwargs["underline"] = style_dict.get("underline", False)
            ranges.append(
                TextStyleRange(
                    start=style_dict.get("start", 0),
                    end=style_dict.get("end", 0),
                    style=Text_style(**style_kwargs),
                )
            )
        return ranges
    except Exception as e:
        print(f"[ERROR] Error converting text_styles: {e}", file=sys.stderr)
        return None


def place_draft_locally(draft_id: str) -> Optional[str]:
    """Move the freshly rendered draft folder into CapCut's local drafts directory."""
    src = os.path.join(PROJECT_ROOT, draft_id)
    if not draft_id or not os.path.isdir(src):
        return None
    os.makedirs(DEFAULT_DRAFT_FOLDER, exist_ok=True)
    dest = os.path.join(DEFAULT_DRAFT_FOLDER, draft_id)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.move(src, dest)
    return dest


def list_option_values(category: str) -> Dict[str, Any]:
    """Enumerate the valid string values for one enum-typed parameter category."""
    if category == "audio_effect":
        groups = [
            (CapCut_Voice_filters_effect_type, "Voice_filters"),
            (CapCut_Voice_characters_effect_type, "Voice_characters"),
            (CapCut_Speech_to_song_effect_type, "Speech_to_song"),
        ]
        values = []
        for enum_cls, group_name in groups:
            for name, member in enum_cls.__members__.items():
                params = [
                    {
                        "name": p.name,
                        "default_value": p.default_value * 100,
                        "min_value": p.min_value * 100,
                        "max_value": p.max_value * 100,
                    }
                    for p in member.value.params
                ]
                values.append({"name": name, "type": group_name, "params": params})
        return {"category": category, "values": values, "count": len(values)}

    enum_cls = OPTION_CATEGORIES.get(category)
    if not enum_cls:
        return {"error": f"Unknown category '{category}'. Valid categories: {ALL_OPTION_CATEGORIES}"}
    values = [{"name": name} for name in enum_cls.__members__]
    return {"category": category, "values": values, "count": len(values)}


def replace_material(
    draft_id: str,
    material_name: str,
    new_url: str,
    material_type: str = "video",
    duration: Optional[float] = None,
    replace_crop: bool = False,
    draft_folder: Optional[str] = None,
) -> Dict[str, Any]:
    """Swap the file backing an existing material in place.

    Script_file.replace_material_by_name only works on drafts loaded from an on-disk template
    (it reads self.imported_materials, populated by Script_file.load_template). This fork's
    get_or_create_draft never loads from disk — drafts are always built fresh in memory — so
    imported_materials stays empty and that method always raises KeyError. Instead, find the
    live Video_material/Audio_material object in script.materials and mutate it in place;
    segments reference materials by material_id, which we leave untouched, so every segment
    using this material picks up the new file automatically.
    """
    if material_type not in ("video", "audio"):
        return {"error": f"Unsupported material_type '{material_type}'; must be 'video' or 'audio'."}

    _draft_id, script = get_or_create_draft(draft_id=draft_id)
    material_duration = duration if duration is not None else 0.0
    name_hash = url_to_hash(new_url)
    material_list = script.materials.videos if material_type == "video" else script.materials.audios

    matches = [m for m in material_list if m.material_name == material_name]
    if not matches:
        return {"error": f"No {material_type} material named {material_name!r} found on draft {draft_id!r}. Use query_script to find the exact name."}
    if len(matches) > 1:
        return {"error": f"Multiple {material_type} materials named {material_name!r} found on draft {draft_id!r}; can't tell which to replace."}
    target = matches[0]

    if material_type == "video":
        new_material_name = f"video_{name_hash}.mp4"
        replace_path = build_asset_path(draft_folder, draft_id, "video", new_material_name) if draft_folder else None
        new_material = Video_material(
            material_type="video",
            remote_url=new_url,
            material_name=new_material_name,
            duration=material_duration,
            width=0,
            height=0,
            replace_path=replace_path,
        )
        target.material_name = new_material.material_name
        target.path = new_material.path
        target.remote_url = new_material.remote_url
        target.duration = new_material.duration
        target.width = new_material.width
        target.height = new_material.height
        target.material_type = new_material.material_type
        target.replace_path = new_material.replace_path
        if replace_crop:
            target.crop_settings = new_material.crop_settings
    else:
        new_material_name = f"audio_{name_hash}.mp3"
        replace_path = build_asset_path(draft_folder, draft_id, "audio", new_material_name) if draft_folder else None
        new_material = Audio_material(
            remote_url=new_url,
            material_name=new_material_name,
            duration=material_duration,
            replace_path=replace_path,
        )
        target.material_name = new_material.material_name
        target.path = new_material.path
        target.remote_url = new_material.remote_url
        target.duration = new_material.duration
        target.replace_path = new_material.replace_path

    return {
        "draft_id": draft_id,
        "replaced_material_name": material_name,
        "new_material_name": new_material_name,
        "new_url": new_url,
    }


def list_drafts() -> Dict[str, Any]:
    """Enumerate draft folders sitting in CapCut's local drafts directory."""
    if not os.path.isdir(DEFAULT_DRAFT_FOLDER):
        return {"drafts": [], "count": 0, "draft_folder": DEFAULT_DRAFT_FOLDER}
    drafts = []
    for name in sorted(os.listdir(DEFAULT_DRAFT_FOLDER)):
        if name.startswith("."):
            continue
        path = os.path.join(DEFAULT_DRAFT_FOLDER, name)
        if not os.path.isdir(path):
            continue
        drafts.append({
            "draft_id": name,
            "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
        })
    return {"drafts": drafts, "count": len(drafts), "draft_folder": DEFAULT_DRAFT_FOLDER}


def delete_draft(draft_id: str) -> Dict[str, Any]:
    """Delete one draft folder from CapCut's local drafts directory, guarding against path traversal."""
    if not draft_id or draft_id in (".", "..") or "/" in draft_id or "\\" in draft_id:
        return {"error": f"Invalid draft_id: {draft_id!r}"}

    target = os.path.realpath(os.path.join(DEFAULT_DRAFT_FOLDER, draft_id))
    draft_folder = os.path.realpath(DEFAULT_DRAFT_FOLDER)
    if os.path.dirname(target) != draft_folder:
        return {"error": f"draft_id resolves outside the drafts folder; refusing to delete: {draft_id!r}"}
    if not os.path.isdir(target):
        return {"error": f"No draft folder found for {draft_id!r}"}

    shutil.rmtree(target)
    return {"deleted": draft_id, "path": target}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch one call from invoke_tool to the underlying CapCut API implementation."""
    try:
        print(f"[DEBUG] Executing tool: {tool_name} with args: {arguments}", file=sys.stderr)

        with capture_stdout():
            if tool_name == "create_draft":
                draft_id, _script = get_or_create_draft(
                    width=arguments.get("width", 1080),
                    height=arguments.get("height", 1920),
                )
                result = {"draft_id": str(draft_id)}

            elif tool_name == "add_video":
                result = add_video_track(**arguments)

            elif tool_name == "add_audio":
                result = add_audio_track(**arguments)

            elif tool_name == "add_image":
                result = add_image_impl(**arguments)

            elif tool_name == "add_text":
                args = dict(arguments)
                if args.get("text_styles"):
                    args["text_styles"] = convert_text_styles(args["text_styles"])
                result = add_text_impl(**args)

            elif tool_name == "add_subtitle":
                result = add_subtitle_impl(**arguments)

            elif tool_name == "add_effect":
                result = add_effect_impl(**arguments)

            elif tool_name == "add_sticker":
                result = add_sticker_impl(**arguments)

            elif tool_name == "add_video_keyframe":
                result = add_video_keyframe_impl(**arguments)

            elif tool_name == "get_video_duration":
                result = {"duration": get_video_duration(arguments["video_url"])}

            elif tool_name == "save_draft":
                draft_id = arguments.get("draft_id")
                draft_folder = arguments.get("draft_folder") or DEFAULT_DRAFT_FOLDER
                save_draft_impl(draft_id=draft_id, draft_folder=draft_folder)
                local_path = place_draft_locally(draft_id)
                result = {
                    "local_path": local_path,
                    "message": (
                        f"Draft saved to {local_path} — open CapCut and look for it in your drafts."
                        if local_path
                        else "Draft render did not produce a local folder; check draft_id."
                    ),
                }

            elif tool_name == "list_option_values":
                result = list_option_values(arguments.get("category", ""))

            elif tool_name == "query_script":
                script = query_script_impl(
                    draft_id=arguments.get("draft_id"),
                    force_update=arguments.get("force_update", True),
                )
                if script is None:
                    return {"success": False, "error": f"Draft {arguments.get('draft_id')} does not exist in cache."}
                result = json.loads(script.dumps())

            elif tool_name == "query_draft_status":
                status = query_task_status(arguments.get("task_id", ""))
                if status.get("status") == "not_found":
                    return {"success": False, "error": f"Task {arguments.get('task_id')!r} not found."}
                result = status

            elif tool_name == "generate_draft_url":
                result = {"draft_url": util_generate_draft_url(arguments.get("draft_id", ""))}

            elif tool_name == "replace_material":
                replacement = replace_material(
                    draft_id=arguments.get("draft_id"),
                    material_name=arguments.get("material_name"),
                    new_url=arguments.get("new_url"),
                    material_type=arguments.get("material_type", "video"),
                    duration=arguments.get("duration"),
                    replace_crop=arguments.get("replace_crop", False),
                    draft_folder=arguments.get("draft_folder"),
                )
                if "error" in replacement:
                    return {"success": False, "error": replacement["error"]}
                result = replacement

            elif tool_name == "list_drafts":
                result = list_drafts()

            elif tool_name == "delete_draft":
                deletion = delete_draft(arguments.get("draft_id", ""))
                if "error" in deletion:
                    return {"success": False, "error": deletion["error"]}
                result = deletion

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        return {"success": True, "result": result}

    except Exception as e:
        print(f"[ERROR] Tool execution error: {e}", file=sys.stderr)
        print(f"[ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)
        return {"success": False, "error": str(e)}


mcp = MCPServer("capcut-api")


@mcp.tool()
def search_tools(query: str = "") -> Dict[str, Any]:
    """
    List or search the CapCut video-editing tools available through invoke_tool.

    Pass a keyword (e.g. "video", "text", "keyframe", "save") to filter by name/description,
    or leave query empty to list all tools. Each result includes the tool's exact name,
    description, and full JSON Schema for its arguments — read the schema before calling
    invoke_tool with that tool's name.
    """
    q = query.strip().lower()
    matches = [t for t in TOOLS if not q or q in t["name"].lower() or q in t["description"].lower()]
    return {"tools": matches, "count": len(matches)}


@mcp.tool()
def invoke_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute one CapCut editing tool by its exact name (from search_tools) with its arguments.

    Typical flow: create_draft -> add_video/add_audio/add_image/add_text/... (repeat, reusing
    the returned draft_id) -> save_draft. save_draft's result includes local_path, where the
    draft now lives on disk inside CapCut's drafts folder.
    """
    return execute_tool(name, arguments or {})


if __name__ == "__main__":
    mcp.run()
