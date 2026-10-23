"""Forgot-password and reset-password screens for Dash.

The reset token is read from the URL fragment and removed from the address
bar before it is sent. It goes to the API only in the reset POST body, and
it is not written to the application log.
"""

from __future__ import annotations

from dash import dcc, html

import frontend.dash_api as dash_api

# Same sentence as password_reset.FORGOT_DETAIL. Kept here so the Dash process
# does not import the API database just to show the message.
NEUTRAL_FORGOT = "If an account exists for that email, a reset link is on its way."

# Reads #token= on /reset-password, then history.replaceState strips the fragment.
# The token is returned to the caller and is not logged.
CAPTURE_RESET_TOKEN_JS = """
function ajoCaptureResetToken(loc, hist) {
  var path = String((loc && loc.pathname) || "/");
  if (path.length > 1 && path.charAt(path.length - 1) === "/") path = path.slice(0, -1);
  var hash = String((loc && loc.hash) || "");
  var token = "";
  if (path === "/reset-password" && hash.indexOf("token=") !== -1) {
    var raw = hash.charAt(0) === "#" ? hash.slice(1) : hash;
    var pieces = raw.split("&");
    for (var i = 0; i < pieces.length; i += 1) {
      var pair = pieces[i].split("=");
      var key = pair[0] || "";
      try { key = decodeURIComponent(key); } catch (e) { key = pair[0] || ""; }
      if (key === "token") {
        var value = pair.slice(1).join("=");
        try { token = decodeURIComponent(value); } catch (e2) { token = value; }
      }
    }
  }
  if (path === "/reset-password" && hash && hist && hist.replaceState) {
    var next = String(loc.pathname || "/") + String(loc.search || "");
    try { hist.replaceState(hist.state, "", next); } catch (e3) { /* keep the token in memory */ }
  }
  return token;
}
""".strip()

RESET_PAGE_BOOT_JS = (
    CAPTURE_RESET_TOKEN_JS
    + """
(function () {
  try {
    var token = ajoCaptureResetToken(window.location, window.history);
    if (token) window.__ajoResetToken = token;
  } catch (e) { /* do not log the address */ }
})();
"""
)

# Runs once Dash is up, including when the head script already stripped the hash.
CLIENTSIDE_CAPTURE_RESET_TOKEN = """
function(hash, pathname) {
  if (pathname !== "/reset-password") {
    return window.dash_clientside.no_update;
  }
  var token = "";
  if (typeof window.__ajoResetToken === "string" && window.__ajoResetToken) {
    token = window.__ajoResetToken;
    window.__ajoResetToken = "";
  }
  if (!token && typeof window.ajoCaptureResetToken === "function") {
    try { token = window.ajoCaptureResetToken(window.location, window.history) || ""; }
    catch (e) { token = ""; }
  }
  if (!token && typeof hash === "string" && hash.indexOf("token=") !== -1 && window.ajoCaptureResetToken) {
    try {
      token = window.ajoCaptureResetToken({pathname: pathname, hash: hash, search: ""}, window.history) || "";
    } catch (e2) { token = ""; }
  }
  try {
    if (window.location && window.location.hash && window.history) {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
  } catch (e3) { /* address bar already clean */ }
  if (!token) return window.dash_clientside.no_update;
  return token;
}
"""


def forgot_message(email: object) -> str:
    """Message for the forgot form. Known and unknown addresses look the same."""
    if not isinstance(email, str) or not email.strip():
        return "Enter an email address."
    try:
        status, payload = dash_api.forgot_password(email.strip())
    except dash_api.ApiUnavailable:
        return dash_api.SERVICE_UNAVAILABLE
    if status == 429:
        return dash_api.safe_detail(payload, "Too many attempts. Try again later.")
    return NEUTRAL_FORGOT


def _detail_without_secrets(payload: object, token: str, password: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    if not isinstance(detail, str):
        return None
    text = detail.strip()
    if not text or len(text) > 180:
        return None
    if token and token in text:
        return None
    if password and password in text:
        return None
    if "bearer" in text.lower():
        return None
    return text


def reset_submission(token: object, password: object, confirm: object) -> tuple[str, str]:
    """Return ('signin', message) after success, or ('stay', message)."""
    if not isinstance(password, str) or not isinstance(confirm, str) or not password or not confirm:
        return "stay", "Enter and confirm a new password."
    if password != confirm:
        return "stay", "Passwords do not match."
    if not isinstance(token, str) or not token.strip():
        return "stay", "Open the reset link from your email."
    try:
        status, payload = dash_api.reset_password(token, password)
    except dash_api.ApiUnavailable:
        return "stay", dash_api.SERVICE_UNAVAILABLE
    if status == 200:
        shown = _detail_without_secrets(payload, token, password)
        return "signin", shown or "Your password has been reset. Sign in again."
    if status in {400, 422, 429}:
        shown = _detail_without_secrets(payload, token, password)
        if shown:
            return "stay", shown
        return "stay", "The password was not changed."
    if status == 0 or status >= 500:
        return "stay", dash_api.SERVICE_UNAVAILABLE
    return "stay", "The password was not changed."


def finish_reset(token: object, password: object, confirm: object) -> tuple[str, str]:
    """Submit the new password and drop the local session when the API accepts it."""
    outcome, message = reset_submission(token, password, confirm)
    if outcome == "signin":
        sid = None
        try:
            from flask import session

            sid = session.get("api_sid")
            session.clear()
        except RuntimeError:
            sid = None
        dash_api.VAULT.drop(sid)
    return outcome, message


def signed_in_email(store) -> str:
    """Email for the signed-in account. Blank when this session has none."""
    if store is None:
        return ""
    stored = store.get("email") if hasattr(store, "get") else ""
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    username = store.get("username") if hasattr(store, "get") else ""
    if isinstance(username, str):
        return dash_api.LOCAL_ACCOUNTS.get(username, "")
    return ""


def reset_layout():
    return html.Div(
        className="auth-screen signin-screen",
        children=[
            html.Div(
                className="auth-brand-row",
                children=[
                    html.Div("a", className="brandmark"),
                    html.Div("AjoCredit", className="auth-brand-name"),
                ],
            ),
            html.H1("Choose a new password", className="auth-title"),
            html.P(
                "Use the link from your email. It works once.",
                className="auth-hint",
            ),
            dcc.Input(
                id="reset-new-password",
                type="password",
                value="",
                placeholder="New password",
                autoComplete="new-password",
                className="auth-input",
            ),
            dcc.Input(
                id="reset-confirm-password",
                type="password",
                value="",
                placeholder="Confirm password",
                autoComplete="new-password",
                className="auth-input",
            ),
            html.Div(id="reset-error", className="auth-error"),
            html.Button(
                "Update password",
                id="reset-submit",
                n_clicks=0,
                type="button",
                className="auth-primary-btn",
            ),
        ],
    )
