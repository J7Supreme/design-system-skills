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


def build_summary_text(metadata: dict, stats: dict, fallback_reason: Optional[str]) -> tuple[str, str]:
    details = [
        summarize_source(metadata),
        f"Token inventory observed: {stats['token_count']}.",
        f"Schema coverage estimate: {stats['category_coverage']}%.",
        f"Potential invalid token names: {stats['invalid_name_count']}.",
    ]
    if fallback_reason:
        details.append(f"Fallback note: {fallback_reason}")
    text = " ".join(details)
    text_zh = (
        f"本次审计基于 {metadata.get('data_source') or '当前设计 Token 快照'} 生成。"
        f" 观测到的 Token 数量为 {stats['token_count']}。"
        f" Schema 覆盖率估算为 {stats['category_coverage']}%。"
        f" 潜在不合规 Token 命名数量为 {stats['invalid_name_count']}。"
    )
    if fallback_reason:
        text_zh += f" 兜底说明：{fallback_reason}"
    return text, text_zh


def build_default_dimensions(summary: dict, metadata: dict, stats: dict, wcag_profile: dict) -> list[dict]:
    overall = int(summary.get("overall_score", 0))
    ai_score = int(summary.get("ai_readiness_score", 0))
    dark_mode_required = metadata.get("dark_mode_required", False)
    dimension_scores = {
        "token_integrity": clamp(overall - 4 - min(12, stats["invalid_name_count"] // 3)),
        "component_integrity": clamp(overall - 2),
        "accessibility": clamp(overall - (10 if dark_mode_required else 4)),
        "structure_semantics": clamp(ai_score - 4),
        "variant_coverage": clamp(overall + 3),
        "naming_consistency": clamp(ai_score - 8 + max(0, 20 - stats["invalid_name_count"]) / 2),
    }
    metrics = {
        "token_integrity": [
            {"label": "Token inventory", "label_zh": "Token 总数", "value": str(stats["token_count"])},
            {"label": "Duplicate token values", "label_zh": "重复 Token 值", "value": str(stats["duplicate_value_count"])},
            {"label": "Potential invalid names", "label_zh": "潜在无效命名", "value": str(stats["invalid_name_count"])},
            {"label": "Schema coverage", "label_zh": "Schema 覆盖率", "value": f"{stats['category_coverage']}%"},
        ],
        "component_integrity": [
            {"label": "Component structure source", "label_zh": "组件结构来源", "value": metadata.get("data_source_kind", "N/A")},
            {"label": "Auto-layout coverage", "label_zh": "自动布局覆盖率", "value": "Pending detailed component scan"},
            {"label": "Detached instances", "label_zh": "断开实例数量", "value": "Pending detailed component scan"},
            {"label": "Token usage coverage", "label_zh": "Token 使用覆盖率", "value": f"{stats['category_coverage']}%"},
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
            {"label": "Missing states", "label_zh": "缺失状态", "value": "Pending component variant scan"},
            {"label": "Scaffold status", "label_zh": "补全状态", "value": "Fallback metrics applied"},
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
                "score": dimension_scores[key],
                "weight": weight,
                "color": "#22c55e" if dimension_scores[key] >= 80 else "#f59e0b" if dimension_scores[key] >= 65 else "#ef4444",
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
            "area": "Component Integrity",
            "area_zh": "组件完整性",
            "issue": "This run used fallback component metrics because detailed component analysis is not yet populated.",
            "issue_zh": "本次运行使用了兜底组件指标，因为详细组件分析结果尚未写入。",
            "impact": "The report remains renderable, but component-level findings should be treated as provisional.",
            "impact_zh": "报告可以稳定展示，但组件层面的结论应视为临时结果。",
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
    ai_score = int(summary.get("ai_readiness_score", 0))
    penalties = []
    if stats["invalid_name_count"] > 0:
        penalties.append(
            {
                "condition": "Invalid token names against configured schema",
                "condition_zh": "Token 命名不符合配置 schema",
                "deduction": min(20, max(4, stats["invalid_name_count"])),
            }
        )
    if stats["category_coverage"] < 100:
        penalties.append(
            {
                "condition": "Schema category coverage incomplete",
                "condition_zh": "Schema 分类覆盖不完整",
                "deduction": max(4, int((100 - stats["category_coverage"]) / 10)),
            }
        )
    if metadata.get("dark_mode_required"):
        penalties.append(
            {
                "condition": "Dark mode validation still required",
                "condition_zh": "仍需完成暗色模式校验",
                "deduction": 6,
            }
        )
    if not penalties:
        penalties.append(
            {
                "condition": "No fallback penalties applied",
                "condition_zh": "未应用兜底扣分项",
                "deduction": 0,
            }
        )
    return {
        "score": ai_score,
        "overall_score_used": summary.get("overall_score", ai_score),
        "hard_code_penalty_applied": False,
        "semantic_instability_detected": stats["invalid_name_count"] > 0,
        "prompt_generation_stability_estimate": clamp(ai_score + 5),
        "penalties": penalties,
        "notes": "AI readiness details were normalized with fallback data so the HTML report remains complete even when detailed analysis fields are missing.",
        "notes_zh": "AI 就绪性详情已通过兜底数据标准化，因此即使缺少详细分析字段，HTML 报告也能完整展示。",
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
    }
    metadata = deep_merge(metadata_defaults, raw_data.get("metadata", {}))

    summary_defaults = {
        "overall_score": 62,
        "ai_readiness_score": 58,
        "risk_level": "Medium",
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
