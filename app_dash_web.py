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
    due_diligence_layout,
    getstarted_loading_uk_layout,
    getstarted_result_uk_layout,
    getstarted_layout,
    home_layout,
    members_layout,
    nigeria_locked_layout,
    payouts_layout,
    settings_layout,
    signin_layout,
    wallet_layout,
    support_layout,
)
from pages.getstarted import SIGNUP_NOTICE, signup_problem  # noqa: E402
from pages.settings import apply_settings_action  # noqa: E402
from pages.components import icon  # noqa: E402
from pages.data import CRUMBS, NAV  # noqa: E402
from pages.credit import assessment_chart, forecast_chart  # noqa: E402
from pages.join import layout as join_layout  # noqa: E402
from pages.join import register_join_callbacks  # noqa: E402
from pages.members import register_callbacks as register_members_callbacks  # noqa: E402
from pages.my_ajo import register_callbacks as register_my_ajo_callbacks  # noqa: E402
from pages.my_circles import my_circles_rows  # noqa: E402
from pages.payout_access import resolve_ajo, visible_ajo_names  # noqa: E402
from pages.payouts import TRACKERS, subtitle_for, tracker_body  # noqa: E402
from pages.wallet import quote_body  # noqa: E402
from pages.support import contact_reply  # noqa: E402


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
    "settings": "/settings",
    "dd-overview": "/settings/complete-profile",
    "join": "/join",
    "support": "/support",
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
    """Page and canonical path the server will allow for this session.

    The #20 role gate runs first. The creator check then applies to `/payouts`
    the same way it does for the menu and the rendered page, including when
    the address was typed. The username comes from the server session.
    """
    username = None
    try:
        _session_role, username = current_identity()
    except RuntimeError:
        username = None
    page = _visible_page(gate_page(page_from_pathname(pathname), role), role, username)
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


def _visible_page(page, role, username):
    """Apply the creator check after the #20 role gate."""
    if page == "payouts" and not visible_ajo_names(username, role):
        return "home"
    return page


def _app_page(page, role):
    if role in {"admin", "member"}:
        return page
    return "signin"


def next_state(trigger, current_page, current_rev, username, password, signup=None):
    """Navigation transition. The signed-in role is read from the session."""
    role, session_username = current_identity()
    rev = current_rev or 0
    if isinstance(trigger, dict) and trigger.get("type") == "nav-btn":
        return _visible_page(gate_page(trigger.get("page"), role), role, session_username), rev, ""
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
            return "getstarted-1", rev, ""
        if action == "getstarted-back-home":
            return "landing", rev, ""
        if action == "signup-submit":
            problem = signup_problem(signup)
            if problem:
                return "getstarted-1", rev, problem
            return "signin", rev + 1, ""
        if action == "settings-complete-profile":
            return _app_page("dd-overview", role), rev, ""
        if action in {"dd-back-settings", "getstarted-finish"}:
            if action == "getstarted-finish" and role in {"admin", "member"}:
                session["profile_uk_checked"] = True
            return _app_page("settings", role), rev, ""
        if action == "dd-start-uk":
            return _app_page("getstarted-uk-loading", role), rev, ""
        if action in {"dd-back-overview", "getstarted-back-step3", "getstarted-back-step1"}:
            return _app_page("dd-overview", role), rev, ""
        if action == "getstarted-back-uk-loading":
            return _app_page("getstarted-uk-loading", role), rev, ""
        if action == "getstarted-to-uk":
            return _app_page("getstarted-uk-loading", role), rev, ""
        if action in {"getstarted-run-check", "getstarted-back-step2"}:
            return _app_page("dd-overview", role), rev, ""
    if isinstance(trigger, dict) and trigger.get("type") == "gs-timer":
        if trigger.get("screen") == "uk":
            return _app_page("getstarted-4", role), rev, ""
        if trigger.get("screen") == "2":
            return _app_page("dd-overview", role), rev, ""
    return _visible_page(gate_page(current_page, role), role, session_username), rev, ""


def sidebar(page, role, username):
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
                    for key, item_label, icon_name in _nav_for(role, username)
                ],
                className="sb-nav",
            ),
            html.Div("My circles", className="sb-section"),
            html.Div(my_circles_rows(username=username, role=role, page=page), className="sb-nav"),
            html.Div([profile_button(page, role, username)], className="sb-footer"),
        ],
    )


def profile_button(page, role, username):
    label = "Admin" if role == "admin" else "Member"
    handle = username or "signed-in"
    initials = handle[:2].upper()
    return html.A(
        [
            html.Div(initials, className="av"),
            html.Div(
                [
                    html.Div(f"@{handle}", className="meta-main"),
                    html.Div("Settings", className="settings-link"),
                    html.Div(label, className="role-fixed"),
                ]
            ),
        ],
        href=path_for_page("settings"),
        className=f"me-btn {'on' if page == 'settings' else ''}",
        **({"aria-current": "page"} if page == "settings" else {}),
    )


