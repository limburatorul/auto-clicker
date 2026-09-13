"""Inlines the screenshots into page.template.html and writes site.html.

Run after editing page.template.html or replacing a screenshot:
    python build_page.py
"""

import base64
from pathlib import Path

HERE = Path(__file__).parent
SHOTS = HERE / "screenshots"

PLACEHOLDERS = {
    "{{HERO_B64}}": "marketing_hero.png",
    "{{POINTS_B64}}": "marketing_points.png",
    "{{SEQUENCE_B64}}": "marketing_sequence.png",
    "{{WAIT_IMAGE_B64}}": "marketing_wait_image.png",
}


def main():
    template = (HERE / "page.template.html").read_text(encoding="utf-8")
    for placeholder, filename in PLACEHOLDERS.items():
        data = base64.b64encode((SHOTS / filename).read_bytes()).decode("ascii")
        template = template.replace(placeholder, data)
    (HERE / "site.html").write_text(template, encoding="utf-8")
    print(f"wrote site.html ({len(template):,} bytes)")


if __name__ == "__main__":
    main()
