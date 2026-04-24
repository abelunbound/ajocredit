from dash import html

ICONS = {
    "home": "bi bi-house-door",
    "circles": "bi bi-diagram-2",
    "wallet": "bi bi-wallet2",
    "user": "bi bi-person",
    "shield": "bi bi-shield",
    "bolt": "bi bi-lightning",
    "search": "bi bi-search",
    "bell": "bi bi-bell",
    "spark": "bi bi-stars",
    "plus": "bi bi-plus",
    "eyeoff": "bi bi-eye-slash",
    "lock": "bi bi-lock",
    "arrdn": "bi bi-arrow-down",
    "arrup": "bi bi-arrow-up",
    "dl": "bi bi-download",
    "check": "bi bi-check2",
    "flag": "bi bi-flag",
    "pound": "bi bi-currency-pound",
}


def icon(name: str, class_name: str = "icn"):
    icon_class = ICONS.get(name, ICONS["home"])
    return html.I(className=f"{icon_class} {class_name}".strip(), **{"aria-hidden": "true"})


def pill(text, style=""):
    return html.Span(text, className=f"pill {style}".strip())


def status_pill(status: str):
    s = status.lower()
    if s == "received":
        return pill("Received")
    if s == "receiving":
        return pill("Receiving", "brand")
    if s == "paid":
        return pill("Paid", "good")
    if s == "pending":
        return pill("Grace period", "gold")
    return pill(status)
