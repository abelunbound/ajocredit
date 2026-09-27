from dash import dcc, html

from .components import icon


def layout():
    return html.Div(
        className="auth-screen gs-screen",
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
                    html.Div("Credit check setup", className="gs-top-title"),
                ],
            ),
            html.Div(icon("flag"), className="gs-icon-wrap"),
            # html.Div("STEP 2 OF 4", className="auth-kicker gs-kicker"),
            html.H2("Registration", className="gs-title"),
            html.P(
                "We'll check your credit in your country of origin to see any pending debt or liability. "
                "This never affects your UK score.",
                className="gs-copy",
            ),
            html.Div("First Name", className="gs-label"),
            dcc.Input(value="", type="text", className=""),

            html.Div("Last Name", className="gs-label"),
            dcc.Input(value="", type="text", className=""),

            html.Div("Email:", className="gs-label"),
            dcc.Input(value="", type="text", className=""),

            html.Div("Phone number:", className="gs-label"),
            dcc.Input(value="", type="text", className=""),

            html.Div("Country of origin", className="gs-label"),
            dcc.Dropdown(
                options=[{"label": "Nigeria", "value": "nigeria"}, {"label": "Ghana", "value": "ghana"}, {"label": "Kenya", "value": "kenya"}],
                value="nigeria",
                clearable=False,
                searchable=False,
                className="gs-select",
            ),
            html.Div("National identifier (BVN / NIN / equivalent)", className="gs-label"),
            dcc.Input(value="2210  ****  ****  4187", type="text", className=""),
            html.Div(
                className="gs-note",
                children=[
                    html.Div(icon("lock"), className="gs-note-ic"),
                    html.Div("Encrypted submission to accredited bureau. Soft check - no impact on your score.", className="gs-note-text"),
                ],
            ),

            html.Div("Set password", className="gs-label"),
            dcc.Input(value="********", type="text", className=""),

            html.Div("Reenter password", className="gs-label"),
            dcc.Input(value="********", type="text", className=""),


            html.Div("Date of birth:", className="gs-label"),
            html.Button(
                "Continue",
                id={"type": "auth-btn", "action": "getstarted-run-check"},
                n_clicks=0,
                className="auth-primary-btn gs-primary",
            ),
        ],
    )


def loading_layout():
    steps = [
        ("Verifying identity", True),
        ("Pulling bureau data", True),
        ("Analyzing transactions", False),
        ("Scoring", False),
    ]
    return html.Div(
        className="auth-screen gs-screen gs-loading-screen",
        children=[
            dcc.Interval(
                id={"type": "gs-timer", "screen": "2"},
                interval=5000,
                n_intervals=0,
                max_intervals=1,
            ),
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "getstarted-back-step1"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Running credit check", className="gs-top-title"),
                ],
            ),
            html.Div(
                className="gs-loader-wrap",
                children=[
                    html.Div(className="gs-loader-ring"),
                    html.Div(className="gs-loader-arc"),
                ],
            ),
            html.H3("Checking your credit in Nigeria...", className="gs-load-title"),
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


def result_origin_layout():
    rows = [
        ("Active liabilities", "£0.00"),
        ("Accounts past due", "0"),
        ("Credit enquiries (12m)", "2"),
        ("Oldest account", "6 yr 4 mo"),
    ]
    return html.Div(
        className="auth-screen gs-screen",
        children=[
            html.Div(
                className="signin-top-row",
                children=[
                    html.Button(
                        html.I(className="bi bi-chevron-left"),
                        id={"type": "auth-btn", "action": "getstarted-back-step2"},
                        n_clicks=0,
                        className="signin-back-btn",
                    ),
                    html.Div("Credit check origin", className="gs-top-title"),
                ],
            ),
            html.Div("RESULT", className="auth-kicker gs-kicker"),
            html.H2("No pending debt found.", className="gs-title gs-result-title"),
            html.Div(
                className="gs-score-card",
                children=[
                    html.Div(
                        className="gs-score-left",
                        children=[
                            html.Div(
                                className="gs-score-ring",
                                children=[
                                    html.Div("CREDIT SCORE", className="gs-score-label"),
                                    html.Div("712", className="gs-score-value"),
                                    html.Div("Good", className="gs-score-band"),
                                ],
                            )
                        ],
                    ),
                    html.Div(
                        className="gs-score-right",
                        children=[
                            html.Div("ORIGIN: NIGERIA · CRC BUREAU", className="gs-meta-kicker"),
                            html.P(
                                "Verified via BVN + NIN. No outstanding loans, no collections, no active judgments.",
                                className="gs-meta-copy",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="gs-table-card",
                children=[
                    html.Div(
                        className="gs-table-row",
                        children=[html.Span(label, className="gs-row-label"), html.Span(value, className="gs-row-value")]
                    )
                    for label, value in rows
                ],
            ),
            html.Button(
                ["Continue to UK check ", html.I(className="bi bi-arrow-right")],
                id={"type": "auth-btn", "action": "getstarted-to-uk"},
                n_clicks=0,
                className="auth-primary-btn gs-primary",
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
            html.Button(
                "Verified - finish setup",
                id={"type": "auth-btn", "action": "getstarted-finish"},
                n_clicks=0,
                className="auth-primary-btn gs-primary",
            ),
        ],
    )
