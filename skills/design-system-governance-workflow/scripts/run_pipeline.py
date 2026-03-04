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
from audit_report_data import normalize_audit_data
from build_audit_html import render_audit_html
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


def sanitize_source_reference(source_path, base_dir: Path) -> Optional[str]:
    if not source_path:
        return None

    if isinstance(source_path, Path):
        try:
            return str(source_path.resolve().relative_to(base_dir.resolve()))
        except ValueError:
            return source_path.name

    source_text = str(source_path)
    parsed = urlparse(source_text)
    if parsed.scheme in {"http", "https"}:
        return parsed.netloc + parsed.path

    candidate = Path(source_text)
    if candidate.is_absolute():
        return candidate.name
    return source_text


def build_source_details(
    source_kind: str,
    source_label: str,
    source_reference: Optional[str],
    fallback_reason: Optional[str] = None,
    prerequisite_actions: Optional[list[dict]] = None,
    prerequisite_notice: Optional[str] = None,
    audit_optimize_prerequisites_met: bool = True,
) -> dict:
    mcp_used = source_kind == "figma-mcp"
    freshness_note = (
        "Primary MCP extraction path used."
        if mcp_used
        else "Fallback source used; freshness/completeness may differ from direct MCP extraction."
    )
    user_notice = None
    if not mcp_used:
        reason = fallback_reason or "Figma MCP data was unavailable."
        user_notice = (
            f"Used fallback source '{source_label}' because {reason} "
            "Results may differ in freshness or completeness from direct Figma MCP extraction."
        )

    return {
        "source_kind": source_kind,
        "source_label": source_label,
        "source_reference": source_reference,
        "mcp_used": mcp_used,
        "fallback_reason": fallback_reason,
        "freshness_note": freshness_note,
        "user_notice": user_notice,
        "prerequisite_actions": prerequisite_actions or [],
        "prerequisite_notice": prerequisite_notice,
        "audit_optimize_prerequisites_met": audit_optimize_prerequisites_met,
    }


