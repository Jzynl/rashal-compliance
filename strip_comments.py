"""
Remove every Django template comment from every template.

Django's {# #} only works on a SINGLE line. Any comment that wraps onto a
second line renders its overflow as visible text on the page. These were
developer notes; none of them belong in the output.

Run once from the project root (the folder containing manage.py):
    python strip_comments.py
"""

import pathlib
import re

root = pathlib.Path("templates")
if not root.exists():
    raise SystemExit("No templates/ folder here. Run this from the project root.")

changed = 0
for path in sorted(root.rglob("*.html")):
    original = path.read_text(encoding="utf-8")
    cleaned = re.sub(r"\{#.*?#\}", "", original, flags=re.DOTALL)
    cleaned = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", cleaned)
    if cleaned != original:
        path.write_text(cleaned, encoding="utf-8")
        changed += 1
        print(f"  cleaned  {path}")

print(f"\n{changed} template(s) cleaned." if changed else "\nNothing to clean.")