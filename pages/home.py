from dash import html

from .components import icon

# Get paid on time even if one person is late or defaults
# Guaranteed payout. Even if 1 member is late or defaults.

def layout():
    benefits = [
        ("bolt", "Delay Cover", "Get paid even when a member's late or defaults."),
        ("arrup", "Early payout", "Get your ajo months before your turn"),
        ("shield", "Safety - credit-checked members", "Global credit, affordability & liability checks"),        
        ("eyeoff", "Privacy", "Other members never see your bank details"),
    ]

    return html.Div(
        className="auth-screen home-screen",
        children=[
            html.Div(
                className="auth-top-row",
                children=[
                    html.Div(
                        className="auth-brand-row",
                        children=[html.Div("a", className="brandmark"), html.Div("AjoFinance", className="auth-brand-name")],
                    ),
                    # html.Div("Skip demo ->", className="auth-skip-demo"),
                ],
            ),
            html.Br(),
            html.H1(
                [
                    "Social capital. ",
                    html.Span("digitised.", className="auth-serif"),
                    # " digitised.",
                ],
                className="auth-title",
            ),
            html.P(
                "Already coordinating your Ajo, Esusu or Pardna informally? "
                "Move it to AjoFinance - and get these benefits!",
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
