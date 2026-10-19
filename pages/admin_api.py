"""Admin screen. Audit and ledger rows come from the API.

The page does not decide who is a platform admin. A refusal from the API
is shown as the API sent it. Tokens are not rendered.
"""

from __future__ import annotations

from dash import Input, Output, State, dcc, html
from flask import session

import clock
import dash_api

LEDGER_UNAVAILABLE = "The ledger view is not available from this API."
AUDIT_UNAVAILABLE = "The audit log is not available from this API."
NEED_API = "Sign in through the API to load the audit log and the ledger."


def _rows(entries: list, columns: list[tuple[str, str]]):
    body = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        body.append(html.Tr([html.Td(str(entry.get(key) if entry.get(key) is not None else "")) for key, _label in columns]))
    if not body:
        body.append(html.Tr([html.Td("No entries.", colSpan=len(columns))]))
    return html.Table(
        className="t",
        children=[
            html.Thead(html.Tr([html.Th(label) for _key, label in columns])),
            html.Tbody(body),
        ],
    )


def _section(title: str, status: int, payload: object, unavailable: str, columns: list[tuple[str, str]], list_key: str):
    children: list = [html.H2(title, className="h2")]
    if status == 0:
        children.append(html.Div(unavailable, className="sub"))
        return html.Div(className="card", children=children)
    if status == 404:
        children.append(html.Div(unavailable, className="sub"))
        return html.Div(className="card", children=children)
    if status != 200:
        children.append(html.Div(dash_api.safe_detail(payload, "The API refused this request."), className="sub"))
        return html.Div(className="card", children=children)
    entries = payload.get(list_key) if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        entries = []
    children.append(_rows(entries, columns))
    return html.Div(className="card", children=children)


def _checked_at() -> str:
    return clock.now().strftime("%Y-%m-%d %H:%M:%S UTC")


def layout():
    sid = None
    try:
        sid = session.get("api_sid")
    except RuntimeError:
        sid = None
    if not isinstance(sid, str) or dash_api.VAULT.get(sid) is None:
        return html.Div(className="stack", children=[html.H1("Admin"), html.Div(NEED_API, className="sub")])

    audit_status, audit_payload = dash_api.request(
        "GET",
        "/api/v1/admin/audit",
        params={"page_size": "20"},
        sid=sid,
    )
    ledger_status, ledger_payload = dash_api.request(
        "GET",
        "/api/v1/admin/ledger",
        params={"page_size": "20"},
        sid=sid,
    )
    circles = session.get("circles") or []
    circle_lines = []
    for circle in circles:
        if isinstance(circle, dict) and circle.get("name") and circle.get("role"):
            circle_lines.append(html.Div(f"{circle['name']} · {circle['role']}", className="circle-row"))
    if not circle_lines:
        circle_lines.append(html.Div("No circles on this session.", className="sub"))

    return html.Div(
        className="stack",
        id="admin-api",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Admin"),
                            html.Div(f"Checked {_checked_at()}", id="admin-checked-at", className="sub"),
                        ]
                    ),
                    html.Button(
                        "Sign out",
                        id="admin-sign-out",
                        n_clicks=0,
                        className="btn btn-ghost",
                    ),
                ],
            ),
            html.Div(className="card", children=[html.H2("Circles", className="h2"), html.Div(circle_lines)]),
            html.Div(
                className="card",
                children=[
                    html.H2("Create or join", className="h2"),
                    html.Div(
                        className="row-btns",
                        children=[
                            dcc.Input(id="admin-circle-name", type="text", placeholder="Circle name", className="search-input"),
                            html.Button("Create Ajo", id="admin-create", n_clicks=0, className="btn btn-primary"),
                        ],
                    ),
                    html.Div(
                        className="row-btns",
                        children=[
                            dcc.Input(id="admin-join-id", type="text", placeholder="Circle id", className="search-input"),
                            html.Button("Join Ajo", id="admin-join", n_clicks=0, className="btn btn-ghost"),
                        ],
                    ),
                    html.Div(id="admin-feedback", className="sub"),
                ],
            ),
            _section(
                "Audit log",
                audit_status,
                audit_payload,
                AUDIT_UNAVAILABLE,
                [
                    ("id", "Id"),
                    ("created_at", "When"),
                    ("action", "Event"),
                    ("actor_user_id", "Actor"),
                    ("actor_role", "Role"),
                    ("circle_id", "Circle"),
                ],
                "entries",
            ),
            *_ledger_sections(ledger_status, ledger_payload),
        ],
    )


