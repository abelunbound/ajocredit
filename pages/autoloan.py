from dash import html

from .components import icon, pill


def layout():
    return html.Div(
        className="stack",
        children=[
            html.Div(className="page-head", children=[html.Div([html.H1("Auto-loan"), html.Div("Interest-free safety net · circles never miss a payout", className="sub")]), pill("Active on 1 circle", "good")]),
            html.Div(
                className="card al-hero al-hero-lg",
                children=[
                    html.Div(
                        className="al-title",
                        children=[
                            "Payouts go out on time — ",
                            html.Span("even when someone's late.", className="al-serif"),
                        ],
                    ),
                    html.Div(
                        "If a member misses their contribution, AjoCredit fronts the amount as a 0% loan. "
                        "The recipient gets their full pot on schedule. The late member repays automatically "
                        "over 60 days — no fees, no default on their credit file.",
                        className="al-copy",
                    ),
                ],
            ),
            html.Div(
                className="g4 al-kpis",
                children=[
                    html.Div([html.Div("Coverage per cycle", className="kl"), html.Div("£500", className="kv"), html.Div("1 missed contribution", className="kd")], className="kpi"),
                    html.Div([html.Div("Your APR", className="kl"), html.Div("0.0%", className="kv"), html.Div("Always interest-free", className="kd")], className="kpi"),
                    html.Div([html.Div("Repay window", className="kl"), html.Div("60 days", className="kv"), html.Div("Automatic · from contributions", className="kd")], className="kpi"),
                    html.Div([html.Div("Used this cycle", className="kl"), html.Div("£500 / £500", className="kv"), html.Div("Dani K. · month 3", className="kd")], className="kpi"),
                ],
            ),
            html.Div(
                className="g2 al-panels",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            html.Div("How it works", className="h2"),
                            html.Div(
                                className="al-steps",
                                children=[
                                    html.Div(className="al-step", children=[html.Div("1", className="al-step-no"), html.Div([html.Div("Member misses a contribution", className="al-step-title"), html.Div("Grace period gives them 48 hours. An SMS + push nudge goes out.", className="al-step-sub")])]),
                                    html.Div(className="al-step", children=[html.Div("2", className="al-step-no"), html.Div([html.Div("AjoCredit steps in", className="al-step-title"), html.Div("We front the missing amount — 0% interest, no fees, no paperwork.", className="al-step-sub")])]),
                                    html.Div(className="al-step", children=[html.Div("3", className="al-step-no"), html.Div([html.Div("Recipient gets the full pot", className="al-step-title"), html.Div("On the scheduled date. No delay.", className="al-step-sub")])]),
                                    html.Div(className="al-step", children=[html.Div("4", className="al-step-no"), html.Div([html.Div("Late member repays", className="al-step-title"), html.Div("Automatic debit over 60 days from next contributions.", className="al-step-sub")])]),
                                    html.Div(className="al-step", children=[html.Div("5", className="al-step-no"), html.Div([html.Div("Credit file stays clean", className="al-step-title"), html.Div("Auto-loan is not a default — it doesn't show on credit report.", className="al-step-sub")])]),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            html.Div("This cycle's activity", className="h2"),
                            html.Div(
                                className="al-activity",
                                children=[
                                    html.Div(
                                        className="between",
                                        children=[
                                            html.Div(className="member-row", children=[html.Div("DK", className="mav", style={"background": "#7F6BB3"}), html.Div([html.Div("@daniel_k · month 3", className="member-tag"), html.Div("Covered Apr 1 · repay by Jun 1", className="meta-sub")])]),
                                            html.Div("£500", className="mono"),
                                        ],
                                    ),
                                    html.Div(className="bar", children=[html.Span(style={"width": "8%"})]),
                                    html.Div(className="between al-activity-meta", children=[html.Span("£40 repaid"), html.Span("£460 remaining")]),
                                ],
                            ),
                            html.Div(className="hr"),
                            html.Div("Auto-loan is funded by a regulated credit facility — not other members' money. Your circle is never at risk.", className="al-foot"),
                        ],
                    ),
                ],
            ),
        ],
    )
