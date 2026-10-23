"""Per-circle roles, checked on the server.

The client never supplies a role. A permission is allowed only when it is
listed in ``PERMISSIONS`` and the caller's stored role in that circle is in
the allow list. Anything else is denied, including an unknown permission and
a caller who is not a member of the circle.

``record_role_change`` writes the append-only audit log (#32) in the same
transaction. ``record_position_change`` does the same for a payout position.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.clock import now as clock_now
from backend.database import Circle, CircleMember, User, get_db

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER})

# permission -> roles that may do it. A missing permission is denied.
PERMISSIONS: dict[str, frozenset[str]] = {
    "circle.read": frozenset({ROLE_ADMIN, ROLE_MEMBER}),
    "payouts.read": frozenset({ROLE_ADMIN}),
    "roles.grant": frozenset({ROLE_ADMIN}),
}

CIRCLE_NOT_FOUND = "Circle not found."
MEMBER_NOT_FOUND = "Member not found."
LAST_ADMIN = "This circle needs an admin."
DENIED = {
    "circle.read": "You cannot open this circle.",
    "payouts.read": "You cannot open Payouts for this circle.",
    "roles.grant": "You cannot change roles in this circle.",
}
NOT_ALLOWED = "Not allowed."


@dataclass(frozen=True)
class RoleChange:
    """One role assignment. ``before`` is None the first time a role is granted."""

    circle_id: int
    user_id: int
    actor_user_id: int | None
    before: str | None
    after: str
    at: datetime


@dataclass(frozen=True)
class CircleAccess:
    """A signed-in user whose stored role in this circle allows the permission."""

    circle: Circle
    membership: CircleMember
    user: User


class RoleAssignment(BaseModel):
    """The new role for the target member. The caller's role is not in this body."""

    model_config = ConfigDict(extra="ignore")

    role: str = Field(min_length=1, max_length=16)


class CircleView(BaseModel):
    circle_id: int
    name: str
    role: str


class PayoutsView(BaseModel):
    circle_id: int
    name: str
    role: str


class RoleView(BaseModel):
    circle_id: int
    user_id: int
    role: str


def permission_allowed(permission: str, role: str | None) -> bool:
    """True only for a listed permission and a role in its allow list."""
    allowed = PERMISSIONS.get(permission)
    if not allowed or role is None:
        return False
    return role in allowed


def _actor_role(db: Session, circle_id: int, actor_user_id: int | None) -> str | None:
    """Role of the actor in this circle, including a membership not flushed yet.

    The session has autoflush off, so a role just granted in this transaction
    is still pending.
    """
    if actor_user_id is None:
        return None
    pending = list(db.new) + list(db.dirty)
    for obj in pending:
        if (
            isinstance(obj, CircleMember)
            and obj.circle_id == circle_id
            and obj.user_id == actor_user_id
        ):
            return obj.role
    actor = membership_for(db, circle_id=circle_id, user_id=actor_user_id)
    if actor is None:
        return None
    return actor.role


def record_role_change(db: Session, change: RoleChange) -> None:
    """Write the role change to the audit log. Do not commit here.

    Called in the same transaction as the role change, before the caller
    commits. ``before`` is None when the membership is new. ``after`` is the
    stored role. ``actor_user_id`` is who assigned it. There is no second
    writer at the call sites.
    """
    if change.after not in ROLES:
        raise ValueError(f"unknown role: {change.after}")
    if change.before is not None and change.before not in ROLES:
        raise ValueError(f"unknown role: {change.before}")
    from backend.audit import record_event

    record_event(
        db,
        action="role_changed",
        actor_user_id=change.actor_user_id,
        actor_role=_actor_role(db, change.circle_id, change.actor_user_id),
        circle_id=change.circle_id,
        target_user_id=change.user_id,
        before={"role": change.before},
        after={"role": change.after},
        at=change.at,
    )


def record_position_change(
    db: Session,
    *,
    circle_id: int,
    user_id: int,
    actor_user_id: int | None,
    before: int | None,
    after: int,
) -> None:
    """Write a payout-position change to the audit log. Do not commit here.

    Positions are integers. The members preview does not save positions; this
    is the server hook that records one when a later change calls it.
    """
    if before is not None and type(before) is not int:
        raise ValueError("position must be an integer")
    if type(after) is not int:
        raise ValueError("position must be an integer")
    from backend.audit import record_event

    record_event(
        db,
        action="payout_position_changed",
        actor_user_id=actor_user_id,
        actor_role=_actor_role(db, circle_id, actor_user_id),
        circle_id=circle_id,
        target_user_id=user_id,
        before={"position": before},
        after={"position": after},
    )


