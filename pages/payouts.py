from dash import dcc, html

from .components import icon, pill


PAYOUT_MEMBERS = [
    {"u": "abel_o", "n": "Abel O.", "pos": 3, "score": 824, "status": "paid", "av": "#B88A2A", "initials": "AO"},
    {"u": "kemi_a", "n": "Kemi A.", "pos": 4, "score": 791, "status": "paid", "av": "#B0392E", "initials": "KA"},
    {"u": "chidi_m", "n": "Chidi M.", "pos": 5, "score": 765, "status": "paid", "av": "#4A89B0", "initials": "CM"},
    {"u": "tola_b", "n": "Tola B.", "pos": 6, "score": 812, "status": "paid", "av": "#7C5AA8", "initials": "TB"},
    {"u": "nneka_o", "n": "Nneka O.", "pos": 7, "score": 743, "status": "paid", "av": "#2F7A4C", "initials": "NO"},
    {"u": "daniel_k", "n": "Daniel K.", "pos": 8, "score": 698, "status": "grace", "av": "#7F6BB3", "initials": "DK"},
]


def _score_style(score):
    if score >= 780:
        return "good"
    if score >= 700:
        return "brand"
    return "gold"


def _contrib_pill(status):
    return pill("£500", "good") if status == "paid" else pill("Grace", "gold")


def queue_table(selected_user):
    return html.Table(
        className="t payouts-t",
        children=[
            html.Thead(html.Tr([html.Th(""), html.Th("#"), html.Th("Member"), html.Th("Credit"), html.Th("Contribution"), html.Th("Receives", style={"textAlign": "right"})])),
            html.Tbody(
                [
                    html.Tr(
                        id={"type": "payout-select-row", "u": m["u"]},
                        n_clicks=0,
                        className=f"payout-row {'sel' if m['u'] == selected_user else ''}",
                        children=[
                            html.Td(
                                html.Button(
                                    html.Span(className=f"payout-radio {'on' if m['u'] == selected_user else ''}"),
                                    id={"type": "payout-select", "u": m["u"]},
                                    n_clicks=0,
                                    className="payout-radio-btn",
                                )
                            ),
                            html.Td(f"#{m['pos']}", className="mono muted"),
                            html.Td(
                                html.Div(
                                    className="member-row",
                                    children=[
                                        html.Div(m["initials"], className="mav", style={"background": m["av"]}),
                                        html.Div([html.Div(f"@{m['u']}", className="member-tag"), html.Div(m["n"], className="meta-sub")]),
                                    ],
                                )
                            ),
                            html.Td(pill(str(m["score"]), _score_style(m["score"]))),
                            html.Td(_contrib_pill(m["status"])),
                            html.Td("£5,000", className="mono", style={"textAlign": "right"}),
                        ],
                    )
                    for m in PAYOUT_MEMBERS
                ]
            ),
        ],
    )


def detail_card(selected_user, role):
    m = next((x for x in PAYOUT_MEMBERS if x["u"] == selected_user), PAYOUT_MEMBERS[0])
    return [
        html.Div(
            className="payout-head",
            children=[
                html.Div(m["initials"], className="payout-av", style={"background": m["av"]}),
                html.Div(f"@{m['u']}", className="recipient"),
                html.Div(f"{m['n']} · position #{m['pos']}", className="muted"),
                html.Div("£5,000", className="mono recipient-val"),
                html.Div("Releases Apr 28", className="muted"),
            ],
        ),
        html.Div(className="hr"),
        html.Div(
            className="payout-meta",
            children=[
                html.Div([html.Div("Method", className="pmeta-k"), html.Div("Virtual account · FPS", className="pmeta-v")], className="pmeta-row"),
                html.Div([html.Div("KYC", className="pmeta-k"), pill("Verified", "good")], className="pmeta-row"),
                html.Div([html.Div("Credit band", className="pmeta-k"), pill("Excellent" if m["score"] >= 780 else "Good" if m["score"] >= 700 else "Fair", _score_style(m["score"]))], className="pmeta-row"),
                html.Div([html.Div("Auto-loan cover", className="pmeta-k"), html.Div("£500 (Daniel K.)", className="pmeta-v mono")], className="pmeta-row"),
                html.Div([html.Div("Fee", className="pmeta-k"), html.Div("Free", className="pmeta-v fee-free")], className="pmeta-row"),
            ],
        ),
        html.Div(className="row-note", children=[icon("lock"), html.Span("Bank details hidden. Funds route through virtual account.")]),
        html.Button("Hold to release £5,000", className="btn btn-primary btn-lg wide") if role == "admin" else html.Div("Admin action · switch role in sidebar", className="muted payout-admin"),
        html.Button("Reschedule", className="btn btn-ghost btn-sm wide") if role == "admin" else None,
    ]


def layout(role):
    selected_default = "kemi_a"
    return html.Div(
        className="stack",
        children=[
            dcc.Store(id="payout-selected", data=selected_default),
            html.Div(className="page-head", children=[html.Div([html.H1("Release payout"), html.Div("Month 3 of 10 · rotation suggests Abel O. · £5,000", className="sub")]), html.Div(className="row-btns", children=[pill("9 of 10 in", "good"), pill("£500 auto-loan", "gold")])]),
            html.Div(
                className="g3-1",
                children=[
                    html.Div(
                        className="stack",
                        children=[
                            html.Div(className="card", children=[html.Div("Rotation queue", className="h2"), html.Div("Order fixed by join-date · swaps require unanimous consent", className="sub mini"), html.Div(id="payout-queue-wrap", children=queue_table(selected_default))]),
                            html.Div(className="card", children=[html.Div("Payout history", className="h2"), html.Div("Immutable audit log", className="sub mini"), html.Table(className="t", children=[html.Thead(html.Tr([html.Th("Month"), html.Th("Recipient"), html.Th("Method"), html.Th("Reference"), html.Th("Amount", style={"textAlign": "right"})])), html.Tbody([html.Tr([html.Td("Feb 2026", className="muted"), html.Td("@ola_t"), html.Td(pill("Virtual acct")), html.Td("AJO-BBM-01-0228", className="mono muted"), html.Td("£5,000", className="mono", style={"textAlign": "right"})]), html.Tr([html.Td("Mar 2026", className="muted"), html.Td("@ebuka_n"), html.Td(pill("Virtual acct")), html.Td("AJO-BBM-02-0328", className="mono muted"), html.Td("£5,000", className="mono", style={"textAlign": "right"})])])])]),
                        ],
                    ),
                    html.Div(className="card payout-side", id="payout-detail-card", children=detail_card(selected_default, role)),
                ],
            ),
        ],
    )
