from dash import dcc, html

from .components import icon, pill
from .payout_access import resolve_ajo, visible_ajo_names


BRUM_MEMBERS = [
    {"u": "abel_o", "n": "Abel O.", "pos": 3, "score": 824, "status": "paid", "av": "#B88A2A", "initials": "AO"},
    {"u": "kemi_a", "n": "Kemi A.", "pos": 4, "score": 791, "status": "paid", "av": "#B0392E", "initials": "KA"},
    {"u": "chidi_m", "n": "Chidi M.", "pos": 5, "score": 765, "status": "paid", "av": "#4A89B0", "initials": "CM"},
    {"u": "tola_b", "n": "Tola B.", "pos": 6, "score": 812, "status": "paid", "av": "#7C5AA8", "initials": "TB"},
    {"u": "nneka_o", "n": "Nneka O.", "pos": 7, "score": 743, "status": "paid", "av": "#2F7A4C", "initials": "NO"},
    {"u": "daniel_k", "n": "Daniel K.", "pos": 8, "score": 698, "status": "grace", "av": "#7F6BB3", "initials": "DK"},
]

SISTER_MEMBERS = [
    {"u": "amina_t", "n": "Amina T.", "pos": 2, "score": 802, "status": "paid", "av": "#B88A2A", "initials": "AT"},
    {"u": "ngozi_p", "n": "Ngozi P.", "pos": 3, "score": 776, "status": "paid", "av": "#B0392E", "initials": "NP"},
    {"u": "funke_n", "n": "Funke N.", "pos": 4, "score": 741, "status": "grace", "av": "#2F7A4C", "initials": "FN"},
]

TRACKERS = {
    "Brum Builders": {
        "summary": "Month 3 of 10 · rotation suggests Abel O.",
        "amount": "£5,000",
        "contrib": "£500",
        "in_count": "9 of 10 in",
        "cover": "£500 auto-loan",
        "cover_detail": "£500 (Daniel K.)",
        "releases": "Releases Apr 28",
        "default": "kemi_a",
        "members": BRUM_MEMBERS,
        "history": [
            ("Feb 2026", "@ola_t", "AJO-BBM-01-0228"),
            ("Mar 2026", "@ebuka_n", "AJO-BBM-02-0328"),
        ],
    },
    "Sister Circle Ajo": {
        "summary": "Month 2 of 8 · rotation suggests Amina T.",
        "amount": "£2,000",
        "contrib": "£250",
        "in_count": "7 of 8 in",
        "cover": "£250 auto-loan",
        "cover_detail": "£250 (Funke N.)",
        "releases": "Releases May 12",
        "default": "amina_t",
        "members": SISTER_MEMBERS,
        "history": [
            ("Mar 2026", "@yewande_f", "AJO-SCA-01-0312"),
        ],
    },
}


def _score_style(score):
    if score >= 780:
        return "good"
    if score >= 700:
        return "brand"
    return "gold"


def _member(tracker, selected_user):
    members = tracker["members"]
    return next((item for item in members if item["u"] == selected_user), members[0])


def _contrib_pill(tracker, status):
    return pill(tracker["contrib"], "good") if status == "paid" else pill("Grace", "gold")


def queue_table(selected_user, tracker):
    amount = tracker["amount"]
    return html.Table(
        className="t payouts-t",
        children=[
            html.Thead(html.Tr([html.Th(""), html.Th("#"), html.Th("Member"), html.Th("Credit"), html.Th("Contribution"), html.Th("Receives", style={"textAlign": "right"})])),
            html.Tbody(
                [
                    html.Tr(
                        id={"type": "payout-select-row", "u": member["u"]},
                        n_clicks=0,
                        className=f"payout-row {'sel' if member['u'] == selected_user else ''}",
                        children=[
                            html.Td(
                                html.Button(
                                    html.Span(className=f"payout-radio {'on' if member['u'] == selected_user else ''}"),
                                    id={"type": "payout-select", "u": member["u"]},
                                    n_clicks=0,
                                    className="payout-radio-btn",
                                )
                            ),
                            html.Td(f"#{member['pos']}", className="mono muted"),
                            html.Td(
                                html.Div(
                                    className="member-row",
                                    children=[
                                        html.Div(member["initials"], className="mav", style={"background": member["av"]}),
                                        html.Div([html.Div(f"@{member['u']}", className="member-tag"), html.Div(member["n"], className="meta-sub")]),
                                    ],
                                )
                            ),
                            html.Td(pill(str(member["score"]), _score_style(member["score"]))),
                            html.Td(_contrib_pill(tracker, member["status"])),
                            html.Td(amount, className="mono", style={"textAlign": "right"}),
                        ],
                    )
                    for member in tracker["members"]
                ]
            ),
        ],
    )


