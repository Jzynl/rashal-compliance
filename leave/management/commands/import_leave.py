"""
Import leave balances from the company's Excel sheets.

    python manage.py import_leave --annual LEAVE_TAKEN_ALL_LOCATIONS_2026_OCT.xlsx \
                                  --sick   SICK_DAYS_HQ_OCT.xlsx --year 2026

By default it reads the LAST worksheet (latest month) of each file, matches
each person to an existing employee by name, and creates the employee if none
is found (so the import also fills the People module). Locations in the annual
sheet are matched to stations by name. Idempotent: re-running updates the same
balances instead of duplicating. Use --dry-run to preview without saving.
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from foundation.models import Employee, Organisation
from leave.models import LeaveBalance, LeaveType
from stations.models import Station

STATUS_MAP = {"paid": "paid", "confirmed": "confirmed"}


def norm(s):
    return " ".join(str(s or "").strip().upper().split())


def to_num(v):
    if v in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return Decimal("0")


class Command(BaseCommand):
    help = "Import annual and/or sick leave balances from the leave sheets."

    def add_arguments(self, parser):
        parser.add_argument("--annual", help="Path to the annual-leave xlsx.")
        parser.add_argument("--sick", help="Path to the sick-days xlsx.")
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--sheet-annual", help="Worksheet name (default: last).")
        parser.add_argument("--sheet-sick", help="Worksheet name (default: last).")
        parser.add_argument("--no-create", action="store_true",
                            help="Skip people with no matching employee instead of creating them.")
        parser.add_argument("--create-stations", action="store_true",
                            help="Create a station for any location that doesn't match an existing one.")
        parser.add_argument("--company", help="Company name to assign imported employees to (created if missing).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required: pip install openpyxl")

        if not o["annual"] and not o["sick"]:
            raise CommandError("Pass --annual and/or --sick.")

        self.openpyxl = openpyxl
        self.year = o["year"]
        self.create = not o["no_create"]
        self.create_stations = o["create_stations"]
        self.dry = o["dry_run"]
        if o.get("company"):
            self.org, _ = Organisation.objects.get_or_create(name=o["company"].strip())
        else:
            self.org = Organisation.objects.first()
        # Build a name -> employee map once.
        self.emp_by_name = {norm(e.full_name): e for e in Employee.objects.all()}
        self.stations = list(Station.objects.all())

        self.created_emp = 0
        self.created_station = 0
        self.unmatched_station = set()

        with transaction.atomic():
            if o["annual"]:
                self._import_annual(o["annual"], o["sheet_annual"])
            if o["sick"]:
                self._import_sick(o["sick"], o["sheet_sick"])
            if self.dry:
                self.stdout.write(self.style.WARNING("DRY RUN — rolling back."))
                transaction.set_rollback(True)

        if self.unmatched_station:
            self.stdout.write("Locations with no matching station (left as HQ/none): "
                              + ", ".join(sorted(self.unmatched_station)))
        self.stdout.write(self.style.SUCCESS(
            f"Done. Employees created: {self.created_emp}. "
            f"Stations created: {self.created_station}."))

    # -- helpers -----------------------------------------------------------
    def _last_sheet(self, wb, name):
        if name:
            return wb[name]
        return wb[wb.sheetnames[-1]]

    def _station_for(self, location):
        loc = norm(location)
        if loc in ("", "HQ", "HEAD OFFICE", "HEADQUARTERS"):
            return None
        for s in self.stations:
            if norm(s.name) == loc or loc in norm(s.name) or norm(getattr(s, "code", "")) == loc:
                return s
        if self.create_stations:
            s = self._make_station(location)
            if s:
                self.stations.append(s)
                self.created_station += 1
                return s
        self.unmatched_station.add(location)
        return None

    def _make_station(self, location):
        from stations.models import Station as S
        name = str(location).strip().title()
        # Build a unique code from the name.
        base = "".join(ch for ch in name.upper() if ch.isalnum())[:18] or "STN"
        code = base
        n = 1
        existing = {norm(getattr(s, "code", "")) for s in self.stations}
        while norm(code) in existing:
            n += 1
            code = f"{base[:16]}{n}"
        station = S(name=name, code=code, region=S.Region.OTHER, district=name)
        if not self.dry:
            station.save()
        return station

    def _employee(self, name, station):
        key = norm(name)
        emp = self.emp_by_name.get(key)
        if emp:
            # Fill in the company if we were told one and theirs is blank.
            if self.org and emp.organisation_id is None:
                emp.organisation = self.org
                if not self.dry:
                    emp.save(update_fields=["organisation"])
            return emp
        if not self.create:
            return None
        parts = str(name).split()
        first = parts[0] if parts else name
        last = parts[-1] if len(parts) > 1 else ""
        middle = " ".join(parts[1:-1]) if len(parts) > 2 else ""
        emp = Employee(organisation=self.org, first_name=first, middle_name=middle,
                       last_name=last, station=station, is_active=True)
        if not self.dry:
            emp.save()
        self.emp_by_name[key] = emp
        self.created_emp += 1
        return emp

    def _save_balance(self, emp, lt, allowed, t1, t2, status):
        if self.dry:
            return
        LeaveBalance.objects.update_or_create(
            employee=emp, leave_type=lt, year=self.year,
            defaults={"allowed": int(allowed), "taken_first": t1,
                      "taken_second": t2, "status": status},
        )

    # -- annual ------------------------------------------------------------
    def _import_annual(self, path, sheet):
        lt, _ = LeaveType.objects.get_or_create(
            name="Annual", defaults={"is_paid": True, "annual_entitlement_days": 28})
        ws = self._last_sheet(self.openpyxl.load_workbook(path, data_only=True), sheet)
        location = None
        n = 0
        for r in range(1, ws.max_row + 1):
            a = ws.cell(r, 1).value
            b = ws.cell(r, 2).value
            if a is None and b is None:
                continue
            a_txt = str(a).strip() if a else ""
            if a_txt == "" or norm(a_txt) in ("EMPLOYEE NAME", "LEAVE", "RASHAL LIMITED"):
                if "LEAVE" in norm(a_txt) or "RASHAL" in norm(a_txt) or norm(a_txt) == "EMPLOYEE NAME":
                    continue
            if b is None or str(b).strip() == "":
                # location header row
                if a_txt and norm(a_txt) not in ("EMPLOYEE NAME",):
                    location = a_txt
                continue
            # employee row
            station = self._station_for(location)
            emp = self._employee(a_txt, station)
            if not emp:
                continue
            allowed = to_num(b) or Decimal("28")
            t1 = to_num(ws.cell(r, 3).value)
            t2 = to_num(ws.cell(r, 4).value)
            status = STATUS_MAP.get(norm(ws.cell(r, 6).value).lower(), "")
            self._save_balance(emp, lt, allowed, t1, t2, status)
            n += 1
        self.stdout.write(f"Annual: processed {n} people from '{ws.title}'.")

    # -- sick --------------------------------------------------------------
    def _import_sick(self, path, sheet):
        lt, _ = LeaveType.objects.get_or_create(
            name="Sick", defaults={"is_paid": True, "annual_entitlement_days": 5})
        ws = self._last_sheet(self.openpyxl.load_workbook(path, data_only=True), sheet)
        n = 0
        for r in range(1, ws.max_row + 1):
            name = ws.cell(r, 2).value  # column B = NAMES
            allowed_cell = ws.cell(r, 3).value
            if not name or norm(name) in ("NAMES",):
                continue
            if allowed_cell in (None, ""):
                continue
            emp = self._employee(str(name).strip(), None)
            if not emp:
                continue
            allowed = to_num(allowed_cell) or Decimal("5")
            taken = to_num(ws.cell(r, 4).value)
            self._save_balance(emp, lt, allowed, taken, Decimal("0"), "")
            n += 1
        self.stdout.write(f"Sick: processed {n} people from '{ws.title}'.")
