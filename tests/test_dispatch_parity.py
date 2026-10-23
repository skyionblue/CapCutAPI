"""Tests that the two dispatch surfaces behave as one.

The HTTP layer used to re-declare every parameter with its own defaults while MCP forwarded
arguments straight through. The two sets drifted apart, and the same logical call produced
different output depending on the transport.

Both now go through `tool_registry`: HTTP forwards only the keys the caller actually sent, so
every default comes from the implementation. These tests hold that line — they check that the
implementations carry the decided values and that the HTTP layer does not quietly reintroduce
defaults of its own.
"""

import inspect

import pytest

import capcut_server
import tool_registry

# route -> (capcut_server attribute holding the impl, minimal valid payload)
ROUTES = {
    "/add_video": ("add_video_track", {"video_url": "https://example.invalid/v.mp4"}),
    "/add_audio": ("add_audio_track", {"audio_url": "https://example.invalid/a.mp3"}),
    "/add_text": ("add_text_impl", {"text": "hello", "start": 0, "end": 1}),
    "/add_image": ("add_image_impl", {"image_url": "https://example.invalid/i.png"}),
    # Sent under the legacy name on purpose: the alias must keep working.
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
    def run(route, payload=None):
        attr, default_payload = ROUTES[route]
        payload = default_payload if payload is None else payload
        seen = {}
        called = []

        def recorder(*args, **kwargs):
            called.append(True)
            seen.update(kwargs)
            return {"draft_id": "d1", "draft_url": ""}

        monkeypatch.setattr(tool_registry, attr, recorder)
        client = capcut_server.app.test_client()
        client.post(route, json=payload)
        # Without this, a route that bypasses the shared dispatch would leave `seen` empty and
        # every "the route does not send X" assertion would pass for the wrong reason.
        assert called, (
            f"{route} did not reach tool_registry.{attr}; it is not going through the shared "
            f"dispatch, so this test proves nothing"
        )
        return seen
    return run


def impl_default(attr, param):
    """The implementation's own default for a parameter."""
    module = __import__(attr if attr.endswith("_impl") else attr)
    func = getattr(module, attr)
    return inspect.signature(func).parameters[param].default


# --------------------------------------------------------------- decided defaults

# Every parameter the two surfaces once disagreed on, with the value decided in Phase C2.
# The HTTP layer no longer declares any of these; the implementation is the single source.
DECIDED = [
    ("/add_video", "track_name", "video_main"),
    ("/add_image", "track_name", "image_main"),
    ("/add_video_keyframe", "track_name", "video_main"),
    ("/add_text", "transform_y", 0),
    ("/add_text", "background_style", 0),
    ("/add_text", "font_color", "#ffffff"),
    ("/add_subtitle", "vertical", False),
    ("/add_subtitle", "alpha", 1),
    ("/add_subtitle", "background_style", 0),
    ("/add_subtitle", "font_size", 8.0),
    ("/add_sticker", "end", 5.0),
]


@pytest.mark.parametrize("route,param,value", DECIDED)
def test_decided_default_lives_in_the_implementation(route, param, value):
    assert impl_default(ROUTES[route][0], param) == value


@pytest.mark.parametrize("route,param,value", DECIDED)
def test_http_does_not_override_the_decided_default(capture, route, param, value):
    """The regression that matters.

    Re-adding `data.get(name, something)` to a route would restart exactly the drift this
    phase removed, and would be invisible in review.
    """
    forwarded = capture(route)
    assert param not in forwarded, (
        f"the HTTP layer is supplying its own {param}; defaults must come from the "
        f"implementation so both transports agree"
    )


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_http_forwards_only_what_the_caller_sent(capture, route):
    """No parameter should reach the implementation unless the caller asked for it."""
    _attr, payload = ROUTES[route]
    forwarded = capture(route)
    # A legacy key is renamed to the canonical one on the way through, so compare post-alias.
    aliases = capcut_server.PARAMETER_ALIASES.get(route.lstrip("/"), {})
    sent = {aliases.get(key, key) for key in payload}
    unexpected = set(forwarded) - sent
    assert not unexpected, f"{route} invented arguments the caller never sent: {sorted(unexpected)}"


def test_caller_supplied_values_still_reach_the_implementation(capture):
    forwarded = capture("/add_video", {
        "video_url": "https://example.invalid/v.mp4", "track_name": "custom", "scale_x": 2.0,
    })
    assert forwarded["track_name"] == "custom"
    assert forwarded["scale_x"] == 2.0


def test_add_subtitle_accepts_both_parameter_names(capture):
    """The route read `srt`; the catalogue and implementation call it `srt_path`.

    Found only because the capture fixture started asserting it had actually intercepted the
    call -- these tests had been passing vacuously, with the request rejected as missing a
    required parameter before dispatch was ever reached.
    """
    for name in ("srt", "srt_path"):
        forwarded = capture("/add_subtitle", {name: "sub.srt"})
        assert forwarded.get("srt_path") == "sub.srt", f"{name} was not accepted"


def test_add_sticker_accepts_both_parameter_names(capture):
    """Regression: HTTP read only `sticker_id`, while MCP and the implementation use
    `resource_id`. Both names still work through the shared dispatch, `resource_id` canonical.
    """
    for name in ("resource_id", "sticker_id"):
        forwarded = capture("/add_sticker", {name: "abc"})
        assert forwarded.get("resource_id") == "abc", f"{name} was not accepted"


def test_add_sticker_error_names_the_canonical_parameter():
    body = capcut_server.app.test_client().post("/add_sticker", json={}).get_json()
    assert body["success"] is False
    assert "resource_id" in body["error"]


def test_add_sticker_end_is_no_longer_required_by_the_implementation():
    schema = [t for t in tool_registry.TOOLS if t["name"] == "add_sticker"][0]["inputSchema"]
    assert "end" not in schema["required"]
    assert impl_default("add_sticker_impl", "end") == 5.0


def test_no_route_declares_its_own_parameter_defaults():
    """Structural guard: the converted routes must stay thin.

    A `data.get('x', default)` creeping back into one of them is how the surfaces drifted the
    first time, so it fails here rather than being noticed months later.
    """
    import ast

    source = open("capcut_server.py").read()
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        route = next((d.args[0].value.lstrip("/") for d in node.decorator_list
                      if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "route"), None)
        if route is None or f"/{route}" not in ROUTES:
            continue
        for call in ast.walk(node):
            if (isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "get"
                    and getattr(call.func.value, "id", "") == "data" and len(call.args) > 1):
                offenders.append(f"{route}:{getattr(call.args[0], 'value', '?')}")
    assert not offenders, f"routes reintroduced their own defaults: {offenders}"


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
    schema = next(t for t in tool_registry.TOOLS if t["name"] == route.lstrip("/"))["inputSchema"]
    if not schema.get("required"):
        pytest.skip(f"{route} has no required parameter")

    called = []
    monkeypatch.setattr(tool_registry, attr, lambda *a, **k: called.append(1))
    body = capcut_server.app.test_client().post(route, json={}).get_json()

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

def test_add_video_without_end_does_not_send_a_zero(capture):
    """Regression: the route defaulted `end` to 0.

    The implementation computes source_duration = end - start and treats None as "use the
    whole video", so a literal 0 produced a zero-length clip over HTTP. The route now sends
    nothing, leaving the implementation's None in place.
    """
    forwarded = capture("/add_video")
    assert "end" not in forwarded
    assert impl_default("add_video_track", "end") is None


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