def build_source_entry(
    kind: str,
    label: str,
    status: str,
    used_for_audit: bool,
    reference: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    return {
        "kind": kind,
        "label": label,
        "status": status,
        "used_for_audit": used_for_audit,
        "reference": reference,
        "reason": reason,
    }


def build_phase1_prerequisite_actions(
    mcp_connected: bool,
    api_connected: bool,
    mcp_reason: Optional[str],
    api_reason: Optional[str],
) -> tuple[list[dict], Optional[str], bool]:
    actions = [
        {
            "id": "connect_figma_mcp",
            "title": "Connect Figma MCP",
            "status": "ready" if mcp_connected else "required",
            "reason": None if mcp_connected else (mcp_reason or "Figma MCP could not provide variables for this file."),
            "instruction": (
                "Reconnect Figma MCP for this file, or export a fresh MCP snapshot and pass "
                "--figma-mcp-variables / FIGMA_MCP_VARIABLES_JSON."
            ),
        },
        {
            "id": "connect_figma_api",
            "title": "Connect Figma API",
            "status": "ready" if api_connected else "required",
            "reason": None if api_connected else (api_reason or "Figma REST API could not be reached for this file."),
            "instruction": (
                "Provide a working Figma REST API token via --figma-api-token or FIGMA_ACCESS_TOKEN "
                "and confirm the target file is reachable."
            ),
        },
    ]

    prerequisites_met = mcp_connected and api_connected
    prerequisite_notice = None
    if not prerequisites_met:
        prerequisite_notice = (
            "Audit/Optimize prerequisites are incomplete. Before relying on this run as the primary result, "
            "do these two things first: 1) connect Figma MCP for the target file; "
            "2) connect the Figma REST API with a valid token and file access."
        )

    return actions, prerequisite_notice, prerequisites_met


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


def resolve_skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_repo_root() -> Path:
    skill_root = resolve_skill_root()
    if skill_root.parent.name == "skills":
        if skill_root.parent.parent.name in {".agents", ".agent"}:
            return skill_root.parent.parent.parent
        return skill_root.parent.parent
    return skill_root.parent


def load_explicit_design_tokens_json(explicit_path: Optional[str]) -> tuple[Optional[dict], Optional[Path], Optional[str]]:
    if not explicit_path:
        return None, None, "No explicit token JSON was provided."

    path = Path(explicit_path)
    if not path.exists():
        return None, path, f"Explicit token JSON file was not found: {path}"

    try:
        with path.open("r") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        return None, path, f"Explicit token JSON is not valid JSON: {exc}"

    if not isinstance(payload, dict):
        return None, path, "Explicit token JSON must decode to a JSON object."

    parsed = parse_figma_mcp_variables_payload(payload)
    if parsed.get("colors"):
        return parsed, path, None

    return None, path, "Explicit token JSON did not contain usable token data."


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
    repo_root: Path,
    skill_root: Path,
    figma_url: str,
    run_id: str,
    figma_mcp_variables_path: Optional[str] = None,
    figma_api_token: Optional[str] = None,
    figma_api_base: str = "https://api.figma.com/v1",
    explicit_design_tokens_json: Optional[str] = None,
):
    file_id, node_id = extract_figma_parts(figma_url)
    design_tokens = None
    source = None
    source_kind = None
    source_path = None
    fallback_reason = None
    rest_tokens = None
    rest_source = None
    rest_reason = None
    explicit_tokens = None
    explicit_source_path = None
    explicit_reason = "No explicit token JSON was provided."

    if explicit_design_tokens_json:
        explicit_tokens, explicit_source_path, explicit_reason = load_explicit_design_tokens_json(
            explicit_design_tokens_json
        )

    # Priority: MCP source -> REST API -> explicit user-provided token JSON
    mcp_tokens, mcp_source, mcp_source_path = load_figma_mcp_tokens(repo_root, file_id, node_id, figma_mcp_variables_path)
    mcp_reason = "No usable Figma MCP snapshot was found for the requested file."
    if mcp_tokens:
        design_tokens = mcp_tokens
        source = mcp_source
        source_kind = "figma-mcp"
        source_path = mcp_source_path
    else:
        fallback_reason = mcp_reason

    if figma_api_token:
        rest_tokens, rest_source = fetch_figma_variables_via_rest(file_id, figma_api_token, figma_api_base)
        if rest_tokens:
            if not design_tokens:
                design_tokens = rest_tokens
                source = rest_source
                source_kind = "figma-rest-api"
                source_path = figma_api_base
        else:
            rest_reason = "Figma REST API variables could not be retrieved for the requested file."
            if not fallback_reason:
                fallback_reason = rest_reason
    else:
        rest_reason = "No Figma REST API token was provided."

    prerequisite_actions, prerequisite_notice, prerequisites_met = build_phase1_prerequisite_actions(
        mcp_connected=bool(mcp_tokens),
        api_connected=bool(rest_tokens),
        mcp_reason=mcp_reason,
        api_reason=rest_reason,
    )
    if not design_tokens:
        if explicit_tokens:
            design_tokens = explicit_tokens
            source = "explicit user-provided token JSON"
            source_kind = "explicit-user-token-json"
            source_path = explicit_source_path
            fallback_reason = "Figma MCP and Figma REST API were unavailable, so the run used explicit user-provided token JSON."
        else:
            reasons = [reason for reason in [fallback_reason, rest_reason, explicit_reason] if reason]
            raise RuntimeError(
                "Pipeline aborted: Figma MCP and Figma REST API were unavailable, and no usable explicit user-provided token JSON was supplied. "
                + " ".join(reasons)
            )

    source_reference = sanitize_source_reference(source_path, repo_root)
    source_details = build_source_details(
        source_kind,
        source,
        source_reference,
        fallback_reason,
        prerequisite_actions=prerequisite_actions,
        prerequisite_notice=prerequisite_notice,
        audit_optimize_prerequisites_met=prerequisites_met,
    )

    data_sources = [
        build_source_entry(
            "figma-mcp",
            "Figma MCP",
            "used" if source_kind == "figma-mcp" else "available_not_used" if mcp_tokens else "unavailable",
            source_kind == "figma-mcp",
            sanitize_source_reference(mcp_source_path, repo_root) if mcp_source_path else None,
            None if mcp_tokens else mcp_reason,
        ),
        build_source_entry(
            "figma-rest-api",
            "Figma REST API",
            "used" if source_kind == "figma-rest-api" else "available_not_used" if rest_tokens else "unavailable",
            source_kind == "figma-rest-api",
            figma_api_base if rest_tokens else None,
            None if rest_tokens else rest_reason,
        ),
        build_source_entry(
            "explicit-user-token-json",
            "Explicit user-provided token JSON",
            "used"
            if source_kind == "explicit-user-token-json"
            else "available_not_used"
            if explicit_tokens
            else "not_provided"
            if not explicit_design_tokens_json
            else "unavailable",
            source_kind == "explicit-user-token-json",
            sanitize_source_reference(explicit_source_path, repo_root) if explicit_source_path else None,
            None if explicit_tokens else explicit_reason,
        ),
    ]

    # Phase 1 consolidation: all outputs go into a single audit directory
    audit_dir = repo_root / "1_audit-report" / f"audit_{run_id}"
    audit_dir.mkdir(parents=True, exist_ok=True)

    # Save the design tokens snapshot used for this run
    used_design_tokens_path = audit_dir / "design-tokens.used.json"
    used_design_tokens_path.write_text(json.dumps(design_tokens, indent=2))

    # ── Optimizer outputs ──
    proposed = build_proposed_tokens(design_tokens)
    proposed["metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "figma_url": figma_url,
        "file_id": file_id,
        "node_id": node_id,
        "source_kind": source_kind,
        "source_label": source,
        "source_reference": source_reference,
        "mcp_used": source_details["mcp_used"],
        "fallback_reason": fallback_reason,
        "user_notice": source_details["user_notice"],
        "prerequisite_notice": source_details["prerequisite_notice"],
        "audit_optimize_prerequisites_met": source_details["audit_optimize_prerequisites_met"],
        "data_sources": data_sources,
        "proposal_note": "This preview renders generated proposal tokens only. Missing categories are shown as unavailable rather than filled with visual fallback values.",
    }
    (audit_dir / "proposed-tokens.json").write_text(json.dumps(proposed, indent=2))

    optimizer_report_json = {
        "figma_url": figma_url,
        "file_id": file_id,
        "node_id": node_id,
        "source": source,
        "source_reference": source_reference,
        "source_kind": source_kind,
        "mcp_used": source_details["mcp_used"],
        "fallback_reason": fallback_reason,
        "user_notice": source_details["user_notice"],
        "audit_optimize_prerequisites_met": source_details["audit_optimize_prerequisites_met"],
        "prerequisite_notice": source_details["prerequisite_notice"],
        "prerequisite_actions": source_details["prerequisite_actions"],
        "data_sources": data_sources,
        "status": "phase1_completed",
    }
    (audit_dir / "optimizer-report.json").write_text(json.dumps(optimizer_report_json, indent=2))
    (audit_dir / "optimizer-report.md").write_text(
        "# Optimizer Report\n\n"
        f"- Figma URL: {figma_url}\n"
        f"- File ID: {file_id}\n"
        f"- Node ID: {node_id}\n"
        f"- Source: {source}\n"
        f"- Source Reference: {source_reference}\n"
        f"- Source Kind: {source_kind}\n"
        f"- MCP Used: {source_details['mcp_used']}\n"
        f"- Audit/Optimize Prerequisites Met: {source_details['audit_optimize_prerequisites_met']}\n"
        f"- Fallback Reason: {fallback_reason or 'None'}\n"
        f"- Prerequisite Notice: {source_details['prerequisite_notice'] or 'None'}\n"
    )

    # ── Audit outputs ──
    audit_json = {
        "metadata": {
            "project_name": "Webapp Design System",
            "file_id": file_id,
            "node_id": node_id,
            "figma_url": figma_url,
            "audit_timestamp": datetime.now().isoformat(),
            "auditor": "Design System Governance Workflow v1 (pipeline-local)",
            "data_source": source,
            "data_source_reference": source_reference,
            "data_source_kind": source_kind,
            "mcp_used": source_details["mcp_used"],
            "fallback_reason": fallback_reason,
            "user_notice": source_details["user_notice"],
            "audit_optimize_prerequisites_met": source_details["audit_optimize_prerequisites_met"],
            "prerequisite_notice": source_details["prerequisite_notice"],
            "prerequisite_actions": source_details["prerequisite_actions"],
            "data_sources": data_sources,
        },
        "summary": {
            "overall_score": None,
            "ai_readiness_score": None,
            "risk_level": "Unknown",
        },
    }
    audit_json = normalize_audit_data(audit_json, skill_root, design_tokens=design_tokens)
    (audit_dir / "audit-report.json").write_text(json.dumps(audit_json, indent=2))
    (audit_dir / "audit-report.md").write_text(
        "# DS Audit Report\n\n"
        f"- Figma URL: {figma_url}\n"
        f"- Data Source: {source}\n"
        f"- Data Source Kind: {source_kind}\n"
        f"- MCP Used: {source_details['mcp_used']}\n"
        f"- Audit/Optimize Prerequisites Met: {source_details['audit_optimize_prerequisites_met']}\n"
        f"- Fallback Reason: {fallback_reason or 'None'}\n"
        f"- Prerequisite Notice: {source_details['prerequisite_notice'] or 'None'}\n"
        "- Overall Score: Not scored in this run\n"
        "- AI Readiness: Not scored in this run\n"
    )

    # Generate audit HTML using template
    audit_template = skill_root / "templates" / "audit-report-template.html"
    if audit_template.exists():
        template_html = audit_template.read_text(encoding="utf-8")
        final_html = render_audit_html(template_html, audit_json)
        (audit_dir / "audit-report.html").write_text(final_html, encoding="utf-8")
    else:
        (audit_dir / "audit-report.html").write_text(
            "<!doctype html><html><body><h1>DS Audit Report</h1>"
            f"<p>Figma URL: {figma_url}</p>"
            f"<p>Data Source: {source}</p>"
            f"<p>Data Source Kind: {source_kind}</p>"
            f"<p>MCP Used: {source_details['mcp_used']}</p>"
            f"<p>Audit/Optimize Prerequisites Met: {source_details['audit_optimize_prerequisites_met']}</p>"
            f"<p>Fallback Reason: {fallback_reason or 'None'}</p>"
            f"<p>Prerequisite Notice: {source_details['prerequisite_notice'] or 'None'}</p>"
            "<p>Overall Score: Not scored in this run</p>"
            "<p>AI Readiness: Not scored in this run</p>"
            "</body></html>"
        )

    # Generate optimizer HTML preview for proposed tokens
    proposed_tokens_json = audit_dir / "proposed-tokens.json"
    html_preview_out = audit_dir / "optimizer-report.html"
    if proposed_tokens_json.exists():
        generate_preview(str(proposed_tokens_json), str(html_preview_out))

    audit_report_json_path = audit_dir / "audit-report.json"
    audit_report_md_path = audit_dir / "audit-report.md"
    audit_report_html_path = audit_dir / "audit-report.html"
    optimizer_report_json_path = audit_dir / "optimizer-report.json"
    optimizer_report_md_path = audit_dir / "optimizer-report.md"
    optimizer_report_html_path = audit_dir / "optimizer-report.html"
    proposed_tokens_path = audit_dir / "proposed-tokens.json"
    pipeline_config_path = audit_dir / "pipeline-config.json"
    full_summary_path = audit_dir / "full-summary.md"
    artifact_manifest_path = audit_dir / "artifact-manifest.json"

    artifact_manifest = {
        "run_id": run_id,
        "phase": "audit_optimize",
        "artifact_directory": {
            "relative": str(audit_dir.relative_to(repo_root)),
            "absolute": str(audit_dir.resolve()),
        },
        "interactive_reports": {
            "audit_report_html": {
                "label": "Audit Report (HTML)",
                "relative": str(audit_report_html_path.relative_to(repo_root)),
                "absolute": str(audit_report_html_path.resolve()),
            },
            "optimizer_preview_html": {
                "label": "Optimizer Preview (HTML)",
                "relative": str(optimizer_report_html_path.relative_to(repo_root)),
                "absolute": str(optimizer_report_html_path.resolve()),
            },
        },
        "reports": {
            "full_summary_markdown": {
                "label": "Full Summary (Markdown)",
                "relative": str(full_summary_path.relative_to(repo_root)),
                "absolute": str(full_summary_path.resolve()),
            },
            "audit_report_markdown": {
                "label": "Audit Report (Markdown)",
                "relative": str(audit_report_md_path.relative_to(repo_root)),
                "absolute": str(audit_report_md_path.resolve()),
            },
            "audit_report_json": {
                "label": "Audit Report (JSON)",
                "relative": str(audit_report_json_path.relative_to(repo_root)),
                "absolute": str(audit_report_json_path.resolve()),
            },
            "optimizer_report_markdown": {
                "label": "Optimizer Report (Markdown)",
                "relative": str(optimizer_report_md_path.relative_to(repo_root)),
                "absolute": str(optimizer_report_md_path.resolve()),
            },
            "optimizer_report_json": {
                "label": "Optimizer Report (JSON)",
                "relative": str(optimizer_report_json_path.relative_to(repo_root)),
                "absolute": str(optimizer_report_json_path.resolve()),
            },
            "proposed_tokens_json": {
                "label": "Proposed Tokens (JSON)",
                "relative": str(proposed_tokens_path.relative_to(repo_root)),
                "absolute": str(proposed_tokens_path.resolve()),
            },
            "design_tokens_used_json": {
                "label": "Design Tokens Used (JSON)",
                "relative": str(used_design_tokens_path.relative_to(repo_root)),
                "absolute": str(used_design_tokens_path.resolve()),
            },
            "pipeline_config_json": {
                "label": "Pipeline Config (JSON)",
                "relative": str(pipeline_config_path.relative_to(repo_root)),
                "absolute": str(pipeline_config_path.resolve()),
            },
        },
        "source": source_details,
        "figma": {
            "url": figma_url,
            "file_id": file_id,
            "node_id": node_id,
        },
    }
    artifact_manifest_path.write_text(json.dumps(artifact_manifest, indent=2))

    full_summary_path.write_text(
        "# Phase 1 Output Summary\n\n"
        f"- Run ID: {run_id}\n"
        f"- Artifact Directory: {audit_dir.resolve()}\n"
        f"- Figma URL: {figma_url}\n"
        f"- File ID: {file_id}\n"
        f"- Node ID: {node_id}\n"
        f"- Data Source: {source_details['source_label']} ({source_details['source_kind']})\n"
        f"- MCP Used: {source_details['mcp_used']}\n"
        f"- Audit/Optimize Prerequisites Met: {source_details['audit_optimize_prerequisites_met']}\n"
        f"- Fallback Reason: {source_details['fallback_reason'] or 'None'}\n"
        f"- Prerequisite Notice: {source_details['prerequisite_notice'] or 'None'}\n\n"
        "## Interactive Reports\n\n"
        f"- Audit Report (HTML): {audit_report_html_path.resolve()}\n"
        f"- Optimizer Preview (HTML): {optimizer_report_html_path.resolve()}\n\n"
        "## Source Reports\n\n"
        f"- Full Summary (Markdown): {full_summary_path.resolve()}\n"
        f"- Audit Report (Markdown): {audit_report_md_path.resolve()}\n"
        f"- Audit Report (JSON): {audit_report_json_path.resolve()}\n"
        f"- Optimizer Report (Markdown): {optimizer_report_md_path.resolve()}\n"
        f"- Optimizer Report (JSON): {optimizer_report_json_path.resolve()}\n"
        f"- Proposed Tokens (JSON): {proposed_tokens_path.resolve()}\n"
        f"- Design Tokens Used (JSON): {used_design_tokens_path.resolve()}\n"
        f"- Artifact Manifest (JSON): {artifact_manifest_path.resolve()}\n"
    )

    return audit_dir, used_design_tokens_path, source_details, full_summary_path, artifact_manifest_path


