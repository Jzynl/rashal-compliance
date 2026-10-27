"""
Role names. Groups are created by accounts' data migration, so these
strings exist in every database including a fresh one.
"""

SUPER_ADMIN = "super_admin"
COMPLIANCE_OFFICER = "compliance_officer"
STATION_MANAGER = "station_manager"
AUDITOR = "auditor"

ALL_ROLES = [SUPER_ADMIN, COMPLIANCE_OFFICER, STATION_MANAGER, AUDITOR]

ROLE_LABELS = {
    SUPER_ADMIN: "Super admin",
    COMPLIANCE_OFFICER: "Compliance officer",
    STATION_MANAGER: "Station manager",
    AUDITOR: "Auditor",
}

# Roles that see every station.
GLOBAL_SCOPE_ROLES = {SUPER_ADMIN, COMPLIANCE_OFFICER, AUDITOR}

# Roles allowed to create/edit periods and upload documents.
WRITE_ROLES = {SUPER_ADMIN, COMPLIANCE_OFFICER, STATION_MANAGER}
