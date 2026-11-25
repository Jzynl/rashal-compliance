"""
Idempotent seeding of the checklist templates from checklist_data.CHECKLISTS.

Safe to run repeatedly: it matches on natural keys (template name, section
title, item text) so re-running never duplicates and never touches audits or
responses already recorded. Works both inside a data migration (pass the
historical `apps`) and from the management command (pass nothing).
"""

from audit.checklist_data import CHECKLISTS


def seed_checklists(apps=None):
    if apps is None:
        from audit.models import ChecklistItem, ChecklistSection, ChecklistTemplate
    else:
        ChecklistTemplate = apps.get_model("audit", "ChecklistTemplate")
        ChecklistSection = apps.get_model("audit", "ChecklistSection")
        ChecklistItem = apps.get_model("audit", "ChecklistItem")

    created = {"templates": 0, "sections": 0, "items": 0}

    for tpl in CHECKLISTS:
        template, t_new = ChecklistTemplate.objects.get_or_create(
            name=tpl["name"],
            defaults={"description": tpl.get("description", ""), "order": tpl.get("order", 0)},
        )
        if t_new:
            created["templates"] += 1

        for s_order, sec in enumerate(tpl["sections"], start=1):
            section, s_new = ChecklistSection.objects.get_or_create(
                template=template, title=sec["title"],
                defaults={"label": sec.get("label", ""), "order": s_order},
            )
            if s_new:
                created["sections"] += 1

            for i_order, text in enumerate(sec["items"], start=1):
                item, i_new = ChecklistItem.objects.get_or_create(
                    section=section, text=text, defaults={"order": i_order},
                )
                if i_new:
                    created["items"] += 1

    return created
