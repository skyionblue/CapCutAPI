"""Characterization tests for the two dispatch surfaces.

The HTTP layer and the MCP layer wire the same implementation functions, but differently:

* MCP forwards the caller's arguments straight through — `add_video_track(**arguments)` — so
  an omitted argument gets the implementation's own default.
* HTTP re-declares every parameter with `data.get(name, default)`, so an omitted argument gets
  whatever default `capcut_server.py` happens to specify.

Those two sets of defaults have **already drifted apart**: the same logical call produces
different output depending on which transport made it. These tests pin the current behaviour
down so a refactor cannot change it silently, and each known divergence is marked DIVERGENCE
with both values.

They are characterization tests: they record what the code does today, not what it should do.
Resolving the divergences is a deliberate, user-facing decision.
"""

import inspect

import pytest

import capcut_server

# route -> (capcut_server attribute holding the impl, minimal valid payload)
ROUTES = {
    "/add_video": ("add_video_track", {"video_url": "https://example.invalid/v.mp4"}),
    "/add_audio": ("add_audio_track", {"audio_url": "https://example.invalid/a.mp3"}),
    "/add_text": ("add_text_impl", {"text": "hello", "start": 0, "end": 1}),
    "/add_image": ("add_image_impl", {"image_url": "https://example.invalid/i.png"}),
    "/add_subtitle": ("add_subtitle_impl", {"srt": "1\n00:00:00,000 --> 00:00:01,000\nhi\n"}),
    "/add_effect": ("add_effect_impl", {"effect_type": "Bling"}),
    # NOTE: HTTP reads "sticker_id" here, while MCP and the implementation call it
    # "resource_id". See test_add_sticker_parameter_is_named_differently_per_surface.
    "/add_sticker": ("add_sticker_impl", {"sticker_id": "abc"}),
    "/add_video_keyframe": ("add_video_keyframe_impl", {}),
}


@pytest.fixture
def capture(monkeypatch):
    """Replace an impl with a recorder and return what the route forwarded to it."""
    def run(route):
        attr, payload = ROUTES[route]
        seen = {}

        def recorder(*args, **kwargs):
            seen.update(kwargs)
            return {"draft_id": "d1", "draft_url": ""}

        monkeypatch.setattr(capcut_server, attr, recorder)
        client = capcut_server.app.test_client()
        client.post(route, json=payload)
        return seen
    return run


def impl_default(attr, param):
    """The implementation's own default for a parameter."""
    module = __import__(attr if attr.endswith("_impl") else attr)
    func = getattr(module, attr)
    return inspect.signature(func).parameters[param].default


# --------------------------------------------------------------- known divergences
#
# Each entry is (route, parameter, value the HTTP layer sends, value MCP would send).
# These are the 11 places where the two transports disagree today.

DIVERGENCES = [
    ("/add_video", "track_name", "video_main", "main"),
    ("/add_text", "transform_y", 0, -0.8),
    ("/add_text", "font_color", "#FF0000", "#ffffff"),
    ("/add_text", "background_style", 0, 1),
    ("/add_image", "track_name", "image_main", "main"),
    ("/add_subtitle", "font_size", 5.0, 8.0),
    ("/add_subtitle", "background_style", 0, 1),
    ("/add_subtitle", "vertical", False, True),
    ("/add_subtitle", "alpha", 1, 0.4),
    ("/add_video_keyframe", "track_name", "video_main", "main"),
]


@pytest.mark.parametrize("route,param,http_value,mcp_value", DIVERGENCES)
def test_known_divergence_between_http_and_mcp_defaults(capture, route, param, http_value, mcp_value):
    """DIVERGENCE: the same call yields different results over HTTP than over MCP.

    Pinned, not endorsed. Unifying these changes behaviour for one transport and is a
    deliberate decision — see enhancements-plan.md, Phase C2.
    """
    forwarded = capture(route)
    assert forwarded[param] == http_value, (
        f"HTTP default for {route} {param} changed; it was {http_value!r}"
    )

    attr = ROUTES[route][0]
    assert impl_default(attr, param) == mcp_value, (
        f"implementation default for {param} changed; MCP callers were getting {mcp_value!r}"
    )
    assert http_value != mcp_value, "this entry is no longer a divergence — remove it"


