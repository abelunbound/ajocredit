"""Dash page for the email verification link.

The token is read from the URL fragment and removed from the address bar
before it is sent. It goes to the API only in the confirm POST body, and it
is not written to the application log.
"""

from __future__ import annotations

from dash import html

import frontend.dash_api as dash_api
from frontend.pages.password_flow import _detail_without_secrets

# Reads the fragment on /verify-email. Mail uses #token. #token= is accepted too.
CAPTURE_VERIFY_TOKEN_JS = """
function ajoCaptureVerifyToken(loc, hist) {
  var path = String((loc && loc.pathname) || "/");
  if (path.length > 1 && path.charAt(path.length - 1) === "/") path = path.slice(0, -1);
  var hash = String((loc && loc.hash) || "");
  var token = "";
  if (path === "/verify-email" && hash.length > 1) {
    var raw = hash.charAt(0) === "#" ? hash.slice(1) : hash;
    if (raw.indexOf("token=") !== -1) {
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
    } else {
      try { token = decodeURIComponent(raw); } catch (e3) { token = raw; }
    }
  }
  if (path === "/verify-email" && hash && hist && hist.replaceState) {
    var next = String(loc.pathname || "/") + String(loc.search || "");
    try { hist.replaceState(hist.state, "", next); } catch (e4) { /* keep the token in memory */ }
  }
  return token;
}
""".strip()

VERIFY_PAGE_BOOT_JS = (
    CAPTURE_VERIFY_TOKEN_JS
    + """
(function () {
  try {
    var token = ajoCaptureVerifyToken(window.location, window.history);
    if (token) window.__ajoVerifyToken = token;
  } catch (e) { /* do not log the address */ }
})();
"""
)

CLIENTSIDE_CAPTURE_VERIFY_TOKEN = """
function(hash, pathname) {
  if (pathname !== "/verify-email") {
    return window.dash_clientside.no_update;
  }
  var token = "";
  if (typeof window.__ajoVerifyToken === "string" && window.__ajoVerifyToken) {
    token = window.__ajoVerifyToken;
    window.__ajoVerifyToken = "";
  }
  if (!token && typeof window.ajoCaptureVerifyToken === "function") {
    try { token = window.ajoCaptureVerifyToken(window.location, window.history) || ""; }
    catch (e) { token = ""; }
  }
  if (!token && typeof hash === "string" && hash.length > 1 && window.ajoCaptureVerifyToken) {
    try {
      token = window.ajoCaptureVerifyToken({pathname: pathname, hash: hash, search: ""}, window.history) || "";
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


def verification_result(token: object) -> str:
    """Show the API detail. Do not invent expired versus used."""
    if not isinstance(token, str) or not token.strip():
        return "Open the verification link from your email."
    try:
        status, payload = dash_api.confirm_verification(token)
    except dash_api.ApiUnavailable:
        return dash_api.SERVICE_UNAVAILABLE
    if status in {200, 400, 422, 429}:
        shown = _detail_without_secrets(payload, token, "")
        if shown:
            return shown
        return "The email was not verified."
    if status == 0 or status >= 500:
        return dash_api.SERVICE_UNAVAILABLE
    return "The email was not verified."


def layout():
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
            html.H1("Confirm your email", className="auth-title"),
            html.Div(id="verify-message", className="auth-hint", children="Open the verification link from your email."),
            html.A("Sign in", href="/signin", className="auth-inline-btn"),
        ],
    )
