import os
import secrets

from dotenv import load_dotenv
from flask import redirect, request, session

load_dotenv(override=False)

from stub_auth import (  # noqa: E402
    SIGNIN_FAILED,
    authenticate,
    enforce_local_stub_policy,
    gate_page,
    nav_entries,
)

# Refuse a stub flag that is enabled off localhost before serving anything.
enforce_local_stub_policy()

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update  # noqa: E402

from pages import (  # noqa: E402
    autoloan_layout,
    circle_layout,
    credit_layout,
    dashboard_layout,
    getstarted_loading_layout,
    getstarted_loading_uk_layout,
    getstarted_result_origin_layout,
    getstarted_result_uk_layout,
    getstarted_layout,
    home_layout,
    members_layout,
    payouts_layout,
    signin_layout,
    wallet_layout,
)
from pages.components import icon  # noqa: E402
from pages.data import CRUMBS, NAV  # noqa: E402
from pages.payouts import detail_card, queue_table  # noqa: E402


# One address per screen. The page id stays the in-app name; the path is what
# refresh, back, and links use. Unknown paths are not a page.
PAGE_PATHS = {
    "landing": "/",
    "signin": "/signin",
    "getstarted-1": "/get-started",
    "getstarted-2": "/get-started/checking",
    "getstarted-3": "/get-started/origin-result",
    "getstarted-uk-loading": "/get-started/uk-check",
    "getstarted-4": "/get-started/uk-result",
    "home": "/dashboard",
    "circle": "/circle",
    "members": "/members",
    "payouts": "/payouts",
    "credit": "/credit",
    "autoloan": "/autoloan",
    "wallet": "/wallet",
}
PATH_PAGES = {path: page for page, path in PAGE_PATHS.items()}


def current_identity():
    """Role and username from the server session. Never from the client."""
    return session.get("role"), session.get("username")


def normalize_pathname(pathname: str | None) -> str:
    """Path only, without a query, hash, or trailing slash."""
    if pathname is None:
        return "/"
    path = str(pathname).split("?", 1)[0].split("#", 1)[0].strip()
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return path


def page_from_pathname(pathname: str | None) -> str | None:
    """Return the page id for a known address, or None when it is not one."""
    return PATH_PAGES.get(normalize_pathname(pathname))


def path_for_page(page: str | None) -> str:
    return PAGE_PATHS.get(page or "", "/")


def gated_path(pathname: str | None, role: str | None) -> tuple[str, str]:
    """Page and canonical path the server will allow for this session role."""
    page = gate_page(page_from_pathname(pathname), role)
    return page, path_for_page(page)


def apply_signin(username, password):
    """Replace the session with a server-decided stub identity, or clear it."""
    identity = authenticate(username, password)
    session.clear()
    if identity is None:
        return None
    session["username"] = identity.username
    session["role"] = identity.role
    return identity


def next_state(trigger, current_page, current_rev, username, password):
    """Navigation transition. The signed-in role is read from the session."""
    role, _username = current_identity()
    rev = current_rev or 0
    if isinstance(trigger, dict) and trigger.get("type") == "nav-btn":
        return gate_page(trigger.get("page"), role), rev, ""
    if isinstance(trigger, dict) and trigger.get("type") == "auth-btn":
        action = trigger.get("action")
        if action == "home-have-account":
            return "signin", rev, ""
        if action == "home-get-started":
            return "getstarted-1", rev, ""
        if action == "signin-back":
            return "landing", rev, ""
        if action == "signin-submit":
            identity = apply_signin(username, password)
            if identity is None:
                return "signin", rev + 1, SIGNIN_FAILED
            return "home", rev + 1, ""
        if action == "signin-get-started":
            return "landing", rev, ""
        if action == "getstarted-back-home":
            return "landing", rev, ""
        if action == "getstarted-run-check":
            return "getstarted-2", rev, ""
        if action == "getstarted-back-step1":
            return "getstarted-1", rev, ""
        if action == "getstarted-back-step2":
            return "getstarted-2", rev, ""
        if action == "getstarted-to-uk":
            return "getstarted-uk-loading", rev, ""
        if action == "getstarted-back-step3":
            return "getstarted-3", rev, ""
        if action == "getstarted-back-uk-loading":
            return "getstarted-uk-loading", rev, ""
        if action == "getstarted-finish":
            if role in {"admin", "member"}:
                return "home", rev, ""
            return "signin", rev, ""
    if isinstance(trigger, dict) and trigger.get("type") == "gs-timer":
        if trigger.get("screen") == "2":
            return "getstarted-3", rev, ""
        if trigger.get("screen") == "uk":
            return "getstarted-4", rev, ""
    return gate_page(current_page, role), rev, ""


