"""Injectable clock. Production always uses the wall clock.

``now()`` is the time provider the rest of the app should call. Tests move it
with ``freeze`` and ``advance``. A dev-only HTTP control can do the same only
when ``ALLOW_TEST_CLOCK`` is set on a loopback process whose ``AJO_ENV`` is
``local`` or ``dev``.

Any other process that sets the flag refuses to start. That includes
production, staging, and a deployed process that is not the test suite.
Production cannot move time even if the flag is set and even if a test-runner
variable is present.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Mapping

FLAG_NAME = "ALLOW_TEST_CLOCK"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
# Staging is treated like production: a deploy must not be able to move time.
PRODUCTION_ENVS = frozenset({"production", "prod", "staging", "live"})
DEV_ENVS = frozenset({"local", "dev"})


class ClockLocked(RuntimeError):
    """Raised when code tries to move time in an environment that forbids it."""


def _source(source: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if source is None else source


def _raw(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if value is None:
        return ""
    return str(value).strip()


def flag_enabled(source: Mapping[str, str] | None = None) -> bool:
    return _raw(_source(source), FLAG_NAME).lower() in TRUE_VALUES


def app_env(source: Mapping[str, str] | None = None) -> str:
    return _raw(_source(source), "AJO_ENV").lower()


def bind_host(source: Mapping[str, str] | None = None) -> str:
    """Return the configured bind host. An unset host is not loopback."""
    return _raw(_source(source), "DASH_HOST").lower()


def running_under_pytest(source: Mapping[str, str] | None = None) -> bool:
    return bool(_raw(_source(source), "PYTEST_CURRENT_TEST"))


def dev_control_allowed(source: Mapping[str, str] | None = None) -> bool:
    """True only for the local loopback dev control, never for a deploy."""
    if app_env(source) in PRODUCTION_ENVS:
        return False
    if app_env(source) not in DEV_ENVS:
        return False
    if not flag_enabled(source):
        return False
    return bind_host(source) in LOCAL_BIND_HOSTS


def clock_mutable(source: Mapping[str, str] | None = None) -> bool:
    """Whether ``advance``, ``freeze``, and ``reset`` may run.

    The test suite may move time. The dev control may move time on loopback.
    Production and staging never can, including when this process is pytest
    simulating those environments.
    """
    if app_env(source) in PRODUCTION_ENVS:
        return False
    if running_under_pytest(source):
        return True
    return dev_control_allowed(source)


def policy_problems(source: Mapping[str, str] | None = None) -> list[str]:
    """Reasons the process must exit because the clock flag is on illegally.

    An empty list means startup may continue. The flag being off is always fine.
    """
    if not flag_enabled(source):
        return []
    if dev_control_allowed(source):
        return []
    if running_under_pytest(source) and app_env(source) not in PRODUCTION_ENVS:
        return []

    env_name = app_env(source) or "(unset)"
    if app_env(source) in PRODUCTION_ENVS:
        return [
            f"AJO_ENV is {env_name!r}; the test clock cannot be enabled in "
            "production or staging."
        ]
    if app_env(source) in DEV_ENVS:
        host = bind_host(source) or "(unset)"
        return [
            f"DASH_HOST is {host}; the dev clock control requires an explicit "
            "bind of 127.0.0.1, localhost, or ::1."
        ]
    return [
        f"AJO_ENV is {env_name!r}; the test clock can be enabled only under "
        "pytest or on a local loopback dev process. A deploy must not set "
        f"{FLAG_NAME}."
    ]


def _fail(messages: list[str]) -> None:
    for line in messages:
        print(f"ERROR: {line}", file=sys.stderr)
    raise SystemExit(1)


def enforce_test_clock_policy(source: Mapping[str, str] | None = None) -> None:
    """Abort when the test clock is enabled outside tests and local dev.

    A disabled flag does not stop startup. Production, staging, and any other
    deploy that sets the flag exits. ``AJO_ENV=test`` with the flag set also
    exits unless this process is the test suite.
    """
    problems = policy_problems(source)
    if not problems:
        return
    _fail(
        [
            "ALLOW_TEST_CLOCK is enabled outside tests.",
            "The test clock must not run in a deploy. Production cannot move time.",
            "Refusing to start.",
            *problems,
        ]
    )


class Clock:
    """Wall clock plus an offset tests or the dev control can set."""

    def __init__(self) -> None:
        self._offset = timedelta(0)
        self._frozen: datetime | None = None
        self._lock = threading.Lock()

    def now(self, source: Mapping[str, str] | None = None) -> datetime:
        """UTC time. Locked environments ignore any freeze or offset."""
        if not clock_mutable(source):
            return datetime.now(timezone.utc)
        with self._lock:
            if self._frozen is not None:
                return self._frozen
            return datetime.now(timezone.utc) + self._offset

    def advance(
        self,
        delta: timedelta,
        source: Mapping[str, str] | None = None,
    ) -> datetime:
        if not isinstance(delta, timedelta):
            raise TypeError("advance() requires a timedelta.")
        self._require_mutable(source)
        with self._lock:
            if self._frozen is not None:
                self._frozen = self._frozen + delta
                return self._frozen
            self._offset += delta
            return datetime.now(timezone.utc) + self._offset

    def freeze(
        self,
        moment: datetime,
        source: Mapping[str, str] | None = None,
    ) -> datetime:
        if not isinstance(moment, datetime):
            raise TypeError("freeze() requires a datetime.")
        if moment.tzinfo is None:
            raise ValueError("freeze() requires a timezone-aware datetime.")
        self._require_mutable(source)
        moment = moment.astimezone(timezone.utc)
        with self._lock:
            self._frozen = moment
            return self._frozen

    def reset(self, source: Mapping[str, str] | None = None) -> datetime:
        self._require_mutable(source)
        with self._lock:
            self._frozen = None
            self._offset = timedelta(0)
            return datetime.now(timezone.utc)

    def clear_for_tests(self) -> None:
        """Drop any offset. Only the test suite may call this."""
        if not running_under_pytest():
            raise ClockLocked("The test clock cannot be cleared outside tests.")
        with self._lock:
            self._frozen = None
            self._offset = timedelta(0)

    def _require_mutable(self, source: Mapping[str, str] | None) -> None:
        if clock_mutable(source):
            return
        raise ClockLocked(
            "The test clock cannot be changed in this environment. "
            "Production and any non-test deploy always use the wall clock."
        )


_default_clock = Clock()
_clock: Clock = _default_clock


def now(source: Mapping[str, str] | None = None) -> datetime:
    """UTC now from the installed clock."""
    return _clock.now(source)


def advance(
    delta: timedelta,
    source: Mapping[str, str] | None = None,
) -> datetime:
    return _clock.advance(delta, source)


def freeze(
    moment: datetime,
    source: Mapping[str, str] | None = None,
) -> datetime:
    return _clock.freeze(moment, source)


def reset(source: Mapping[str, str] | None = None) -> datetime:
    return _clock.reset(source)


def install_clock(clock: Clock, source: Mapping[str, str] | None = None) -> None:
    """Replace the process clock. Refused in production and other locked envs."""
    global _clock
    if not clock_mutable(source):
        raise ClockLocked(
            "The test clock cannot be replaced in this environment. "
            "Production and any non-test deploy always use the wall clock."
        )
    if not hasattr(clock, "now"):
        raise TypeError("An installed clock must provide now().")
    _clock = clock


def restore_for_tests() -> None:
    """Put the built-in clock back and clear its offset. Tests only."""
    global _clock
    if not running_under_pytest():
        raise ClockLocked("The test clock cannot be restored outside tests.")
    _default_clock.clear_for_tests()
    _clock = _default_clock
