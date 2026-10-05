"""Local catalog for the Join Ajo screen.

These circles are UI fixtures for the signed-in stub profiles. They are not
loaded from the git-ignored persona file, so the screen still renders in CI.
Brum Builders and Sister Circle Ajo match the circles from the persona fixture:
``admintest`` created them, and ``membertest`` is a member of both.
"""

from __future__ import annotations

from datetime import date

GROUPS: list[dict] = [
    {
        "id": "brum-builders",
        "name": "Brum Builders",
        "city": "Birmingham",
        "contribution": 500,
        "frequency": "monthly",
        "member_count": 10,
        "capacity": 10,
        "pool": 5000,
        "status": "active",
        "start": "2025-09-01",
        "end": "2026-07-28",
        "creator_role": "admin",
        "member_roles": ["admin", "member"],
        "summary": "Monthly builders' circle. The pot is already full.",
        "avatars": [("OT", "#4F6AA3"), ("EN", "#4E5FA8"), ("AO", "#B88A2A"), ("KA", "#B0392E")],
        "roster": [
            ("Ola T.", "Admin"),
            ("Ebuka N.", "Member"),
            ("Abel O.", "Member"),
            ("Kemi A.", "Member"),
            ("Chidi M.", "Member"),
        ],
    },
    {
        "id": "sister-circle",
        "name": "Sister Circle Ajo",
        "city": "Birmingham",
        "contribution": 200,
        "frequency": "monthly",
        "member_count": 8,
        "capacity": 10,
        "pool": 1600,
        "status": "active",
        "start": "2025-11-01",
        "end": "2026-09-01",
        "creator_role": "admin",
        "member_roles": ["admin", "member"],
        "summary": "Sisters' savings circle started in Birmingham.",
        "avatars": [("AT", "#7C5AA8"), ("FS", "#2F7A4C"), ("NP", "#4A89B0")],
        "roster": [
            ("Amina T.", "Admin"),
            ("Funke S.", "Member"),
            ("Ngozi P.", "Member"),
        ],
    },
    {
        "id": "eastside-friends",
        "name": "Eastside Friends",
        "city": "Birmingham",
        "contribution": 100,
        "frequency": "monthly",
        "member_count": 6,
        "capacity": 8,
        "pool": 600,
        "status": "open",
        "start": "2026-01-15",
        "end": "2026-09-15",
        "creator_role": None,
        "member_roles": ["admin"],
        "summary": "Open neighbourhood circle. The creator is not one of the test profiles.",
        "avatars": [("YK", "#1B6E89"), ("LR", "#B88A2A")],
        "roster": [("Yara K.", "Admin"), ("Leo R.", "Member")],
    },
    {
        "id": "coventry-savers",
        "name": "Coventry Savers",
        "city": "Coventry",
        "contribution": 150,
        "frequency": "monthly",
        "member_count": 4,
        "capacity": 12,
        "pool": 600,
        "status": "open",
        "start": "2026-04-01",
        "end": "2027-04-01",
        "creator_role": None,
        "member_roles": [],
        "summary": "Open circle for Coventry members. Eight places are still free.",
        "avatars": [("MS", "#0E4F47"), ("JD", "#B0392E")],
        "roster": [("Maya S.", "Admin"), ("Jon D.", "Member")],
    },
    {
        "id": "leeds-family-pot",
        "name": "Leeds Family Pot",
        "city": "Leeds",
        "contribution": 250,
        "frequency": "monthly",
        "member_count": 3,
        "capacity": 10,
        "pool": 750,
        "status": "open",
        "start": "2026-05-01",
        "end": "2027-03-01",
        "creator_role": None,
        "member_roles": [],
        "summary": "Family pot with seven places left.",
        "avatars": [("HA", "#7C5AA8")],
        "roster": [("Hana A.", "Admin")],
    },
    {
        "id": "handsworth-traders",
        "name": "Handsworth Traders",
        "city": "Birmingham",
        "contribution": 75,
        "frequency": "weekly",
        "member_count": 9,
        "capacity": 12,
        "pool": 675,
        "status": "open",
        "start": "2026-03-02",
        "end": "2026-08-24",
        "creator_role": None,
        "member_roles": [],
        "summary": "Weekly traders' circle with a short cycle.",
        "avatars": [("TB", "#2A6E89"), ("CW", "#2F7A4C"), ("PR", "#4F6AA3")],
        "roster": [("Tobi B.", "Admin"), ("Chi W.", "Member")],
    },
    {
        "id": "manchester-market",
        "name": "Manchester Market Ajo",
        "city": "Manchester",
        "contribution": 150,
        "frequency": "monthly",
        "member_count": 10,
        "capacity": 10,
        "pool": 1500,
        "status": "completed",
        "start": "2024-01-08",
        "end": "2024-11-04",
        "creator_role": None,
        "member_roles": [],
        "summary": "Finished market circle. It is closed to new members.",
        "avatars": [("SK", "#39495A")],
        "roster": [("Sade K.", "Admin")],
    },
    {
        "id": "wolverhampton-sisters",
        "name": "Wolverhampton Sisters",
        "city": "Wolverhampton",
        "contribution": 80,
        "frequency": "monthly",
        "member_count": 8,
        "capacity": 8,
        "pool": 640,
        "status": "completed",
        "start": "2024-02-01",
        "end": "2024-10-01",
        "creator_role": "admin",
        "member_roles": ["admin", "member"],
        "summary": "Completed circle created by the admin test profile.",
        "avatars": [("IF", "#7C5AA8"), ("BN", "#B88A2A")],
        "roster": [("Ife F.", "Admin"), ("Bisi N.", "Member")],
    },
]

