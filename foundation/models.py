"""
The foundation layer: Organisation, Department, Position and Employee.

Employee is the key new concept in Rashal One. It is deliberately SEPARATE
from accounts.User: a User is a login account, an Employee is a person on
payroll. Most employees (pump attendants, etc.) never log in, so they have an
Employee record and no User. Someone who logs in links their User to their
Employee with the optional one-to-one below.

Every field here is evidenced by the supplied company documents (payroll,
WCF register, statutory returns, leave registers, settlements). Nothing about
pay AMOUNTS or statutory RATES lives here -- those belong to the payroll and
statutory modules and stay configurable, never hardcoded.
"""

from django.conf import settings
from django.db import models

from core import roles as role_consts
from core.models import TimeStampedModel


class Organisation(TimeStampedModel):
    """The employing company. Normally a single row (Rashal Petroleum Ltd)."""

    name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=200, blank=True)
    tin = models.CharField("TIN", max_length=20, blank=True)
    postal_address = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(TimeStampedModel):
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE,
        related_name="departments", null=True, blank=True,
    )
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(TimeStampedModel):
    title = models.CharField(max_length=120)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        related_name="positions", null=True, blank=True,
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class EmployeeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_related(self):
        return self.select_related("station", "department", "position", "user")

    def for_user(self, user):
        """
        HR and payroll roles (and super admins) see every employee. A station
        manager sees only the employees at their own station(s). Everyone
        else sees none through this manager -- their own record is reached by
        self-service, not here.
        """
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_superuser or user.has_any_role(role_consts.HR_SCOPE_ROLES):
            return self
        station_ids = user.accessible_station_ids()
        if station_ids is None:
            return self
        if not station_ids:
            return self.none()
        return self.filter(station_id__in=station_ids)


class Employee(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class EmploymentCategory(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        TEMPORARY = "temporary", "Temporary"
        CONTRACT = "contract", "Contract"
        PROBATION = "probation", "Probation"

    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT,
        related_name="employees", null=True, blank=True,
    )

    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)

    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    national_id = models.CharField("National ID (NIDA)", max_length=30, blank=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)

    # Where they work.
    station = models.ForeignKey(
        "stations.Station", on_delete=models.SET_NULL,
        related_name="employees", null=True, blank=True,
        help_text="Leave blank for head-office staff.",
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        related_name="employees", null=True, blank=True,
    )
    position = models.ForeignKey(
        Position, on_delete=models.SET_NULL,
        related_name="employees", null=True, blank=True,
    )
    job_title = models.CharField(
        max_length=120, blank=True,
        help_text="Free-text title where no Position record is used.",
    )
    employment_category = models.CharField(
        max_length=20, choices=EmploymentCategory.choices, blank=True,
    )

    date_joined = models.DateField(null=True, blank=True, help_text="Employment start date.")
    date_left = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # The Employee <-> User link. Null for staff who never log in.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="employee", null=True, blank=True,
    )

    # Banking, for salary payments. Access-controlled; shown only to payroll/HR.
    bank_name = models.CharField(max_length=80, blank=True)
    bank_branch = models.CharField(max_length=80, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)

    # Statutory membership numbers (the amounts/rates live in the payroll module).
    nssf_number = models.CharField("NSSF / PF number", max_length=40, blank=True)
    nhif_number = models.CharField("NHIF number", max_length=40, blank=True)
    wcf_number = models.CharField("WCF number", max_length=40, blank=True)
    tin = models.CharField("Employee TIN", max_length=20, blank=True)

    objects = EmployeeQuerySet.as_manager()

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["station", "is_active"])]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def title_display(self):
        """Job title if set, else the linked Position's title, else blank."""
        if self.job_title:
            return self.job_title
        if self.position_id and self.position:
            return self.position.title
        return ""


class EmployeeCredential(TimeStampedModel):
    """
    A training course or a certification held by an employee. One model covers
    both via `kind`. Expiry is optional; when set, it drives a simple
    valid/expiring/expired status (no scoring, just dates).
    """

    class Kind(models.TextChoices):
        TRAINING = "training", "Training"
        CERTIFICATION = "certification", "Certification"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="credentials",
    )
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.TRAINING)
    title = models.CharField(max_length=160)
    provider = models.CharField(max_length=160, blank=True, help_text="Trainer or issuing body.")
    reference = models.CharField(max_length=80, blank=True, help_text="Certificate number, if any.")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-issue_date", "title"]

    def __str__(self):
        return f"{self.employee} — {self.title}"

    @property
    def status(self):
        """valid / expiring / expired / none — based on expiry_date only."""
        if not self.expiry_date:
            return "none"
        from datetime import date, timedelta
        today = date.today()
        if self.expiry_date < today:
            return "expired"
        if self.expiry_date <= today + timedelta(days=30):
            return "expiring"
        return "valid"
