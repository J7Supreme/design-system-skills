import json
import re
from pathlib import Path
from typing import Optional


DIMENSION_SPECS = [
    ("token_integrity", "Token Integrity", "Token 完整性", "25%"),
    ("component_integrity", "Component Integrity", "组件完整性", "20%"),
    ("accessibility", "Accessibility", "无障碍合规", "20%"),
    ("structure_semantics", "Structure & Semantics", "结构与语义", "15%"),
    ("variant_coverage", "Variant Coverage", "变体覆盖率", "10%"),
    ("naming_consistency", "Naming Consistency", "命名一致性", "10%"),
]

TOP_LEVEL_CATEGORY_ALIASES = {
    "colors": "color",
    "color": "color",
    "typography": "font",
    "font": "font",
    "spacing": "spacing",
    "radius": "radius",
    "border": "border",
    "shadow": "shadow",
    "opacity": "opacity",
}


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_profiles(skill_root: Path) -> tuple[dict, dict]:
    wcag_profile = load_profile(skill_root / "wcag-profile-customer-v1.json")
    token_schema = load_profile(skill_root / "ai-token-schema-simple-v1.json")
    return wcag_profile, token_schema


def clamp(value: int, lower: int = 0, upper: int = 100) -> int:
    return max(lower, min(upper, int(round(value))))


def flatten_token_names(node, prefix="") -> list[str]:
    names = []
    if isinstance(node, dict):
        if "value" in node and len(node) == 1:
            if prefix:
                names.append(prefix)
            return names
        for key, value in node.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                names.extend(flatten_token_names(value, next_prefix))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    names.extend(flatten_token_names(item, f"{next_prefix}.{index}"))
            else:
                names.append(next_prefix)
    return names


