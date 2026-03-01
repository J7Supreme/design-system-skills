import json
import os
import re
import argparse


def build_audit_html(json_path: str, template_path: str, output_path: str):
    """Inject audit JSON data into the HTML template and write to output."""
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = f.read()

    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    # Replace the AUDIT_DATA block
    pattern = r"const AUDIT_DATA = \{.*?\};\n"
    replacement = f"const AUDIT_DATA = {json_data};\n"

    new_html = re.sub(pattern, replacement, html_template, flags=re.DOTALL)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"Audit HTML report generated at: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Audit HTML Report from JSON + Template")
    parser.add_argument("--json", required=True, help="Path to audit-report.json")
    parser.add_argument("--template", default=None, help="Path to audit-report-template.html (defaults to templates/ in skill dir)")
    parser.add_argument("--out", required=True, help="Output HTML path")
    args = parser.parse_args()

    template = args.template
    if template is None:
        template = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "audit-report-template.html")

    build_audit_html(args.json, template, args.out)