GROUP_BY_ID = {group["id"]: group for group in GROUPS}
ACTION_ORDER = ("view", "invite", "manage", "join")
ACTION_LABELS = {
    "view": "View details",
    "invite": "Invite Member",
    "manage": "Manage Members",
    "join": "Join",
}
STATUS_FILTERS = ("all", "active", "completed", "open", "managed")


def group_by_id(group_id: str) -> dict | None:
    if not isinstance(group_id, str):
        return None
    return GROUP_BY_ID.get(group_id)


def viewer_is_creator(group: dict, role: str | None) -> bool:
    """True only when this signed-in role created the circle."""
    creator = group.get("creator_role")
    return bool(creator) and creator == role


def viewer_is_member(group: dict, role: str | None, joined_ids: list[str] | None) -> bool:
    if role and role in group.get("member_roles", []):
        return True
    return bool(joined_ids) and group["id"] in joined_ids


def displayed_member_count(group: dict, role: str | None, joined_ids: list[str] | None) -> int:
    count = int(group["member_count"])
    already = role in group.get("member_roles", [])
    if group["id"] in (joined_ids or []) and not already:
        count += 1
    return count


def can_join(group: dict, role: str | None, joined_ids: list[str] | None) -> bool:
    if viewer_is_member(group, role, joined_ids):
        return False
    if group.get("status") != "open":
        return False
    return displayed_member_count(group, role, joined_ids) < int(group["capacity"])


def card_actions(group: dict, role: str | None, joined_ids: list[str] | None = None) -> list[str]:
    """Buttons on one card row, in the order the screen renders them."""
    actions = ["view", "invite"]
    if viewer_is_creator(group, role):
        actions.append("manage")
    if can_join(group, role, joined_ids):
        actions.append("join")
    return actions


def role_label(group: dict, role: str | None, joined_ids: list[str] | None) -> str:
    if viewer_is_creator(group, role):
        return "Admin"
    if viewer_is_member(group, role, joined_ids):
        return "Member"
    return "Not joined"


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _overlaps(group: dict, start: date | None, end: date | None) -> bool:
    group_start = date.fromisoformat(group["start"])
    group_end = date.fromisoformat(group["end"])
    if start is not None and group_end < start:
        return False
    if end is not None and group_start > end:
        return False
    return True


def filter_groups(
    role: str | None,
    search: str = "",
    status: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Search, status filter, and date-range overlap. Catalog order is kept."""
    chosen = status if status in STATUS_FILTERS else "all"
    needle = search.strip().lower() if isinstance(search, str) else ""
    start = _parse_date(date_from)
    end = _parse_date(date_to)
    if start and end and start > end:
        start, end = end, start

    matched = []
    for group in GROUPS:
        if chosen == "managed" and not viewer_is_creator(group, role):
            continue
        if chosen in {"active", "completed", "open"} and group["status"] != chosen:
            continue
        if needle and needle not in group["name"].lower() and needle not in group["city"].lower():
            continue
        if not _overlaps(group, start, end):
            continue
        matched.append(group)
    return matched
