"""Regression tests for per-range text styling.

`add_text` accepts `text_styles` — styling applied to character ranges rather than the whole
string. Combining that with a shadow raised `UnboundLocalError`, because the branch that builds
the default style range for the characters *before* the first styled range assigned its shadow
to `style_item`, a name belonging to a different branch.

The combination is reachable from both transports and was silently broken.
"""

import json

import pytest

import draft_cache
import tool_registry


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", str(tmp_path / "store"))
    draft_cache.DRAFT_CACHE.clear()
    yield
    draft_cache.DRAFT_CACHE.clear()


def add_text(**overrides):
    arguments = {"text": "hello world", "start": 0, "end": 3}
    arguments.update(overrides)
    return tool_registry.execute_tool("add_text", arguments)


def text_content(draft_id):
    data = json.loads(draft_cache.get_script(draft_id).dumps())
    return json.loads(data["materials"]["texts"][0]["content"])


def test_styled_range_starting_after_zero_with_a_shadow():
    """The exact failing combination: a leading unstyled run, plus a shadow."""
    result = add_text(
        text_styles=[{"start": 2, "end": 5, "font_size": 12}],
        shadow_enabled=True,
    )
    assert result["success"] is True, result.get("error")

    content = text_content(result["result"]["draft_id"])
    # default run (0-2), the styled run, and the remainder
    assert len(content["styles"]) == 3
    assert "shadows" in content["styles"][0], "the leading run lost its shadow"


def test_styled_range_starting_after_zero_without_a_shadow():
    result = add_text(text_styles=[{"start": 2, "end": 5, "font_size": 12}])
    assert result["success"] is True
    assert len(text_content(result["result"]["draft_id"])["styles"]) == 3


def test_styled_range_starting_at_zero_with_a_shadow():
    """No leading run, so the branch that was broken is not taken."""
    result = add_text(
        text_styles=[{"start": 0, "end": 5, "font_size": 12}],
        shadow_enabled=True,
    )
    assert result["success"] is True


def test_shadow_without_per_range_styles():
    result = add_text(shadow_enabled=True)
    assert result["success"] is True
    assert "shadows" in text_content(result["result"]["draft_id"])["styles"][0]


def test_plain_text_still_works():
    result = add_text()
    assert result["success"] is True