def grant_circle_role(
    db: Session,
    *,
    circle_id: int,
    user_id: int,
    role: str,
    actor_user_id: int | None,
    joined_at: datetime | None = None,
) -> CircleMember:
    """Store ``role`` for this user in this circle and notify the audit hook.

    An unchanged role does not call the hook. The caller commits.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    membership = (
        db.query(CircleMember)
        .filter(CircleMember.circle_id == circle_id, CircleMember.user_id == user_id)
        .one_or_none()
    )
    if membership is not None and membership.role == role:
        return membership
    before = None if membership is None else membership.role
    if membership is None:
        membership = CircleMember(
            circle_id=circle_id,
            user_id=user_id,
            role=role,
            joined_at=joined_at or clock_now(),
        )
        db.add(membership)
    else:
        membership.role = role
    record_role_change(
        db,
        RoleChange(
            circle_id=circle_id,
            user_id=user_id,
            actor_user_id=actor_user_id,
            before=before,
            after=role,
            at=clock_now(),
        ),
    )
    return membership


def membership_for(db: Session, *, circle_id: int, user_id: int) -> CircleMember | None:
    return (
        db.query(CircleMember)
        .filter(CircleMember.circle_id == circle_id, CircleMember.user_id == user_id)
        .one_or_none()
    )


def require_circle_permission(get_current_user, permission: str):
    """Dependency: signed-in user with ``permission`` in this path's circle.

    The role is read from ``circle_members``. Query strings, headers, and
    body fields are not read. No membership is a 404. A membership without
    the permission is a 403.
    """

    def dependency(
        circle_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CircleAccess:
        circle = db.get(Circle, circle_id)
        membership = membership_for(db, circle_id=circle_id, user_id=user.id)
        if circle is None or membership is None:
            raise HTTPException(status_code=404, detail=CIRCLE_NOT_FOUND)
        if not permission_allowed(permission, membership.role):
            raise HTTPException(status_code=403, detail=DENIED.get(permission, NOT_ALLOWED))
        return CircleAccess(circle=circle, membership=membership, user=user)

    return dependency


def register_role_routes(fastapi_app: FastAPI, get_current_user) -> None:
    read_circle = require_circle_permission(get_current_user, "circle.read")
    read_payouts = require_circle_permission(get_current_user, "payouts.read")
    grant_roles = require_circle_permission(get_current_user, "roles.grant")

    @fastapi_app.get("/api/v1/circles/{circle_id}", response_model=CircleView)
    def get_circle(access: CircleAccess = Depends(read_circle)):
        return CircleView(
            circle_id=access.circle.id,
            name=access.circle.name,
            role=access.membership.role,
        )

    @fastapi_app.get("/api/v1/circles/{circle_id}/payouts", response_model=PayoutsView)
    def get_payouts(access: CircleAccess = Depends(read_payouts)):
        return PayoutsView(
            circle_id=access.circle.id,
            name=access.circle.name,
            role=access.membership.role,
        )

    @fastapi_app.post(
        "/api/v1/circles/{circle_id}/members/{user_id}/role",
        response_model=RoleView,
    )
    def assign_member_role(
        circle_id: int,
        user_id: int,
        body: RoleAssignment,
        access: CircleAccess = Depends(grant_roles),
        db: Session = Depends(get_db),
    ):
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail="Role must be admin or member.")
        target = membership_for(db, circle_id=circle_id, user_id=user_id)
        if target is None:
            raise HTTPException(status_code=404, detail=MEMBER_NOT_FOUND)
        if target.role == ROLE_ADMIN and body.role != ROLE_ADMIN:
            admin_count = (
                db.query(CircleMember)
                .filter(
                    CircleMember.circle_id == circle_id,
                    CircleMember.role == ROLE_ADMIN,
                )
                .count()
            )
            if admin_count <= 1:
                raise HTTPException(status_code=409, detail=LAST_ADMIN)
        membership = grant_circle_role(
            db,
            circle_id=circle_id,
            user_id=user_id,
            role=body.role,
            actor_user_id=access.user.id,
        )
        db.commit()
        db.refresh(membership)
        return RoleView(circle_id=circle_id, user_id=user_id, role=membership.role)
