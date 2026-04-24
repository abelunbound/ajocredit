from dash import html

from .components import icon, status_pill


def layout():
    rows = [
        {"u": "ola_t", "n": "Ola T.", "pos": 1, "status": "received", "score": 818, "on_time": "100%", "circles": 3, "joined": "Sep 2024", "av": "#4F6AA3"},
        {"u": "ebuka_n", "n": "Ebuka N.", "pos": 2, "status": "received", "score": 779, "on_time": "100%", "circles": 2, "joined": "Sep 2024", "av": "#4E5FA8"},
        {"u": "abel_o", "n": "Abel O.", "pos": 3, "status": "receiving", "score": 824, "on_time": "100%", "circles": 4, "joined": "Sep 2024", "av": "#B88A2A", "next": True},
        {"u": "kemi_a", "n": "Kemi A.", "pos": 4, "status": "paid", "score": 791, "on_time": "100%", "circles": 2, "joined": "Sep 2024", "av": "#B0392E", "me": True},
        {"u": "chidi_m", "n": "Chidi M.", "pos": 5, "status": "paid", "score": 765, "on_time": "100%", "circles": 1, "joined": "Oct 2024", "av": "#4A89B0"},
        {"u": "tola_b", "n": "Tola B.", "pos": 6, "status": "paid", "score": 812, "on_time": "100%", "circles": 2, "joined": "Oct 2024", "av": "#7C5AA8"},
        {"u": "nneka_o", "n": "Nneka O.", "pos": 7, "status": "paid", "score": 743, "on_time": "100%", "circles": 1, "joined": "Oct 2024", "av": "#2F7A4C"},
        {"u": "daniel_k", "n": "Daniel K.", "pos": 8, "status": "pending", "score": 698, "on_time": "94%", "circles": 1, "joined": "Nov 2024", "av": "#7F6BB3"},
        {"u": "femi_r", "n": "Femi R.", "pos": 9, "status": "paid", "score": 772, "on_time": "100%", "circles": 2, "joined": "Nov 2024", "av": "#2A6E89"},
        {"u": "aisha_w", "n": "Aisha W.", "pos": 10, "status": "paid", "score": 801, "on_time": "100%", "circles": 3, "joined": "Nov 2024", "av": "#2F7A4C"},
    ]

    def score_band(score):
        if score >= 780:
            return "Excellent", "good"
        if score >= 700:
            return "Good", "brand"
        return "Fair", "gold"

    return html.Div(
        className="stack",
        children=[
            html.Div(className="page-head", children=[html.Div([html.H1("Members"), html.Div("Brum Builders · 10 credit-verified · usernames only", className="sub")])]),
            html.Div(
                className="between members-controls",
                children=[
                    html.Div(className="tabs", children=[html.Button("All · 10", className="on"), html.Button("Paid · 9"), html.Button("Pending · 1"), html.Button("Received · 2")]),
                    html.Div(
                        className="row-btns members-tools",
                        children=[
                            html.Select([html.Option("Sort: Rotation position"), html.Option("Sort: Credit score"), html.Option("Sort: Name")], className="inp inp-sm"),
                            html.Button([icon("dl"), "CSV"], className="btn btn-ghost btn-sm"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card members-card",
                children=[
                    html.Table(
                        className="t",
                        children=[
                            html.Thead(html.Tr([html.Th("#", style={"width": "42px"}), html.Th("Member"), html.Th("Status"), html.Th("UK score"), html.Th("Origin"), html.Th("On-time"), html.Th("Circles"), html.Th("Joined"), html.Th("Actions", style={"textAlign": "right"})])),
                            html.Tbody(
                                [
                                    html.Tr(
                                        [
                                            html.Td(m["pos"], className="mono muted"),
                                            html.Td(
                                                [
                                                    html.Div(
                                                        className="member-row",
                                                        children=[
                                                            html.Div("".join([x[0] for x in m["n"].split(" ")])[:2].upper(), className="mav", style={"background": m["av"]}),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.Span(f"@{m['u']}", className="member-tag"),
                                                                            html.Span("next", className="pill gold mini-pill") if m.get("next") else None,
                                                                            html.Span("you", className="pill brand mini-pill") if m.get("me") else None,
                                                                        ],
                                                                        className="member-top",
                                                                    ),
                                                                    html.Div(m["n"], className="meta-sub"),
                                                                ],
                                                            ),
                                                        ],
                                                    )
                                                ]
                                            ),
                                            html.Td(status_pill(m["status"])),
                                            html.Td(html.Span(score_band(m["score"])[0], className=f"pill {score_band(m['score'])[1]}")),
                                            html.Td([icon("check"), html.Span(" Clear", className="muted")], className="origin-ok"),
                                            html.Td(m["on_time"], className="mono"),
                                            html.Td(m["circles"], className="mono"),
                                            html.Td(m["joined"], className="muted"),
                                            html.Td(html.Button("View", className="btn btn-sm btn-ghost"), style={"textAlign": "right"}),
                                        ]
                                    )
                                    for m in rows
                                ]
                            ),
                        ],
                    )
                ],
            ),
        ],
    )
