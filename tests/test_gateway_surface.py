"""Guards the MCP gateway's advertised surface.

Every tool an MCP server advertises is loaded into the model's context for the whole session,
schemas included. This project's toolset is large and its schemas are detailed, so it
deliberately advertises only two tools — search_tools and invoke_tool — and keeps the rest as
an internal catalogue reachable through them.

That is easy to undo by accident: adding an @mcp.tool() function is the obvious way to expose a
new capability, and nothing about it looks wrong in review. These tests make the constraint
fail loudly instead.
"""

import inspect

import mcp_server

GATEWAY_TOOLS = {"search_tools", "invoke_tool"}


def registered_tool_names():
    """Tool names the MCP runtime will advertise to the model."""
    manager = mcp_server.mcp._tool_manager
    tools = manager.list_tools() if hasattr(manager, "list_tools") else manager._tools
    return {getattr(t, "name", t) for t in tools}


def test_only_the_two_gateway_tools_are_advertised():
    """Adding a third advertised tool costs context for every session.

    If this fails because a capability was added: put it in TOOLS and give it a branch in
    execute_tool instead of decorating a new function.
    """
    assert registered_tool_names() == GATEWAY_TOOLS


def test_the_catalogue_is_larger_than_the_advertised_surface():
    """Sanity check that the catalogue really is being kept out of the tool list."""
    assert len(mcp_server.TOOLS) > len(GATEWAY_TOOLS)


def test_every_catalogue_entry_is_reachable_through_invoke_tool():
    """A catalogue entry with no dispatch branch is invisible and unusable."""
    source = inspect.getsource(mcp_server.execute_tool)
    missing = [t["name"] for t in mcp_server.TOOLS if f'"{t["name"]}"' not in source]
    assert not missing, f"catalogue entries with no execute_tool branch: {missing}"


def test_every_catalogue_entry_has_a_description_and_schema():
    """search_tools is the only discovery the model gets, so entries must be self-describing."""
    for tool in mcp_server.TOOLS:
        assert tool.get("name")
        assert tool.get("description"), f"{tool['name']} has no description"
        assert "inputSchema" in tool, f"{tool['name']} has no inputSchema"
        assert tool["inputSchema"].get("type") == "object"


def test_search_tools_returns_schemas_so_the_model_need_not_guess():
    found = mcp_server.search_tools("export")
    assert found["count"] >= 1
    assert all("inputSchema" in tool for tool in found["tools"])


def test_search_tools_with_no_query_lists_the_whole_catalogue():
    assert mcp_server.search_tools("")["count"] == len(mcp_server.TOOLS)
