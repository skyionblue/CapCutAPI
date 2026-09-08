# CapCut API MCP Server Documentation

## Overview

The CapCut API MCP Server is a video editing service based on the Model Context Protocol (MCP), providing complete CapCut video editing functionality. It exposes that functionality through **two** MCP tools rather than one per capability:

- **`search_tools(query)`** — discover available editing tools and their full JSON Schema. Pass a keyword (e.g. `"video"`, `"mask"`, `"keyframe"`) to filter, or leave `query` empty to list everything.
- **`invoke_tool(name, arguments)`** — execute one of those tools by its exact name.

This keeps the top-level MCP tool count fixed at 2 no matter how much CapCut functionality gets wrapped underneath. Every example below calls a capability through `invoke_tool`, not directly.

## Features

### 🎬 Core Capabilities
- **Draft Management**: Create, save, inspect, list, and delete video projects
- **Multimedia Support**: Video, audio, image, and text processing, including swapping the file behind an existing clip in place
- **Advanced Effects**: Effects, animations, transitions, masks, and keyframes
- **Precise Control**: Timeline, layer stacking order, and full mask/animation parameter access
- **Discoverability**: Enum lookups so effect/mask/font/transition names never have to be guessed

### 🛠️ Available Tools (18 tools, via `invoke_tool`)

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `create_draft` | Create new video draft project | `width`, `height` |
| `add_video` | Add video track | `video_url`, `start`/`end`, `transform_x/y`, `scale_x/y`, `speed`, `volume`, `transition`, full mask fine-tuning (`mask_type`, `mask_center_x/y`, `mask_size`, `mask_rotation`, `mask_feather`, `mask_invert`, `mask_rect_width`, `mask_round_corner`), `relative_index`, `duration`, `background_blur` |
| `add_audio` | Add audio track | `audio_url`, `start`/`end`, `volume`, `speed`, `sound_effects`, `duration` |
| `add_image` | Add image asset | `image_url`, `transform_x/y`, `scale_x/y`, `intro_animation`/`outro_animation`/`combo_animation` + durations, `transition`, full mask fine-tuning, `background_blur`, `relative_index` |
| `add_text` | Add text elements | `text`, `start`/`end`, `font`, `font_color`/`font_size`/`font_alpha`, `border_width`/`border_color`/`border_alpha`, shadow params, full background-box geometry, `bubble_effect_id`/`bubble_resource_id`/`effect_effect_id`, `intro_animation`/`outro_animation`, `transform_x/y`, `text_styles` (per-range overrides) |
| `add_subtitle` | Import SRT subtitle file | `srt_path`, font/border/background styling, `bubble_effect_id`/`effect_effect_id`, `scale_x/y`, `rotation`, `vertical`, `alpha` |
| `add_effect` | Add a visual effect track | `effect_type`, `start`/`end`, `params` |
| `add_sticker` | Add sticker elements | `resource_id`, `transform_x/y`, `scale_x/y`, `alpha`, `rotation`, `flip_horizontal`/`flip_vertical`, `relative_index` |
| `add_video_keyframe` | Add keyframe animations | `property_type`/`time`/`value` (single) or `property_types`/`times`/`values` (batch) |
| `get_video_duration` | Probe a video file's duration | `video_url` |
| `save_draft` | Render the draft and copy it into CapCut's local drafts folder | `draft_id`, `draft_folder` |
| `list_option_values` | List valid enum strings for a category (`transition`, `mask`, `font`, `audio_effect`, `text_intro`, `text_outro`, `text_loop_anim`, `video_scene_effect`, `video_character_effect`, `intro_animation`, `outro_animation`, `combo_animation`) — call before guessing a string value | `category` |
| `query_script` | Get a draft's full current timeline as JSON | `draft_id`, `force_update` |
| `query_draft_status` | Poll a save task's status by `task_id` (safety net — `save_draft` returns synchronously today) | `task_id` |
| `generate_draft_url` | Format the cloud preview URL for a `draft_id` (only meaningful if the OSS/cloud-preview flow is configured) | `draft_id` |
| `replace_material` | Swap the video/audio/image file behind an *existing* material in place, without touching that segment's transforms, masks, effects, or keyframes | `draft_id`, `material_name`, `new_url`, `material_type`, `duration`, `replace_crop` |
| `list_drafts` | Enumerate drafts sitting in the local CapCut drafts folder | *(none)* |
| `delete_draft` | Permanently remove a draft folder from the local CapCut drafts folder (path-traversal guarded) | `draft_id` |

