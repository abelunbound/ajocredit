from dash import html

from .components import icon, pill
from .data import TXNS


def layout(role):
    return html.Div(
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div([html.H1("Good afternoon, Kemi."), html.Div("Month 3 of 10 · Abel O. receives £5,000 on Apr 28", className="sub")]),
                    html.Div(className="row-btns head-actions", children=[html.Button([icon("dl"), "Export"], className="btn btn-ghost"), html.Button("Release payout" if role == "admin" else "Pay this month", className="btn btn-primary")]),
                ],
            ),
            html.Div(
                className="g4",
                children=[
                    html.Div([html.Div("This month's pot", className="kl"), html.Div("£5,000", className="kv"), html.Div("9 of 10 paid", className="kd")], className="kpi"),
                    html.Div([html.Div("Your next contribution", className="kl"), html.Div("£500", className="kv"), html.Div("Autopay · Apr 28", className="kd")], className="kpi"),
                    html.Div([html.Div("Your UK score", className="kl"), html.Div("791", className="kv"), html.Div("↑ +34 in 12 months", className="kd up")], className="kpi"),
                    html.Div([html.Div("On-time rate", className="kl"), html.Div("100%", className="kv"), html.Div("0 defaults across 2 circles", className="kd")], className="kpi"),
                ],
            ),
            html.Div(
                className="dash-board",
                children=[
                    html.Div(
                        className="dash-row dash-row-1",
                        children=[
                            html.Div(
                                className="card hero-pot",
                                children=[
                                    html.Div(className="between hero-top", children=[html.Span([html.Span(className="pd"), "Active · month 3/10"], className="pill pill-hero"), html.Span("Brum Builders · monthly", className="hero-minor")]),
                                    html.Div(
                                        className="hero-grid",
                                        children=[
                                            html.Div([html.Div("Total pot this month", className="label-xs hero-label"), html.Div("£5,000", className="hero-value mono"), html.Div("Goes to Abel O. on Apr 28 · auto-released", className="hero-sub")]),
                                            html.Div(
                                                className="hero-side",
                                                children=[
                                                    html.Div("Contributions collected", className="label-xs hero-label"),
                                                    html.Div(className="bar hero-bar", children=[html.Span(style={"width": "90%"})]),
                                                    html.Div(className="between hero-bar-meta", children=[html.Span("9 of 10 · £4,500"), html.Span("£500 auto-loan")]),
                                                    html.Div(className="row-btns hero-btns", children=[html.Button("Review & release" if role == "admin" else "Pay this month", className="btn btn-sm btn-white"), html.Button("Circle detail", className="btn btn-sm btn-glass")]),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card dash-ad",
                                children=[
                                    html.Div("Sponsored Ad", className="dash-ad-kicker"),
                                    html.Div(
                                        className="dash-bank-card",
                                        children=[
                                            html.Div(className="dash-bank-card-top", children=[
                                                html.Div("AjoCard", className="dash-bank-brand"),
                                                html.Div("Virtual debit", className="dash-bank-chip"),
                                            ]),
                                            html.Div("••••  ••••  ••••  4281", className="dash-bank-pan mono"),
                                            html.Div(className="dash-bank-card-foot", children=[
                                                html.Div([html.Div("Cardholder", className="dash-bank-mini"), html.Div("Kemi A.", className="dash-bank-name")]),
                                                html.Div([html.Div("Exp", className="dash-bank-mini"), html.Div("08/29", className="dash-bank-name")]),
                                            ]),
                                        ],
                                    ),
                                    html.Div(
                                        className="dash-ad-row",
                                        children=[
                                            html.Div("Payouts on your card", className="h2 dash-ad-title"),
                                            html.Button("See product →", className="btn btn-sm btn-ghost dash-ad-cta"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="dash-row dash-row-2",
                        children=[
                            html.Div(
                                className="card dash-equal",
                                children=[
                                    html.Div(className="card-hd", children=[html.Div("Recent activity", className="h2"), html.Button("All transactions", className="btn btn-sm btn-ghost")]),
                                    html.Table(
                                        className="t",
                                        children=[
                                            html.Thead(html.Tr([html.Th("Transaction"), html.Th("Date"), html.Th("Status"), html.Th("Amount", style={"textAlign": "right"})])),
                                            html.Tbody([html.Tr([html.Td(t["label"]), html.Td(t["date"], className="muted"), html.Td(pill(t["status"], "good" if t["status"] == "Settled" else "gold")), html.Td(t["amount"], className="mono", style={"textAlign": "right", "fontWeight": "600"})]) for t in TXNS]),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="dash-side",
                                children=[
                                    html.Div(className="card al-hero dash-equal", children=[html.Div("Delay Cover · on", className="label-xs white"), html.Div("Payouts on time — every time.", className="h2 white"), html.P("0% interest cover if a member is late. Repay over 60 days automatically.", className="white-sub"), html.Div(className="between hero-bar-meta", children=[html.Span("Used this cycle"), html.Span("£500 / £500", className="mono")]), html.Div(className="bar hero-bar", children=[html.Span(style={"width": "100%"})]), html.Button("How it works →", className="btn btn-sm btn-glass")]),
                                    html.Div(className="card dash-equal", children=[html.Div("Circle safety", className="h2"), html.Div(className="safe-row", children=[html.Div(icon("shield"), className="safe-ic"), html.Div([html.Div("All 10 members credit-checked", className="safe-title"), html.Div("Min score 680 · UK + origin", className="safe-sub")])]), html.Div(className="safe-row", children=[html.Div(icon("bolt"), className="safe-ic"), html.Div([html.Div("Delay Cover backstop armed", className="safe-title"), html.Div("Up to £500 covered", className="safe-sub")])]), html.Div(className="safe-row", children=[html.Div(icon("eyeoff"), className="safe-ic"), html.Div([html.Div("Usernames only", className="safe-title"), html.Div("No bank details shared", className="safe-sub")])]), html.Div(className="safe-row", children=[html.Div(icon("lock"), className="safe-ic"), html.Div([html.Div("Regulated account", className="safe-title"), html.Div("FCA e-money safeguarded", className="safe-sub")])])]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
