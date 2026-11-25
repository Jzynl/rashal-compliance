"""
Create a retrenchment batch from a retrenchment payout file.

    python manage.py import_retrenchment --file "Retrenchment_Ruangwa_2026.xlsx" \
        --year 2026 --station Ruangwa

Reads the columns ID, Name, AccountNo, Amount, Bank, Branch, Description and
creates one RetrenchmentBatch with a payment per row. Amounts are taken exactly
as in the file -- severance is NOT calculated here. Use --dry-run to preview.
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from foundation.models import Employee
from payroll.models import RetrenchmentBatch, RetrenchmentPayment
from stations.models import Station


def norm(s):
    return " ".join(str(s or "").strip().upper().split())


def to_amount(v):
    if v in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return Decimal("0")


class Command(BaseCommand):
    help = "Create a retrenchment batch from a payout xlsx."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--station", help="Station name to attach (optional).")
        parser.add_argument("--title", default="Retrenchment benefits")
        parser.add_argument("--sheet", help="Worksheet name (default: first).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required: pip install openpyxl")

        wb = openpyxl.load_workbook(o["file"], data_only=True)
        ws = wb[o["sheet"]] if o["sheet"] else wb[wb.sheetnames[0]]

        station = None
        if o["station"]:
            station = Station.objects.filter(name__icontains=o["station"]).first()
            if not station:
                self.stdout.write(self.style.WARNING(
                    f"No station matched '{o['station']}' — batch left with no station."))

        emp_by_name = {norm(e.full_name): e for e in Employee.objects.all()}

        # Header row contains "Name" in column 2.
        header_row = None
        for r in range(1, min(ws.max_row, 10) + 1):
            if norm(ws.cell(r, 2).value) == "NAME":
                header_row = r
                break
        if header_row is None:
            raise CommandError("Could not find the Name header row.")

        rows = []
        description = o["title"]
        for r in range(header_row + 1, ws.max_row + 1):
            name = ws.cell(r, 2).value
            if not name or not str(name).strip():
                continue
            desc = ws.cell(r, 7).value
            rows.append({
                "name": str(name).strip(),
                "account": "" if ws.cell(r, 3).value is None else str(ws.cell(r, 3).value).strip(),
                "amount": to_amount(ws.cell(r, 4).value),
                "bank": "" if ws.cell(r, 5).value is None else str(ws.cell(r, 5).value).strip(),
                "branch": "" if ws.cell(r, 6).value is None else str(ws.cell(r, 6).value).strip(),
                "description": (str(desc).strip() if desc else ""),
            })
        if not rows:
            raise CommandError("No data rows found.")
        if rows[0]["description"]:
            description = rows[0]["description"]

        matched = 0
        with transaction.atomic():
            batch = RetrenchmentBatch(
                station=station, year=o["year"], title=o["title"], description=description)
            if not o["dry_run"]:
                batch.save()
            for row in rows:
                emp = emp_by_name.get(norm(row["name"]))
                if emp:
                    matched += 1
                if not o["dry_run"]:
                    RetrenchmentPayment.objects.create(
                        batch=batch, employee=emp, name=row["name"],
                        account_no=row["account"], amount=row["amount"],
                        bank=row["bank"], branch=row["branch"], description=row["description"])
            if o["dry_run"]:
                transaction.set_rollback(True)

        total = sum(r["amount"] for r in rows)
        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if o['dry_run'] else ''}Batch '{description}' — {len(rows)} payments, "
            f"total {total}, {matched} matched to employees."))
        if not o["dry_run"]:
            self.stdout.write(f"Open it at /payroll/retrenchment/{batch.pk}/")
