from dash import html

from .components import icon


def layout():
    benefits = [
        ("shield", "Credit-checked members", "Global liability + UK Affordability"),
        ("bolt", "My Cover", "Get paid on time even if one person is late"),
        ("eyeoff", "Usernames only", "No bank details ever shown to members"),
        ("arrup", "Early payout", "For when you need your money earlier than your due month"),
    ]

    return html.Div(
        className="auth-screen",
        children=[
            html.Div(
                className="auth-top-row",
                children=[
                    html.Div(
                        className="auth-brand-row",
                        children=[html.Div("a", className="brandmark"), html.Div("AjoCredit", className="auth-brand-name")],
                    ),
                    html.Div("Skip demo ->", className="auth-skip-demo"),
                ],
            ),
            html.Div("COMMUNITY SAVINGS, DONE RIGHT", className="auth-kicker"),
            html.H1(
                [
                    "Save together, ",
                    html.Span("get paid", className="auth-serif"),
                    " in turn.",
                ],
                className="auth-title",
            ),
            html.P(
                "Already coordinating your Ajo or Esusu offline or on WhatsApp? "
                "Move it to our FinTech platform - or start a new one - and get the following benefits!",
                className="auth-copy",
            ),
            html.Div(
                className="auth-benefits",
                children=[
                    html.Div(
                        className="auth-benefit",
                        children=[
                            html.Div(icon(icon_name), className="auth-benefit-icon"),
                            html.Div(
                                [
                                    html.Div(title, className="auth-benefit-title"),
                                    html.Div(sub, className="auth-benefit-sub"),
                                ]
                            ),
                        ],
                    )
                    for icon_name, title, sub in benefits
                ],
            ),
            html.Button("Get started", id={"type": "auth-btn", "action": "home-get-started"}, n_clicks=0, className="auth-primary-btn"),
            html.Button("I have an account", id={"type": "auth-btn", "action": "home-have-account"}, n_clicks=0, className="auth-link-btn"),
        ],
    )
