"""Landing, sign-in, and getting started share one card width and control height.

Acceptance criteria for issue #22:
- the sign-in card is the same width as the getting started card
- the sign-in buttons are the same height as the Get started button
- the fields are the same height as that button
"""

import re

from pages.getstarted import layout as getstarted_layout
from pages.home import layout as home_layout
from pages.signin import layout as signin_layout

CSS_PATH = "assets/dash_web.css"


def _css():
    with open(CSS_PATH, encoding="utf-8") as handle:
        return handle.read()


def _class_names(component):
    found = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        data = node.to_plotly_json() if hasattr(node, "to_plotly_json") else node
        if not isinstance(data, dict):
            return
        props = data.get("props") or {}
        class_name = props.get("className")
        if class_name:
            found.append(class_name)
        walk(props.get("children"))

    walk(component)
    return found


def _prop_values(component, prop):
    found = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        data = node.to_plotly_json() if hasattr(node, "to_plotly_json") else node
        if not isinstance(data, dict):
            return
        props = data.get("props") or {}
        if prop in props:
            found.append(props[prop])
        walk(props.get("children"))

    walk(component)
    return found


def test_auth_cards_share_one_width():
    css = _css()
    match = re.search(r"--auth-card-width:\s*([^;]+);", css)
    assert match is not None
    assert match.group(1).strip() == "520px"
    for snippet in (
        ".auth-screen{width:100%;max-width:var(--auth-card-width);",
        ".signin-screen{max-width:var(--auth-card-width);}",
        ".gs-screen{max-width:var(--auth-card-width);",
        ".home-screen,\n.signup-screen{max-width:var(--auth-card-width);}",
    ):
        assert snippet in css
    assert ".home-screen,\n.signup-screen{max-width:420px" not in css
    assert ".signin-screen{max-width:560px" not in css
    assert ".auth-screen{width:100%;max-width:560px" not in css


def test_signin_buttons_and_fields_match_get_started_height():
    css = _css()
    match = re.search(r"--auth-control-height:\s*([^;]+);", css)
    assert match is not None
    assert match.group(1).strip() == "56px"
    assert ".auth-primary-btn{height:var(--auth-control-height);" in css
    assert ".auth-google-btn{height:var(--auth-control-height);" in css
    assert ".gs-primary{margin-top:16px;height:var(--auth-control-height);}" in css
    assert ".auth-input,.gs-input{width:100%;height:var(--auth-control-height);" in css
    assert "button.gs-select{width:100%;height:var(--auth-control-height);" in css
    assert (
        ".home-screen .auth-primary-btn,\n"
        ".signin-screen .auth-primary-btn,\n"
        ".signin-screen .auth-google-btn,\n"
        ".gs-screen .auth-primary-btn,\n"
        ".signup-screen .auth-primary-btn{\n"
        "  height:var(--auth-control-height);\n"
        "}"
    ) in css
    assert "height:40px" not in css
    assert "height:64px" not in css
    assert "height:52px" not in css
    assert "height:58px" not in css


def test_landing_and_signin_keep_stub_entry_points():
    """Layout-only change: the local stub sign-in hooks stay in place."""
    home_classes = _class_names(home_layout())
    signin_classes = _class_names(signin_layout())
    started_classes = _class_names(getstarted_layout())

    assert any("home-screen" in name for name in home_classes)
    assert any(name == "auth-primary-btn" for name in home_classes)
    assert any("signin-screen" in name for name in signin_classes)
    assert any(name == "auth-primary-btn" for name in signin_classes)
    assert any(name == "auth-google-btn" for name in signin_classes)
    assert any("auth-input" in name for name in signin_classes)
    assert any("signup-screen" in name and "auth-screen" in name for name in started_classes)
    assert sum(name == "auth-input" for name in started_classes) == 6
    assert not any("gs-screen" in name for name in started_classes)

    home_ids = _prop_values(home_layout(), "id")
    signin_ids = _prop_values(signin_layout(), "id")
    assert {"type": "auth-btn", "action": "home-get-started"} in home_ids
    assert {"type": "auth-btn", "action": "home-have-account"} in home_ids
    assert "signin-username" in signin_ids
    assert "signin-password" in signin_ids
    assert {"type": "auth-btn", "action": "signin-submit"} in signin_ids
