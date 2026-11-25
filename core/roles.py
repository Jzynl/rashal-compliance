"""
Role names. Groups are created by the bootstrap_roles command (run on every
deploy), so these strings exist in every database including a fresh one.

Rashal One keeps roles as Django Groups rather than a field on User, so one
person can hold several roles (a station manager who is also an auditor).
Each module decides which roles may see and write its data.
"""

# -- Compliance-era roles (unchanged) -------------------------------------
SUPER_ADMIN = "super_admin"
COMPLIANCE_OFFICER = "compliance_officer"
STATION_MANAGER = "station_manager"
AUDITOR = "auditor"

# -- Rashal One: people / payroll roles -----------------------------------
HR_MANAGER = "hr_manager"
PAYROLL_OFFICER = "payroll_officer"
EMPLOYEE = "employee"

ALL_ROLES = [
    SUPER_ADMIN,
    COMPLIANCE_OFFICER,
    STATION_MANAGER,
    AUDITOR,
    HR_MANAGER,
    PAYROLL_OFFICER,
    EMPLOYEE,
]

ROLE_LABELS = {
    SUPER_ADMIN: "Super admin",
    COMPLIANCE_OFFICER: "Compliance officer",
    STATION_MANAGER: "Station manager",
    AUDITOR: "Auditor",
    HR_MANAGER: "HR manager",
    PAYROLL_OFFICER: "Payroll officer",
    EMPLOYEE: "Employee",
}

# Roles that see every station in the COMPLIANCE module.
GLOBAL_SCOPE_ROLES = {SUPER_ADMIN, COMPLIANCE_OFFICER, AUDITOR}

# Roles allowed to create/edit compliance periods and upload documents.
WRITE_ROLES = {SUPER_ADMIN, COMPLIANCE_OFFICER, STATION_MANAGER}

# Roles that see every employee across the company (foundation / people).
HR_SCOPE_ROLES = {SUPER_ADMIN, HR_MANAGER, PAYROLL_OFFICER}