def sidebar(page, role, username):
    label = "Admin" if role == "admin" else "Member"
    handle = username or "signed-in"
    initials = handle[:2].upper()
    return html.Aside(
        className="sidebar",
        children=[
            html.Div([html.Div("a", className="brandmark"), "AjoFinance"], className="sb-brand"),
            html.Div(
                [
                    html.A(
                        [icon(icon_name), item_label],
                        href=path_for_page(key),
                        className=f"nav-btn {'on' if page == key else ''}",
                        **({"aria-current": "page"} if page == key else {}),
                    )
                    for key, item_label, icon_name in nav_entries(NAV, role)
                ],
                className="sb-nav",
            ),
            html.Div("My circles", className="sb-section"),
            html.Div(
                [
                    html.Div([html.Span(className="cdot"), "Brum Builders"], className="circle-row"),
                    html.Div([html.Span(className="cdot"), "Sister Circle"], className="circle-row"),
                    html.Div([icon("plus"), "Create circle"], className="circle-row muted"),
                ],
                className="sb-nav",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(initials, className="av"),
                            html.Div(
                                [
                                    html.Div(f"@{handle}", className="meta-main"),
                                    html.Div(label, className="role-fixed"),
                                ]
                            ),
                        ],
                        className="me-row",
                    ),
                ],
                className="sb-footer",
            ),
        ],
    )


def topbar(page):
    crumbs = CRUMBS.get(page, ["AjoFinance"])
    return html.Div(
        className="topbar",
        children=[
            html.Div(
                [
                    item
                    for i, crumb in enumerate(crumbs)
                    for item in (
                        ([html.Span("/", className="sep")] if i > 0 else [])
                        + [html.Span(crumb, className="crumb strong" if i == len(crumbs) - 1 else "crumb")]
                    )
                ],
                className="crumbs",
            ),
            html.Div(
                [
                    html.Div([icon("search"), dcc.Input(placeholder="Search members, circles…", className="search-input")], className="search-wrap"),
                    html.Button([icon("bell"), html.Span(className="notif-dot")], className="ib"),
                ],
                className="top-right",
            ),
        ],
    )


def render_page(page, role):
    if page == "payouts" and role != "admin":
        page = "home"
    pages = {
        "home": dashboard_layout(role),
        "members": members_layout(),
        "payouts": payouts_layout(role),
        "credit": credit_layout(),
        "autoloan": autoloan_layout(),
        "wallet": wallet_layout(),
        "circle": circle_layout(role),
    }
    return pages.get(page, dashboard_layout(role))


def render_shell(page, _client_value=None):
    """Render the shell for a page. `_client_value` is ignored on purpose.

    Authorization uses the server session only, so a client-supplied role
    cannot change what is rendered.
    """
    role, username = current_identity()
    page = gate_page(page, role)
    if page == "signin":
        return html.Div()
    if page == "landing":
        return html.Div(className="auth-shell-wrap", children=home_layout())
    if page == "getstarted-1":
        return html.Div(className="auth-shell-wrap", children=getstarted_layout())
    if page == "getstarted-2":
        return html.Div(className="auth-shell-wrap", children=getstarted_loading_layout())
    if page == "getstarted-3":
        return html.Div(className="auth-shell-wrap", children=getstarted_result_origin_layout())
    if page == "getstarted-uk-loading":
        return html.Div(className="auth-shell-wrap", children=getstarted_loading_uk_layout())
    if page == "getstarted-4":
        return html.Div(className="auth-shell-wrap", children=getstarted_result_uk_layout())
    return html.Div(
        className="shell",
        children=[
            sidebar(page, role, username),
            html.Div(className="main", children=[topbar(page), html.Div(render_page(page, role), id="content", className="content")]),
        ],
    )