def flatten_token_values(node) -> list[str]:
    values = []
    if isinstance(node, dict):
        if "value" in node and len(node) == 1:
            values.append(str(node["value"]))
            return values
        for value in node.values():
            values.extend(flatten_token_values(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(flatten_token_values(item))
    elif node is not None:
        values.append(str(node))
    return values


def infer_total_token_count(design_tokens: Optional[dict]) -> int:
    if not isinstance(design_tokens, dict):
        return 0
    return len(flatten_token_names(design_tokens))


def infer_invalid_name_count(token_names: list[str], separator: str) -> int:
    if not token_names:
        return 0
    pattern = re.compile(rf"^[a-z0-9]+(?:\{separator}[a-z0-9]+){{2,}}$")
    invalid = 0
    for token_name in token_names:
        if not pattern.match(token_name):
            invalid += 1
    return invalid


def infer_duplicate_value_count(values: list[str]) -> int:
    seen = {}
    duplicates = 0
    for value in values:
        seen[value] = seen.get(value, 0) + 1
    for count in seen.values():
        if count > 1:
            duplicates += count - 1
    return duplicates


def infer_category_coverage(design_tokens: Optional[dict], token_schema: dict) -> int:
    if not isinstance(design_tokens, dict):
        return 0
    schema_categories = set(token_schema.get("categories", []))
    present = set()
    for key in design_tokens.keys():
        normalized = TOP_LEVEL_CATEGORY_ALIASES.get(str(key).lower())
        if normalized in schema_categories:
            present.add(normalized)
    if not schema_categories:
        return 0
    return clamp((len(present) / len(schema_categories)) * 100)


def summarize_source(metadata: dict) -> str:
    source = metadata.get("data_source") or "available design-token snapshot"
    source_kind = metadata.get("data_source_kind") or "unknown-source"
    return f"Audit synthesized from {source} ({source_kind})."


def summarize_source_ledger(metadata: dict) -> str:
    entries = metadata.get("data_sources") or []
    if not entries:
        return "No source ledger was recorded for this run."
    parts = []
    for entry in entries:
        label = entry.get("label", entry.get("kind", "Unknown source"))
        status = entry.get("status", "unknown")
        if entry.get("used_for_audit"):
            parts.append(f"{label}: used")
        elif status == "available_not_used":
            parts.append(f"{label}: available, not used")
        elif status == "not_provided":
            parts.append(f"{label}: not provided")
        else:
            parts.append(f"{label}: unavailable")
    return "Source ledger: " + "; ".join(parts) + "."


def build_summary_text(metadata: dict, stats: dict, fallback_reason: Optional[str]) -> tuple[str, str]:
    details = [
        summarize_source(metadata),
        summarize_source_ledger(metadata),
        f"Token inventory observed: {stats['token_count']}.",
        f"Schema coverage estimate: {stats['category_coverage']}%.",
        f"Potential invalid token names: {stats['invalid_name_count']}.",
    ]
    if metadata.get("user_notice"):
        details.append(f"User notice: {metadata['user_notice']}")
    if metadata.get("prerequisite_notice"):
        details.append(f"Prerequisite notice: {metadata['prerequisite_notice']}")
    if fallback_reason:
        details.append(f"Fallback note: {fallback_reason}")
    text = " ".join(details)
    text_zh = (
        f"本次审计基于 {metadata.get('data_source') or '当前设计 Token 快照'} 生成。"
        f" 来源台账：{summarize_source_ledger(metadata)}"
        f" 观测到的 Token 数量为 {stats['token_count']}。"
        f" Schema 覆盖率估算为 {stats['category_coverage']}%。"
        f" 潜在不合规 Token 命名数量为 {stats['invalid_name_count']}。"
    )
    if metadata.get("user_notice"):
        text_zh += f" 用户提示：{metadata['user_notice']}"
    if metadata.get("prerequisite_notice"):
        text_zh += f" 前置条件提示：{metadata['prerequisite_notice']}"
    if fallback_reason:
        text_zh += f" 兜底说明：{fallback_reason}"
    return text, text_zh


def build_default_dimensions(summary: dict, metadata: dict, stats: dict, wcag_profile: dict) -> list[dict]:
    dark_mode_required = metadata.get("dark_mode_required", False)
    metrics = {
        "token_integrity": [
            {"label": "Token inventory", "label_zh": "Token 总数", "value": str(stats["token_count"])},
            {"label": "Duplicate token values", "label_zh": "重复 Token 值", "value": str(stats["duplicate_value_count"])},
            {"label": "Potential invalid names", "label_zh": "潜在无效命名", "value": str(stats["invalid_name_count"])},
            {"label": "Schema coverage", "label_zh": "Schema 覆盖率", "value": f"{stats['category_coverage']}%"},
        ],
        "component_integrity": [
            {"label": "Component structure source", "label_zh": "组件结构来源", "value": metadata.get("data_source_kind", "N/A")},
            {"label": "Auto-layout coverage", "label_zh": "自动布局覆盖率", "value": "Not analyzed in this run"},
            {"label": "Detached instances", "label_zh": "断开实例数量", "value": "Not analyzed in this run"},
            {"label": "Component detail status", "label_zh": "组件明细状态", "value": "Detailed component audit data unavailable"},
        ],
        "accessibility": [
            {"label": "WCAG target", "label_zh": "WCAG 目标级别", "value": wcag_profile.get("target_level", "AA")},
            {"label": "Body text minimum", "label_zh": "正文最小对比度", "value": str(wcag_profile.get("contrast_rules", {}).get("body_text_min_ratio", 4.5))},
            {"label": "Large text minimum", "label_zh": "大字号最小对比度", "value": str(wcag_profile.get("contrast_rules", {}).get("large_text_min_ratio", 3.0))},
            {"label": "Dark mode required", "label_zh": "必须支持暗色模式", "value": "Yes / 是" if dark_mode_required else "No / 否"},
        ],
        "structure_semantics": [
            {"label": "Schema pattern", "label_zh": "Schema 模式", "value": metadata.get("token_schema_structure", "flat")},
            {"label": "Semantic layer required", "label_zh": "是否要求语义层", "value": "Yes / 是" if metadata.get("semantic_layer_required") else "No / 否"},
            {"label": "Naming convention", "label_zh": "命名规范", "value": metadata.get("token_naming_pattern", "category.role.scale")},
        ],
        "variant_coverage": [
            {"label": "Focus indicator required", "label_zh": "必须包含焦点指示器", "value": "Yes / 是" if metadata.get("focus_indicator_required") else "No / 否"},
            {"label": "Missing states", "label_zh": "缺失状态", "value": "Not analyzed in this run"},
            {"label": "Variant audit status", "label_zh": "变体审计状态", "value": "Detailed variant coverage unavailable"},
        ],
        "naming_consistency": [
            {"label": "Invalid token names", "label_zh": "无效 Token 命名", "value": str(stats["invalid_name_count"])},
            {"label": "Separator", "label_zh": "命名分隔符", "value": metadata.get("token_separator", ".")},
            {"label": "Lowercase required", "label_zh": "是否要求小写", "value": "Yes / 是" if metadata.get("lowercase_required") else "No / 否"},
        ],
    }

    output = []
    for key, label, label_zh, weight in DIMENSION_SPECS:
        output.append(
            {
                "key": key,
                "label": label,
                "label_zh": label_zh,
                "score": None,
                "weight": weight,
                "color": "#71717a",
                "metrics": metrics[key],
            }
        )
    return output


def build_default_critical_issues(metadata: dict, stats: dict) -> list[dict]:
    issues = []
    if stats["invalid_name_count"] > 0:
        issues.append(
            {
                "area": "Naming Consistency",
                "area_zh": "命名一致性",
                "issue": f"{stats['invalid_name_count']} token names do not match the configured schema pattern.",
                "issue_zh": f"有 {stats['invalid_name_count']} 个 Token 命名不符合当前 schema 规则。",
                "impact": "Weakens AI mapping reliability and makes downstream token sync less deterministic.",
                "impact_zh": "会削弱 AI 映射可靠性，并降低后续 Token 同步的确定性。",
                "severity": "High" if stats["invalid_name_count"] >= 10 else "Medium",
            }
        )
    if metadata.get("dark_mode_required"):
        issues.append(
            {
                "area": "Accessibility",
                "area_zh": "无障碍合规",
                "issue": "Dark mode is required by the WCAG profile and should be validated for contrast parity.",
                "issue_zh": "WCAG profile 要求支持暗色模式，需要验证其对比度一致性。",
                "impact": "If dark tokens are incomplete, accessibility certification can be blocked.",
                "impact_zh": "如果暗色 Token 不完整，无障碍认证会被阻塞。",
                "severity": "High",
            }
        )
    issues.append(
        {
            "area": "Audit Coverage",
            "area_zh": "审计覆盖率",
            "issue": "Detailed component and variant audit data were unavailable in this run.",
            "issue_zh": "本次运行缺少详细的组件与变体审计数据。",
            "impact": "Sections without underlying measurements are marked as unavailable instead of being scored.",
            "impact_zh": "没有底层测量数据的部分会标记为不可用，而不是继续给出评分。",
            "severity": "Medium",
        }
    )
    if metadata.get("fallback_reason"):
        issues.append(
            {
                "area": "Data Provenance",
                "area_zh": "数据来源",
                "issue": f"Fallback source was used: {metadata['fallback_reason']}",
                "issue_zh": f"本次运行使用了兜底来源：{metadata['fallback_reason']}",
                "impact": "Reviewers should validate the fallback source before treating the run as authoritative.",
                "impact_zh": "在将本次结果视为权威结论前，需要先验证兜底来源。",
                "severity": "Medium",
            }
        )
    return issues


def build_default_roadmap(metadata: dict, stats: dict) -> list[dict]:
    return [
        {
            "priority": "High",
            "area": "Token Naming",
            "area_zh": "Token 命名",
            "action": f"Rename the {stats['invalid_name_count']} invalid token names to follow {metadata.get('token_naming_pattern', 'category.role.scale')}.",
            "action_zh": f"将 {stats['invalid_name_count']} 个无效 Token 名称重命名为 {metadata.get('token_naming_pattern', 'category.role.scale')} 规范。",
            "expected_impact": "Improves token parsing stability for audits, refactors, and code sync.",
            "expected_impact_zh": "提升审计、重构和代码同步阶段的 Token 可解析性。",
        },
        {
            "priority": "High",
            "area": "Accessibility",
            "area_zh": "无障碍合规",
            "action": f"Validate all text and surface tokens against WCAG {metadata.get('wcag_target', 'AA')} thresholds from the external profile.",
            "action_zh": f"按外部 profile 中的 WCAG {metadata.get('wcag_target', 'AA')} 阈值校验所有文本和表面 Token。",
            "expected_impact": "Turns profile requirements into enforceable token checks instead of implicit assumptions.",
            "expected_impact_zh": "将 profile 要求转化为可执行的 Token 校验，而不是隐式假设。",
        },
        {
            "priority": "Medium",
            "area": "Audit Coverage",
            "area_zh": "审计覆盖率",
            "action": "Populate component structure metrics so the HTML report can replace fallback cards with actual findings.",
            "action_zh": "补充组件结构指标，让 HTML 报告用真实审计结果替代兜底卡片。",
            "expected_impact": "Reduces provisional audit content and increases report trustworthiness.",
            "expected_impact_zh": "减少临时兜底内容，提高审计报告的可信度。",
        },
    ]


def build_default_ai_readiness(summary: dict, metadata: dict, stats: dict) -> dict:
    penalties = []
    return {
        "score": None,
        "overall_score_used": summary.get("overall_score"),
        "hard_code_penalty_applied": False,
        "semantic_instability_detected": None,
        "prompt_generation_stability_estimate": None,
        "penalties": penalties,
        "notes": "AI readiness was not scored in this run because no dedicated AI-readiness analysis data was provided. The report shows provenance and observed token facts only.",
        "notes_zh": "本次运行未提供专门的 AI 就绪性分析数据，因此没有给出 AI 就绪性评分。报告仅展示来源信息和已观测的 Token 事实。",
    }


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def normalize_audit_data(raw_data: dict, skill_root: Path, design_tokens: Optional[dict] = None) -> dict:
    wcag_profile, token_schema = load_profiles(skill_root)
    raw_data = raw_data or {}

    token_names = flatten_token_names(design_tokens) if isinstance(design_tokens, dict) else []
    token_values = flatten_token_values(design_tokens) if isinstance(design_tokens, dict) else []
    stats = {
        "token_count": infer_total_token_count(design_tokens),
        "invalid_name_count": infer_invalid_name_count(
            token_names, token_schema.get("naming_convention", {}).get("separator", ".")
        ),
        "duplicate_value_count": infer_duplicate_value_count(token_values),
        "category_coverage": infer_category_coverage(design_tokens, token_schema),
    }

    metadata_defaults = {
        "project_name": "Webapp Design System",
        "file_id": "unknown-file",
        "node_id": "",
        "figma_url": "",
        "audit_timestamp": "",
        "auditor": "Design System Governance Workflow v1 (pipeline-local)",
        "wcag_profile": wcag_profile.get("profile_name"),
        "wcag_target": wcag_profile.get("target_level"),
        "enforce_wcag_aaa": wcag_profile.get("contrast_rules", {}).get("enforce_aaa", False),
        "theme_modes_checked": ["light", "dark"],
        "dark_mode_required": wcag_profile.get("dark_mode_rules", {}).get("dark_mode_required", False),
        "focus_indicator_required": wcag_profile.get("interaction_rules", {}).get("focus_indicator_required", False),
        "token_schema_version": token_schema.get("schema_name"),
        "token_schema_structure": token_schema.get("structure_type"),
        "token_naming_pattern": token_schema.get("naming_convention", {}).get("pattern"),
        "token_separator": token_schema.get("naming_convention", {}).get("separator", "."),
        "lowercase_required": token_schema.get("naming_convention", {}).get("lowercase_required", True),
        "semantic_layer_required": token_schema.get("rules", {}).get("semantic_layer_required", False),
        "hard_code_warning_threshold_percent": token_schema.get("rules", {}).get("hard_code_warning_threshold_percent", 15),
        "data_source": "unknown",
        "data_source_reference": None,
        "data_source_kind": "unknown",
        "mcp_used": False,
        "fallback_reason": None,
        "user_notice": None,
        "prerequisite_notice": None,
        "data_sources": [],
    }
    metadata = deep_merge(metadata_defaults, raw_data.get("metadata", {}))

    summary_defaults = {
        "overall_score": None,
        "ai_readiness_score": None,
        "risk_level": "Unknown",
    }
    summary = deep_merge(summary_defaults, raw_data.get("summary", {}))
    summary_text, summary_text_zh = build_summary_text(metadata, stats, metadata.get("fallback_reason"))
    summary.setdefault("text", summary_text)
    summary.setdefault("text_zh", summary_text_zh)

    dimensions = raw_data.get("dimensions") or build_default_dimensions(summary, metadata, stats, wcag_profile)
    critical_issues = raw_data.get("critical_issues") or build_default_critical_issues(metadata, stats)
    roadmap = raw_data.get("roadmap") or build_default_roadmap(metadata, stats)
    ai_readiness = deep_merge(
        build_default_ai_readiness(summary, metadata, stats),
        raw_data.get("ai_readiness", {}),
    )

    return {
        "metadata": metadata,
        "summary": summary,
        "dimensions": dimensions,
        "critical_issues": critical_issues,
        "roadmap": roadmap,
        "ai_readiness": ai_readiness,
    }
