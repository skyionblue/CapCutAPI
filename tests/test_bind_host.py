"""The HTTP server must not bind beyond loopback by default.

It has no authentication, it fetches caller-supplied URLs from this machine, it writes
local files, and the CapCut backend moves the real cursor. It used to bind 0.0.0.0,
which offered all of that to the network. A regression here is silent -- everything
still works, it just also works for everyone else -- so it is pinned.
"""

import ast
import os

import pytest

from settings.local import HOST

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_default_bind_is_loopback():
    assert HOST == "127.0.0.1"


def test_the_server_binds_the_configured_host_and_not_a_literal():
    """Reading the source, because importing capcut_server starts nothing."""
    source = open(os.path.join(REPO_ROOT, "capcut_server.py"), encoding="utf-8").read()
    tree = ast.parse(source)

    run_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "app"
    ]
    assert run_calls, "no app.run(...) found; this test needs updating"

    for call in run_calls:
        host = next((kw.value for kw in call.keywords if kw.arg == "host"), None)
        assert host is not None, "app.run must pass host explicitly, not rely on Flask's default"
        assert isinstance(host, ast.Name) and host.id == "HOST", (
            "app.run must bind settings.local.HOST so the default stays loopback "
            "and stays overridable in one place"
        )


@pytest.mark.parametrize("exposed", ["0.0.0.0", "::", ""])
def test_known_wildcard_binds_are_not_the_default(exposed):
    assert HOST != exposed


def _settings_with(config: dict, tmp_path) -> dict:
    """Run settings.local against a config file of our own, not the repository's.

    The module reads its config at import time, so it is executed in a fresh
    namespace with CONFIG_FILE_PATH redirected. Reloading in place would leave the
    rest of the suite looking at a temp config that no longer exists.
    """
    import json
    import settings.local as local

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    original = ('CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '
                '"config.json")')
    source = open(local.__file__, encoding="utf-8").read()
    assert original in source, "settings.local no longer builds CONFIG_FILE_PATH this way"
    source = source.replace(original, f"CONFIG_FILE_PATH = {str(config_path)!r}")

    namespace: dict = {"__file__": local.__file__, "__name__": "settings._probe"}
    exec(compile(source, local.__file__, "exec"), namespace)
    return namespace


def test_the_host_key_overrides_the_default(tmp_path):
    assert _settings_with({"host": "192.168.1.50"}, tmp_path)["HOST"] == "192.168.1.50"


def test_omitting_the_host_key_leaves_loopback(tmp_path):
    namespace = _settings_with({"port": 9001}, tmp_path)
    assert namespace["HOST"] == "127.0.0.1"
    assert namespace["PORT"] == 9001, "the probe must really be reading the config"
