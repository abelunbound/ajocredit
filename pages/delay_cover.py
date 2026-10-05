"""Delay Cover request popup.

Members can flag a future month and Ajo they may not be able to pay, plus when
they expect to pay it back. This is a screen-only flow: nothing is stored, no
advance is granted, and no money moves.
"""

from __future__ import annotations

from dash import Input, Output, State, ctx, dcc, html

from pages.personas import GROUP_NAMES

PRODUCT_NAME = "Delay Cover"

# Demo cycle is in month 3 (April). These are the later contribution months.
COVER_MONTHS = (
    "May 2026",
    "Jun 2026",
    "Jul 2026",
    "Aug 2026",
    "Sep 2026",
    "Oct 2026",
    "Nov 2026",
)
# Payback can run past the cycle so the last cover month still has a choice.
PAYBACK_MONTHS = COVER_MONTHS + (
    "Dec 2026",
    "Jan 2027",
    "Feb 2027",
)
AJO_GROUPS = GROUP_NAMES
STEPS = ("month", "group", "repay", "review", "done")

_MONTH_INDEX = {name: index for index, name in enumerate(PAYBACK_MONTHS)}


def initial_state():
    return {"open": False, "step": "month", "month": "", "group": "", "repay": ""}


def payback_options(cover_month: str) -> tuple[str, ...]:
    """Months strictly after the selected cover month."""
    index = _MONTH_INDEX.get(cover_month)
    if index is None:
        return ()
    return tuple(name for name in PAYBACK_MONTHS if _MONTH_INDEX[name] > index)


