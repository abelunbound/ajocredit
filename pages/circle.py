from dash import html

from .components import icon, pill
from .data import CIRCLE


def layout(_role):
    timeline = [
        ("ola_t", "Ola T.", 1, "received", "OT", "#4F6AA3"),
        ("ebuka_n", "Ebuka N.", 2, "received", "EN", "#4E5FA8"),
        ("abel_o", "Abel O.", 3, "now", "AO", "#B88A2A"),
        ("kemi_a", "Kemi A.", 4, "upcoming-me", "KA", "#B0392E"),
        ("chidi_m", "Chidi M.", 5, "upcoming", "CM", "#4A89B0"),
        ("tola_b", "Tola B.", 6, "upcoming", "TB", "#7C5AA8"),
        ("nneka_o", "Nneka O.", 7, "upcoming", "NO", "#2F7A4C"),
        ("daniel_k", "Daniel K.", 8, "upcoming", "DK", "#7F6BB3"),
        ("femi_r", "Femi R.", 9, "upcoming", "FR", "#2A6E89"),
        ("aisha_w", "Aisha W.", 10, "upcoming", "AW", "#2F7A4C"),
    ]

    return html.Div(
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.Div([html.H1(CIRCLE["name"]), pill("Verified", "good"), pill("Month 3/10", "brand")], className="row-head"),
                            html.Div(f"{CIRCLE['city']}  ·  £{CIRCLE['amount']} x {CIRCLE['size']} monthly  ·  pot £{CIRCLE['pot']:,}", className="sub"),
                        ]
                    )
                ],
            ),
            html.Div(
                className="g3-1",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            html.Div("Rotation timeline", className="h2"),
                            html.Div(
                                className="circle-timeline",
                                children=[
                                    html.Div(
                                        className=f"tl-item {state}",
                                        children=[
                                            html.Span(className="tl-dot"),
                                            html.Div(
                                                className="tl-row",
                                                children=[
                                                    html.Div(initials, className="tl-av", style={"background": color}),
                                                    html.Div(
                                                        className="tl-main",
                                                        children=[
                                                            html.Div(
                                                                [
                                                                    html.Span(name),
                                                                    html.Span("you", className="pill brand tl-you") if state == "upcoming-me" else None,
                                                                ],
                                                                className="tl-name",
                                                            ),
                                                            html.Div(
                                                                f"Month {pos} · {'received' if state == 'received' else CIRCLE['next_date'] if state == 'now' else 'upcoming'}",
                                                                className="tl-sub",
                                                            ),
                                                        ],
                                                    ),
                                                    html.Div("£5,000", className="mono tl-amt"),
                                                ],
                                            ),
                                        ],
                                    )
                                    for username, name, pos, state, initials, color in timeline
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="stack",
                        children=[
                            html.Div(
                                className="card",
                                children=[
                                    html.Div("Circle rules", className="h2"),
                                    html.Div(className="rules-list", children=[
                                        html.Div([html.Div("Contribution", className="label-xs"), html.Div(f"£{CIRCLE['amount']} monthly · autopay 1st", className="rule-val")], className="rule-item"),
                                        html.Div([html.Div("Rotation", className="label-xs"), html.Div("Fixed by join-date", className="rule-val")], className="rule-item"),
                                        html.Div([html.Div("Late grace", className="label-xs"), html.Div("48 hours", className="rule-val")], className="rule-item"),
                                        html.Div([html.Div("Exit", className="label-xs"), html.Div("Only after payout month", className="rule-val")], className="rule-item"),
                                        html.Div([html.Div("Min credit score", className="label-xs"), html.Div("680", className="rule-val")], className="rule-item"),
                                    ]),
                                ],
                            ),
                            html.Div(
                                className="card",
                                children=[
                                    html.Div("Contribution progress", className="h2"),
                                    html.Div(className="between prog-meta", children=[html.Span("9 of 10 collected"), html.Span("£4,500 / £5,000", className="mono")]),
                                    html.Div(className="bar prog-bar", children=[html.Span(style={"width": "90%"})]),
                                    html.Div(className="prog-note", children=[icon("bolt"), html.Span("Auto-loan covering £500 for @daniel_k")]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
