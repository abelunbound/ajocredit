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
            html.Br(),
            html.H1(["Sign in to ", html.Span("your account", className="auth-serif")], className="auth-title"),
            html.Div(
                className="signin-field",
                **{"aria-label": "Username"},
                children=[
                    dcc.Input(
                        id="signin-username",
                        type="text",
                        value="",
                        placeholder="Username",
                        autoComplete="username",
                        className="auth-input",
                    ),
                ],
            ),
            html.Div(
                className="signin-field",
                **{"aria-label": "Password"},
                children=[
                    html.Div(
                        className="auth-pass-wrap",
                        children=[
                            dcc.Input(
                                id="signin-password",
                                type="password",
                                value="",
                                placeholder="Password",
                                autoComplete="current-password",
                                className="auth-input auth-input-pass",
                            ),
                            html.Span(icon("eyeoff"), className="auth-pass-icon"),
                        ],
                    ),
                ],
            ),
            html.Div(id="signin-notice", className="auth-hint"),
            html.Div(id="signin-error", className="auth-error"),
            html.Div("Local test accounts only.", className="auth-hint"),
            html.Button(
                "Forgot password?",
                id="forgot-open",
                n_clicks=0,
                type="button",
                className="auth-forgot",
            ),
            html.Div(
                id="forgot-panel",
                className="forgot-panel",
                style={"display": "none"},
                children=[
                    dcc.Input(
                        id="forgot-email",
                        type="email",
                        value="",
                        placeholder="Email",
                        autoComplete="email",
                        className="auth-input",
                    ),
                    html.Button(
                        "Send reset link",
                        id="forgot-submit",
                        n_clicks=0,
                        type="button",
                        className="auth-primary-btn",
                    ),
                    html.Div(id="forgot-message", className="auth-hint"),
                ],
            ),
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
