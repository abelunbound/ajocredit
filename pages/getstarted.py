from dash import dcc, html

from .components import icon

SIGNUP_NOTICE = (
    "Registration on this screen does not create a server account. "
    "Sign in with a local test account."
)
SIGNUP_INCOMPLETE = "Enter first name, last name, email, phone, and both password fields."


def signup_problem(fields):
    """Return a registration error, or an empty string when the form is complete.

    Passwords are checked for a match only. They are not stored.
    """
    fields = fields or {}
    first = fields.get("first")
    last = fields.get("last")
    email = fields.get("email")
    phone = fields.get("phone")
    password = fields.get("password")
    confirm = fields.get("confirm")
    values = (first, last, email, phone, password, confirm)
    if not all(isinstance(value, str) and value.strip() for value in values):
        return SIGNUP_INCOMPLETE
    address = email.strip()
    domain = address.split("@")[-1] if "@" in address else ""
    if address.startswith("@") or "@" not in address or "." not in domain:
        return "Enter a valid email address."
    if password != confirm:
        return "Passwords do not match."
    return ""


def layout():
    """Registration only. Credit checks live on Settings."""
    return html.Div(
        className="auth-screen signup-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "getstarted-back-home"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Get started", className="gs-top-title"),
                ],
            ),
            html.Div(icon("user"), className="gs-icon-wrap"),
            html.H2("Registration", className="gs-title"),
            html.P(
                "Create your profile with your name, email, phone, and password.",
                className="gs-copy",
            ),
            html.Div("First name", className="gs-label"),
            dcc.Input(
                id="signup-first-name",
                type="text",
                value="",
                autoComplete="given-name",
                className="auth-input",
            ),
            html.Div("Last name", className="gs-label"),
            dcc.Input(
                id="signup-last-name",
                type="text",
                value="",
                autoComplete="family-name",
                className="auth-input",
            ),
            html.Div("Email", className="gs-label"),
            dcc.Input(
                id="signup-email",
                type="email",
                value="",
                autoComplete="email",
                className="auth-input",
            ),
            html.Div("Phone", className="gs-label"),
            dcc.Input(
                id="signup-phone",
                type="tel",
                value="",
                autoComplete="tel",
                className="auth-input",
            ),
            html.Div("Set password", className="gs-label"),
            dcc.Input(
                id="signup-password",
                type="password",
                value="",
                autoComplete="new-password",
                className="auth-input",
            ),
            html.Div("Confirm password", className="gs-label"),
            dcc.Input(
                id="signup-password-confirm",
                type="password",
                value="",
                autoComplete="new-password",
                className="auth-input",
            ),
            html.Div(id="signup-error", className="auth-error"),
            html.Button(
                "Create account",
                id={"type": "auth-btn", "action": "signup-submit"},
                n_clicks=0,
                className="auth-primary-btn gs-primary",
            ),
        ],
    )


def nigeria_locked_step():
    """Nigeria credit check, visible but not runnable. UK stays the default path."""
    return html.Div(
        className="dd-step dd-step-locked",
        **{"aria-disabled": "true"},
        children=[
            html.Div(
                className="dd-step-head",
                children=[
                    html.Div("Checking your credit in Nigeria", className="dd-step-title"),
                    html.Div(
                        [icon("lock"), html.Span("Locked")],
                        className="dd-lock",
                    ),
                ],
            ),
            html.P(
                "This step is locked. The default path is the UK credit check only.",
                className="dd-step-copy",
            ),
        ],
    )


def due_diligence_layout():
    """Credit checks opened from Settings. UK first; Nigeria is locked."""
    return html.Div(
        className="auth-screen gs-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "dd-back-settings"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Complete profile", className="gs-top-title"),
                ],
            ),
            html.Div("UK-ONLY DEFAULT", className="auth-kicker gs-kicker"),
            html.H2("Credit and affordability", className="gs-title"),
            html.P(
                "The UK check runs first. The Nigeria check stays locked until it is available.",
                className="gs-copy",
            ),
            html.Div(
                className="dd-steps",
                children=[
                    html.Div(
                        className="dd-step dd-step-uk",
                        children=[
                            html.Div("1 · Default path", className="dd-kicker"),
                            html.Div("Check UK credit", className="dd-step-title"),
                            html.P(
                                "UK bureau file, electoral roll, and affordability.",
                                className="dd-step-copy",
                            ),
                            html.Button(
                                ["Check UK credit ", html.I(className="bi bi-arrow-right")],
                                id={"type": "auth-btn", "action": "dd-start-uk"},
                                n_clicks=0,
                                className="auth-primary-btn gs-primary",
                            ),
                        ],
                    ),
                    nigeria_locked_step(),
                ],
            ),
        ],
    )


def nigeria_locked_layout():
    """Full-page locked Nigeria step. It does not start a bureau check."""
    return html.Div(
        className="auth-screen gs-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "dd-back-overview"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Credit check origin", className="gs-top-title"),
                ],
            ),
            html.Div(icon("lock"), className="gs-icon-wrap"),
            html.H2("Nigeria check", className="gs-title"),
            nigeria_locked_step(),
        ],
    )