def signin_dock_style(page):
    role, _username = current_identity()
    if gate_page(page, role) == "signin":
        return {}
    return {"display": "none"}


app = Dash(
    __name__,
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
    ],
)
app.title = "AjoFinance"
app.config.suppress_callback_exceptions = True
app.server.secret_key = secrets.token_hex(32)
app.server.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

app.layout = html.Div(
    className="app-root",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="store-auth-rev", data=0),
        html.Div(id="app-shell"),
        html.Div(
            id="signin-dock",
            className="auth-shell-wrap",
            style={"display": "none"},
            children=signin_layout(),
        ),
    ],
)


def _skip_document_gate(path: str) -> bool:
    return path.startswith("/_dash") or path.startswith("/assets/") or path.startswith("/_favicon")


@app.server.before_request
def redirect_disallowed_path():
    """Send a direct visit to the address this session is allowed to see.

    Dash serves the app shell for every path. The role check happens here,
    before that shell is returned, so typing an admin URL does not render it.
    """
    if request.method not in {"GET", "HEAD"}:
        return None
    path = request.path or "/"
    if _skip_document_gate(path):
        return None
    role, _username = current_identity()
    _page, target = gated_path(path, role)
    if path != target:
        return redirect(target)
    return None


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("store-auth-rev", "data"),
    Output("signin-error", "children"),
    Input({"type": "nav-btn", "page": ALL}, "n_clicks"),
    Input({"type": "auth-btn", "action": ALL}, "n_clicks"),
    Input({"type": "gs-timer", "screen": ALL}, "n_intervals"),
    State("url", "pathname"),
    State("store-auth-rev", "data"),
    State("signin-username", "value"),
    State("signin-password", "value"),
    prevent_initial_call=True,
)
def update_state(_nav, _auth, _timers, current_pathname, current_rev, username, password):
    current_page = page_from_pathname(current_pathname) or "landing"
    page, rev, error = next_state(ctx.triggered_id, current_page, current_rev, username, password)
    target = path_for_page(page)
    path_out = target if normalize_pathname(current_pathname) != target else no_update
    return path_out, rev, error


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("url", "pathname"),
    Input("store-auth-rev", "data"),
    prevent_initial_call="initial_duplicate",
)
def canonicalize_pathname(pathname, _auth_rev):
    """Rewrite a client-side address the session is not allowed to keep."""
    role, _username = current_identity()
    _page, target = gated_path(pathname, role)
    if normalize_pathname(pathname) == target:
        return no_update
    return target


@app.callback(
    Output("app-shell", "children"),
    Output("signin-dock", "style"),
    Input("url", "pathname"),
    Input("store-auth-rev", "data"),
)
def render_shell_callback(pathname, auth_rev):
    role, _username = current_identity()
    page, _target = gated_path(pathname, role)
    return render_shell(page, auth_rev), signin_dock_style(page)


@app.callback(
    Output("payout-selected", "data"),
    Input({"type": "payout-select", "u": ALL}, "n_clicks"),
    Input({"type": "payout-select-row", "u": ALL}, "n_clicks"),
    State("payout-selected", "data"),
    prevent_initial_call=True,
)
def select_payout_member(_buttons, _rows, current_selected):
    if session.get("role") != "admin":
        return current_selected
    trig = ctx.triggered_id
    if isinstance(trig, dict) and trig.get("type") in {"payout-select", "payout-select-row"}:
        return trig["u"]
    return current_selected


@app.callback(
    Output("payout-queue-wrap", "children"),
    Output("payout-detail-card", "children"),
    Input("payout-selected", "data"),
)
def render_payout_selection(selected_user):
    if session.get("role") != "admin":
        return html.Div(), html.Div()
    selected_user = selected_user or "kemi_a"
    return queue_table(selected_user), detail_card(selected_user, "admin")


if __name__ == "__main__":
    debug = os.getenv("DASH_DEBUG", "false").lower() in ("true", "1", "yes")
    host = os.getenv("DASH_HOST", "127.0.0.1")
    port = int(os.getenv("DASH_PORT", "8055"))
    app.run(debug=debug, host=host, port=port)