def topbar(page, role, username):
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
                    html.Div(profile_button(page, role, username), className="top-settings"),
                ],
                className="top-right",
            ),
        ],
    )


def _nav_for(role, username):
    """#20 hides the tracker from every non-admin. #31 also hides it from an admin who did not create the Ajo."""
    entries = nav_entries(NAV, role)
    if not visible_ajo_names(username, role):
        return [item for item in entries if item[0] != "payouts"]
    return entries


def profile_from_session():
    return {
        "address_line": session.get("address_line", ""),
        "address_city": session.get("address_city", ""),
        "address_postcode": session.get("address_postcode", ""),
        "profile_phone": session.get("profile_phone", ""),
        "uk_checked": bool(session.get("profile_uk_checked")),
    }


def render_page(page, role, username=None, profile=None):
    if page == "payouts" and not visible_ajo_names(username, role):
        page = "home"
    pages = {
        "home": dashboard_layout(role),
        "members": members_layout(role, username),
        "payouts": payouts_layout(role, username),
        "credit": credit_layout(),
        "autoloan": autoloan_layout(),
        "wallet": wallet_layout(),
        "circle": circle_layout(role, username),
        "settings": settings_layout(username, profile or {}),
        "join": join_layout(role),
        "support": support_layout(),
    }
    return pages.get(page, dashboard_layout(role))


def render_shell(page, _client_value=None):
    """Render the shell for a page. `_client_value` is ignored on purpose.

    Authorization uses the server session only, so a client-supplied role
    cannot change what is rendered.
    """
    role, username = current_identity()
    page = gate_page(page, role)
    if page == "payouts" and not visible_ajo_names(username, role):
        page = "home"
    if page == "signin":
        return html.Div()
    if page == "landing":
        return html.Div(className="auth-shell-wrap", children=home_layout())
    if page == "getstarted-1":
        return html.Div()
    if page == "dd-overview":
        return html.Div(className="auth-shell-wrap", children=due_diligence_layout())
    if page in {"getstarted-2", "getstarted-3"}:
        return html.Div(className="auth-shell-wrap", children=nigeria_locked_layout())
    if page == "getstarted-uk-loading":
        return html.Div(className="auth-shell-wrap", children=getstarted_loading_uk_layout())
    if page == "getstarted-4":
        return html.Div(className="auth-shell-wrap", children=getstarted_result_uk_layout())
    return html.Div(
        className="shell",
        children=[
            sidebar(page, role, username),
            html.Div(
                className="main",
                children=[
                    topbar(page, role, username),
                    html.Div(
                        render_page(page, role, username, profile_from_session()),
                        id="content",
                        className="content",
                    ),
                ],
            ),
        ],
    )


def signin_dock_style(page):
    role, _username = current_identity()
    if gate_page(page, role) == "signin":
        return {}
    return {"display": "none"}


def signup_dock_style(page):
    if page == "getstarted-1":
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

from pages.delay_cover import register_callbacks  # noqa: E402

register_callbacks(app)
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
        html.Div(
            id="signup-dock",
            className="auth-shell-wrap",
            style={"display": "none"},
            children=getstarted_layout(),
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
    Output("signup-error", "children"),
    Output("signin-notice", "children"),
    Input({"type": "nav-btn", "page": ALL}, "n_clicks"),
    Input({"type": "auth-btn", "action": ALL}, "n_clicks"),
    Input({"type": "gs-timer", "screen": ALL}, "n_intervals"),
    State("url", "pathname"),
    State("store-auth-rev", "data"),
    State("signin-username", "value"),
    State("signin-password", "value"),
    State("signup-first-name", "value"),
    State("signup-last-name", "value"),
    State("signup-email", "value"),
    State("signup-phone", "value"),
    State("signup-password", "value"),
    State("signup-password-confirm", "value"),
    prevent_initial_call=True,
)
def update_state(
    _nav,
    _auth,
    _timers,
    current_pathname,
    current_rev,
    username,
    password,
    first_name,
    last_name,
    email,
    phone,
    signup_password,
    signup_confirm,
):
    current_page = page_from_pathname(current_pathname) or "landing"
    trigger = ctx.triggered_id
    signup = {
        "first": first_name,
        "last": last_name,
        "email": email,
        "phone": phone,
        "password": signup_password,
        "confirm": signup_confirm,
    }
    page, rev, error = next_state(trigger, current_page, current_rev, username, password, signup)
    action = trigger.get("action") if isinstance(trigger, dict) else None
    signup_error = error if page == "getstarted-1" and action == "signup-submit" else ""
    signin_error = error if page == "signin" and action == "signin-submit" else ""
    notice = SIGNUP_NOTICE if action == "signup-submit" and page == "signin" and not error else ""
    target = path_for_page(page)
    path_out = target if normalize_pathname(current_pathname) != target else no_update
    return path_out, rev, signin_error, signup_error, notice


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
    Output("signup-dock", "style"),
    Input("url", "pathname"),
)
def toggle_signup_dock(pathname):
    return signup_dock_style(page_from_pathname(pathname))


