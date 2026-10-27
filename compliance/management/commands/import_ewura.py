"""
Import the EWURA licence register from the company spreadsheet.

Re-runnable: it updates what has changed and leaves the rest alone, so you
can drop in a newer copy of the sheet and run it again.

    python manage.py import_ewura EWURA_STATUS_2026.xlsx
    python manage.py import_ewura EWURA_STATUS_2026.xlsx --dry-run

Expected columns, from row 3 down:
    No | Station | PRL number | APRL number | Start date | End date
"""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from compliance.models import ComplianceType, CompliancePeriod, StationCompliance
from stations.models import Station

# Where a station sits, for any that the register introduces. Anything not
# listed is created as "Other" and reported, rather than being skipped.
REGIONS = {
    "SHELUI": ("singida", "Iramba"),
    "ITIGI": ("singida", "Itigi"),
    "RUANGWA": ("lindi", "Ruangwa"),
    "MAGUGU": ("manyara", "Babati"),
    "NEWALA": ("mtwara", "Newala"),
    "TANDAHIMBA": ("mtwara", "Tandahimba"),
    "MLIMBA": ("morogoro", "Mlimba"),
    "LIWALE": ("lindi", "Liwale"),
    "MANYONI": ("singida", "Manyoni"),
    "KARATU": ("arusha", "Karatu"),
    "MKALAMA": ("singida", "Mkalama"),
    "SINGIDA": ("singida", "Singida Urban"),
    "MASASI": ("mtwara", "Masasi"),
    "NACHINGWEA": ("lindi", "Nachingwea"),
    "UTETE": ("pwani", "Rufiji"),
}


def parse_date(value):
    """
    The register mixes real dates with text like '31/12/2025'. Accept both
    rather than dropping the row -- a licence missing because of a
    formatting slip is exactly the failure this system exists to prevent.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = "Import EWURA licences from the company spreadsheet."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the .xlsx register")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change without writing.")
        parser.add_argument("--sheet", default=None, help="Sheet name (default: first)")

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required:  pip install openpyxl")

        dry = options["dry_run"]
        wb = openpyxl.load_workbook(options["path"], data_only=True)
        ws = wb[options["sheet"]] if options["sheet"] else wb.worksheets[0]

        rows = []
        for raw in ws.iter_rows(min_row=1, values_only=True):
            if len(raw) < 6 or not raw[1]:
                continue
            index, name, prl, aprl, start, end = raw[:6]
            if not isinstance(index, int):      # header / title rows
                continue
            rows.append({
                "name": str(name).strip().title(),
                "key": str(name).strip().upper(),
                "prl": (str(prl).strip() if prl else ""),
                "aprl": (str(aprl).strip() if aprl else ""),
                "start": parse_date(start),
                "end": parse_date(end),
            })

        if not rows:
            raise CommandError("No data rows found. Expected station names in column B.")

        self.stdout.write(f"Read {len(rows)} licence row(s) from {options['path']}\n")

        with transaction.atomic():
            ewura = self._ensure_type(dry)
            created_st, updated_st = 0, 0
            imported, skipped = 0, 0
            warnings = []

            for row in rows:
                station, made = self._ensure_station(row, dry)
                if made:
                    created_st += 1
                    self.stdout.write(f"  + station  {row['name']}")

                if row["key"] not in REGIONS:
                    warnings.append(
                        f"{row['name']}: no region mapping, filed as 'Other'"
                    )

                if not row["start"] or not row["end"]:
                    skipped += 1
                    warnings.append(
                        f"{row['name']}: unreadable dates "
                        f"(start={row['start']!r} end={row['end']!r}) — skipped"
                    )
                    continue

                years = round((row["end"] - row["start"]).days / 365.25, 1)
                if years != 5.0:
                    warnings.append(
                        f"{row['name']}: licence runs {years} years, not 5 "
                        f"({row['start']} to {row['end']}) — check the register"
                    )
                if row["aprl"] in ("", "APRL/"):
                    warnings.append(f"{row['name']}: application number incomplete")

                if not dry:
                    self._import_period(station, ewura, row)
                imported += 1

            if dry:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{'Would import' if dry else 'Imported'} {imported} licence(s); "
            f"{created_st} new station(s); {skipped} skipped."
        ))

        if warnings:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Register needs attention:"))
            for w in warnings:
                self.stdout.write(f"  ! {w}")

        # Anything we hold that the register does not mention.
        listed = {r["key"] for r in rows}
        missing = [
            s.name for s in Station.objects.filter(is_active=True)
            if s.name.upper() not in listed
        ]
        if missing:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Active stations with no EWURA licence in this register: "
                + ", ".join(missing)
            ))

    def _ensure_type(self, dry):
        ewura, made = ComplianceType.objects.get_or_create(
            short_code="EWURA",
            defaults={
                "name": "EWURA petroleum retail licence",
                "issuing_authority": "Energy and Water Utilities Regulatory Authority",
                "default_validity_months": 60,
                "alert_thresholds": [365, 180, 90, 30, 7, 0],
                "requires_payment_receipt": True,
                "sort_order": 0,
            },
        )
        # The register shows five-year licences, so correct the default if it
        # is still the generic twelve months.
        if not made and ewura.default_validity_months != 60:
            self.stdout.write(
                f"  ~ EWURA validity {ewura.default_validity_months} -> 60 months"
            )
            if not dry:
                ewura.default_validity_months = 60
                ewura.save(update_fields=["default_validity_months"])
        return ewura

    def _ensure_station(self, row, dry):
        station = Station.objects.filter(name__iexact=row["name"]).first()
        if station:
            return station, False
        region, district = REGIONS.get(row["key"], ("other", ""))
        if dry:
            return Station(name=row["name"], code="(new)"), True
        station = Station.objects.create(
            name=row["name"],
            code=f"RSH-{row['key'][:3]}-{Station.objects.count() + 1:02d}",
            region=region,
            district=district,
        )
        return station, True

    def _import_period(self, station, ewura, row):
        sc, _ = StationCompliance.objects.get_or_create(
            station=station, compliance_type=ewura, label=""
        )

        note = f"EWURA register import. Application {row['aprl']}." if row["aprl"] else ""

        period = sc.periods.filter(certificate_number=row["prl"]).first()
        if period is None:
            period = CompliancePeriod(station_compliance=sc,
                                      certificate_number=row["prl"])

        period.start_date = row["start"]
        period.expiry_date = row["end"]
        period.notes = note
        period.status = (
            CompliancePeriod.Status.EXPIRED
            if row["end"] < timezone.localdate()
            else CompliancePeriod.Status.ACTIVE
        )

        # Anything currently marked current on this obligation steps aside.
        sc.periods.exclude(pk=period.pk).filter(is_current=True).update(
            is_current=False, status=CompliancePeriod.Status.SUPERSEDED
        )
        period.is_current = True
        period.save()

        sc.current_period = period
        sc.save(update_fields=["current_period"])