def test_add_sticker_accepts_both_parameter_names(capture):
    """Regression: HTTP read only `sticker_id`, while MCP and the implementation use
    `resource_id`, so an HTTP caller following the MCP schema was told the parameter was
    missing. Both names now work, with `resource_id` canonical.
    """
    import mcp_server
    schema = [t for t in mcp_server.TOOLS if t["name"] == "add_sticker"][0]["inputSchema"]
    assert "resource_id" in schema["properties"]

    client = capcut_server.app.test_client()
    for name in ("resource_id", "sticker_id"):
        seen = {}

        def recorder(*args, **kwargs):
            seen.update(kwargs)
            return {"draft_id": "d1"}

        original = capcut_server.add_sticker_impl
        capcut_server.add_sticker_impl = recorder
        try:
            client.post("/add_sticker", json={name: "abc"})
        finally:
            capcut_server.add_sticker_impl = original
        assert seen.get("resource_id") == "abc", f"{name} was not accepted"


def test_add_sticker_error_names_the_canonical_parameter(capture):
    client = capcut_server.app.test_client()
    body = client.post("/add_sticker", json={}).get_json()
    assert body["success"] is False
    assert "resource_id" in body["error"]


def test_add_sticker_end_is_required_by_the_impl_but_defaulted_over_http(capture):
    """DIVERGENCE: HTTP supplies a default for an argument the implementation requires.

    `end` has no default in add_sticker_impl and is listed as required by the MCP schema, but
    the HTTP route substitutes 5.0, so an omitted `end` silently produces a 5-second sticker
    over HTTP and an error over MCP.
    """
    import mcp_server
    schema = [t for t in mcp_server.TOOLS if t["name"] == "add_sticker"][0]["inputSchema"]
    assert "end" in schema["required"]
    assert impl_default("add_sticker_impl", "end") is inspect._empty

    forwarded = capture("/add_sticker")
    assert forwarded["end"] == 5.0


# --------------------------------------------------------------- agreed defaults

AGREED = [
    ("/add_video", "scale_x", 1),
    ("/add_video", "scale_y", 1),
    ("/add_video", "speed", 1.0),
    ("/add_video", "volume", 1.0),
    ("/add_video", "transform_x", 0),
    ("/add_video", "target_start", 0),
    ("/add_video", "transition_duration", 0.5),
    ("/add_audio", "volume", 1.0),
    ("/add_audio", "speed", 1.0),
    ("/add_text", "font_size", 8.0),
    ("/add_image", "scale_x", 1),
    ("/add_sticker", "scale_x", 1.0),
]


@pytest.mark.parametrize("route,param,value", AGREED)
def test_defaults_the_two_surfaces_agree_on(capture, route, param, value):
    forwarded = capture(route)
    assert forwarded[param] == value


# --------------------------------------------------------------- shared contract

@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_route_returns_the_http_envelope(capture, route):
    """HTTP answers {success, output, error}; MCP answers {success, result}.

    Both shapes are a contract for existing callers and must survive any refactor.
    """
    attr, payload = ROUTES[route]
    capture(route)   # installs the recorder
    client = capcut_server.app.test_client()
    body = client.post(route, json=payload).get_json()
    assert set(body) == {"success", "output", "error"}


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_missing_required_parameter_is_rejected_without_calling_the_impl(monkeypatch, route):
    attr, _ = ROUTES[route]
    called = []
    monkeypatch.setattr(capcut_server, attr, lambda *a, **k: called.append(1))
    client = capcut_server.app.test_client()
    body = client.post(route, json={}).get_json()
    if route == "/add_video_keyframe":
        pytest.skip("add_video_keyframe has no strictly required parameter")
    assert body["success"] is False
    assert body["error"]
    assert not called, "validation must run before the implementation is invoked"