def _ledger_sections(status: int, payload: object):
    """Balances and every line of each transaction. Amounts stay the API's display strings."""
    sections = [
        _section(
            "Ledger balances",
            status,
            payload,
            LEDGER_UNAVAILABLE,
            [
                ("code", "Account"),
                ("account_type", "Type"),
                ("balance_pence", "Balance (pence)"),
                ("balance_display", "Balance"),
            ],
            "balances",
        )
    ]
    if status != 200 or not isinstance(payload, dict):
        return sections
    sections.append(
        _section(
            "Ledger transactions",
            status,
            payload,
            LEDGER_UNAVAILABLE,
            [
                ("posted_at", "When"),
                ("description", "Description"),
                ("reference", "Reference"),
            ],
            "transactions",
        )
    )
    lines = []
    for transaction in payload.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        for entry in transaction.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            lines.append(
                {
                    "posted_at": transaction.get("posted_at") or "",
                    "description": transaction.get("description") or "",
                    "account_code": entry.get("account_code") or "",
                    "direction": entry.get("direction") or "",
                    "amount_pence": entry.get("amount_pence") if entry.get("amount_pence") is not None else "",
                    "amount_display": entry.get("amount_display") or "",
                }
            )
    sections.append(
        html.Div(
            className="card",
            children=[
                html.H2("Ledger lines", className="h2"),
                _rows(
                    lines,
                    [
                        ("posted_at", "When"),
                        ("description", "Description"),
                        ("account_code", "Account"),
                        ("direction", "Direction"),
                        ("amount_pence", "Pence"),
                        ("amount_display", "Amount"),
                    ],
                ),
            ],
        )
    )
    return sections


def register_callbacks(app) -> None:
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Output("store-auth-rev", "data", allow_duplicate=True),
        Input("admin-sign-out", "n_clicks"),
        State("store-auth-rev", "data"),
        prevent_initial_call=True,
    )
    def sign_out(n_clicks, rev):
        from dash.exceptions import PreventUpdate

        if not n_clicks:
            raise PreventUpdate
        dash_api.logout(session.get("api_sid"))
        session.clear()
        return "/signin", (rev or 0) + 1

    @app.callback(
        Output("admin-feedback", "children"),
        Input("admin-create", "n_clicks"),
        Input("admin-join", "n_clicks"),
        State("admin-circle-name", "value"),
        State("admin-join-id", "value"),
        prevent_initial_call=True,
    )
    def update_admin_circles(create_clicks, join_clicks, name, circle_id):
        from dash import ctx
        from dash.exceptions import PreventUpdate

        if not create_clicks and not join_clicks:
            raise PreventUpdate
        sid = session.get("api_sid")
        if not isinstance(sid, str) or dash_api.VAULT.get(sid) is None:
            return NEED_API
        trigger = ctx.triggered_id
        if trigger == "admin-create":
            cleaned = name.strip() if isinstance(name, str) else ""
            if not cleaned:
                return "Enter a circle name."
            status, payload = dash_api.request(
                "POST",
                "/api/v1/circles",
                json_body={"name": cleaned},
                sid=sid,
            )
            if status != 201:
                return dash_api.safe_detail(payload, "The circle was not created.")
            dash_api.sync_session_force()
            return f"Created {cleaned}."
        if trigger == "admin-join":
            raw = circle_id.strip() if isinstance(circle_id, str) else ""
            if not raw.isdigit():
                return "Enter a circle id."
            status, payload = dash_api.request("POST", f"/api/v1/circles/{int(raw)}/join", sid=sid)
            if status not in {200, 201}:
                return dash_api.safe_detail(payload, "The join was not accepted.")
            dash_api.sync_session_force()
            return f"Joined circle {int(raw)}."
        return ""