@app.callback(
    Output("settings-feedback", "children"),
    Input({"type": "settings-action", "action": ALL}, "n_clicks"),
    State("settings-address-line", "value"),
    State("settings-city", "value"),
    State("settings-postcode", "value"),
    State("settings-phone", "value"),
    prevent_initial_call=True,
)
def update_settings_action(_clicks, line, city, postcode, phone):
    if session.get("role") not in {"admin", "member"}:
        return ""
    trigger = ctx.triggered_id
    action = trigger.get("action") if isinstance(trigger, dict) else None
    return apply_settings_action(
        action,
        {"line": line, "city": city, "postcode": postcode, "phone": phone},
        session,
    )


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
    if not visible_ajo_names(session.get("username"), session.get("role")):
        return current_selected
    trig = ctx.triggered_id
    if isinstance(trig, dict) and trig.get("type") in {"payout-select", "payout-select-row"}:
        return trig["u"]
    return current_selected


def _ajo_tab_classes(selected):
    specs = ctx.outputs_list[-1] if ctx.outputs_list else []
    if not isinstance(specs, list):
        return []
    classes = []
    for spec in specs:
        ident = spec.get("id") if isinstance(spec, dict) else None
        name = ident.get("name") if isinstance(ident, dict) else None
        classes.append("on" if name and name == selected else "")
    return classes


@app.callback(
    Output("payout-ajo", "data"),
    Input({"type": "payout-ajo-btn", "name": ALL}, "n_clicks"),
    State("payout-ajo", "data"),
    prevent_initial_call=True,
)
def select_payout_ajo(_clicks, current):
    username = session.get("username")
    role = session.get("role")
    allowed = visible_ajo_names(username, role)
    if not allowed:
        return None
    trig = ctx.triggered_id
    requested = trig.get("name") if isinstance(trig, dict) and trig.get("type") == "payout-ajo-btn" else current
    return resolve_ajo(requested, username, role)


@app.callback(
    Output("payout-tracker-sub", "children"),
    Output("payout-tracker-body", "children"),
    Output({"type": "payout-ajo-btn", "name": ALL}, "className"),
    Input("payout-ajo", "data"),
    Input("payout-selected", "data"),
)
def render_payout_selection(ajo_name, selected_user):
    username = session.get("username")
    role = session.get("role")
    ajo_name = resolve_ajo(ajo_name, username, role)
    classes = _ajo_tab_classes(ajo_name)
    if ajo_name is None:
        return "", html.Div(), classes
    tracker = TRACKERS.get(ajo_name)
    if tracker and not any(member["u"] == selected_user for member in tracker["members"]):
        selected_user = tracker["default"]
    left, side = tracker_body(ajo_name, selected_user, "admin")
    return subtitle_for(ajo_name, tracker), [left, side], classes


@app.callback(
    Output("support-feedback", "children"),
    Input("support-send", "n_clicks"),
    State("support-topic", "value"),
    State("support-subject", "value"),
    State("support-message", "value"),
    prevent_initial_call=True,
)
def submit_support_note(_n_clicks, topic, subject, message):
    """Confirm a support note on screen. No email or SMS is sent."""
    if session.get("role") not in {"admin", "member"}:
        return ""
    return contact_reply(topic, subject, message)


@app.callback(
    Output("early-payout-quote", "children"),
    Input("early-payout-request", "n_clicks"),
    prevent_initial_call=True,
)
def request_early_payout(n_clicks):
    """Show the local early-payout quote. Nothing is submitted or paid."""
    return [quote_body(bool(n_clicks))]


register_members_callbacks(app)
register_join_callbacks(app)
register_my_ajo_callbacks(app)


@app.callback(
    Output("fh-assess-chart", "children"),
    Input("fh-assess-view", "value"),
)
def render_finhealth_assessment(view):
    return assessment_chart(view or "history")


@app.callback(
    Output("fh-forecast-chart", "children"),
    Input("fh-forecast-view", "value"),
)
def render_finhealth_forecast(view):
    return forecast_chart(view or "forecast")


if __name__ == "__main__":
    debug = os.getenv("DASH_DEBUG", "false").lower() in ("true", "1", "yes")
    host = os.getenv("DASH_HOST", "127.0.0.1")
    port = int(os.getenv("DASH_PORT", "8055"))
    app.run(debug=debug, host=host, port=port)