# --------------------------------------------------------------- draft url consistency

def test_generate_draft_url_matches_every_other_response_from_the_same_server():
    """Regression: the route hand-rolled "?=<id>" — a query string with no parameter name.

    Every other response from this server, and the MCP tool, use util.generate_draft_url,
    which emits "?draft_id=<id>". The route now uses the same helper.
    """
    from util import generate_draft_url

    client = capcut_server.app.test_client()
    body = client.post("/generate_draft_url", json={"draft_id": "dfd_123"}).get_json()

    assert body["success"] is True
    assert body["output"]["draft_url"] == generate_draft_url("dfd_123")
    assert "?draft_id=dfd_123" in body["output"]["draft_url"]
    assert "?=" not in body["output"]["draft_url"]


def test_generate_draft_url_still_requires_a_draft_id():
    client = capcut_server.app.test_client()
    body = client.post("/generate_draft_url", json={}).get_json()
    assert body["success"] is False
    assert "draft_id" in body["error"]


# --------------------------------------------------------------- add_video end regression

def test_add_video_without_end_forwards_none_not_zero(capture):
    """Regression: the route defaulted `end` to 0.

    The implementation computes source_duration = end - start and treats None as "use the
    whole video", so a literal 0 produced a ZERO-LENGTH clip over HTTP while the same call
    over MCP produced the full video.
    """
    forwarded = capture("/add_video")
    assert forwarded["end"] is None


def test_add_video_end_none_uses_the_full_duration(tmp_path, monkeypatch):
    """The behaviour the route default was silently breaking, exercised for real."""
    import json
    import draft_cache
    from add_video_track import add_video_track

    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", str(tmp_path))

    def clip_seconds(**overrides):
        kwargs = dict(video_url="https://example.invalid/v.mp4", duration=10.0, track_name="t")
        kwargs.update(overrides)
        result = add_video_track(**kwargs)
        data = json.loads(draft_cache.get_script(result["draft_id"]).dumps())
        segments = [s for t in data["tracks"] for s in t.get("segments", [])]
        return segments[0]["source_timerange"]["duration"] / 1_000_000

    assert clip_seconds() == 10.0, "omitting end must use the whole video"
    assert clip_seconds(end=0) == 0.0, "end=0 really does mean a zero-length clip"


# --------------------------------------------------------------- deferred duration probe

def test_zero_length_placeholder_is_corrected_at_save_time(tmp_path, monkeypatch):
    """add_video defers the duration probe to save_draft, on purpose.

    The segment carries a zero or negative source duration until then, and that placeholder is
    load-bearing: update_media_metadata corrects a segment only when its source end is past the
    real duration or <= 0. Clamping the placeholder to 0 would leave `end` positive for any
    segment with start > 0, the correction would not fire, and the clip would stay zero-length.
    """
    import json
    import subprocess

    import draft_cache
    from add_video_track import add_video_track
    from save_draft_impl import update_media_metadata

    ffmpeg = __import__("shutil").which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not on PATH")

    source = tmp_path / "six.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x240:rate=30:duration=6",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True,
    )
    monkeypatch.setattr(draft_cache, "DRAFT_STORE_DIR", str(tmp_path / "store"))

    def source_timerange(**kwargs):
        result = add_video_track(video_url=str(source), track_name="t", **kwargs)
        script = draft_cache.get_script(result["draft_id"])
        before = [s for t in json.loads(script.dumps())["tracks"]
                  for s in t.get("segments", [])][0]["source_timerange"]
        update_media_metadata(script)
        after = [s for t in json.loads(script.dumps())["tracks"]
                 for s in t.get("segments", [])][0]["source_timerange"]
        return before, after

    before, after = source_timerange()
    assert before["duration"] == 0, "the placeholder is what triggers the correction"
    assert after["duration"] == 6_000_000, "save must fill in the real duration"

    before, after = source_timerange(start=2)
    assert before["duration"] < 0, "a start offset makes the placeholder negative, by design"
    assert after == {"start": 2_000_000, "duration": 4_000_000}
