from dash import ALL, Dash, Input, Output, State, ctx, dcc, html

from pages import (
    autoloan_layout,
    circle_layout,
    credit_layout,
    dashboard_layout,
    home_layout,
    members_layout,
    payouts_layout,
    signin_layout,
    wallet_layout,
)
from pages.components import icon
from pages.data import CRUMBS, ME, NAV
from pages.payouts import detail_card, queue_table


def sidebar(page, role):
    return html.Aside(
        className="sidebar",
        children=[
            html.Div([html.Div("a", className="brandmark"), "AjoCredit"], className="sb-brand"),
            html.Div(
                [
                    html.Button(
                        [icon(icon_name), label],
                        id={"type": "nav-btn", "page": k},
                        n_clicks=0,
                        className=f"nav-btn {'on' if page == k else ''}",
                    )
                    for k, label, icon_name in NAV
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
                            html.Div("KA", className="av"),
                            html.Div(
                                [html.Div(f"@{ME['username']}", className="meta-main"), html.Div(ME["city"], className="meta-sub")]
                            ),
                        ],
                        className="me-row",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Member",
                                id={"type": "role-btn", "role": "member"},
                                n_clicks=0,
                                className=f"{'on' if role == 'member' else ''}",
                            ),
                            html.Button(
                                "Admin",
                                id={"type": "role-btn", "role": "admin"},
                                n_clicks=0,
                                className=f"{'on' if role == 'admin' else ''}",
                            ),
                        ],
                        className="role-seg",
                    ),
                ],
                className="sb-footer",
            ),
        ],
    )


def topbar(page):
    crumbs = CRUMBS.get(page, ["AjoCredit"])
    return html.Div(
        className="topbar",
        children=[
            html.Div(
                [
                    item
                    for i, c in enumerate(crumbs)
                    for item in (
                        ([html.Span("/", className="sep")] if i > 0 else [])
                        + [html.Span(c, className="crumb strong" if i == len(crumbs) - 1 else "crumb")]
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


app = Dash(
    __name__,
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
    ],
)
app.title = "AjoCredit Web (Dash)"
app.config.suppress_callback_exceptions = True

app.layout = html.Div(
    className="app-root",
    children=[
        dcc.Store(id="store-page", data="landing"),
        dcc.Store(id="store-role", data="member"),
        html.Div(id="app-shell"),
    ],
)


@app.callback(
    Output("store-page", "data"),
    Output("store-role", "data"),
    Input({"type": "nav-btn", "page": ALL}, "n_clicks"),
    Input({"type": "role-btn", "role": ALL}, "n_clicks"),
    Input({"type": "auth-btn", "action": ALL}, "n_clicks"),
    State("store-page", "data"),
    State("store-role", "data"),
    prevent_initial_call=True,
)
def update_state(_, __, ___, current_page, current_role):
    trig = ctx.triggered_id
    if isinstance(trig, dict) and trig.get("type") == "nav-btn":
        return trig["page"], current_role
    if isinstance(trig, dict) and trig.get("type") == "role-btn":
        return current_page, trig.get("role", current_role)
    if isinstance(trig, dict) and trig.get("type") == "auth-btn":
        action = trig.get("action")
        if action == "home-have-account":
            return "signin", current_role
        if action == "home-get-started":
            return "home", current_role
        if action == "signin-back":
            return "landing", current_role
        if action == "signin-submit":
            return "home", current_role
        if action == "signin-get-started":
            return "landing", current_role
    return current_page, current_role


@app.callback(
    Output("app-shell", "children"),
    Input("store-page", "data"),
    Input("store-role", "data"),
)
def render_shell(page, role):
    if page == "landing":
        return html.Div(className="auth-shell-wrap", children=home_layout())
    if page == "signin":
        return html.Div(className="auth-shell-wrap", children=signin_layout())
    return html.Div(
        className="shell",
        children=[
            sidebar(page, role),
            html.Div(className="main", children=[topbar(page), html.Div(render_page(page, role), id="content", className="content")]),
        ],
    )


@app.callback(
    Output("payout-selected", "data"),
    Input({"type": "payout-select", "u": ALL}, "n_clicks"),
    Input({"type": "payout-select-row", "u": ALL}, "n_clicks"),
    State("payout-selected", "data"),
    prevent_initial_call=True,
)
def select_payout_member(_, __, current_selected):
    trig = ctx.triggered_id
    if isinstance(trig, dict) and trig.get("type") in {"payout-select", "payout-select-row"}:
        return trig["u"]
    return current_selected


@app.callback(
    Output("payout-queue-wrap", "children"),
    Output("payout-detail-card", "children"),
    Input("payout-selected", "data"),
    Input("store-role", "data"),
)
def render_payout_selection(selected_user, role):
    selected_user = selected_user or "kemi_a"
    return queue_table(selected_user), detail_card(selected_user, role)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
