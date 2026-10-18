import math
import statistics
from urllib.parse import quote

from dash import dcc, html

from .components import icon


PAGE_TITLE = "Financial Health Overview"

# Illustrative open-banking series for the FinHealth overview. Figures match
# the affordability cards: tuition £14,000, latest balance £16,258, and a
# 30th-day forecast of £17,950 (buffer £3,950).
TUITION = 14000
APPLICANT_BALANCE = 16258
FORECAST_DAY30 = 17950
BUFFER = FORECAST_DAY30 - TUITION

_HISTORY_KEYS = [
    (0, 5100),
    (19, 4500),
    (30, 4200),
    (33, 4200),
    (36, 7300),
    (58, 5400),
    (69, 5000),
    (84, 3800),
    (90, 2600),
    (93, 2500),
    (96, 8100),
    (108, 6800),
    (120, 5400),
    (123, 5300),
    (126, 11200),
    (132, 9800),
    (140, 10100),
    (151, 9600),
    (154, 9600),
    (157, 12600),
    (169, 10800),
    (181, 9600),
    (183, 9400),
    (186, 15600),
    (196, 13800),
    (212, 13200),
    (216, 13200),
    (219, 16300),
    (230, 14500),
    (238, 13600),
    (243, APPLICANT_BALANCE),
]

# Next-30-days path. Day 0 is 28 Jul 2024; day 30 is the £17,950 forecast.
_FORECAST_KEYS = [
    (0, 14400),
    (2, 14620),
    (5, 13700),
    (7, 13820),
    (10, 13600),
    (14, 13420),
    (17, 13380),
    (21, 13720),
    (23, 13700),
    (25, 14250),
    (28, 15900),
    (30, FORECAST_DAY30),
]

_VALIDATION_KEYS = [
    (0, 14320),
    (3, 14540),
    (6, 14110),
    (9, 13940),
    (12, 14080),
    (15, 14260),
    (18, 14410),
    (21, 14680),
    (24, 14840),
    (27, 15120),
    (30, 15480),
]


def _interp(keys, steps):
    values = []
    for step in range(steps + 1):
        if step <= keys[0][0]:
            values.append(keys[0][1])
            continue
        if step >= keys[-1][0]:
            values.append(keys[-1][1])
            continue
        for (x0, y0), (x1, y1) in zip(keys, keys[1:]):
            if x0 <= step <= x1:
                span = x1 - x0 or 1
                values.append(y0 + (y1 - y0) * (step - x0) / span)
                break
    return values


def history_series():
    return _interp(_HISTORY_KEYS, 243)


def volatility_series(window=7):
    balances = history_series()
    series = []
    for index in range(len(balances)):
        chunk = balances[max(0, index - window + 1) : index + 1]
        series.append(statistics.pstdev(chunk) if len(chunk) > 1 else 0.0)
    return series


def forecast_series():
    return _interp(_FORECAST_KEYS, 30)


def validation_series():
    return _interp(_VALIDATION_KEYS, 30)


def layout():
    return html.Div(
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1(PAGE_TITLE),
                            html.Div(
                                "Country of origin is locked. UK affordability is below.",
                                className="sub",
                            ),
                        ]
                    ),
                    html.Button([icon("dl"), "Download report"], className="btn btn-ghost"),
                ],
            ),
            _origin_card(),
            _assessment_card(),
            _forecast_card(),
        ],
    )


def _origin_card():
    return html.Div(
        className="card cr-locked",
        **{"aria-disabled": "true"},
        children=[
            html.Div(
                className="cr-lock-note",
                children=[
                    icon("lock"),
                    html.Span("Country of origin check is locked"),
                ],
            ),
            html.Div(
                className="cr-lock-body",
                children=[
                    html.Div(
                        className="card-hd",
                        children=[
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(icon("flag"), className="cr-ic"),
                                            html.Div(
                                                [
                                                    html.Div("Check A · Country of origin", className="h2"),
                                                    html.Div("Nigeria · CRC Bureau · BVN", className="muted mini"),
                                                ]
                                            ),
                                        ],
                                        className="cr-head-row",
                                    )
                                ]
                            ),
                            html.Span([icon("lock"), "Locked"], className="pill fh-lock"),
                        ],
                    ),
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
        ],
    )


