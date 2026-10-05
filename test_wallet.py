"""Early Payouts wallet page (#29)."""

from pages.data import CRUMBS
from pages.wallet import layout, quote_body


def _button_labels(node):
    labels = []
    class_name = getattr(node, "className", "") or ""
    if "btn" in class_name.split():
        for child in node.children or []:
            if isinstance(child, str):
                labels.append(child)
    for child in getattr(node, "children", None) or []:
        if not isinstance(child, str):
            labels.extend(_button_labels(child))
    return labels


def _text(node):
    if node is None or isinstance(node, (str, int, float)):
        return "" if node is None else str(node)
    children = getattr(node, "children", None)
    if children is None:
        return ""
    if isinstance(children, (str, int, float)):
        return str(children)
    parts = [_text(child) for child in children]
    return " ".join(part for part in parts if part)


def test_wallet_title_and_actions():
    page = layout()
    assert page.children[0].children[0].children[0].children == "EarlyPayout Wallet"
    labels = _button_labels(page.children[0])
    assert labels == ["Top up", "Withdraw", "Request EarlyPayout", "Statement"]
    request = page.children[0].children[1].children[2]
    assert request.id == "early-payout-request"


def test_available_early_payout_replaces_balance_label():
    text = _text(layout())
    assert "Available Early Payout" in text
    assert "Available balance" not in text
    assert "£1,500" in text
    assert "Paid into Brum Builders" in text


def test_breadcrumb_matches_page_title():
    assert CRUMBS["wallet"][-1] == "EarlyPayout Wallet"


def test_quote_stays_hidden_until_requested():
    waiting = _text(quote_body(False))
    assert "Quote" in waiting
    assert "£0 · waived" not in waiting
    shown = _text(quote_body(True))
    assert "£1,500" in shown
    assert "£0 · waived" in shown
    assert "You receive" in shown
    assert "local-preview" in shown
    assert "Nothing is paid" in shown


def test_request_callback_returns_the_preview_quote():
    from app_dash_web import app

    client = app.server.test_client()
    response = client.post(
        "/_dash-update-component",
        json={
            "output": "early-payout-quote.children",
            "outputs": [{"id": "early-payout-quote", "property": "children"}],
            "inputs": [{"id": "early-payout-request", "property": "n_clicks", "value": 1}],
            "changedPropIds": ["early-payout-request.n_clicks"],
            "state": [],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_data(as_text=True)
    assert "local-preview" in body
    assert "waived" in body
