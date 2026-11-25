from django.db import migrations


def load(apps, schema_editor):
    from audit.seeding import seed_checklists
    seed_checklists(apps)


def unload(apps, schema_editor):
    # Non-destructive reverse: leave seeded data in place.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_checklistsection_checklisttemplate_checklistitem_and_more"),
    ]

    operations = [
        migrations.RunPython(load, unload),
    ]