def _clean(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def reduce_request(state, action, month, group, repay):
    """Move the popup one step. Returns ``(state, error)``."""
    current = initial_state()
    if isinstance(state, dict):
        current.update({key: state.get(key, current[key]) for key in current})
    current["month"] = _clean(month) or _clean(current.get("month"))
    current["group"] = _clean(group) or _clean(current.get("group"))
    current["repay"] = _clean(repay) or _clean(current.get("repay"))
    if current["step"] not in STEPS:
        current["step"] = "month"

    if action == "open":
        return {**initial_state(), "open": True}, ""
    if action == "close":
        return initial_state(), ""
    if not current["open"]:
        return initial_state(), ""

    if action == "back":
        order = ("month", "group", "repay", "review")
        if current["step"] in order:
            index = order.index(current["step"])
            if index > 0:
                current["step"] = order[index - 1]
        return current, ""

    if action == "next" and current["step"] == "month":
        if current["month"] not in COVER_MONTHS:
            return current, "Select the month you anticipate you will need cover."
        if current["repay"] not in payback_options(current["month"]):
            current["repay"] = ""
        current["step"] = "group"
        return current, ""

    if action == "next" and current["step"] == "group":
        if current["group"] not in AJO_GROUPS:
            return current, "Select the Ajo group."
        current["step"] = "repay"
        return current, ""

    if action == "next" and current["step"] == "repay":
        if current["repay"] not in payback_options(current["month"]):
            return current, "Select a payback month after the cover month."
        current["step"] = "review"
        return current, ""

    if action == "submit" and current["step"] == "review":
        if current["month"] not in COVER_MONTHS or current["group"] not in AJO_GROUPS:
            return current, "Check the month and Ajo group."
        if current["repay"] not in payback_options(current["month"]):
            return current, "Select a payback month after the cover month."
        current["step"] = "done"
        return current, ""

    return current, ""


def _hidden(shown: bool):
    return {} if shown else {"display": "none"}


def present(state, error=""):
    """Visibility and copy for the popup, derived from request state."""
    current = initial_state()
    if isinstance(state, dict):
        current.update({key: state.get(key, current[key]) for key in current})
    step = current["step"] if current["step"] in STEPS else "month"
    summary = (
        f"{current['month']} · {current['group']} · pay back {current['repay']}"
        if current["month"] and current["group"] and current["repay"]
        else ""
    )
    later = payback_options(current["month"]) or PAYBACK_MONTHS
    return {
        "modal_style": {"display": "flex"} if current["open"] else {"display": "none"},
        "repay_options": [{"label": name, "value": name} for name in later],
        "repay_value": current["repay"] if current["repay"] in later else "",
        "month_style": _hidden(step == "month"),
        "group_style": _hidden(step == "group"),
        "repay_style": _hidden(step == "repay"),
        "review_style": _hidden(step == "review"),
        "done_style": _hidden(step == "done"),
        "back_style": _hidden(step in {"group", "repay", "review"}),
        "next_style": _hidden(step in {"month", "group", "repay"}),
        "submit_style": _hidden(step == "review"),
        "error": error or "",
        "summary": summary,
        "state": current,
    }


def _choices(field_id, options):
    return dcc.RadioItems(
        id=field_id,
        options=[{"label": name, "value": name} for name in options],
        value="",
        className="dc-choices",
        inputClassName="dc-choice-input",
        labelClassName="dc-choice",
    )


def request_controls():
    """Status pill, Request Cover label, and the popup. Closed until opened."""
    closed = present(initial_state())
    return html.Div(
        className="dc-request",
        children=[
            html.Div(
                className="dc-head-actions",
                children=[
                    html.Span(
                        [html.Span(className="pd"), "Active on 1 circle"],
                        className="pill good",
                    ),
                    html.Button(
                        "Request Cover",
                        id="dc-open",
                        n_clicks=0,
                        type="button",
                        className="dc-request-btn",
                    ),
                ],
            ),
            html.Div(
                id="dc-modal",
                className="dc-modal",
                style=closed["modal_style"],
                role="dialog",
                **{"aria-modal": "true", "aria-labelledby": "dc-dialog-title"},
                children=[
                    html.Button(
                        "Close",
                        id="dc-backdrop",
                        n_clicks=0,
                        type="button",
                        className="dc-backdrop",
                        **{"aria-label": "Close request cover"},
                    ),
                    html.Div(
                        className="dc-dialog",
                        children=[
                            html.Div(
                                className="dc-dialog-top",
                                children=[
                                    html.Div(PRODUCT_NAME, className="label-xs"),
                                    html.Button(
                                        "Close",
                                        id="dc-close",
                                        n_clicks=0,
                                        type="button",
                                        className="btn btn-ghost btn-sm",
                                    ),
                                ],
                            ),
                            html.Div(
                                id="dc-month-wrap",
                                style=closed["month_style"],
                                children=[
                                    html.H2(
                                        "Which month?",
                                        id="dc-dialog-title",
                                        className="dc-title",
                                    ),
                                    html.P(
                                        "Select the month you anticipate you will need cover.",
                                        className="dc-copy",
                                    ),
                                    _choices("dc-month", COVER_MONTHS),
                                ],
                            ),
                            html.Div(
                                id="dc-group-wrap",
                                style=closed["group_style"],
                                children=[
                                    html.H2("Which Ajo?", className="dc-title"),
                                    html.P(
                                        "Select the Ajo group that contribution belongs to.",
                                        className="dc-copy",
                                    ),
                                    _choices("dc-group", AJO_GROUPS),
                                ],
                            ),
                            html.Div(
                                id="dc-repay-wrap",
                                style=closed["repay_style"],
                                children=[
                                    html.H2("When can you pay it back?", className="dc-title"),
                                    html.P(
                                        "Select a month after the one you may miss.",
                                        className="dc-copy",
                                    ),
                                    _choices("dc-repay", PAYBACK_MONTHS),
                                ],
                            ),
                            html.Div(
                                id="dc-review-wrap",
                                style=closed["review_style"],
                                children=[
                                    html.H2("Check this request", className="dc-title"),
                                    html.P(
                                        "This notes the month only. It does not pay anyone, and it does not grant cover.",
                                        className="dc-copy",
                                    ),
                                    html.Div(id="dc-summary", className="dc-summary"),
                                ],
                            ),
                            html.Div(
                                id="dc-done-wrap",
                                style=closed["done_style"],
                                children=[
                                    html.H2("Request noted", className="dc-title"),
                                    html.P(
                                        "Saved for this screen only. No money moves, and Delay Cover is not approved.",
                                        className="dc-copy",
                                    ),
                                    html.Div(id="dc-done-summary", className="dc-summary"),
                                ],
                            ),
                            html.Div(id="dc-error", className="dc-error", role="alert"),
                            html.Div(
                                className="dc-actions",
                                children=[
                                    html.Button(
                                        "Back",
                                        id="dc-back",
                                        n_clicks=0,
                                        type="button",
                                        className="btn btn-ghost btn-sm",
                                        style=closed["back_style"],
                                    ),
                                    html.Button(
                                        "Continue",
                                        id="dc-next",
                                        n_clicks=0,
                                        type="button",
                                        className="btn btn-primary btn-sm",
                                        style=closed["next_style"],
                                    ),
                                    html.Button(
                                        "Submit request",
                                        id="dc-submit",
                                        n_clicks=0,
                                        type="button",
                                        className="btn btn-primary btn-sm",
                                        style=closed["submit_style"],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Store(id="dc-store", data=initial_state()),
        ],
    )


def handle_delay_cover(triggered, store, month, group, repay):
    """Callback body. ``triggered`` is the Dash triggered id."""
    action = {
        "dc-open": "open",
        "dc-close": "close",
        "dc-backdrop": "close",
        "dc-back": "back",
        "dc-next": "next",
        "dc-submit": "submit",
    }.get(triggered if isinstance(triggered, str) else "", "")
    state, error = reduce_request(store, action, month, group, repay)
    view = present(state, error)
    return (
        view["modal_style"],
        view["month_style"],
        view["group_style"],
        view["repay_style"],
        view["review_style"],
        view["done_style"],
        view["back_style"],
        view["next_style"],
        view["submit_style"],
        view["error"],
        view["summary"],
        view["summary"],
        view["repay_options"],
        view["repay_value"],
        view["state"],
    )


def register_callbacks(app):
    @app.callback(
        Output("dc-modal", "style"),
        Output("dc-month-wrap", "style"),
        Output("dc-group-wrap", "style"),
        Output("dc-repay-wrap", "style"),
        Output("dc-review-wrap", "style"),
        Output("dc-done-wrap", "style"),
        Output("dc-back", "style"),
        Output("dc-next", "style"),
        Output("dc-submit", "style"),
        Output("dc-error", "children"),
        Output("dc-summary", "children"),
        Output("dc-done-summary", "children"),
        Output("dc-repay", "options"),
        Output("dc-repay", "value"),
        Output("dc-store", "data"),
        Input("dc-open", "n_clicks"),
        Input("dc-close", "n_clicks"),
        Input("dc-backdrop", "n_clicks"),
        Input("dc-back", "n_clicks"),
        Input("dc-next", "n_clicks"),
        Input("dc-submit", "n_clicks"),
        State("dc-store", "data"),
        State("dc-month", "value"),
        State("dc-group", "value"),
        State("dc-repay", "value"),
        prevent_initial_call=True,
    )
    def _on_delay_cover(_open, _close, _backdrop, _back, _next, _submit, store, month, group, repay):
        return handle_delay_cover(ctx.triggered_id, store, month, group, repay)
