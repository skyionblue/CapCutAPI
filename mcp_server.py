#!/usr/bin/env python3
"""CapCut API MCP Server (2-tool gateway).

A thin adapter over `tool_registry`, which holds the catalogue and the dispatch shared with the
HTTP server.

  - search_tools(query): discover available editing tools and their input schemas
  - invoke_tool(name, arguments): execute one of them by name

DESIGN CONSTRAINT -- do not register the catalogue as individual MCP tools.

Every tool an MCP server advertises is loaded into the model's context for the whole session,
schemas and all. This project's toolset is large and its schemas are detailed (add_video alone
takes well over twenty parameters), so advertising one tool per capability would spend a
substantial slice of the context window before any work began. The gateway keeps the advertised
surface at two tools and moves discovery to search_tools, which returns only the schemas the
model actually asks for.

Adding a capability means an entry in tool_registry.TOOLS and a branch in
tool_registry.execute_tool -- never a new function registered as an MCP tool. Only search_tools
and invoke_tool are registered that way, and that is deliberate;
tests/test_gateway_surface.py enforces it.

Runs over stdio using the official `mcp` SDK (FastMCP).
"""

import sys
from typing import Any, Dict, List, Optional  # noqa: F401

from mcp.server.mcpserver import MCPServer

from tool_registry import TOOLS, execute_tool  # noqa: F401

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
