# 🎬 CapCutAPI

<div align="center">

![CapCutAPI Logo](https://img.shields.io/badge/CapCutAPI-v1.1.0-blue?style=for-the-badge&logo=video&logoColor=white)

[![Python Version](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://python.org)
[![MCP Support](https://img.shields.io/badge/MCP-Supported-orange?style=for-the-badge)](./MCP_Documentation_English.md)

**🚀 CapCut video editing automation with MCP (Model Context Protocol) support**

[🔧 MCP Docs](./MCP_Documentation_English.md)

</div>

---

## 🎯 Project Overview

**CapCutAPI** is a powerful enterprise-grade video editing automation platform built with Python, providing complete CapCut video editing capabilities. Through dual interfaces of HTTP API and MCP protocol, it enables seamless integration with AI assistants and automation tools.

### 🏆 Core Advantages

<table>
<tr>
<td width="50%">

**🎬 Professional Video Editing**
- Complete CapCut functionality support
- Multi-track timeline editing
- Advanced effects and transitions
- Keyframe animation system

</td>
<td width="50%">

**🤖 AI Smart Integration**
- Native MCP protocol support
- Seamless AI assistant integration
- Automated workflow processes
- Batch processing capabilities

</td>
</tr>
<tr>
<td>

**🔌 Dual API Interfaces**
- RESTful HTTP API
- Model Context Protocol
- Real-time processing response
- Enterprise-grade stability

</td>
<td>

**🌍 Cross-platform Compatibility**
- CapCut International support
- Windows/macOS compatible
- Cloud deployment ready

</td>
</tr>
</table>

---

## 🚀 Core Features

### 📋 Feature Matrix

| Feature Module | HTTP API | MCP Protocol | Description |
|---------------|----------|--------------|-------------|
| 🎬 **Draft Management** | ✅ | ✅ | Create, read, modify, save CapCut draft files |
| 🎥 **Video Processing** | ✅ | ✅ | Multi-format video import, editing, transitions, effects |
| 🔊 **Audio Editing** | ✅ | ✅ | Audio tracks, volume control, audio effects |
| 🖼️ **Image Processing** | ✅ | ✅ | Image import, animations, masks, filters |
| 📝 **Text Editing** | ✅ | ✅ | Multi-style text, shadows, backgrounds, animations |
| 📄 **Subtitle System** | ✅ | ✅ | SRT subtitle import, styling, time sync |
| ✨ **Effects Engine** | ✅ | ✅ | Visual effects, filters, transition animations |
| 🎭 **Sticker System** | ✅ | ✅ | Sticker assets, position control, animation effects |
| 🎯 **Keyframes** | ✅ | ✅ | Property animations, timeline control, easing functions |
| 📊 **Media Analysis** | ✅ | ✅ | Video duration detection, format analysis |
| 📤 **Subtitle Export** | ✅ | ✅ | Write a draft's text segments back out as an SRT file |
| 🎞️ **Video Export** | ✅ | ✅ | Render a draft to a finished MP4 — full fidelity via CapCut, or headless via ffmpeg |

### 🛠️ API Interface Overview

<details>
<summary><b>📡 HTTP API Endpoints (29 endpoints)</b></summary>

🎬 Draft Management
├── POST /create_draft        # Create new draft
├── POST /save_draft          # Save draft file
├── POST /query_script        # Get a draft's full current timeline as JSON
├── POST /query_draft_status  # Poll a save task's status
├── POST /generate_draft_url  # Format the cloud preview URL for a draft_id
├── POST /export_video        # Export a saved draft to a video file (async)
├── POST /query_export_status # Poll an export task's status by task_id
├── GET  /export_preflight    # Report which export backends are available here
└── POST /export_subtitles    # Write a draft's text segments out as an SRT file

🎥 Media Assets
├── POST /add_video           # Add video material
├── POST /add_audio           # Add audio material
├── POST /add_image           # Add image material
└── POST /add_video_keyframe  # Add keyframe animation to a video segment

📝 Text Content
├── POST /add_text            # Add text elements
└── POST /add_subtitle        # Add subtitle files

✨ Effect Enhancement
├── POST /add_effect          # Add visual effects
└── POST /add_sticker         # Add sticker elements

🔍 Option Lookups (read-only, GET)
├── GET /get_intro_animation_types
├── GET /get_outro_animation_types
├── GET /get_combo_animation_types
├── GET /get_transition_types
├── GET /get_mask_types
├── GET /get_audio_effect_types
├── GET /get_font_types
├── GET /get_text_intro_types
├── GET /get_text_outro_types
├── GET /get_text_loop_anim_types
├── GET /get_video_scene_effect_types
└── GET /get_video_character_effect_types

</details>

<details>
<summary><b>🔧 MCP Tool Set (22 tools, via a 2-tool <code>search_tools</code>/<code>invoke_tool</code> gateway)</b></summary>

`mcp_server.py` exposes exactly two top-level MCP tools — `search_tools(query)` to discover capabilities and `invoke_tool(name, arguments)` to run one — so the list below is what `invoke_tool` dispatches to, not top-level MCP tools themselves. See `MCP_Documentation_English.md` for the full reference and usage examples.

🎬 Project Management
├── create_draft           # Create video project
├── save_draft              # Save project file to CapCut's local drafts folder
├── list_drafts             # Enumerate drafts in the local drafts folder
├── delete_draft            # Remove a draft folder (path-traversal guarded)
├── query_draft_status      # Poll a save task's status by task_id
├── generate_draft_url      # Format the cloud preview URL for a draft_id
├── export_video            # Export a saved draft to a video file (async)
├── query_export_status     # Poll an export task's status by task_id
├── export_preflight        # Report which export backends are available here
└── export_subtitles        # Write a draft's text segments out as an SRT file

🎥 Media Editing
├── add_video               # Video track + transitions + full mask control + keyframable properties
├── add_audio               # Audio track + volume/speed control + scene sound effects
├── add_image               # Image assets + intro/outro/combo animation + full mask control
└── replace_material        # Swap the file behind an existing material without touching segment settings

📝 Text System
├── add_text                # Font, border, shadow, background box, bubble/effect IDs, intro/outro animation, multi-style runs
└── add_subtitle            # SRT subtitles + full styling (border, background, bubble/effect, scale/rotation)

✨ Advanced Features
├── add_effect              # Visual effects engine
├── add_sticker             # Sticker placement + flip + animation
├── add_video_keyframe      # Keyframe animations (single or batch)
├── get_video_duration      # Media information retrieval
├── list_option_values      # Enum lookups (transition/mask/font/audio_effect/etc.) — call before guessing a string
└── query_script            # Full current draft timeline as JSON — inspect before editing, verify after

</details>

---

## 🛠️ Quick Start

### 📋 System Requirements

<table>
<tr>
<td width="30%"><b>🐍 Python Environment</b></td>
<td>Python 3.8.20+ (Recommended 3.10+)</td>
</tr>
<tr>
<td><b>🎬 CapCut Application</b></td>
<td>CapCut International</td>
</tr>
<tr>
<td><b>🎵 FFmpeg</b></td>
<td>For media file processing and analysis</td>
</tr>
<tr>
<td><b>💾 Storage Space</b></td>
<td>At least 2GB available space</td>
</tr>
</table>

### ⚡ One-Click Installation

```bash
# 1. Clone the project
git clone git@ghtm:skyionblue/CapCutAPI.git
cd CapCutAPI

# 2. Create virtual environment (recommended)
python -m venv venv-capcut
source venv-capcut/bin/activate  # Linux/macOS
# or venv-capcut\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt      # HTTP API basic dependencies
pip install -r requirements-mcp.txt  # MCP protocol support (optional)

# 4. Configuration
cp config.json.example config.json
# Edit config.json as needed
```

#### Configuration reference

| Key | Default | What it does |
|---|---|---|
| `is_capcut_env` | `true` | CapCut International mode. This project only runs in CapCut mode. |
| `port` | `9000` | Port the HTTP server listens on. |
| `draft_store_dir` | `./drafts_store` | Where drafts are persisted after every edit, so a server restart cannot lose in-progress work. |
| `draft_domain` | — | Base URL used to build draft preview links. |
| `preview_router` | `/draft/downloader` | Path appended to `draft_domain` for preview links. |
| `is_upload_draft` | `false` | Upload the zipped draft to `oss_config` storage on save. |
| `oss_config` | — | Object storage for **draft archives**, used when `is_upload_draft` is true. |
| `mp4_oss_config` | — | Object storage for **exported videos**. When set, a finished `export_video` is uploaded here and the task's `video_url` carries a signed link valid for 24 hours. Leave it out to keep exports local — `output_path` still works either way. |

> `oss_config` and `mp4_oss_config` are separate on purpose: one holds draft archives, the other
> finished video files, and they can point at different buckets or domains.

### 🚀 Start Services

<table>
<tr>
<td width="50%">

**🌐 HTTP API Server**

```bash
python capcut_server.py
```

*Default port: 9001*

</td>
<td width="50%">

**🔧 MCP Protocol Server**

```bash
python mcp_server.py
```

*Supports stdio communication*

</td>
</tr>
</table>

---

## 🔧 MCP Integration Guide

### 📱 Client Configuration

Create or update `mcp_config.json` configuration file:

```json
{
  "mcpServers": {
    "capcut-api": {
      "command": "python3",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/CapCutAPI",
      "env": {
        "PYTHONPATH": "/path/to/CapCutAPI",
        "DEBUG": "0"
      }
    }
  }
}
```

### 🧪 Connection Testing

```bash
# Test MCP connection
python test_mcp_client.py

# Expected output
✅ MCP server started successfully
✅ Retrieved 11 available tools
✅ Draft creation test passed
```

### 🎯 MCP Featured Functions

<div align="center">

| Feature | Description | Example |
|---------|-------------|----------|
| 🎨 **Advanced Text Styling** | Multi-color, shadow, background effects | `shadow_enabled: true` |
| 🎬 **Keyframe Animation** | Position, scale, opacity animations | `property_types: ["scale_x", "alpha"]` |
| 🔊 **Audio Precision Control** | Volume, speed, audio effects | `volume: 0.8, speed: 1.2` |
| 📱 **Multi-format Support** | Various video dimensions and formats | `width: 1080, height: 1920` |
| ⚡ **Real-time Processing** | Instant draft updates and previews | Millisecond response time |
| 🎞️ **End-to-end Export** | Build *and* render a video with no manual CapCut step | `export_video` → `query_export_status` |

</div>

---

## 💡 Usage Examples

### 🌐 HTTP API Examples

<details>
<summary><b>📹 Adding Video Material</b></summary>

```python
import requests

# Add background video
response = requests.post("http://localhost:9001/add_video", json={
    "video_url": "https://example.com/background.mp4",
    "start": 0,
    "end": 10,
    "width": 1080,
    "height": 1920,
    "volume": 0.8,
    "transition": "fade_in"
})

print(f"Video addition result: {response.json()}")
```

</details>

<details>
<summary><b>📝 Creating Styled Text</b></summary>

```python
import requests

# Add title text
response = requests.post("http://localhost:9001/add_text", json={
    "text": "🎬 Welcome to CapCutAPI",
    "start": 0,
    "end": 5,
    "font": "Arial",
    "font_color": "#FFD700",
    "font_size": 48,
    "shadow_enabled": True,
    "background_color": "#000000"
})

print(f"Text addition result: {response.json()}")
```

</details>

### 🔧 MCP Protocol Examples

Every capability below runs through the gateway: `mcp_client.call_tool("invoke_tool", {"name": ..., "arguments": {...}})`. See `MCP_Documentation_English.md` for the full tool reference.

<details>
<summary><b>🎯 Complete Workflow</b></summary>

```python
# 1. Create new project
draft = mcp_client.call_tool("invoke_tool", {
    "name": "create_draft",
    "arguments": {"width": 1080, "height": 1920}
})
draft_id = draft["result"]["draft_id"]

# 2. Add background video
mcp_client.call_tool("invoke_tool", {
    "name": "add_video",
    "arguments": {
        "video_url": "https://example.com/bg.mp4",
        "draft_id": draft_id,
        "start": 0,
        "end": 10,
        "volume": 0.6
    }
})

# 3. Add title text
mcp_client.call_tool("invoke_tool", {
    "name": "add_text",
    "arguments": {
        "text": "AI-Driven Video Production",
        "draft_id": draft_id,
        "start": 1,
        "end": 6,
        "font_size": 56,
        "shadow_enabled": True,
        "background_color": "#1E1E1E"
    }
})

# 4. Add keyframe animation
mcp_client.call_tool("invoke_tool", {
    "name": "add_video_keyframe",
    "arguments": {
        "draft_id": draft_id,
        "track_name": "main",
        "property_types": ["scale_x", "scale_y", "alpha"],
        "times": [0, 2, 4],
        "values": ["1.0", "1.2", "0.8"]
    }
})

# 5. Swap the placeholder clip for the final render, keeping the keyframes above
mcp_client.call_tool("invoke_tool", {
    "name": "replace_material",
    "arguments": {
        "draft_id": draft_id,
        "material_name": "video_<hash>.mp4",  # from query_script's materials.videos[].material_name
        "new_url": "https://example.com/bg_final.mp4"
    }
})

# 6. Save project
result = mcp_client.call_tool("invoke_tool", {
    "name": "save_draft",
    "arguments": {"draft_id": draft_id}
})
print(f"Project saved: {result['result']['local_path']}")
```

</details>

### Running the Tests

```bash
pip install pytest
pytest
```

63 tests covering the export pipeline — draft parsing, ffmpeg command compilation, task status
and backend dispatch. They run in well under a second and need **no CapCut installation**;
`ffmpeg`/`ffprobe` must be on `PATH` (tests that need them skip automatically if absent).

Tests that would require a macOS GUI session are marked `gui` and are excluded by default.
Run them with `pytest -m gui`.

Lint the export modules with:

```bash
flake8 export_impl.py export_task_cache.py export_backends/ tests/
```

### Testing with REST Client

You can use the `rest_client_test.http` file with REST Client IDE plugins for HTTP testing.

### Draft Management

Calling `save_draft` generates a folder starting with `dfd_` in the server's current directory. Copy this folder to your CapCut draft directory to access the generated draft in CapCut.

> **Note (MCP gateway):** when using the MCP `save_draft` tool (via `invoke_tool`) rather than the HTTP API, this copy step happens automatically — the result's `local_path` already points inside CapCut's real drafts folder, so no manual copy is needed. Use `list_drafts`/`delete_draft` to manage what accumulates there.

### Saving Large Drafts

`save_draft` downloads every remote asset the draft references, so a project with a lot of
media can take long enough to time out an HTTP client or an MCP call. It blocks by default, so
existing callers are unaffected. For large drafts, run it in the background instead:

```bash
# Start the save, get a task_id back immediately
curl -X POST http://localhost:9001/save_draft \
  -H "Content-Type: application/json" \
  -d '{"draft_id": "dfd_...", "wait": false}'

# Poll until status is "completed" or "failed"
curl -X POST http://localhost:9001/query_draft_status \
  -H "Content-Type: application/json" \
  -d '{"task_id": "dfd_..."}'
```

When it completes, the status carries `local_path` — where the draft landed in CapCut's drafts
folder.

### Subtitle Export

`add_subtitle` reads SRT in; `export_subtitles` writes it back out, so captions written or
adjusted in a draft can be handed to a platform as a separate file rather than burned into the
frame — which is what YouTube, TikTok and Instagram prefer.

```bash
curl -X POST http://localhost:9001/export_subtitles \
  -H "Content-Type: application/json" \
  -d '{"draft_id": "dfd_...", "output_path": "~/Movies/captions.srt"}'
```

Returns the SRT inline as `srt` and writes the file when `output_path` is given. `track_name`
limits it to one text track; `time_offset` shifts every cue, for syncing against a trimmed
export. Works before or after `save_draft`.

### Draft Persistence

Drafts are written to disk after every edit, so a server restart — a crash, a config reload, an
MCP client restart — no longer loses in-progress work. `save_draft`, `query_script` and
`add_*` all fall back to the store when a draft is no longer in memory, and resuming a known
`draft_id` returns that draft rather than silently starting a new one.

The store defaults to `drafts_store/` beside the project and is configurable:

```json
{
  "draft_store_dir": "./drafts_store"
}
```

> A restored draft comes back on the draft library's *imported* tracks. Saving and querying
> round-trip correctly; further edits append new tracks rather than extending the restored ones.

### Video Export

`save_draft` writes a CapCut draft; `export_video` turns that draft into a finished video file,
so an assistant can take a request all the way to an MP4 with no manual step in CapCut.

Export is **asynchronous** — `export_video` returns a `task_id` immediately and the file does not
exist yet. Poll `query_export_status` until `status` is `completed` or `failed`.

```bash
# 1. Start the export (after save_draft)
curl -X POST http://localhost:9001/export_video \
  -H "Content-Type: application/json" \
  -d '{"draft_id": "dfd_...", "backend": "auto", "output_path": "~/Movies/out.mp4"}'

# 2. Poll until it finishes
curl -X POST http://localhost:9001/query_export_status \
  -H "Content-Type: application/json" \
  -d '{"task_id": "export-dfd_...-1a2b3c4d"}'

# Which backends can run here, and why one cannot
curl http://localhost:9001/export_preflight
```

#### Choosing a backend

| | `capcut` | `ffmpeg` |
|---|---|---|
| **Fidelity** | **Full** — every effect, filter, mask, animation, transition and sticker | **Subset** — cuts, trims, placement, transforms, audio, basic text |
| **Needs a GUI?** | Yes: macOS with CapCut installed **and visible on the active Space** | No — works on servers, CI and containers |
| **`resolution`/`framerate`/`bitrate`** | Not settable (reported in `fidelity_warnings`) | Honoured |
| **Use it when** | The output is the deliverable | There is no GUI, or you want a quick preview |

`backend: "auto"` (the default) picks `capcut` when a GUI session is available and falls back to
`ffmpeg` otherwise.

#### Fidelity warnings

Every export result carries a `fidelity_warnings` list. CapCut's effects, filters, masks,
animations, transitions and stickers are stored only as CapCut effect IDs and are resolved by
CapCut's own renderer, so the `ffmpeg` backend cannot reproduce them — it reports each one it
dropped rather than quietly returning a degraded video. **Always surface these to the user.**

#### Requirements for the `capcut` backend

| Permission | Why | Where |
|---|---|---|
| **Accessibility** | Read CapCut's UI and drive its menus | System Settings → Privacy & Security → Accessibility |
| **Automation → CapCut** | Bring CapCut to the foreground | Granted on first use |

It also needs `pyobjc-framework-Quartz` (installed automatically from `requirements.txt` on macOS).

> **Safe alongside other apps.** Every click is hit-tested against the window actually on screen
> and is refused unless it belongs to CapCut, so an export aborts with a clear error rather than
> clicking into whatever else you are doing — a screen-recorded call included. CapCut does need to
> be visible on the active Space while the export runs, and exports are serialised because they
> share one GUI.

> **Encoder settings:** the `capcut` backend cannot operate CapCut's export-dialog dropdowns. Set
> your preferred resolution/format once by hand in CapCut and it persists for later exports.

---

## 📚 Documentation Center

<div align="center">

| 📖 Document Type | 📄 Link | 📝 Description |
|-----------------|---------|----------------|
| **MCP Complete Guide** | [MCP Documentation](./MCP_Documentation_English.md) | Complete MCP server usage guide |
| **API Reference** | [example.py](./example.py) | Code examples and best practices |
| **REST Testing** | [rest_client_test.http](./rest_client_test.http) | HTTP interface test cases |

</div>

---

## 🌟 Enterprise Features

### 🔒 Security

- **🛡️ Input Validation**: Strict parameter validation and type checking
- **🔐 Error Handling**: Comprehensive exception catching and error reporting
- **📊 Logging**: Detailed operation logs and debug information
- **🚫 Resource Limits**: Memory and processing time limit protection

### ⚡ Performance Optimization

- **🚀 Async Processing**: Non-blocking concurrent operation support
- **💾 Memory Management**: Smart resource recycling and caching mechanisms
- **📈 Batch Processing**: Efficient batch operation interfaces
- **⏱️ Response Time**: Millisecond-level API response speed

### 🔧 Scalability

- **🔌 Plugin Architecture**: Modular functionality extension support
- **🌐 Multi-protocol**: HTTP REST and MCP dual protocol support
- **☁️ Cloud Deployment**: Containerization and microservice architecture ready
- **📊 Monitoring Integration**: Complete performance monitoring and metrics collection

---

## 📄 License

<div align="center">

**Licence to be determined.**

This project does not currently carry a licence. Until one is added, no usage rights are
granted. Any licence chosen must be compatible with the upstream project this work derives
from and with the vendored `pyJianYingDraft` library.

</div>

---

<div align="center">

## 🎉 Get Started Now

[![Documentation](https://img.shields.io/badge/📖_Documentation-orange?style=for-the-badge&logo=book)](./MCP_Documentation_English.md)

</div>
