# 🎬 CapCutAPI - Open source CapCut API tool.

<div align="center">

![CapCutAPI Logo](https://img.shields.io/badge/CapCutAPI-v1.1.0-blue?style=for-the-badge&logo=video&logoColor=white)

[![GitHub Stars](https://img.shields.io/github/stars/sun-guannan/CapCutAPI?style=for-the-badge&logo=github)](https://github.com/sun-guannan/CapCutAPI/stargazers)
[![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://python.org)
[![MCP Support](https://img.shields.io/badge/MCP-Supported-orange?style=for-the-badge)](./MCP_Documentation_English.md)

**🚀 Open source CapCut API tool with MCP (Model Context Protocol) support**

[🌐 Try Online](https://www.capcutapi.top) • [📖 中文文档](README-zh.md) • [🔧 MCP Docs](./MCP_Documentation_English.md) • [🌍 MCP 中文指南](./MCP_文档_中文.md)

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
- JianYing China support
- Windows/macOS compatible
- Cloud deployment ready

</td>
</tr>
</table>

---

## 🎥 Product Showcase

<div align="center">

### 🐎 AI Generated Video Cases

[![Horse Video](https://img.youtube.com/vi/IF1RDFGOtEU/hqdefault.jpg)](https://www.youtube.com/watch?v=IF1RDFGOtEU)

### 🎵 Music Video Production

[![Song Video](https://img.youtube.com/vi/rGNLE_slAJ8/hqdefault.jpg)](https://www.youtube.com/watch?v=rGNLE_slAJ8)

*AI-driven video generation powered by CapCutAPI*

</div>

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

### 🛠️ API Interface Overview

<details>
<summary><b>📡 HTTP API Endpoints (9 endpoints)</b></summary>

🎬 Draft Management
├── POST /create_draft     # Create new draft
└── POST /save_draft       # Save draft file

🎥 Media Assets
├── POST /add_video        # Add video material
├── POST /add_audio        # Add audio material
└── POST /add_image        # Add image material

📝 Text Content
├── POST /add_text         # Add text elements
└── POST /add_subtitle     # Add subtitle files

✨ Effect Enhancement
├── POST /add_effect       # Add visual effects
└── POST /add_sticker      # Add sticker elements


</details>

<details>
<summary><b>🔧 MCP Tool Set (18 tools, via a 2-tool <code>search_tools</code>/<code>invoke_tool</code> gateway)</b></summary>

This fork's `mcp_server.py` exposes exactly two top-level MCP tools — `search_tools(query)` to discover capabilities and `invoke_tool(name, arguments)` to run one — so the list below is what `invoke_tool` dispatches to, not top-level MCP tools themselves. See `MCP_Documentation_English.md` for the full reference and usage examples.

🎬 Project Management
├── create_draft           # Create video project
├── save_draft              # Save project file to CapCut's local drafts folder
├── list_drafts             # Enumerate drafts in the local drafts folder
├── delete_draft            # Remove a draft folder (path-traversal guarded)
├── query_draft_status      # Poll a save task's status by task_id
└── generate_draft_url      # Format the cloud preview URL for a draft_id

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
<td>CapCut International or JianYing China</td>
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
git clone https://github.com/sun-guannan/CapCutAPI.git
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

### Testing with REST Client

You can use the `rest_client_test.http` file with REST Client IDE plugins for HTTP testing.

### Draft Management

Calling `save_draft` generates a folder starting with `dfd_` in the server's current directory. Copy this folder to your CapCut draft directory to access the generated draft in CapCut.

> **Note (MCP gateway):** when using the MCP `save_draft` tool (via `invoke_tool`) rather than the HTTP API, this copy step happens automatically — the result's `local_path` already points inside CapCut's real drafts folder, so no manual copy is needed. Use `list_drafts`/`delete_draft` to manage what accumulates there.

---

## 📚 Documentation Center

<div align="center">

| 📖 Document Type | 🌍 Language | 📄 Link | 📝 Description |
|-----------------|-------------|---------|----------------|
| **MCP Complete Guide** | 🇺🇸 English | [MCP Documentation](./MCP_Documentation_English.md) | Complete MCP server usage guide |
| **MCP User Manual** | 🇨🇳 Chinese | [MCP 中文文档](./MCP_文档_中文.md) | Detailed Chinese usage instructions |
| **API Reference** | 🇺🇸 English | [example.py](./example.py) | Code examples and best practices |
| **REST Testing** | 🌐 Universal | [rest_client_test.http](./rest_client_test.http) | HTTP interface test cases |

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

## 🤝 Community & Support

### 💬 Get Help

<div align="center">

| 📞 Support Channel | 🔗 Link | 📝 Description |
|-------------------|---------|----------------|
| **🐛 Bug Reports** | [GitHub Issues](https://github.com/sun-guannan/CapCutAPI/issues) | Bug reports and feature requests |
| **💡 Feature Suggestions** | [Discussions](https://github.com/sun-guannan/CapCutAPI/discussions) | Community discussions and suggestions |
| **📖 Documentation Feedback** | [Documentation Issues](https://github.com/sun-guannan/CapCutAPI/issues?q=label%3Adocumentation) | Documentation improvement suggestions |
| **🔧 Technical Support** | [Stack Overflow](https://stackoverflow.com/questions/tagged/capcut-api) | Technical Q&A |

</div>

### 🎯 Contributing Guide

We welcome all forms of contributions!

```bash
# 1. Fork the project
git clone https://github.com/your-username/CapCutAPI.git

# 2. Create feature branch
git checkout -b feature/amazing-feature

# 3. Commit changes
git commit -m 'Add amazing feature'

# 4. Push branch
git push origin feature/amazing-feature

# 5. Create Pull Request
```

---

## 📈 Project Statistics

<div align="center">

### ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=sun-guannan/CapCutAPI&type=Date)](https://www.star-history.com/#sun-guannan/CapCutAPI&Date)

### 📊 Project Metrics

![GitHub repo size](https://img.shields.io/github/repo-size/sun-guannan/CapCutAPI?style=flat-square)
![GitHub code size](https://img.shields.io/github/languages/code-size/sun-guannan/CapCutAPI?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/sun-guannan/CapCutAPI?style=flat-square)
![GitHub pull requests](https://img.shields.io/github/issues-pr/sun-guannan/CapCutAPI?style=flat-square)
![GitHub last commit](https://img.shields.io/github/last-commit/sun-guannan/CapCutAPI?style=flat-square)

</div>

---

## 📄 License

<div align="center">

This project is open source under the Apache 2.0 License. See [LICENSE](LICENSE) file for details.

Apache License 2.0

Copyright (c) 2025 CapCutAPI Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

</div>

---

<div align="center">

## 🎉 Get Started Now

**Experience the power of CapCutAPI today!**

[![Get Started](https://img.shields.io/badge/🚀_Get_Started-blue?style=for-the-badge&logo=rocket)](https://www.capcutapi.top)
[![Download](https://img.shields.io/badge/📥_Download-green?style=for-the-badge&logo=download)](https://github.com/sun-guannan/CapCutAPI/archive/refs/heads/main.zip)
[![Documentation](https://img.shields.io/badge/📖_Documentation-orange?style=for-the-badge&logo=book)](./MCP_Documentation_English.md)

---

**🆕 New Feature**: Now with MCP protocol support for seamless AI assistant integration! Try the MCP server for advanced video editing automation.

*Made with ❤️ by the CapCutAPI Community*

</div>
