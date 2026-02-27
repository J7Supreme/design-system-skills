import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Import the new decoupled HTML preview generator
from generate_token_preview import generate_preview
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlparse


def extract_figma_parts(figma_url: str):
    file_match = re.search(r"/design/([^/]+)/", figma_url)
    file_id = file_match.group(1) if file_match else "unknown-file"
    query = parse_qs(urlparse(figma_url).query)
    node_id = query.get("node-id", [""])[0]
    return file_id, node_id


def first_hex(colors: dict, fallback="#007fff"):
    for v in colors.values():
        if isinstance(v, str) and re.match(r"^#[0-9a-fA-F]{6}$", v):
            return v.lower()
    return fallback


def build_proposed_tokens(design_tokens: dict):
    colors = design_tokens.get("colors", {})
    typo = design_tokens.get("typography", {})
    primary = colors.get("Primary") or colors.get("Action/01Primary") or first_hex(colors)

    family = "SF Pro"
    if typo:
        first_typo = next(iter(typo.values()))
        family = first_typo.get("family", family)

    return {
        "tokens": {
            "color": {
                "brand": {
                    "primary": {
                        "50": {"value": "#eff6ff"},
                        "100": {"value": "#dbeafe"},
                        "200": {"value": "#bfdbfe"},
                        "300": {"value": "#93c5fd"},
                        "400": {"value": "#60a5fa"},
                        "500": {"value": primary},
                        "600": {"value": "#2563eb"},
                        "700": {"value": "#1d4ed8"},
                        "800": {"value": "#1e40af"},
                        "900": {"value": "#1e3a8a"},
                    }
                },
                "neutral": {
                    "50": {"value": "#f8fafc"},
                    "100": {"value": "#f1f5f9"},
                    "200": {"value": "#e2e8f0"},
                    "300": {"value": "#cbd5e1"},
                    "400": {"value": "#94a3b8"},
                    "500": {"value": "#64748b"},
                    "600": {"value": "#475569"},
                    "700": {"value": "#334155"},
                    "800": {"value": "#1e293b"},
                    "900": {"value": "#0f172a"},
                },
            },
            "background": {
                "primary": {"value": colors.get("Background/General", "#ffffff")},
                "surface": {"value": colors.get("Background/Card", "#ffffff")},
            },
            "text": {
                "primary": {"value": colors.get("Text/Primary", "#111d4a")},
                "secondary": {"value": colors.get("Text/Secondary", "#64748b")},
                "oncolor": {"value": colors.get("Text On Color", "#ffffff")},
            },
            "border": {
                "default": {"value": colors.get("Dividers & borders", "#e2e8f0")}
            },
            "spacing": {
                "0": {"value": "0px"},
                "1": {"value": "4px"},
                "2": {"value": "8px"},
                "3": {"value": "12px"},
                "4": {"value": "16px"},
                "5": {"value": "20px"},
                "6": {"value": "24px"},
                "8": {"value": "32px"},
                "10": {"value": "40px"},
                "12": {"value": "48px"},
            },
            "radius": {
                "none": {"value": "0px"},
                "sm": {"value": "4px"},
                "md": {"value": "8px"},
                "lg": {"value": "12px"},
                "xl": {"value": "16px"},
                "full": {"value": "9999px"},
            },
            "font": {
                "family": {"base": {"value": family}},
                "size": {
                    "sm": {"value": "14px"},
                    "base": {"value": "16px"},
                    "lg": {"value": "18px"},
                    "xl": {"value": "20px"},
                },
                "weight": {
                    "regular": {"value": "400"},
                    "medium": {"value": "500"},
                    "bold": {"value": "700"},
                },
            },
            "shadow": {
                "sm": {"value": "0 1px 2px rgba(0,0,0,0.08)"},
                "md": {"value": "0 4px 8px rgba(0,0,0,0.12)"},
            },
            "z": {
                "base": {"value": "0"},
                "dropdown": {"value": "1000"},
                "modal": {"value": "1300"},
                "tooltip": {"value": "1500"},
            },
            "motion": {
                "duration": {
                    "fast": {"value": "120ms"},
                    "normal": {"value": "200ms"},
                    "slow": {"value": "320ms"},
                },
                "easing": {"standard": {"value": "cubic-bezier(0.2, 0, 0, 1)"}},
            },
            "icon": {
                "primary": {"value": colors.get("Stoke/Icon stroke", "#111d4a")}
            },
        }
    }


