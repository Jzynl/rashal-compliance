"""
Create a pay run from an NMB salary file.

    python manage.py import_payrun --file "OCT_SALARY_NMB_2026.xlsx" --year 2026 --month 10

Reads the seven NMB columns (Beneficiary_Name, Amount, Beneficiary_Account,
Payment Type, Destination, Narration, Ownreference) and creates one PayRun with
a line per row. Links each line to an employee where the name matches. Use
--dry-run to preview. Amounts are taken exactly as in the file -- nothing is
calculated.
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from foundation.models import Employee, Organisation
from payroll.models import PayLine, PayRun


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
    help = "Create a pay run from an NMB salary xlsx."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)
        parser.add_argument("--sheet", help="Worksheet name (default: first).")
        parser.add_argument("--no-create", action="store_true",
                            help="Skip people with no matching employee instead of creating them.")
        parser.add_argument("--company", help="Company name to assign created employees to (created if missing).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required: pip install openpyxl")

        wb = openpyxl.load_workbook(o["file"], data_only=True)
        ws = wb[o["sheet"]] if o["sheet"] else wb[wb.sheetnames[0]]

        emp_by_name = {norm(e.full_name): e for e in Employee.objects.all()}

        # Find the header row (the one containing Beneficiary_Name).
        header_row = None
        for r in range(1, min(ws.max_row, 10) + 1):
            if norm(ws.cell(r, 1).value) == "BENEFICIARY_NAME":
                header_row = r
                break
        if header_row is None:
            raise CommandError("Could not find the Beneficiary_Name header row.")

        rows = []
        for r in range(header_row + 1, ws.max_row + 1):
            name = ws.cell(r, 1).value
            if not name or not str(name).strip():
                continue
            rows.append({
                "name": str(name).strip(),
                "amount": to_amount(ws.cell(r, 2).value),
                "account": "" if ws.cell(r, 3).value is None else str(ws.cell(r, 3).value).strip(),
                "narration": (str(ws.cell(r, 6).value).strip() if ws.cell(r, 6).value else ""),
                "reference": (str(ws.cell(r, 7).value).strip() if ws.cell(r, 7).value else ""),
            })

        if not rows:
            raise CommandError("No data rows found.")

        reference = rows[0]["reference"] or ""
        if o.get("company"):
            org, _ = Organisation.objects.get_or_create(name=o["company"].strip())
        else:
            org = Organisation.objects.first()
        create = not o["no_create"]
        matched = 0      # linked to an employee that already existed
        created = 0      # new employee records created from this file
        acct_filled = 0  # existing employees whose bank account we filled in

        def resolve_employee(name, account):
            nonlocal matched, created, acct_filled
            key = norm(name)
            emp = emp_by_name.get(key)
            if emp:
                matched += 1
                fields = []
                # Fill in the bank account if we have one and theirs is blank.
                if account and not emp.bank_account_number:
                    emp.bank_account_number = account
                    fields.append("bank_account_number")
                    acct_filled += 1
                # Fill in the company if we were told one and theirs is blank.
                if org and emp.organisation_id is None:
                    emp.organisation = org
                    fields.append("organisation")
                if fields and not o["dry_run"]:
                    emp.save(update_fields=fields)
                return emp
            if not create:
                return None
            parts = str(name).split()
            first = parts[0] if parts else name
            last = parts[-1] if len(parts) > 1 else ""
            middle = " ".join(parts[1:-1]) if len(parts) > 2 else ""
            emp = Employee(organisation=org, first_name=first, middle_name=middle,
                           last_name=last, bank_account_number=account, is_active=True)
            if not o["dry_run"]:
                emp.save()
            emp_by_name[key] = emp
            created += 1
            return emp

        with transaction.atomic():
            run = PayRun(year=o["year"], month=o["month"], reference=reference)
            if not o["dry_run"]:
                run.save()
            for row in rows:
                emp = resolve_employee(row["name"], row["account"])
                if not o["dry_run"]:
                    PayLine.objects.create(
                        pay_run=run, employee=emp,
                        beneficiary_name=row["name"],
                        beneficiary_account=row["account"],
                        amount=row["amount"],
                        narration=row["narration"] if row["narration"] not in ("SALARY", "") else "",
                    )
            if o["dry_run"]:
                transaction.set_rollback(True)

        total = sum(r["amount"] for r in rows)
        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if o['dry_run'] else ''}Pay run {run} — {len(rows)} lines, total {total}."))
        self.stdout.write(
            f"Employees: {matched} already existed, {created} created, "
            f"{acct_filled} had their bank account filled in.")
        if not o["dry_run"]:
            self.stdout.write(f"Open it at /payroll/{run.pk}/")
