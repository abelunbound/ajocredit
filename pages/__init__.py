from .autoloan import layout as autoloan_layout
from .circle import layout as circle_layout
from .credit import layout as credit_layout
from .dashboard import layout as dashboard_layout
from .members import layout as members_layout
from .payouts import layout as payouts_layout
from .home import layout as home_layout
from .signin import layout as signin_layout
from .getstarted import layout as getstarted_layout
from .getstarted import loading_layout as getstarted_loading_layout
from .getstarted import loading_uk_layout as getstarted_loading_uk_layout
from .getstarted import result_origin_layout as getstarted_result_origin_layout
from .getstarted import result_uk_layout as getstarted_result_uk_layout
from .wallet import layout as wallet_layout

__all__ = [
    "dashboard_layout",
    "home_layout",
    "signin_layout",
    "getstarted_layout",
    "getstarted_loading_layout",
    "getstarted_loading_uk_layout",
    "getstarted_result_origin_layout",
    "getstarted_result_uk_layout",
    "members_layout",
    "payouts_layout",
    "credit_layout",
    "autoloan_layout",
    "wallet_layout",
    "circle_layout",
]
