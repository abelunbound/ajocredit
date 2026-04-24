from dash import dcc, html

from .components import icon


def layout():
    return html.Div(
        className="auth-screen signin-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "signin-back"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div(
                        className="auth-brand-row",
                        children=[html.Div("a", className="brandmark"), html.Div("AjoCredit", className="auth-brand-name")],
                    ),
                ],
            ),
            html.Div("WELCOME BACK", className="auth-kicker"),
            html.H1(["Sign in to ", html.Span("your account", className="auth-serif")], className="auth-title"),
            html.P("Your circles, contributions and payouts are waiting.", className="auth-copy"),
            html.Div("Email address", className="auth-label"),
            dcc.Input(type="email", value="kemi@example.com", className="auth-input"),
            html.Div("Password", className="auth-label"),
            html.Div(
                className="auth-pass-wrap",
                children=[
                    dcc.Input(type="password", value="password", className="auth-input auth-input-pass"),
                    html.Span(icon("eyeoff"), className="auth-pass-icon"),
                ],
            ),
            html.Button("Forgot password?", className="auth-forgot"),
            html.Button(
                ["Sign in ", html.I(className="bi bi-arrow-right")],
                id={"type": "auth-btn", "action": "signin-submit"},
                n_clicks=0,
                className="auth-primary-btn",
            ),
            html.Div(className="auth-divider", children=[html.Span(), html.Div("or"), html.Span()]),
            html.Button(
                [html.I(className="bi bi-google auth-google"), "Continue with Google"],
                className="auth-google-btn",
            ),
            html.Div(
                className="auth-bottom-row",
                children=[
                    html.Span("Don't have an account?"),
                    html.Button(
                        "Get started",
                        id={"type": "auth-btn", "action": "signin-get-started"},
                        n_clicks=0,
                        className="auth-inline-btn",
                    ),
                ],
            ),
        ],
    )
