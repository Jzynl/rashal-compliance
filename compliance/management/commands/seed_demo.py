"""
Demo data.

Every date is generated as today +/- N days, never typed. A demo where
the arithmetic does not add up undermines confidence in a system that is
entirely about dates -- so the seed is always coherent, whenever it runs.
"""

import random
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from compliance.models import ComplianceType, CompliancePeriod, StationCompliance
from core import roles
from stations.models import Station

TYPES = [
    ("EWURA", "EWURA", "Energy and Water Utilities Regulatory Authority", 12, "", [365, 180, 90, 30, 7, 0]),
    ("NEMC", "NEMC", "National Environment Management Council", 36, "", [365, 180, 90, 30, 0]),
    ("Fire and rescue", "FIRE", "Fire and Rescue Force", 12, "", [90, 30, 7, 0]),
    ("OSHA", "OSHA", "Occupational Safety and Health Authority", 12, "", [180, 90, 30, 7, 0]),
    ("TRA tax clearance", "TRA", "Tanzania Revenue Authority", 12, "", [365, 180, 90, 30, 0]),
    ("TRA taxpayer ID", "TIN", "Tanzania Revenue Authority", 0, "", []),
    ("WCF", "WCF", "Workers Compensation Fund", 12, "", [180, 90, 30, 0]),
    ("NSSF", "NSSF", "National Social Security Fund", 12, "", [180, 90, 30, 0]),
    ("TBS", "TBS", "Tanzania Bureau of Standards", 12, "", [180, 90, 30, 0]),
    ("Weights and measures", "WMA", "Weights and Measures Agency", 12, "", [180, 90, 30, 0]),
    ("Business licence", "BIZ", "Local Government Authority", 12, "", [180, 90, 30, 0]),
    ("Land rent", "LAND", "Ministry of Lands", 12, "", [180, 90, 30, 0]),
    ("Petroleum handling", "PET", "EWURA", 12, "", [180, 90, 30, 0]),
    ("Health and sanitation", "HEALTH", "Local Government Authority", 12, "", [180, 90, 30, 0]),
]

STATIONS = [
    # The 13 live Rashal stations.
    # Coordinates are district-centre approximations -- replace them with
    # each station's real GPS reading before the map goes in front of anyone.
    ("Itigi",       "RSH-ITG-01", "singida",  "Itigi",         -5.7000, 34.4833),
    ("Karatu",      "RSH-KRT-02", "arusha",   "Karatu",        -3.3333, 35.6667),
    ("Liwale",      "RSH-LWL-03", "lindi",    "Liwale",        -9.7667, 37.9333),
    ("Manyoni",     "RSH-MNY-04", "singida",  "Manyoni",       -5.7500, 34.8333),
    ("Masasi",      "RSH-MSS-05", "mtwara",   "Masasi",       -10.7167, 38.8000),
    ("Mkalama",     "RSH-MKL-06", "singida",  "Mkalama",       -4.4667, 34.8333),
    ("Mlimba",      "RSH-MLB-07", "morogoro", "Mlimba",        -8.8167, 35.8167),
    ("Nachingwea",  "RSH-NCH-08", "lindi",    "Nachingwea",   -10.3667, 38.7667),
    ("Newala",      "RSH-NWL-09", "mtwara",   "Newala",       -10.9500, 39.3000),
    ("Ruangwa",     "RSH-RNG-10", "lindi",    "Ruangwa",      -10.0500, 38.9500),
    ("Shelui",      "RSH-SHL-11", "singida",  "Iramba",        -4.3000, 34.3000),
    ("Singida",     "RSH-SGD-12", "singida",  "Singida Urban", -4.8167, 34.7500),
    ("Utete",       "RSH-UTT-13", "pwani",    "Rufiji",        -8.0167, 38.7667),
]

# Days-until-expiry targets, weighted to look like a real, mostly-compliant
# company: a lot of quiet white cards, a handful of genuine problems.
# Cycling a flat list instead gives every station an expired licence, which
# paints the whole map one colour and teaches the eye nothing.
BAND_WEIGHTS = [
    # (days-until-expiry range, weight)
    ((366, 900), 60),   # safe    -> white, needs no attention
    ((181, 365), 23),   # active  -> green
    ((91, 180), 10),    # warning -> orange tint
    ((1, 90), 5),       # critical-> strong orange
    ((-60, -3), 2),     # expired -> filled burnt orange
]