def detail_card(selected_user, role, tracker):
    member = _member(tracker, selected_user)
    band = "Excellent" if member["score"] >= 780 else "Good" if member["score"] >= 700 else "Fair"
    return [
        html.Div(
            className="payout-head",
            children=[
                html.Div(member["initials"], className="payout-av", style={"background": member["av"]}),
                html.Div(f"@{member['u']}", className="recipient"),
                html.Div(f"{member['n']} · position #{member['pos']}", className="muted"),
                html.Div(tracker["amount"], className="mono recipient-val"),
                html.Div(tracker["releases"], className="muted"),
            ],
        ),
        html.Div(className="hr"),
        html.Div(
            className="payout-meta",
            children=[
                html.Div([html.Div("Method", className="pmeta-k"), html.Div("Virtual account · FPS", className="pmeta-v")], className="pmeta-row"),
                html.Div([html.Div("KYC", className="pmeta-k"), pill("Verified", "good")], className="pmeta-row"),
                html.Div([html.Div("Credit band", className="pmeta-k"), pill(band, _score_style(member["score"]))], className="pmeta-row"),
                html.Div([html.Div("Delay Cover cover", className="pmeta-k"), html.Div(tracker["cover_detail"], className="pmeta-v mono")], className="pmeta-row"),
                html.Div([html.Div("Fee", className="pmeta-k"), html.Div("Free", className="pmeta-v fee-free")], className="pmeta-row"),
            ],
        ),
        html.Div(className="row-note", children=[icon("lock"), html.Span("Bank details hidden. Funds route through virtual account.")]),
        html.Button(f"Hold to release {tracker['amount']}", className="btn btn-primary btn-lg wide") if role == "admin" else html.Div("Admin action", className="muted payout-admin"),
        html.Button("Reschedule", className="btn btn-ghost btn-sm wide") if role == "admin" else None,
    ]


def history_card(tracker):
    amount = tracker["amount"]
    return html.Div(
        className="card",
        children=[
            html.Div("Payout history", className="h2"),
            html.Div("Immutable audit log", className="sub mini"),
            html.Table(
                className="t",
                children=[
                    html.Thead(html.Tr([html.Th("Month"), html.Th("Recipient"), html.Th("Method"), html.Th("Reference"), html.Th("Amount", style={"textAlign": "right"})])),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(month, className="muted"),
                                    html.Td(recipient),
                                    html.Td(pill("Virtual acct")),
                                    html.Td(reference, className="mono muted"),
                                    html.Td(amount, className="mono", style={"textAlign": "right"}),
                                ]
                            )
                            for month, recipient, reference in tracker["history"]
                        ]
                    ),
                ],
            ),
        ],
    )


def subtitle_for(ajo_name, tracker):
    summary = tracker["summary"] if tracker else "No payout rows recorded yet"
    return f"{ajo_name} · {summary} · only the creator of this Ajo can see this tracker"


def empty_tracker(ajo_name):
    return html.Div(
        className="card",
        children=[
            html.Div("Payouts Tracker", className="h2"),
            html.Div(f"No payout rows are recorded for {ajo_name} yet.", className="sub"),
        ],
    )


def tracker_body(ajo_name, selected_user, role):
    """Queue, history, and detail for one Ajo. Unknown names get no other Ajo's rows."""
    tracker = TRACKERS.get(ajo_name)
    if tracker is None:
        return empty_tracker(ajo_name), html.Div()
    selected_user = selected_user if any(member["u"] == selected_user for member in tracker["members"]) else tracker["default"]
    queue = html.Div(
        className="card",
        children=[
            html.Div(
                className="between",
                children=[
                    html.Div(
                        [
                            html.Div(f"Rotation queue · {ajo_name}", className="h2"),
                            html.Div("Order fixed by join-date · swaps require unanimous consent", className="sub mini"),
                        ]
                    ),
                    html.Div(className="row-btns", children=[pill(tracker["in_count"], "good"), pill(tracker["cover"], "gold")]),
                ],
            ),
            queue_table(selected_user, tracker),
        ],
    )
    side = html.Div(className="card payout-side", children=detail_card(selected_user, role, tracker))
    return html.Div(className="stack", children=[queue, history_card(tracker)]), side


def ajo_switch(names, selected):
    return html.Div(
        className="tabs",
        id="payout-ajo-switch",
        children=[
            html.Button(
                name,
                id={"type": "payout-ajo-btn", "name": name},
                n_clicks=0,
                className="on" if name == selected else "",
            )
            for name in names
        ],
    )


def layout(role, username=None):
    names = visible_ajo_names(username, role)
    if not names:
        return html.Div(id="payouts-tracker-denied")
    selected = resolve_ajo(names[0], username, role)
    tracker = TRACKERS.get(selected)
    selected_user = tracker["default"] if tracker else None
    return html.Div(
        className="stack",
        id="payouts-tracker",
        children=[
            dcc.Store(id="payout-selected", data=selected_user),
            dcc.Store(id="payout-ajo", data=selected),
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Payouts Tracker"),
                            html.Div(subtitle_for(selected, tracker), id="payout-tracker-sub", className="sub"),
                        ]
                    ),
                ],
            ),
            ajo_switch(names, selected),
            html.Div(
                className="g3-1",
                id="payout-tracker-body",
                children=list(tracker_body(selected, selected_user, role)),
            ),
        ],
    )
