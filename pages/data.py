ME = {"username": "kemi_a", "name": "Kemi A.", "city": "Birmingham"}

MEMBERS = [
    {"u": "ola_t", "n": "Ola T.", "pos": 1, "status": "received", "score": 818, "joined": "Sep 2024", "circles": 3, "on_time": "100%"},
    {"u": "ebuka_n", "n": "Ebuka N.", "pos": 2, "status": "received", "score": 779, "joined": "Sep 2024", "circles": 2, "on_time": "100%"},
    {"u": "abel_o", "n": "Abel O.", "pos": 3, "status": "receiving", "score": 824, "joined": "Sep 2024", "circles": 4, "on_time": "100%"},
    {"u": "kemi_a", "n": "Kemi A.", "pos": 4, "status": "paid", "score": 791, "joined": "Sep 2024", "circles": 2, "on_time": "100%"},
    {"u": "chidi_m", "n": "Chidi M.", "pos": 5, "status": "paid", "score": 765, "joined": "Oct 2024", "circles": 1, "on_time": "100%"},
    {"u": "daniel_k", "n": "Daniel K.", "pos": 8, "status": "pending", "score": 698, "joined": "Nov 2024", "circles": 1, "on_time": "94%"},
]

CIRCLE = {
    "name": "Brum Builders",
    "city": "Birmingham, UK",
    "amount": 500,
    "freq": "monthly",
    "size": 10,
    "pot": 5000,
    "month": 3,
    "next_date": "Apr 28",
}

TXNS = [
    {"label": "Brum Builders · April", "amount": "−£500", "date": "Apr 1", "status": "Settled"},
    {"label": "Referral bonus", "amount": "+£10", "date": "Mar 30", "status": "Settled"},
    {"label": "Brum Builders · March", "amount": "−£500", "date": "Mar 1", "status": "Settled"},
    {"label": "Payout · Brum Builders", "amount": "+£5,000", "date": "Aug 28", "status": "Queued"},
]

NAV = [
    ("home", "Dashboard", "home"),
    ("circle", "My Ajo", "circles"),
    ("members", "Members", "user"),
    ("payouts", "PayoutsTracker", "bolt"),
    ("credit", "FinHealth", "shield"),
    ("autoloan", "Delay Cover", "spark"),
    ("wallet", "EarlyPayouts", "wallet"),
]

CRUMBS = {
    "home": ["AjoFinance", "Dashboard"],
    "circle": ["AjoFinance", "My Ajo"],
    "members": ["AjoFinance", "Members"],
    "payouts": ["AjoFinance", "Payouts Tracker"],
    "credit": ["AjoFinance", "Me", "Financial Health Overview"],
    "autoloan": ["AjoFinance", "Safety", "Delay Cover"],
    "wallet": ["AjoFinance", "Me", "EarlyPayout Wallet"],
    "settings": ["AjoFinance", "Settings"],
    "dd-overview": ["AjoFinance", "Settings", "Complete profile"],
    "getstarted-uk-loading": ["AjoFinance", "Settings", "UK credit check"],
    "getstarted-4": ["AjoFinance", "Settings", "UK credit check"],
    "join": ["AjoFinance", "Join Ajo"],
}