def loading_layout():
    """Kept for the Nigeria screen. The live path does not mount this timer."""
    steps = [
        ("Verifying identity", True),
        ("Pulling bureau data", True),
        ("Analyzing transactions", False),
        ("Scoring", False),
    ]
    return html.Div(
        className="auth-screen gs-screen gs-loading-screen dd-nigeria-parked",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "dd-back-overview"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Nigeria check", className="gs-top-title"),
                ],
            ),
            nigeria_locked_step(),
            html.H3("Checking your credit in Nigeria...", className="gs-load-title dd-parked-title"),
            html.P("Locked. This check does not run.", className="gs-load-sub"),
            html.Div(
                className="gs-steps",
                children=[
                    html.Div(
                        className=f"gs-step {'done' if done else ''}",
                        children=[
                            html.Span(className="gs-step-dot"),
                            html.Span(label, className="gs-step-label"),
                            html.Span(icon("check", "gs-step-check") if done else "", className="gs-step-right"),
                        ],
                    )
                    for label, done in steps
                ],
            ),
        ],
    )


def result_origin_layout():
    return html.Div(
        className="auth-screen gs-screen dd-nigeria-parked",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "dd-back-overview"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Credit check result", className="gs-top-title"),
                ],
            ),
            nigeria_locked_step(),
            html.Div("RESULT", className="auth-kicker gs-kicker"),
            html.H2("Nigeria credit check result", className="gs-title gs-result-title"),
            html.P(
                "The Nigeria result stays locked. Finish the UK check to complete your profile.",
                className="gs-copy",
            ),
        ],
    )


def loading_uk_layout():
    steps = [
        ("Pulling UK bureau file", True),
        ("Checking electoral roll", True),
        ("Running affordability", False),
        ("Final score", False),
    ]
    return html.Div(
        className="auth-screen gs-screen gs-loading-screen",
        children=[
            dcc.Interval(
                id={"type": "gs-timer", "screen": "uk"},
                interval=5000,
                n_intervals=0,
                max_intervals=1,
            ),
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "getstarted-back-step3"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Running UK check", className="gs-top-title"),
                ],
            ),
            html.Div(
                className="gs-loader-wrap",
                children=[
                    html.Div(className="gs-loader-ring"),
                    html.Div(className="gs-loader-arc"),
                ],
            ),
            html.H3("Checking your UK credit file...", className="gs-load-title"),
            html.P("Usually takes under a minute.", className="gs-load-sub"),
            html.Div(
                className="gs-steps",
                children=[
                    html.Div(
                        className=f"gs-step {'done' if done else ''}",
                        children=[
                            html.Span(className="gs-step-dot"),
                            html.Span(label, className="gs-step-label"),
                            html.Span(icon("check", "gs-step-check") if done else "", className="gs-step-right"),
                        ],
                    )
                    for label, done in steps
                ],
            ),
        ],
    )


def result_uk_layout():
    return html.Div(
        className="auth-screen gs-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "getstarted-back-uk-loading"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Credit check UK", className="gs-top-title"),
                ],
            ),
            html.Div("RESULT", className="auth-kicker gs-kicker"),
            html.H6("You can comfortably contribute up to £1140/mo.", className="gs-title gs-result-title"),
            html.Div(
                className="gs-score-card",
                children=[
                    html.Div(
                        className="gs-score-left",
                        children=[
                            html.Div(
                                className="gs-score-ring gs-score-ring-uk",
                                children=[
                                    html.Div("CREDIT SCORE", className="gs-score-label"),
                                    html.Div("791", className="gs-score-value"),
                                    html.Div("Good", className="gs-score-band"),
                                ],
                            )
                        ],
                    ),
                    html.Div(
                        className="gs-score-right",
                        children=[
                            html.Div("UK · EXPERIAN", className="gs-meta-kicker"),
                            html.P(
                                "7 yrs in UK · On electoral roll · 0 missed payments in 24 months.",
                                className="gs-meta-copy",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="gs-afford-card",
                children=[
                    html.Div(
                        className="gs-aff-head",
                        children=[html.Span("Affordability", className="gs-aff-title"), html.Span("Last 3 months", className="gs-aff-sub")],
                    ),
                    html.Div(className="gs-aff-row", children=[html.Span("Net income"), html.Span("£3,240", className="gs-aff-val")]),
                    html.Div(className="bar gs-aff-bar gs-aff-bar-1", children=[html.Span()]),
                    html.Div(className="gs-aff-row", children=[html.Span("Fixed outgoings"), html.Span("£1,680", className="gs-aff-val")]),
                    html.Div(className="bar gs-aff-bar gs-aff-bar-2", children=[html.Span()]),
                    html.Div(className="gs-aff-row", children=[html.Span("Discretionary"), html.Span("£420", className="gs-aff-val")]),
                    html.Div(className="bar gs-aff-bar gs-aff-bar-3", children=[html.Span()]),
                    html.Div(className="hr"),
                    html.Div(
                        className="gs-aff-row gs-aff-row-total",
                        children=[html.Span("Safe contribution headroom"), html.Span("£1140", className="gs-aff-total")],
                    ),
                ],
            ),
            html.Div(
                className="gs-eligible",
                children=[
                    html.Div(icon("check"), className="gs-eligible-ic"),
                    html.Div(
                        [
                            html.Div("Eligible for all circle tiers", className="gs-eligible-title"),
                            html.Div("£50, £100, £500, £800 monthly - weekly and monthly cadences.", className="gs-eligible-copy"),
                        ]
                    ),
                ],
            ),
            nigeria_locked_step(),
            html.Button(
                "Verified - finish setup",
                id={"type": "auth-btn", "action": "getstarted-finish"},
                n_clicks=0,
                className="auth-primary-btn gs-primary",
            ),
        ],
    )
