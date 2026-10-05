from dash import dcc, html


def apply_settings_action(action, fields, store):
    """Update session profile fields and return a message.

    Email, SMS, and direct debit are not sent from this local build.
    """
    fields = fields or {}
    if action == "save-address":
        line = fields.get("line")
        city = fields.get("city")
        postcode = fields.get("postcode")
        if not all(isinstance(value, str) and value.strip() for value in (line, city, postcode)):
            return "Enter an address line, city, and postcode."
        store["address_line"] = line.strip()
        store["address_city"] = city.strip()
        store["address_postcode"] = postcode.strip()
        return "Address saved for this session."
    if action == "verify-phone":
        phone = fields.get("phone")
        if not isinstance(phone, str) or not phone.strip():
            return "Enter a phone number to verify."
        store["profile_phone"] = phone.strip()
        return "No SMS was sent. Phone verification is unavailable in this local build."
    if action == "reset-password":
        return "No email was sent. Password reset by email is not active in this local build."
    if action == "setup-direct-debit":
        return "Direct debit setup is not available in this local build."
    return ""


def layout(username=None, profile=None):
    profile = profile or {}
    handle = username or "signed-in"
    uk_done = bool(profile.get("uk_checked"))
    status = "UK credit check complete for this session." if uk_done else "UK credit check not completed."
    return html.Div(
        className="stack settings-page",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Settings"),
                            html.P(f"@{handle}", className="sub"),
                        ]
                    )
                ],
            ),
            html.Div(id="settings-feedback", className="settings-feedback"),
            html.Div(
                className="card settings-card",
                children=[
                    html.Div("Complete profile", className="h2"),
                    html.P("Credit / affordability check.", className="sub"),
                    html.P(status, className="settings-status"),
                    html.P(
                        "Nigeria is locked. The check that runs is the UK path.",
                        className="sub",
                    ),
                    html.Button(
                        "Complete profile",
                        id={"type": "auth-btn", "action": "settings-complete-profile"},
                        n_clicks=0,
                        className="btn btn-primary",
                    ),
                ],
            ),
            html.Div(
                className="card settings-card",
                children=[
                    html.Div("Address Completion", className="h2"),
                    html.Div("Address line", className="gs-label"),
                    dcc.Input(
                        id="settings-address-line",
                        type="text",
                        value=profile.get("address_line") or "",
                        className="auth-input",
                    ),
                    html.Div("City", className="gs-label"),
                    dcc.Input(
                        id="settings-city",
                        type="text",
                        value=profile.get("address_city") or "",
                        className="auth-input",
                    ),
                    html.Div("Postcode", className="gs-label"),
                    dcc.Input(
                        id="settings-postcode",
                        type="text",
                        value=profile.get("address_postcode") or "",
                        className="auth-input",
                    ),
                    html.Button(
                        "Save address",
                        id={"type": "settings-action", "action": "save-address"},
                        n_clicks=0,
                        className="btn btn-primary settings-action",
                    ),
                ],
            ),
            html.Div(
                className="card settings-card",
                children=[
                    html.Div("Verify phone number", className="h2"),
                    html.Div("Phone", className="gs-label"),
                    dcc.Input(
                        id="settings-phone",
                        type="tel",
                        value=profile.get("profile_phone") or "",
                        className="auth-input",
                    ),
                    html.Button(
                        "Verify phone number",
                        id={"type": "settings-action", "action": "verify-phone"},
                        n_clicks=0,
                        className="btn btn-ghost settings-action",
                    ),
                ],
            ),
            html.Div(
                className="card settings-card",
                children=[
                    html.Div("Reset password", className="h2"),
                    html.P("Reset password via email.", className="sub"),
                    html.Button(
                        "Email reset link",
                        id={"type": "settings-action", "action": "reset-password"},
                        n_clicks=0,
                        className="btn btn-ghost settings-action",
                    ),
                ],
            ),
            html.Div(
                className="card settings-card",
                children=[
                    html.Div("Set up direct debit", className="h2"),
                    html.P(
                        "Direct debit for Ajo contributions. More Ajo settings can be added here later.",
                        className="sub",
                    ),
                    html.Button(
                        "Set up direct debit",
                        id={"type": "settings-action", "action": "setup-direct-debit"},
                        n_clicks=0,
                        className="btn btn-ghost settings-action",
                    ),
                ],
            ),
        ],
    )
