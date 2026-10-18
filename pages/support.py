"""Support Center.

FAQ answers are placeholder copy for a later review. The contact form checks
the fields and confirms on screen. It does not send email or SMS.
"""

from __future__ import annotations

from dash import dcc, html

SUPPORT_EMAIL = "support@ajo-platform.com"
NO_EMAIL_SENT = "Noted for this session. No email was sent."
SUBJECT_MAX = 120
MESSAGE_MAX = 2000

FAQS = (
    {
        "id": "what-is-ajo",
        "question": "What is Ajo and how does it work?",
        "answer": (
            "An Ajo is a rotating savings group. Members agree a contribution "
            "amount and a schedule, pay in together, and one member receives "
            "the pot each turn until the cycle is complete. AjoFinance shows "
            "your group, the roster, and whose turn is next."
        ),
    },
    {
        "id": "create-group",
        "question": "How do I create a new Ajo group?",
        "answer": (
            "A new group needs a name, a contribution amount, how often members "
            "pay, and the people you invite. You can review the circles you "
            "already belong to from My Ajo. Opening a live group is not switched "
            "on in this local build."
        ),
    },
    {
        "id": "contributions",
        "question": "How do I make contributions to my group?",
        "answer": (
            "Pay the amount your group agreed, on the date shown on your "
            "dashboard. Use Pay this month when a contribution is due. This "
            "local build does not take a payment."
        ),
    },
    {
        "id": "payout",
        "question": "How do I receive my payout?",
        "answer": (
            "Your payout arrives when it is your turn in the rotation. The "
            "group admin reviews it in Payouts Tracker and releases the pot. "
            "You can follow the queue from your group. This local build does "
            "not pay out real money."
        ),
    },
    {
        "id": "safety",
        "question": "Is my money safe on the platform?",
        "answer": (
            "You join groups with people you know, and the app shows who has "
            "paid and who is next. This milestone does not hold or move real "
            "money, so there is nothing stored here to withdraw."
        ),
    },
)

TOPICS = (
    ("account", "Account"),
    ("group", "Creating a group"),
    ("contribution", "Contributions"),
    ("payout", "Payouts"),
    ("safety", "Safety"),
    ("other", "Something else"),
)
TOPIC_VALUES = frozenset(value for value, _label in TOPICS)


def contact_reply(topic, subject, message) -> str:
    """Validate a support note. Nothing is emailed or stored as a ticket."""
    topic = topic.strip() if isinstance(topic, str) else ""
    subject = subject.strip() if isinstance(subject, str) else ""
    message = message.strip() if isinstance(message, str) else ""
    if topic not in TOPIC_VALUES:
        return "Choose a topic."
    if not subject:
        return "Enter a subject."
    if len(subject) > SUBJECT_MAX:
        return f"Keep the subject under {SUBJECT_MAX} characters."
    if not message:
        return "Enter a message."
    if len(message) > MESSAGE_MAX:
        return f"Keep the message under {MESSAGE_MAX} characters."
    return NO_EMAIL_SENT


def _faq_item(item):
    return html.Details(
        className="faq-item",
        children=[
            html.Summary(
                [
                    html.Span(item["question"], className="faq-q-text"),
                    html.I(className="bi bi-chevron-down faq-chevron", **{"aria-hidden": "true"}),
                ],
                className="faq-q",
            ),
            html.P(item["answer"], className="faq-a"),
        ],
    )


def _field(label, control):
    return html.Div(
        className="support-field",
        children=[
            html.Label(label, htmlFor=control.id, className="support-label"),
            control,
        ],
    )


def layout():
    return html.Div(
        className="stack support-page",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Support Center"),
                            html.P(
                                "Get help with your Ajo account and groups.",
                                className="sub",
                            ),
                        ]
                    )
                ],
            ),
            html.Section(
                className="support-block",
                children=[
                    html.H2("Frequently Asked Questions"),
                    html.Div(
                        className="card faq-list",
                        children=[_faq_item(item) for item in FAQS],
                    ),
                ],
            ),
            html.Section(
                className="support-block",
                children=[
                    html.H2("Contact Support"),
                    html.Div(
                        className="card support-contact-card",
                        children=[
                            html.Div(id="support-feedback", className="support-feedback"),
                            html.Div(
                                className="support-contact",
                                children=[
                                    html.Div(
                                        className="support-form",
                                        children=[
                                            _field(
                                                "Topic",
                                                dcc.Dropdown(
                                                    id="support-topic",
                                                    options=[
                                                        {"label": label, "value": value}
                                                        for value, label in TOPICS
                                                    ],
                                                    value=None,
                                                    placeholder="",
                                                    clearable=False,
                                                    searchable=False,
                                                    className="support-dropdown",
                                                ),
                                            ),
                                            _field(
                                                "Subject",
                                                dcc.Input(
                                                    id="support-subject",
                                                    type="text",
                                                    value="",
                                                    className="support-input",
                                                    maxLength=SUBJECT_MAX,
                                                    debounce=False,
                                                ),
                                            ),
                                            _field(
                                                "Message",
                                                dcc.Textarea(
                                                    id="support-message",
                                                    value="",
                                                    className="support-textarea",
                                                    maxLength=MESSAGE_MAX,
                                                ),
                                            ),
                                            html.Button(
                                                "Send message",
                                                id="support-send",
                                                n_clicks=0,
                                                type="button",
                                                className="btn btn-primary support-send",
                                            ),
                                        ],
                                    ),
                                    html.Aside(
                                        className="support-aside",
                                        children=[
                                            html.H3("Other Ways to Reach Us"),
                                            html.Div(
                                                [
                                                    html.I(
                                                        className="bi bi-envelope",
                                                        **{"aria-hidden": "true"},
                                                    ),
                                                    html.Span(
                                                        [
                                                            "Email: ",
                                                            html.Span(
                                                                SUPPORT_EMAIL,
                                                                className="support-email-address",
                                                            ),
                                                        ]
                                                    ),
                                                ],
                                                className="support-email",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