def _metric(label, value, accent=None):
    accent_class = f" fh-accent-{accent}" if accent else ""
    return html.Div(
        className=f"fh-metric{accent_class}",
        children=[
            html.Div(label, className="fh-metric-k"),
            html.Div(value, className="fh-metric-v"),
        ],
    )


def _radios(radio_id, options, value):
    return dcc.RadioItems(
        id=radio_id,
        options=[{"label": label, "value": option_value} for label, option_value in options],
        value=value,
        className="fh-radios",
        inputClassName="fh-radio-input",
        labelClassName="fh-radio-label",
    )


def assessment_chart(view):
    if view == "volatility":
        series = volatility_series()
        return html.Div(
            [
                _legend([("line", "7-day rolling standard deviation")]),
                _chart(
                    series,
                    y_min=0,
                    y_max=_nice_max(max(series)),
                    y_ticks=None,
                    y_label="Std. dev. (£)",
                    x_labels=_month_labels(),
                    line_name="7-day rolling standard deviation",
                ),
            ]
        )
    return html.Div(
        [
            _legend(
                [
                    ("area", "Last 3 Months"),
                    ("line", "Daily Bank Balance"),
                    ("req", "Required Amount"),
                ]
            ),
            _chart(
                history_series(),
                y_min=0,
                y_max=17500,
                y_ticks=[0, 5000, 10000, 15000],
                y_label="Balance (£)",
                x_labels=_month_labels(),
                required=TUITION,
                shade_from=0.625,
                line_name="Daily bank balance",
            ),
        ]
    )


def forecast_chart(view):
    compare = view == "validation"
    legend = [
        ("req", "Required Amount"),
        ("line", "Forecasted Balance (£)"),
    ]
    if compare:
        legend.append(("alt", "Validation data (£)"))
    return html.Div(
        [
            _legend(legend),
            _chart(
                forecast_series(),
                y_min=13200,
                y_max=18200,
                y_ticks=[13500, 14000, 14500, 15000, 15500, 16000],
                y_label="Balance (£)",
                x_labels=_forecast_labels(len(forecast_series())),
                required=TUITION,
                comparison=validation_series() if compare else None,
                line_name="Forecast versus validation" if compare else "Forecasted balance",
                money="k",
            ),
        ]
    )


def _assessment_card():
    return html.Div(
        className="card fh-card",
        children=[
            html.Div(
                className="fh-split",
                children=[
                    html.Div(
                        className="fh-side",
                        children=[
                            html.H2("Affordability Assessment", className="fh-title"),
                            _metric("Tuition & Living Expenses (£)", "£14000"),
                            _metric("Applicant Bank Balance", "£16258", "orange"),
                            _metric("Threshold met", "Yes", "red"),
                            _metric("Cross-border debt/liability", "£0", "red"),
                        ],
                    ),
                    html.Div(
                        className="fh-switch",
                        children=[
                            _radios(
                                "fh-assess-view",
                                [
                                    ("Financial History (£) – 12 Months", "history"),
                                    ("Volatility check - 7-Day rolling standard deviation", "volatility"),
                                ],
                                "history",
                            ),
                            html.Div(id="fh-assess-chart", children=assessment_chart("history")),
                        ],
                    ),
                ],
            )
        ],
    )


