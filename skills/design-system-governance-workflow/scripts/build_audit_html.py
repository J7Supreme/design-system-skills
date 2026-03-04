import json
import os
import re
import argparse
from pathlib import Path
from datetime import datetime

from audit_report_data import normalize_audit_data


def get_audit_template_context(normalized_payload: dict) -> dict:
    metadata = normalized_payload.get("metadata", {})
    project_name = metadata.get("project_name") or "Design System"
    auditor = metadata.get("auditor") or "Design System Governance Workflow v1"

    timestamp_raw = metadata.get("audit_timestamp") or ""
    try:
        audit_dt = datetime.fromisoformat(timestamp_raw)
    except ValueError:
        audit_dt = None

    display_date = audit_dt.strftime("%b %d, %Y") if audit_dt else ""
    iso_date = audit_dt.date().isoformat() if audit_dt else ""
    wcag_target = metadata.get("wcag_target") or "AA"
    file_id = metadata.get("file_id") or "unknown-file"
    token_schema_version = metadata.get("token_schema_version") or "ai_token_schema_simple_v1"

    return {
        "{{project_name}}": project_name,
        "{{audit_date_display}}": display_date,
        "{{audit_date_iso}}": iso_date,
        "{{auditor}}": auditor,
        "{{hero_meta_fallback}}": f"Audited on {display_date} · {auditor}" if display_date else auditor,
        "{{hero_desc_fallback}}": f"Figma file: {file_id} · WCAG {wcag_target} · {token_schema_version}",
    }


def render_audit_html(html_template: str, normalized_payload: dict) -> str:
    json_data = json.dumps(normalized_payload)

    pattern = r"const AUDIT_DATA = \{.*?\};\n"
    new_html = re.sub(
        pattern,
        lambda _: f"const AUDIT_DATA = {json_data};\n",
        html_template,
        flags=re.DOTALL,
    )

    for placeholder, value in get_audit_template_context(normalized_payload).items():
        new_html = new_html.replace(placeholder, value)

    return new_html


def build_audit_html(json_path: str, template_path: str, output_path: str):
    """Inject audit JSON data into the HTML template and write to output."""
    skill_root = Path(template_path).resolve().parent.parent
    with open(json_path, "r", encoding="utf-8") as f:
        json_payload = json.load(f)
    normalized_payload = normalize_audit_data(json_payload, skill_root)

    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    new_html = render_audit_html(html_template, normalized_payload)

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
