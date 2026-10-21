"""Create and join an Ajo. Both require a verified email on the server."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clock import now as clock_now
from database import Circle, CircleMember, User, get_db
from email_verification import require_verified_email
from roles import ROLE_ADMIN, ROLE_MEMBER, grant_circle_role


class CircleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CircleResponse(BaseModel):
    circle_id: int
    name: str


class CircleMembership(BaseModel):
    circle_id: int
    name: str
    role: str


class CircleList(BaseModel):
    circles: list[CircleMembership]


def register_circle_routes(fastapi_app: FastAPI, get_current_user) -> None:
    @fastapi_app.get("/api/v1/circles", response_model=CircleList)
    def list_circles(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Circles this session belongs to. The role is the stored membership."""
        rows = (
            db.query(Circle, CircleMember)
            .join(CircleMember, CircleMember.circle_id == Circle.id)
            .filter(CircleMember.user_id == user.id)
            .order_by(Circle.id)
            .all()
        )
        return CircleList(
            circles=[
                CircleMembership(circle_id=circle.id, name=circle.name, role=membership.role)
                for circle, membership in rows
            ]
        )

    @fastapi_app.post("/api/v1/circles", response_model=CircleResponse, status_code=201)
    def create_circle(
        body: CircleRequest,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_verified_email(user)
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Enter a circle name.")
        when = clock_now()
        circle = Circle(name=name, created_by_user_id=user.id, created_at=when)
        db.add(circle)
        db.flush()
        # The creator is the admin. A role on the request is ignored.
        grant_circle_role(
            db,
            circle_id=circle.id,
            user_id=user.id,
            role=ROLE_ADMIN,
            actor_user_id=user.id,
            joined_at=when,
        )
        from audit import record_event

        record_event(
            db,
            action="ajo_created",
            actor_user_id=user.id,
            actor_role=ROLE_ADMIN,
            circle_id=circle.id,
            target_user_id=user.id,
        )
        db.commit()
        return CircleResponse(circle_id=circle.id, name=circle.name)

    @fastapi_app.post("/api/v1/circles/{circle_id}/join", response_model=CircleResponse)
    def join_circle(
        circle_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_verified_email(user)
        circle = db.get(Circle, circle_id)
        if circle is None:
            raise HTTPException(status_code=404, detail="Circle not found.")
        existing = (
            db.query(CircleMember)
            .filter(CircleMember.circle_id == circle.id, CircleMember.user_id == user.id)
            .one_or_none()
        )
        if existing is None:
            # Joining grants member. A role on the request is ignored.
            grant_circle_role(
                db,
                circle_id=circle.id,
                user_id=user.id,
                role=ROLE_MEMBER,
                actor_user_id=user.id,
                joined_at=clock_now(),
            )
            from audit import record_event

            record_event(
                db,
                action="ajo_joined",
                actor_user_id=user.id,
                actor_role=ROLE_MEMBER,
                circle_id=circle.id,
                target_user_id=user.id,
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        return CircleResponse(circle_id=circle.id, name=circle.name)