## Installation & Setup

### Requirements
- Python 3.10+
- CapCut Application (macOS/Windows)
- MCP Client Support

### Dependencies Installation
```bash
# Create virtual environment
python3.10 -m venv venv-mcp
source venv-mcp/bin/activate  # macOS/Linux
# or venv-mcp\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements-mcp.txt
```

### MCP Configuration
Create or update your MCP client's server config (e.g. `.mcp.json`):

```json
{
  "mcpServers": {
    "capcut-api": {
      "command": "/path/to/CapCutAPI/venv-mcp/bin/python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/CapCutAPI"
    }
  }
}
```

## Usage Guide

### Basic Workflow

Every call below goes through `invoke_tool(name=..., arguments={...})`.

#### 1. Create Draft
```python
result = mcp_client.call_tool("invoke_tool", {
    "name": "create_draft",
    "arguments": {"width": 1080, "height": 1920}
})
draft_id = result["result"]["draft_id"]
```

#### 2. Add Content
```python
# Add title text
mcp_client.call_tool("invoke_tool", {
    "name": "add_text",
    "arguments": {
        "text": "My Video Title",
        "start": 0,
        "end": 5,
        "draft_id": draft_id,
        "font_size": 48,
        "font_color": "#FFFFFF"
    }
})

# Add background video
mcp_client.call_tool("invoke_tool", {
    "name": "add_video",
    "arguments": {
        "video_url": "https://example.com/video.mp4",
        "draft_id": draft_id,
        "start": 0,
        "end": 10,
        "volume": 0.8
    }
})
```

#### 3. Save Project
```python
result = mcp_client.call_tool("invoke_tool", {
    "name": "save_draft",
    "arguments": {"draft_id": draft_id}
})
# result["result"]["local_path"] is where the draft now lives in CapCut's drafts folder
```

### Advanced Features

#### Discovering valid option strings
Never guess a transition, mask, font, or animation name — look it up first:
```python
mcp_client.call_tool("invoke_tool", {
    "name": "list_option_values",
    "arguments": {"category": "transition"}
})
# -> {"category": "transition", "values": [{"name": "Dissolve"}, ...], "count": 116}
```

#### Full mask control
```python
mcp_client.call_tool("invoke_tool", {
    "name": "add_video",
    "arguments": {
        "draft_id": draft_id,
        "video_url": "https://example.com/video.mp4",
        "mask_type": "Circle",
        "mask_center_x": 0.5,
        "mask_center_y": 0.5,
        "mask_size": 0.8,
        "mask_feather": 0.2
    }
})
```

#### Text Styling
```python
# Text with font, border, shadow, and background
mcp_client.call_tool("invoke_tool", {
    "name": "add_text",
    "arguments": {
        "text": "Advanced Text Effects",
        "draft_id": draft_id,
        "font": "Arial",
        "font_size": 56,
        "font_color": "#FFD700",
        "border_width": 5.0,
        "border_color": "#000000",
        "shadow_enabled": True,
        "shadow_color": "#000000",
        "shadow_alpha": 0.8,
        "background_color": "#1E1E1E",
        "background_alpha": 0.7,
        "background_round_radius": 15
    }
})
```

#### Keyframe Animation
```python
# Scale and opacity animation
mcp_client.call_tool("invoke_tool", {
    "name": "add_video_keyframe",
    "arguments": {
        "draft_id": draft_id,
        "track_name": "video_main",
        "property_types": ["scale_x", "scale_y", "alpha"],
        "times": [0, 2, 4],
        "values": ["1.0", "1.5", "0.5"]
    }
})
```

#### Multi-Style Text
```python
# Different colored text segments
mcp_client.call_tool("invoke_tool", {
    "name": "add_text",
    "arguments": {
        "text": "Colorful Text Effect",
        "draft_id": draft_id,
        "text_styles": [
            {"start": 0, "end": 2, "font_color": "#FF0000"},
            {"start": 2, "end": 4, "font_color": "#00FF00"}
        ]
    }
})
```

#### Inspecting a draft
```python
# See everything currently on the draft — useful before adding more,
# or to verify an edit landed
mcp_client.call_tool("invoke_tool", {
    "name": "query_script",
    "arguments": {"draft_id": draft_id}
})
```

