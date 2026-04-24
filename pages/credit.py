import math
from urllib.parse import quote

from dash import html

from .components import icon, pill


def layout():
    breakdown = [
        ("Payment history", "Perfect · 24 months", 100, "var(--good)"),
        ("Credit utilization", "18% of available credit", 84, "var(--brand)"),
        ("Age of accounts", "Oldest 7y · avg 3.2y", 72, "var(--accent)"),
        ("Credit mix", "1 mortgage · 2 cards · AjoCredit", 55, "var(--gold)"),
        ("New credit", "1 hard enquiry in 12m", 88, "var(--brand)"),
    ]

    return html.Div(
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div([html.H1("Credit & checks"), html.Div("Dual-bureau · origin + UK affordability · updated 2 days ago", className="sub")]),
                    html.Button([icon("dl"), "Download report"], className="btn btn-ghost"),
                ],
            ),
            html.Div(
                className="g2",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            html.Div(className="card-hd", children=[html.Div([html.Div([html.Div(icon("flag"), className="cr-ic"), html.Div([html.Div("Check A · Country of origin", className="h2"), html.Div("Nigeria · CRC Bureau · BVN", className="muted mini")])], className="cr-head-row")]), pill("Clear", "good")]),
                            html.Div(
                                className="cr-main",
                                children=[
                                    score_ring(712, band="Good", color="var(--brand)"),
                                    html.Div(
                                        className="cr-metrics",
                                        children=[
                                            html.Div(className="between cr-metric", children=[html.Span("Active liabilities"), html.Span("£0.00", className="mono")]),
                                            html.Div(className="between cr-metric", children=[html.Span("Accounts past due"), html.Span("0", className="mono")]),
                                            html.Div(className="between cr-metric", children=[html.Span("Enquiries (12m)"), html.Span("2", className="mono")]),
                                            html.Div(className="between cr-metric", children=[html.Span("Oldest account"), html.Span("6y 4m", className="mono")]),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            html.Div(className="card-hd", children=[html.Div([html.Div([html.Div(icon("pound"), className="cr-ic"), html.Div([html.Div("Check B · UK affordability", className="h2"), html.Div("7 yrs UK · Experian + Open Banking 90d", className="muted mini")])], className="cr-head-row")]), pill("Eligible", "good")]),
                            html.Div(
                                className="cr-main",
                                children=[
                                    score_ring(791, band="Excellent", color="var(--brand)"),
                                    html.Div(
                                        className="cr-bars",
                                        children=[
                                            html.Div([html.Div(className="between", children=[html.Span("Net income"), html.Span("£3,240", className="mono")]), html.Div(className="bar", children=[html.Span(style={"width": "86%"})])], className="cr-bar-row"),
                                            html.Div([html.Div(className="between", children=[html.Span("Fixed outgoings"), html.Span("£1,680", className="mono")]), html.Div(className="bar", children=[html.Span(style={"width": "56%"})])], className="cr-bar-row"),
                                            html.Div([html.Div(className="between", children=[html.Span("Discretionary"), html.Span("£420", className="mono")]), html.Div(className="bar", children=[html.Span(style={"width": "22%"})])], className="cr-bar-row"),
                                            html.Div([html.Div(className="between", children=[html.Span("Safe headroom"), html.Span("£1,140", className="mono")]), html.Div(className="bar", children=[html.Span(style={"width": "38%", "background": "var(--good)"})])], className="cr-bar-row"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.Div(className="card-hd", children=[html.Div([html.Div("Score breakdown", className="h2"), html.Div("12-month trend · +34 pts · Experian", className="muted mini")]), pill("Improving", "good")]),
                    html.Div(
                        className="cr-breakdown",
                        children=[
                            html.Div(
                                className="cr-break-row",
                                children=[
                                    html.Div([html.Div(name, className="cr-break-name"), html.Div(sub, className="muted mini")]),
                                    html.Div(f"{pct}%", className="mono cr-break-pct"),
                                    html.Div(className="bar cr-break-bar", children=[html.Span(style={"width": f"{pct}%", "background": color})]),
                                ],
                            )
                            for name, sub, pct, color in breakdown
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card cr-banner",
                children=[
                    html.Div(icon("spark"), className="cr-banner-ic"),
                    html.Div([html.Div("AjoCredit reports on-time contributions to UK bureaus", className="cr-banner-title"), html.Div("Complete the Brum Builders cycle → estimated +18 points to your Experian score.", className="cr-banner-sub")]),
                ],
            ),
        ],
    )


def score_ring(score, max_score=999, label="UK SCORE", band="Good", size=126, stroke=8, color="var(--brand)"):
    radius = (size - stroke) / 2
    circumference = 2 * math.pi * radius
    pct = max(0.0, min(1.0, score / max_score))
    arc = circumference * pct
    center = size / 2

    color_map = {
        "var(--brand)": "#0E4F47",
        "var(--good)": "#2F7A4C",
        "var(--gold)": "#B88A2A",
        "var(--accent)": "#1B6E89",
    }
    stroke_color = color_map.get(color, color if color.startswith("#") else "#0E4F47")
    track_color = "#EEF2F5"

    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {size} {size}'>
  <g transform='rotate(-90 {center} {center})'>
    <circle cx='{center}' cy='{center}' r='{radius}' fill='none' stroke='{track_color}' stroke-width='{stroke}' />
    <circle cx='{center}' cy='{center}' r='{radius}' fill='none' stroke='{stroke_color}' stroke-width='{stroke}'
      stroke-dasharray='{arc} {circumference}' stroke-linecap='round' />
  </g>
</svg>
""".strip()

    return html.Div(
        className="cr-ring-svg",
        style={"width": f"{size}px", "height": f"{size}px"},
        children=[
            html.Img(src=f"data:image/svg+xml;utf8,{quote(svg)}", className="cr-ring-canvas"),
            html.Div(
                className="cr-ring-center",
                children=[
                    html.Div(label, className="label-xs cr-ring-label"),
                    html.Div(str(score), className="mono cr-ring-score"),
                    html.Div(band, className="cr-ring-band"),
                ],
            ),
        ],
    )
