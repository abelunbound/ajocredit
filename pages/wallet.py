from dash import html

from .components import icon, pill
from .data import CIRCLE, ME, TXNS

# Prototype figures for the local request preview. The cap is what this member
# has already paid into the active circle (three months at the circle amount).
# A stored server quote, with an id and expiry, is a later milestone.
PAID_IN_MONTHS = 3
PAID_IN_PENCE = PAID_IN_MONTHS * CIRCLE["amount"] * 100
QUOTE_REFERENCE = "local-preview"


def _pounds(pence: int) -> str:
    return f"£{pence // 100:,}"


def _button(icon_name: str, label: str, **kwargs):
    return html.Button([icon(icon_name), label], className="btn btn-ghost", **kwargs)


def quote_body(requested: bool):
    """Quote panel. Detail stays hidden until Request EarlyPayout is used."""
    if not requested:
        children = [
            html.Div("Quote", className="h2"),
            html.Div(
                "Use Request EarlyPayout to preview the amount, the £0 fee, and what you would receive.",
                className="ep-note",
            ),
        ]
    else:
        amount = _pounds(PAID_IN_PENCE)
        children = [
            html.Div(
                className="between",
                children=[html.Div("Quote", className="h2"), pill("Preview", "gold")],
            ),
            html.Div(
                className="ep-lines",
                children=[
                    html.Div(className="pmeta-row", children=[html.Span("Ajo", className="pmeta-k"), html.Span(CIRCLE["name"], className="pmeta-v")]),
                    html.Div(className="pmeta-row", children=[html.Span("Amount", className="pmeta-k"), html.Span(amount, className="pmeta-v")]),
                    html.Div(className="pmeta-row", children=[html.Span("Fee", className="pmeta-k"), html.Span("£0 · waived", className="pmeta-v fee-free")]),
                    html.Div(className="pmeta-row", children=[html.Span("You receive", className="pmeta-k"), html.Span(amount, className="pmeta-v")]),
                    html.Div(className="pmeta-row", children=[html.Span("Reference", className="pmeta-k"), html.Span(QUOTE_REFERENCE, className="pmeta-v mono")]),
                ],
            ),
            html.Div(
                "Preview only. Nothing is paid. This quote is not stored and cannot be accepted yet.",
                className="ep-note",
            ),
        ]
    return html.Div(children)


def layout():
    paid_in = _pounds(PAID_IN_PENCE)
    return html.Div(
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("EarlyPayout Wallet"),
                            html.Div("Virtual account · FCA safeguarded", className="sub"),
                        ]
                    ),
                    html.Div(
                        className="row-btns head-actions",
                        children=[
                            _button("arrdn", "Top up"),
                            _button("arrup", "Withdraw"),
                            _button("pound", "Request EarlyPayout", id="early-payout-request", n_clicks=0),
                            _button("dl", "Statement"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="g4",
                children=[
                    html.Div(
                        [
                            html.Div("Available Early Payout", className="kl"),
                            html.Div(paid_in, className="kv"),
                            html.Div(f"Paid into {CIRCLE['name']}", className="kd"),
                        ],
                        className="kpi",
                    ),
                    html.Div(
                        [html.Div("Incoming", className="kl"), html.Div("£5,000", className="kv"), html.Div("Aug 28", className="kd")],
                        className="kpi",
                    ),
                    html.Div(
                        [
                            html.Div("Lifetime received", className="kl"),
                            html.Div("£10,510", className="kv"),
                            html.Div("2 previous circles", className="kd"),
                        ],
                        className="kpi",
                    ),
                    html.Div(
                        [
                            html.Div("Lifetime contributed", className="kl"),
                            html.Div("£10,000", className="kv"),
                            html.Div("20 contributions", className="kd"),
                        ],
                        className="kpi",
                    ),
                ],
            ),
            html.Div(
                className="g2",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            html.Div("Request", className="h2"),
                            html.Div(
                                "Ask for the contributions you have already paid into this Ajo, before your rotation month.",
                                className="ep-note",
                            ),
                            html.Div(
                                className="ep-lines",
                                children=[
                                    html.Div(className="pmeta-row", children=[html.Span("Ajo", className="pmeta-k"), html.Span(CIRCLE["name"], className="pmeta-v")]),
                                    html.Div(className="pmeta-row", children=[html.Span("Member", className="pmeta-k"), html.Span(f"@{ME['username']} · {ME['name']}", className="pmeta-v")]),
                                    html.Div(className="pmeta-row", children=[html.Span("Paid in", className="pmeta-k"), html.Span(paid_in, className="pmeta-v")]),
                                    html.Div(className="pmeta-row", children=[html.Span("Cap", className="pmeta-k"), html.Span(paid_in, className="pmeta-v")]),
                                ],
                            ),
                            html.Div(
                                "An early payout cannot be more than the amount already paid in. The fee stays £0.",
                                className="ep-note",
                            ),
                        ],
                    ),
                    html.Div(className="card", id="early-payout-quote", children=[quote_body(False)]),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.Div("All transactions", className="h2"),
                    html.Table(
                        className="t",
                        children=[
                            html.Thead(html.Tr([html.Th("Transaction"), html.Th("Date"), html.Th("Status"), html.Th("Amount")])),
                            html.Tbody(
                                [
                                    html.Tr(
                                        [
                                            html.Td(t["label"]),
                                            html.Td(t["date"]),
                                            html.Td(t["status"]),
                                            html.Td(t["amount"], className="mono"),
                                        ]
                                    )
                                    for t in TXNS
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