#### Swapping footage without rebuilding a shot
```python
# Find the material name from query_script's materials.videos[].material_name
# (materials.audios[].name for audio), then:
mcp_client.call_tool("invoke_tool", {
    "name": "replace_material",
    "arguments": {
        "draft_id": draft_id,
        "material_name": "video_6a6d23bc5056cf52.mp4",
        "new_url": "/path/to/final_render.mp4"
    }
})
# All transforms, masks, effects, and keyframes on segments using this
# material are untouched — only the underlying file changes.
```

#### Managing drafts
```python
mcp_client.call_tool("invoke_tool", {"name": "list_drafts", "arguments": {}})
mcp_client.call_tool("invoke_tool", {"name": "delete_draft", "arguments": {"draft_id": draft_id}})
```

## Testing & Validation

### Functionality Checklist
- [ ] Server starts successfully
- [ ] `search_tools` returns all 18 tools
- [ ] Draft creation functionality
- [ ] Text addition functionality
- [ ] Video/audio/image addition
- [ ] Effects, masks, and animation functionality
- [ ] `query_script` reflects edits accurately
- [ ] `replace_material` swaps the file without disturbing segment settings
- [ ] Draft saving, listing, and deletion functionality

## Troubleshooting

### Common Issues

#### 1. "CapCut modules not available"
**Solution**:
- Confirm CapCut application is installed
- Check Python path configuration
- Verify dependency package installation

#### 2. Server startup failure
**Solution**:
- Check virtual environment activation
- Verify configuration file paths
- Review error logs

#### 3. Tool call errors
**Solution**:
- Check parameter format
- Verify media file URLs
- Confirm time range settings
- Call `search_tools` to re-check a tool's exact `inputSchema` before assuming a parameter name is wrong

#### 4. "Unknown tool: X"
`invoke_tool` only recognizes the exact names returned by `search_tools`. There is no way to call a capability directly by its own name at the top level — it must go through `invoke_tool`.

### Debug Mode
```bash
# Enable verbose logging
export DEBUG=1
python mcp_server.py
```

## Best Practices

### Performance Optimization
1. **Media Files**: Use compressed formats, avoid oversized files
2. **Time Management**: Plan element timelines reasonably, avoid overlaps
3. **Memory Usage**: Save drafts promptly, clean temporary files (use `list_drafts`/`delete_draft` to keep the drafts folder tidy)

### Error Handling
1. **Parameter Validation**: Check required parameters before calling
2. **Exception Catching**: Handle network and file errors
3. **Retry Mechanism**: Retry on temporary failures
4. **Verify, don't assume**: Use `query_script` after an edit to confirm it landed rather than trusting the call succeeded

## API Reference

### Common Parameters
- `draft_id`: Unique draft identifier, returned by `create_draft`
- `start`/`end`: Time range (seconds)
- `width`/`height`: Project dimensions
- `transform_x`/`transform_y`: Position coordinates
- `scale_x`/`scale_y`: Scale ratios

### Response Format
Every `invoke_tool` call returns:
```json
{
  "success": true,
  "result": {
    "draft_id": "dfd_cat_xxx",
    "draft_url": "https://..."
  }
}
```
or, on failure:
```json
{
  "success": false,
  "error": "description of what went wrong"
}
```

## Changelog

### Unreleased
- Refactored from one MCP tool per capability into the `search_tools`/`invoke_tool` gateway
- Expanded every existing tool's schema to expose parameters the underlying implementation already supported but weren't wired up (full mask fine-tuning, text font/border/bubble/animation, subtitle styling, sticker flip, etc.)
- Added `list_option_values`, `query_script`, `list_drafts`, `delete_draft`, `query_draft_status`, `generate_draft_url`, `replace_material`
- Added `Text_shadow` and `TextStyleRange` support to `pyJianYingDraft`
- Became an independent repository rather than a GitHub fork
- Removed JianYing-mode support (this project only ever runs in CapCut mode) — deleted the JianYing-only effect/transition/mask/animation enum catalogs, collapsed every CapCut-vs-JianYing branch in the codebase down to the CapCut path, and removed the two Chinese-language doc files
- Fixed `add_effect` crashing with `'NoneType' object is not subscriptable` when called without a `params` argument

### v1.0.0
- Initial release
- Support for 11 core tools
- Complete MCP protocol implementation

---

*This documentation is continuously updated. Please follow the latest version.*
