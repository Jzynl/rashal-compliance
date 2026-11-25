"""
The hub tile registry.

Rashal One is a modular monolith: one login lands the user on a hub of tiles,
one tile per module. This file is the single list of those tiles and decides,
per user, which ones appear and whether each is live yet.

A tile is a plain dict so templates can read it without extra machinery:

    key        short id, unique
    label      what the user sees
    description one line under the label
    icon       an emoji (kept trivial; swap for real icons later)
    url_name   Django url name to reverse, or None for a planned module
    status     "live"    -> clickable
               "planned" -> shown greyed, no link (so the roadmap is visible)
    roles      set of role names that may see the tile; None = any logged-in
               user. Super admins always see every tile.
    accent     palette key for the tile stripe (brand orange/green family)

Nothing here grants data access on its own -- each module still scopes its own
queries. The registry only decides what the launcher shows.
"""

from core import roles as r

MODULES = [
    {
        "key": "compliance",
        "label": "Compliance",
        "description": "Licences, permits and renewals across every station.",
        "icon": "\U0001F4CB",  # clipboard
        "url_name": "compliance:matrix",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.COMPLIANCE_OFFICER, r.STATION_MANAGER, r.AUDITOR},
        "accent": "orange",
    },
    {
        "key": "stations",
        "label": "Stations",
        "description": "The station directory and each station's record.",
        "icon": "⛽",  # fuel pump
        "url_name": "stations:list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.COMPLIANCE_OFFICER, r.STATION_MANAGER, r.AUDITOR},
        "accent": "green",
    },
    {
        "key": "people",
        "label": "People & Organisation",
        "description": "Employees, departments and positions across the company.",
        "icon": "\U0001F465",  # busts
        "url_name": "foundation:employee_list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.HR_MANAGER},
        "accent": "green",
    },
    {
        "key": "payroll",
        "label": "Payroll",
        "description": "Monthly salary runs and the NMB bank payment file.",
        "icon": "\U0001F4B0",  # money bag
        "url_name": "payroll:run_list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.PAYROLL_OFFICER},
        "accent": "orange",
    },
    {
        "key": "leave",
        "label": "Leave",
        "description": "Annual and sick leave registers.",
        "icon": "\U0001F4C5",  # calendar
        "url_name": "leave:balance_list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.HR_MANAGER},
        "accent": "green",
    },
    {
        "key": "audit",
        "label": "Audit",
        "description": "Station audits and findings. No scoring until a rule is confirmed.",
        "icon": "\U0001F50D",  # magnifier
        "url_name": "audit:audit_list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.AUDITOR, r.COMPLIANCE_OFFICER},
        "accent": "orange",
    },
    {
        "key": "incidents",
        "label": "Incidents",
        "description": "Report and track station incidents — fires, spills, theft, accidents.",
        "icon": "\U0001F6A8",  # rotating light
        "url_name": "incidents:list",
        "status": "live",
        "roles": {r.SUPER_ADMIN, r.COMPLIANCE_OFFICER, r.AUDITOR, r.STATION_MANAGER},
        "accent": "orange",
    },
    {
        "key": "setup",
        "label": "Setup",
        "description": "Users, roles and master data (admin).",
        "icon": "⚙️",  # gear
        "url_name": "admin:index",
        "status": "live",
        "roles": {r.SUPER_ADMIN},
        "accent": "green",
    },
]


def visible_modules(user):
    """Tiles this user may see, in registry order."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    visible = []
    for module in MODULES:
        allowed = module["roles"]
        if user.is_superuser or allowed is None or user.has_any_role(allowed):
            visible.append(module)
    return visible
