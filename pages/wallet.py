from dash import html

from .components import icon
from .data import TXNS


def layout():
    return html.Div(
        className="stack",
        children=[
            html.Div(className="page-head", children=[html.Div([html.H1("Wallet"), html.Div("Virtual account · FCA safeguarded", className="sub")]), html.Div(className="row-btns", children=[html.Button([icon("arrdn"), "Top up"], className="btn btn-ghost"), html.Button([icon("arrup"), "Withdraw"], className="btn btn-ghost"), html.Button([icon("dl"), "Statement"], className="btn btn-ghost")])]),
            html.Div(className="g4", children=[html.Div([html.Div("Available balance", className="kl"), html.Div("£42.18", className="kv"), html.Div("Ready to send", className="kd")], className="kpi"), html.Div([html.Div("Incoming", className="kl"), html.Div("£5,000", className="kv"), html.Div("Aug 28", className="kd")], className="kpi"), html.Div([html.Div("Lifetime received", className="kl"), html.Div("£10,510", className="kv"), html.Div("2 previous circles", className="kd")], className="kpi"), html.Div([html.Div("Lifetime contributed", className="kl"), html.Div("£10,000", className="kv"), html.Div("20 contributions", className="kd")], className="kpi")]),
            html.Div(className="card", children=[html.Div("All transactions", className="h2"), html.Table(className="t", children=[html.Thead(html.Tr([html.Th("Transaction"), html.Th("Date"), html.Th("Status"), html.Th("Amount")])), html.Tbody([html.Tr([html.Td(t["label"]), html.Td(t["date"]), html.Td(t["status"]), html.Td(t["amount"], className="mono")]) for t in TXNS])])]),
        ],
    )