class Command(BaseCommand):
    help = "Load demo stations, compliance types, users and periods."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Delete existing demo data first.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)
        today = timezone.localdate()

        if options["flush"]:
            CompliancePeriod.objects.all().delete()
            StationCompliance.objects.all().delete()
            ComplianceType.objects.all().delete()
            Station.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write("Flushed.")

        for name in roles.ALL_ROLES:
            Group.objects.get_or_create(name=name)

        # -- types (signals fan these out across stations) ----------------
        for order, (name, code, authority, months, _icon, thresholds) in enumerate(TYPES):
            ComplianceType.objects.update_or_create(
                short_code=code,
                defaults={
                    "name": name,
                    "issuing_authority": authority,
                    "default_validity_months": months or 12,
                    "is_perpetual": months == 0,
                    "alert_thresholds": thresholds,
                    "sort_order": order * 10,
                    "requires_payment_receipt": code not in {"TIN"},
                },
            )
        self.stdout.write(f"Compliance types: {ComplianceType.objects.count()}")

        for name, code, region, district, lat, lng in STATIONS:
            Station.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "region": region, "district": district,
                    "latitude": lat, "longitude": lng,
                    "commissioned_on": today - relativedelta(years=random.randint(3, 9)),
                },
            )
        self.stdout.write(f"Stations: {Station.objects.count()}")

        # Backfill: types created before stations, or vice versa.
        pairs = [
            StationCompliance(station=s, compliance_type=t)
            for s in Station.objects.filter(is_active=True)
            for t in ComplianceType.objects.filter(is_active=True)
        ]
        StationCompliance.objects.bulk_create(pairs, ignore_conflicts=True)
        self.stdout.write(f"Obligations: {StationCompliance.objects.count()}")

        # -- users --------------------------------------------------------
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@rashal.co.tz", "first_name": "Rashal",
                      "last_name": "Admin", "is_staff": True, "is_superuser": True,
                      "phone": "0754000001", "job_title": "Administrator"},
        )
        if created:
            admin.set_password("ChangeMe2026!")
            admin.save()
        admin.groups.add(Group.objects.get(name=roles.SUPER_ADMIN))

        officer, created = User.objects.get_or_create(
            username="officer",
            defaults={"email": "compliance@rashal.co.tz", "first_name": "Asha",
                      "last_name": "Mrisho", "phone": "0754000002",
                      "job_title": "Compliance officer", "is_staff": False},
        )
        if created:
            officer.set_password("ChangeMe2026!")
            officer.save()
        officer.groups.add(Group.objects.get(name=roles.COMPLIANCE_OFFICER))

        manager_group = Group.objects.get(name=roles.STATION_MANAGER)
        # Managers are scoped by region, which is the real shape here:
        # five stations sit in Singida, three in Lindi, two in Mtwara.
        managers = [
            ("john", "John", "Mushi", "0754000003", ["RSH-SGD-12"]),
            ("neema", "Neema", "Kileo", "0754000004",
             ["RSH-ITG-01", "RSH-MNY-04", "RSH-MKL-06", "RSH-SHL-11", "RSH-SGD-12"]),
            ("juma", "Juma", "Said", "0754000005",
             ["RSH-LWL-03", "RSH-NCH-08", "RSH-RNG-10"]),
            ("amina", "Amina", "Hassan", "0754000006",
             ["RSH-MSS-05", "RSH-NWL-09"]),
            ("baraka", "Baraka", "Mwita", "0754000007", ["RSH-KRT-02"]),
        ]
        for username, first, last, phone, codes in managers:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@rashal.co.tz", "first_name": first,
                          "last_name": last, "phone": phone,
                          "job_title": "Station manager"},
            )
            if created:
                user.set_password("ChangeMe2026!")
                user.save()
            user.groups.add(manager_group)
            user.stations.set(Station.objects.filter(code__in=codes))

        self.stdout.write(f"Users: {User.objects.count()}")

        # -- periods ------------------------------------------------------
        created_periods = 0
        for index, sc in enumerate(StationCompliance.objects.with_related()):
            ctype = sc.compliance_type

            if ctype.is_perpetual:
                period = CompliancePeriod.objects.create(
                    station_compliance=sc,
                    status=CompliancePeriod.Status.ACTIVE,
                    is_current=True,
                    start_date=today - relativedelta(years=5),
                    expiry_date=today + relativedelta(years=50),
                    certificate_number=f"TIN-{100000 + index}",
                    submitted_by=officer,
                )
                sc.current_period = period
                sc.save(update_fields=["current_period"])
                created_periods += 1
                continue

            spans, weights = zip(*BAND_WEIGHTS)
            low, high = random.choices(spans, weights=weights, k=1)[0]
            target = random.randint(low, high)

            # ~5% of obligations are mid-renewal.
            if index % 21 == 5:
                lapsed = CompliancePeriod.objects.create(
                    station_compliance=sc,
                    status=CompliancePeriod.Status.EXPIRED,
                    is_current=True,
                    start_date=today - relativedelta(months=14),
                    expiry_date=today - timedelta(days=28),
                    certificate_number=f"{ctype.short_code}/{today.year - 1}/{200 + index}",
                    amount_paid=random.choice([380000, 420000, 450000]),
                    paid_at=timezone.now() - timedelta(days=430),
                    submitted_by=officer,
                )
                sc.current_period = lapsed
                sc.save(update_fields=["current_period"])
                CompliancePeriod.objects.create(
                    station_compliance=sc,
                    status=CompliancePeriod.Status.PROCESSING,
                    is_current=False,
                    processing_started_on=today - timedelta(days=random.randint(5, 70)),
                    amount_paid=random.choice([450000, 500000]),
                    paid_at=timezone.now() - timedelta(days=20),
                    payment_reference=f"REF{random.randint(10000, 99999)}",
                    submitted_by=officer,
                )
                created_periods += 2
                continue

            expiry = today + timedelta(days=target)
            months = ctype.default_validity_months
            start = expiry - relativedelta(months=months) + timedelta(days=1)

            status = (
                CompliancePeriod.Status.EXPIRED if target < 0
                else CompliancePeriod.Status.ACTIVE
            )
            current = CompliancePeriod.objects.create(
                station_compliance=sc,
                status=status,
                is_current=True,
                start_date=start,
                expiry_date=expiry,
                certificate_number=f"{ctype.short_code}/{start.year}/{300 + index}",
                amount_paid=random.choice([180000, 250000, 380000, 420000, 450000]),
                paid_at=timezone.make_aware(
                    timezone.datetime.combine(start - timedelta(days=5),
                                              timezone.datetime.min.time())
                ),
                submitted_by=officer,
            )
            sc.current_period = current
            sc.save(update_fields=["current_period"])
            created_periods += 1

            # Two superseded periods behind it, so History has something in it.
            for back in (1, 2):
                hist_expiry = start - timedelta(days=1) - relativedelta(months=months * (back - 1))
                hist_start = hist_expiry - relativedelta(months=months) + timedelta(days=1)
                CompliancePeriod.objects.create(
                    station_compliance=sc,
                    status=CompliancePeriod.Status.SUPERSEDED,
                    is_current=False,
                    start_date=hist_start,
                    expiry_date=hist_expiry,
                    certificate_number=f"{ctype.short_code}/{hist_start.year}/{100 + index}",
                    amount_paid=random.choice([150000, 200000, 340000, 380000]),
                    submitted_by=officer,
                )
                created_periods += 1

        self.stdout.write(self.style.SUCCESS(
            f"Periods: {created_periods}. Demo ready.\n"
            f"  admin / ChangeMe2026!   (super admin)\n"
            f"  officer / ChangeMe2026! (compliance officer)\n"
            f"  john / ChangeMe2026!    (manager, Singida only)\n"
            f"  neema / ChangeMe2026!   (manager, 5 Singida-region stations)\n"
            f"  juma / ChangeMe2026!    (manager, 3 Lindi-region stations)"
        ))