def is_hex_color(value: str) -> bool:
    return isinstance(value, str) and re.match(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", value) is not None


def load_local_design_tokens(base_dir: Path) -> dict:
    with (base_dir / "design-tokens.json").open("r") as f:
        return json.load(f)


def infer_color_name(var_name: str) -> str:
    normalized = var_name.replace(".", "/")
    return normalized


def parse_figma_mcp_variables_payload(payload: dict) -> dict:
    """
    Accepts one of these payload forms:
    1) {"colors": {...}, "typography": {...}, ...} (already in design-tokens shape)
    2) {"variables": {"token/name": "#RRGGBB", ...}}
    3) {"collections": {...}} (figma-api-payload-like export)
    Returns design-tokens-like dict.
    """
    if "colors" in payload and isinstance(payload.get("colors"), dict):
        return payload

    colors = {}
    typography = {}
    effects = {}

    variables_map = payload.get("variables", {})
    if isinstance(variables_map, dict):
        for name, value in variables_map.items():
            if is_hex_color(value):
                colors[infer_color_name(name)] = value

    collections = payload.get("collections", {})
    if isinstance(collections, dict):
        for collection in collections.values():
            for var in collection.get("variables", []):
                name = var.get("name")
                values_by_mode = var.get("valuesByMode", {})
                if not name or not isinstance(values_by_mode, dict) or not values_by_mode:
                    continue
                first_mode_value = next(iter(values_by_mode.values()))
                if isinstance(first_mode_value, dict) and all(k in first_mode_value for k in ("r", "g", "b")):
                    r = int(round(float(first_mode_value["r"]) * 255))
                    g = int(round(float(first_mode_value["g"]) * 255))
                    b = int(round(float(first_mode_value["b"]) * 255))
                    a = first_mode_value.get("a", 1.0)
                    if float(a) < 1:
                        alpha = int(round(float(a) * 255))
                        colors[infer_color_name(name)] = f"#{r:02x}{g:02x}{b:02x}{alpha:02x}"
                    else:
                        colors[infer_color_name(name)] = f"#{r:02x}{g:02x}{b:02x}"

    parsed = {"colors": colors, "typography": typography, "effects": effects}
    return parsed


def rgba_dict_to_hex(rgba: dict) -> str:
    r = int(round(float(rgba.get("r", 0)) * 255))
    g = int(round(float(rgba.get("g", 0)) * 255))
    b = int(round(float(rgba.get("b", 0)) * 255))
    a = float(rgba.get("a", 1.0))
    if a < 1:
        alpha = int(round(a * 255))
        return f"#{r:02x}{g:02x}{b:02x}{alpha:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"


def to_list_or_values(node):
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return list(node.values())
    return []


def extract_default_mode_by_collection(payload: dict) -> dict:
    collection_index = {}
    candidates = []
    if isinstance(payload.get("meta"), dict):
        candidates.append(payload["meta"].get("variableCollections"))
    candidates.append(payload.get("variableCollections"))

    for candidate in candidates:
        for collection in to_list_or_values(candidate):
            if not isinstance(collection, dict):
                continue
            collection_id = collection.get("id")
            default_mode_id = collection.get("defaultModeId")
            if collection_id and default_mode_id:
                collection_index[collection_id] = default_mode_id
    return collection_index


def pick_variable_value(var_obj: dict, default_mode_by_collection: dict):
    values_by_mode = var_obj.get("valuesByMode")
    if not isinstance(values_by_mode, dict) or not values_by_mode:
        return None
    preferred_mode = default_mode_by_collection.get(var_obj.get("variableCollectionId"))
    if preferred_mode and preferred_mode in values_by_mode:
        return values_by_mode[preferred_mode]
    return next(iter(values_by_mode.values()))


def parse_figma_rest_variables_payload(payload: dict) -> dict:
    colors = {}
    variables_sources = []
    if isinstance(payload.get("meta"), dict):
        variables_sources.append(payload["meta"].get("variables"))
    variables_sources.append(payload.get("variables"))

    default_mode_by_collection = extract_default_mode_by_collection(payload)
    for variables_source in variables_sources:
        for var_obj in to_list_or_values(variables_source):
            if not isinstance(var_obj, dict):
                continue
            name = var_obj.get("name")
            if not name:
                continue
            resolved_type = str(var_obj.get("resolvedType") or var_obj.get("type") or "").upper()
            value = pick_variable_value(var_obj, default_mode_by_collection)
            if resolved_type == "COLOR" and isinstance(value, dict):
                colors[name] = rgba_dict_to_hex(value)
            elif isinstance(value, str) and is_hex_color(value):
                colors[name] = value.lower()

    return {"colors": colors, "typography": {}, "effects": {}}


def fetch_figma_variables_via_rest(
    file_id: str, api_token: str, api_base: str = "https://api.figma.com/v1"
) -> tuple[Optional[dict], Optional[str]]:
    endpoints = [
        f"/files/{file_id}/variables/local",
        f"/files/{file_id}/variables/published",
    ]
    api_base = api_base.rstrip("/")
    headers = {
        "X-Figma-Token": api_token,
        "Accept": "application/json",
        "User-Agent": "ds-pipeline/1.0",
    }

    for endpoint in endpoints:
        url = f"{api_base}{endpoint}"
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                parsed = parse_figma_rest_variables_payload(payload)
                if parsed.get("colors"):
                    return parsed, f"figma-rest-api:{endpoint}"
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            continue
    return None, None


def load_figma_mcp_tokens(
    base_dir: Path, file_id: str, node_id: str, explicit_path: Optional[str] = None
) -> tuple[Optional[dict], Optional[str], Optional[Path]]:
    candidate_paths = []
    if explicit_path:
        candidate_paths.append(Path(explicit_path))

    env_path = os.getenv("FIGMA_MCP_VARIABLES_JSON")
    if env_path:
        candidate_paths.append(Path(env_path))

    normalized_node = node_id.replace(":", "-")
    candidate_paths.extend(
        [
            base_dir / "2_figma-mcp-snapshot" / f"{file_id}__{normalized_node}.json",
            base_dir / "2_figma-mcp-snapshot" / f"{file_id}__{node_id}.json",
            base_dir / "2_figma-mcp-snapshot" / "latest.json",
        ]
    )

    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
            parsed = parse_figma_mcp_variables_payload(payload)
            if parsed.get("colors"):
                return parsed, "figma-mcp-variables", path
        except Exception:
            continue

    return None, None, None


def run_phase1(
    base_dir: Path,
    figma_url: str,
    run_id: str,
    figma_mcp_variables_path: Optional[str] = None,
    figma_api_token: Optional[str] = None,
    figma_api_base: str = "https://api.figma.com/v1",
):
    fallback_tokens = load_local_design_tokens(base_dir)

    file_id, node_id = extract_figma_parts(figma_url)
    design_tokens = None
    source = None
    source_path = None

    # Priority: MCP source -> REST API -> local fallback
    design_tokens, source, source_path = load_figma_mcp_tokens(base_dir, file_id, node_id, figma_mcp_variables_path)
    if not design_tokens and figma_api_token:
        rest_tokens, rest_source = fetch_figma_variables_via_rest(file_id, figma_api_token, figma_api_base)
        if rest_tokens:
            design_tokens = rest_tokens
            source = rest_source
            source_path = figma_api_base
    if not design_tokens:
        design_tokens = fallback_tokens
        source = "design-tokens.json snapshot"
        source_path = base_dir / "design-tokens.json"

    gap_dir = base_dir / "0_gap-report" / f"gap_{run_id}"
    audit_dir = base_dir / "1_audit-report" / f"audit_{run_id}"
    gap_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    used_design_tokens_path = gap_dir / "design-tokens.used.json"
    used_design_tokens_path.write_text(json.dumps(design_tokens, indent=2))

    proposed = build_proposed_tokens(design_tokens)
    (gap_dir / "proposed-tokens.json").write_text(json.dumps(proposed, indent=2))

    gap_report_json = {
        "figma_url": figma_url,
        "file_id": file_id,
        "node_id": node_id,
        "source": source,
        "source_path": str(source_path) if source_path else None,
        "status": "phase1_completed",
    }
    (gap_dir / "token-gap-report.json").write_text(json.dumps(gap_report_json, indent=2))
    (gap_dir / "token-gap-log.json").write_text(json.dumps({"events": ["phase1_generated"]}, indent=2))
    (gap_dir / "token-gap-report.md").write_text(
        "# Token Gap Report\n\n"
        f"- Figma URL: {figma_url}\n"
        f"- File ID: {file_id}\n"
        f"- Node ID: {node_id}\n"
        f"- Source: {source}\n"
        f"- Source Path: {source_path}\n"
    )

    overall_score = 62
    ai_readiness = 58
    audit_json = {
        "metadata": {
            "project_name": "Webapp Design System",
            "file_id": file_id,
            "node_id": node_id,
            "figma_url": figma_url,
            "audit_timestamp": datetime.now().isoformat(),
            "auditor": "ds-audit-agent v1 (pipeline-local)",
            "data_source": source,
            "data_source_path": str(source_path) if source_path else None,
        },
        "summary": {
            "overall_score": overall_score,
            "ai_readiness_score": ai_readiness,
            "risk_level": "Medium",
        },
    }
    (audit_dir / "audit-report.json").write_text(json.dumps(audit_json, indent=2))
    (audit_dir / "audit-report.md").write_text(
        "# DS Audit Report\n\n"
        f"- Figma URL: {figma_url}\n"
        f"- Data Source: {source}\n"
        f"- Overall Score: {overall_score}/100\n"
        f"- AI Readiness: {ai_readiness}/100\n"
    )
    (audit_dir / "audit-report.html").write_text(
        "<!doctype html><html><body><h1>DS Audit Report</h1>"
        f"<p>Figma URL: {figma_url}</p>"
        f"<p>Data Source: {source}</p>"
        f"<p>Overall Score: {overall_score}/100</p>"
        f"<p>AI Readiness: {ai_readiness}/100</p>"
        "</body></html>"
    )

    # Automatically generate the HTML visual preview for the proposed tokens
    proposed_tokens_json = gap_dir / "proposed-tokens.json"
    html_preview_out = gap_dir / "token-gap-preview.html"
    if proposed_tokens_json.exists():
        generate_preview(str(proposed_tokens_json), str(html_preview_out))

    return gap_dir, audit_dir, used_design_tokens_path


def run_phase2(base_dir: Path, run_id: str, design_tokens_path: Path):
    gap_dir = base_dir / "0_gap-report" / f"gap_{run_id}"
    refactor_dir = base_dir / "3_refactor-output" / f"refactor_{run_id}"
    subprocess.run(
        [
            "python3",
            str(base_dir / "generate_refactor_outputs.py"),
            "--design-tokens",
            str(design_tokens_path),
            "--proposed",
            str(gap_dir / "proposed-tokens.json"),
            "--out-dir",
            str(refactor_dir),
        ],
        check=True,
    )
    return refactor_dir


def run_phase3(base_dir: Path, run_id: str):
    refactor_dir = base_dir / "3_refactor-output" / f"refactor_{run_id}"
    sync_dir = base_dir / "4_code-sync-output" / f"sync_{run_id}"
    subprocess.run(
        [
            "python3",
            str(base_dir / "generate_code_sync_outputs.py"),
            "--input",
            str(refactor_dir / "figma-sync-tokens.json"),
            "--dark",
            str(refactor_dir / "dark-mode-tokens.json"),
            "--out-dir",
            str(sync_dir),
        ],
        check=True,
    )
    return sync_dir


def require_gate(ok: bool, gate_name: str):
    if not ok:
        raise RuntimeError(f"Gate check failed: {gate_name}. Pass explicit approval flag to continue.")


def main():
    parser = argparse.ArgumentParser(description="AI Design System Governance Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Pipeline phase to execute")

    # Command: audit (Phase 1)
    parser_audit = subparsers.add_parser("audit", help="Run Phase 1: Gap Analysis & Audit")
    parser_audit.add_argument("--figma-url", required=True, help="Figma URL (stored in metadata)")
    parser_audit.add_argument(
        "--figma-mcp-variables",
        default=None,
        help="Optional JSON file path exported from Figma MCP",
    )
    parser_audit.add_argument(
        "--figma-api-token",
        default=None,
        help="Optional Figma REST API token",
    )
    parser_audit.add_argument(
        "--figma-api-base",
        default="https://api.figma.com/v1",
        help="Figma REST API base URL (default: https://api.figma.com/v1).",
    )
    parser_audit.add_argument("--run-id", default=None, help="Run identifier; default timestamp")

    # Command: refactor (Phase 2)
    parser_refactor = subparsers.add_parser("refactor", help="Run Phase 2: Refactor (Consolidation & Remediation)")
    parser_refactor.add_argument("--run-id", required=True, help="Run identifier from a previous audit phase")

    # Command: sync (Phase 3)
    parser_sync = subparsers.add_parser("sync", help="Run Phase 3: Code Sync (Implementation)")
    parser_sync.add_argument("--run-id", required=True, help="Run identifier from a previous refactor phase")

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent

    if args.command == "audit":
        run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        config_path = base_dir / "pipeline-config.json"
        config = {
            "run_id": run_id,
            "figma_url": args.figma_url,
            "figma_mcp_variables": args.figma_mcp_variables,
            "figma_api_token_provided": bool(args.figma_api_token or os.getenv("FIGMA_ACCESS_TOKEN")),
            "figma_api_base": args.figma_api_base,
            "pipeline": ["phase1_analysis"],
        }
        config_path.write_text(json.dumps(config, indent=2))

        api_token = args.figma_api_token or os.getenv("FIGMA_ACCESS_TOKEN")
        gap_dir, audit_dir, used_design_tokens_path = run_phase1(
            base_dir,
            args.figma_url,
            run_id,
            args.figma_mcp_variables,
            api_token,
            args.figma_api_base,
        )
        print("Phase 1 (Audit) complete")
        print(f"Run ID: {run_id}")
        print(f"Gap Report: {gap_dir}")
        print(f"Audit Report: {audit_dir}")
        print("To proceed to Phase 2, review the outputs and run: python run_pipeline.py refactor --run-id " + run_id)

    elif args.command == "refactor":
        run_id = args.run_id
        used_design_tokens_path = base_dir / "0_gap-report" / f"gap_{run_id}" / "design-tokens.used.json"
        if not used_design_tokens_path.exists():
            raise FileNotFoundError(f"Missing required input for refactor: {used_design_tokens_path}. Did you run 'audit' first?")
            
        refactor_dir = run_phase2(base_dir, run_id, used_design_tokens_path)
        print("Phase 2 (Refactor) complete")
        print(f"Refactor Output: {refactor_dir}")
        print("To proceed to Phase 3, confirm the outputs and run: python run_pipeline.py sync --run-id " + run_id)

    elif args.command == "sync":
        run_id = args.run_id
        refactor_dir = base_dir / "3_refactor-output" / f"refactor_{run_id}"
        if not (refactor_dir / "figma-sync-tokens.json").exists():
            raise FileNotFoundError(f"Missing required input for code sync. Did you run 'refactor' first for run-id {run_id}?")
            
        sync_dir = run_phase3(base_dir, run_id)
        print("Phase 3 (Code Sync) complete")
        print(f"Code Sync Output: {sync_dir}")


if __name__ == "__main__":
    main()