def run_phase2(repo_root: Path, script_dir: Path, run_id: str, design_tokens_path: Path):
    audit_dir = repo_root / "1_audit-report" / f"audit_{run_id}"
    refactor_dir = repo_root / "3_refactor-output" / f"refactor_{run_id}"
    subprocess.run(
        [
            "python3",
            str(script_dir / "generate_refactor_outputs.py"),
            "--design-tokens",
            str(design_tokens_path),
            "--proposed",
            str(audit_dir / "proposed-tokens.json"),
            "--out-dir",
            str(refactor_dir),
        ],
        check=True,
    )
    return refactor_dir


def run_phase3(repo_root: Path, script_dir: Path, run_id: str):
    refactor_dir = repo_root / "3_refactor-output" / f"refactor_{run_id}"
    sync_dir = repo_root / "4_code-sync-output" / f"sync_{run_id}"
    subprocess.run(
        [
            "python3",
            str(script_dir / "generate_code_sync_outputs.py"),
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
    parser = argparse.ArgumentParser(description="Design System Governance Workflow")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Pipeline phase to execute")

    # Command: audit (Phase 1)
    parser_audit = subparsers.add_parser("audit", help="Run Phase 1: Audit & Optimization")
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
    parser_audit.add_argument(
        "--design-tokens-json",
        default=None,
        help="Explicit token JSON path. Only use when the user has explicitly provided token JSON to proceed without MCP/API.",
    )
    parser_audit.add_argument("--run-id", default=None, help="Run identifier; default timestamp")

    # Command: refactor (Phase 2)
    parser_refactor = subparsers.add_parser("refactor", help="Run Phase 2: Refactor (Consolidation & Remediation)")
    parser_refactor.add_argument("--run-id", required=True, help="Run identifier from a previous audit phase")

    # Command: sync (Phase 3)
    parser_sync = subparsers.add_parser("sync", help="Run Phase 3: Code Sync (Implementation)")
    parser_sync.add_argument("--run-id", required=True, help="Run identifier from a previous refactor phase")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_root = resolve_skill_root()
    repo_root = resolve_repo_root()

    if args.command == "audit":
        run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        config_dir = repo_root / "1_audit-report" / f"audit_{run_id}"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "pipeline-config.json"
        config = {
            "run_id": run_id,
            "figma_url": args.figma_url,
            "figma_mcp_variables": args.figma_mcp_variables,
            "figma_api_token_provided": bool(args.figma_api_token or os.getenv("FIGMA_ACCESS_TOKEN")),
            "figma_api_base": args.figma_api_base,
            "explicit_design_tokens_json": args.design_tokens_json,
            "pipeline": ["phase1_analysis"],
        }
        config_path.write_text(json.dumps(config, indent=2))

        api_token = args.figma_api_token or os.getenv("FIGMA_ACCESS_TOKEN")
        audit_dir, used_design_tokens_path, source_details, full_summary_path, artifact_manifest_path = run_phase1(
            repo_root,
            skill_root,
            args.figma_url,
            run_id,
            args.figma_mcp_variables,
            api_token,
            args.figma_api_base,
            args.design_tokens_json,
        )
        print("Phase 1 (Audit & Optimize) complete")
        print(f"Run ID: {run_id}")
        print(f"Data Source: {source_details['source_label']} ({source_details['source_kind']})")
        print(f"MCP Used: {source_details['mcp_used']}")
        if source_details["source_reference"]:
            print(f"Source Reference: {source_details['source_reference']}")
        print(f"Audit/Optimize Prerequisites Met: {source_details['audit_optimize_prerequisites_met']}")
        if source_details["fallback_reason"]:
            print(f"Fallback Reason: {source_details['fallback_reason']}")
        if source_details["user_notice"]:
            print(f"NOTICE: {source_details['user_notice']}")
        if source_details["prerequisite_notice"]:
            print(f"ACTION REQUIRED: {source_details['prerequisite_notice']}")
            for action in source_details["prerequisite_actions"]:
                if action["status"] == "required":
                    print(f"- {action['title']}: {action['instruction']}")
                    print(f"  Reason: {action['reason']}")
        config["audit_optimize_prerequisites_met"] = source_details["audit_optimize_prerequisites_met"]
        config["prerequisite_notice"] = source_details["prerequisite_notice"]
        config["prerequisite_actions"] = source_details["prerequisite_actions"]
        config_path.write_text(json.dumps(config, indent=2))
        print(f"Audit + Optimizer Report: {audit_dir}")
        print(f"Audit HTML: {audit_dir / 'audit-report.html'}")
        print(f"Optimizer HTML: {audit_dir / 'optimizer-report.html'}")
        print(f"Full Summary: {full_summary_path}")
        print(f"Artifact Manifest: {artifact_manifest_path}")
        print("To proceed to Phase 2, review the outputs and run: python run_pipeline.py refactor --run-id " + run_id)

    elif args.command == "refactor":
        run_id = args.run_id
        used_design_tokens_path = repo_root / "1_audit-report" / f"audit_{run_id}" / "design-tokens.used.json"
        if not used_design_tokens_path.exists():
            raise FileNotFoundError(f"Missing required input for refactor: {used_design_tokens_path}. Did you run 'audit' first?")
            
        refactor_dir = run_phase2(repo_root, script_dir, run_id, used_design_tokens_path)
        print("Phase 2 (Refactor) complete")
        print(f"Refactor Output: {refactor_dir}")
        print("To proceed to Phase 3, confirm the outputs and run: python run_pipeline.py sync --run-id " + run_id)

    elif args.command == "sync":
        run_id = args.run_id
        refactor_dir = repo_root / "3_refactor-output" / f"refactor_{run_id}"
        if not (refactor_dir / "figma-sync-tokens.json").exists():
            raise FileNotFoundError(f"Missing required input for code sync. Did you run 'refactor' first for run-id {run_id}?")
            
        sync_dir = run_phase3(repo_root, script_dir, run_id)
        print("Phase 3 (Code Sync) complete")
        print(f"Code Sync Output: {sync_dir}")


if __name__ == "__main__":
    main()
