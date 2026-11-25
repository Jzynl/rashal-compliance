from django.db import migrations

# Entitlements read from the company's own leave sheets (ALLOWED column):
# Annual = 28, Sick = 5. Stored as editable defaults, not hardcoded policy.
SEED = [
    {"name": "Annual", "is_paid": True, "annual_entitlement_days": 28},
    {"name": "Sick", "is_paid": True, "annual_entitlement_days": 5},
]


def load(apps, schema_editor):
    LeaveType = apps.get_model("leave", "LeaveType")
    for row in SEED:
        LeaveType.objects.get_or_create(
            name=row["name"],
            defaults={
                "is_paid": row["is_paid"],
                "annual_entitlement_days": row["annual_entitlement_days"],
                "is_active": True,
            },
        )


def unload(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0002_leavebalance"),
    ]

    operations = [
        migrations.RunPython(load, unload),
    ]