def _forecast_card():
    return html.Div(
        className="card fh-card",
        children=[
            html.Div(
                className="fh-split",
                children=[
                    html.Div(
                        className="fh-side",
                        children=[
                            html.H2("Affordability Forecast", className="fh-title"),
                            _metric("Tuition and Living Expenses(£)", "£14000.00"),
                            _metric("30th day Forecast (£)", "£17950.00", "orange"),
                            _metric("Buffer amount (£)", "£3950.00", "red"),
                            html.Div(
                                className="fh-prob",
                                children=[
                                    "Probability of affording payments: ",
                                    html.Span("50-90%", className="fh-prob-val"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="fh-switch",
                        children=[
                            _radios(
                                "fh-forecast-view",
                                [
                                    ("Next 30 days Forecast (£)", "forecast"),
                                    ("Forecast vs Validation data (£)", "validation"),
                                ],
                                "forecast",
                            ),
                            html.Div(id="fh-forecast-chart", children=forecast_chart("forecast")),
                        ],
                    ),
                ],
            )
        ],
    )


def _legend(items):
    return html.Div(
        className="fh-legend",
        children=[
            html.Span([html.Span(className=f"fh-swatch {kind}"), text], className="fh-legend-item")
            for kind, text in items
        ],
    )


def _month_labels():
    # Jan 2024 through Aug 2024, 244 daily points (index 0..243).
    names = ["Jan 2024", "Feb 2024", "Mar 2024", "Apr 2024", "May 2024", "Jun 2024", "Jul 2024", "Aug 2024"]
    starts = [0, 31, 60, 91, 121, 152, 182, 213]
    return [(start / 243, name) for start, name in zip(starts, names)]


def _forecast_labels(length):
    # Day 0 = 28 Jul 2024, so 4 Aug is index 7.
    last = length - 1
    return [(7 / last, "Aug 4"), (14 / last, "Aug 11"), (21 / last, "Aug 18"), (28 / last, "Aug 25")]


def _nice_max(value):
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    return math.ceil(value / magnitude) * magnitude


def _tick_text(value, money):
    if money == "k":
        shown = value / 1000
        text = f"{shown:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    if value >= 1000:
        return f"{value / 1000:.0f}k"
    return f"{value:.0f}"


def _chart(series, y_min, y_max, y_ticks, y_label, x_labels, required=None, shade_from=None, comparison=None, line_name="series", money=None):
    width, height = 680, 320
    left, right, top, bottom = 56, 14, 10, 42
    plot_w = width - left - right
    plot_h = height - top - bottom
    if y_ticks is None:
        y_ticks = [0, y_max / 2, y_max]

    def x_at(index, count):
        if count <= 1:
            return left
        return left + plot_w * index / (count - 1)

    def y_at(value):
        span = y_max - y_min or 1
        frac = (value - y_min) / span
        return top + plot_h * (1 - frac)

    parts = [
        f"<rect x='{left}' y='{top}' width='{plot_w}' height='{plot_h}' rx='8' fill='#E6EEF6'/>",
    ]
    if shade_from is not None:
        shade_x = left + plot_w * shade_from
        parts.append(
            f"<rect x='{shade_x:.1f}' y='{top}' width='{left + plot_w - shade_x:.1f}' height='{plot_h}' fill='#D3E1F0'/>"
        )
    for tick in y_ticks:
        y = y_at(tick)
        parts.append(f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#F7FAFC' stroke-width='1'/>")
        parts.append(
            f"<text x='{left - 8}' y='{y + 4:.1f}' text-anchor='end' font-size='11' fill='#5C6E80' font-family='Arial, Helvetica, sans-serif'>{_tick_text(tick, money)}</text>"
        )
    for frac, label in x_labels:
        x = left + plot_w * frac
        parts.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{top + plot_h}' stroke='#F7FAFC' stroke-width='1'/>")
        parts.append(
            f"<text x='{x:.1f}' y='{top + plot_h + 18}' text-anchor='middle' font-size='11' fill='#5C6E80' font-family='Arial, Helvetica, sans-serif'>{label}</text>"
        )
    parts.append(
        f"<text x='16' y='{top + plot_h / 2}' text-anchor='middle' font-size='11' fill='#5C6E80' font-family='Arial, Helvetica, sans-serif' transform='rotate(-90 16 {top + plot_h / 2})'>{y_label}</text>"
    )
    parts.append(
        f"<text x='{width / 2}' y='{height - 4}' text-anchor='middle' font-size='12' fill='#3E5164' font-family='Arial, Helvetica, sans-serif'>Date</text>"
    )

    def poly(values, color, dash=None):
        coords = " ".join(f"{x_at(i, len(values)):.1f},{y_at(v):.1f}" for i, v in enumerate(values))
        dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
        return (
            f"<polyline fill='none' stroke='{color}' stroke-width='2.4' stroke-linejoin='round' stroke-linecap='round'{dash_attr} points='{coords}'/>"
        )

    if required is not None:
        y = y_at(required)
        parts.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#E07A62' stroke-width='2' stroke-dasharray='7 6'/>"
        )
    parts.append(poly(series, "#5346E0"))
    if comparison is not None:
        parts.append(poly(comparison, "#1B6E89", "2 4"))

    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img' aria-label='{line_name}'>"
        + "".join(parts)
        + "</svg>"
    )
    return html.Img(src=f"data:image/svg+xml;utf8,{quote(svg)}", className="fh-chart", alt=line_name)


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
