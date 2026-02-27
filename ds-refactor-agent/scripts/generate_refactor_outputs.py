import argparse
import json
from datetime import datetime
from pathlib import Path

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    elif len(hex_str) == 8:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4, 6))
    return (0,0,0)

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def overlay_on_white(r, g, b, a):
    # a is 0 to 255
    alpha = a / 255.0
    out_r = int(r * alpha + 255 * (1 - alpha))
    out_g = int(g * alpha + 255 * (1 - alpha))
    out_b = int(b * alpha + 255 * (1 - alpha))
    return rgb_to_hex(out_r, out_g, out_b)

def find_latest_proposed_tokens(base_dir: Path) -> Path:
    candidates = list(base_dir.glob("0_gap-report/gap_*/proposed-tokens.json"))
    if not candidates:
        raise FileNotFoundError("No proposed-tokens.json found under 0_gap-report/gap_*/")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def flatten_dict(d, parent_key=""):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict) and "value" not in v:
            items.extend(flatten_dict(v, new_key))
        elif isinstance(v, dict) and "value" in v:
            items.append((new_key, v["value"]))
    return items

def main():
    parser = argparse.ArgumentParser(description="Generate refactor artifacts from proposed tokens.")
    parser.add_argument("--design-tokens", type=str, default=None, help="Path to design-tokens.json")
    parser.add_argument("--proposed", type=str, default=None, help="Path to proposed-tokens.json")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for refactor artifacts")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    design_tokens_path = Path(args.design_tokens) if args.design_tokens else base_dir / "design-tokens.json"
    proposed_tokens_path = Path(args.proposed) if args.proposed else find_latest_proposed_tokens(base_dir)
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = base_dir / "3_refactor-output" / f"refactor_{timestamp}"

    out_dir.mkdir(parents=True, exist_ok=True)

    with design_tokens_path.open("r") as f:
        design_tokens = json.load(f)

    with proposed_tokens_path.open("r") as f:
        proposed_data = json.load(f)

    proposed_tokens = proposed_data.get("tokens", {})

    accessibility_fixes = []
    for k, v in design_tokens.get("colors", {}).items():
        if isinstance(v, str) and len(v) == 9 and v.startswith("#"):
            rgba = hex_to_rgb(v)
            solid_hex = overlay_on_white(rgba[0], rgba[1], rgba[2], rgba[3])
            accessibility_fixes.append({
                "legacy_name": k,
                "legacy_value": v,
                "resolved_solid_hex": solid_hex,
                "action": "Converted opacity hex to solid hex based on white background",
            })

    with (out_dir / "accessibility-fixes.json").open("w") as f:
        json.dump({"fixes": accessibility_fixes}, f, indent=4)

    dark_mode_tokens = {}
    for category, roles in proposed_tokens.get("color", {}).items():
        dark_mode_tokens[category] = {}
        for role, scales in roles.items():
            dark_mode_tokens[category][role] = {}
            if "500" in scales:
                for scale_val, data in scales.items():
                    if scale_val.isdigit():
                        num = int(scale_val)
                        inverted_num = 950 - num if num != 50 else 900
                        if inverted_num == 450:
                            inverted_num = 500
                        legacy_val = scales.get(str(inverted_num), data)["value"]
                        dark_mode_tokens[category][role][scale_val] = {
                            "value": legacy_val,
                            "method": f"Inverted from light mode {inverted_num}",
                        }
                    else:
                        dark_mode_tokens[category][role][scale_val] = {
                            "value": data["value"],
                            "method": "Direct passthrough for non-numeric scales (requires manual tuning)",
                        }

    with (out_dir / "dark-mode-tokens.json").open("w") as f:
        json.dump({"color": dark_mode_tokens}, f, indent=4)

    variant_gaps = [
        {
            "component": "Button",
            "missing_states": ["focus", "loading", "error", "skeleton"],
            "recommended_action": "Add variant property 'state' with values: focus, loading, error, skeleton",
        },
        {
            "component": "Input",
            "missing_states": ["focus", "error", "disabled"],
            "recommended_action": "Add variant property 'state' with values: focus, error, disabled",
        },
        {
            "component": "Card",
            "missing_states": ["hover", "focus", "skeleton"],
            "recommended_action": "Add variant property 'state' with values: hover, focus, skeleton for clickable cards",
        },
    ]
    with (out_dir / "variant-gaps.json").open("w") as f:
        json.dump(variant_gaps, f, indent=4)

    auto_layout_fixes = [
        {
            "target": "Modal Container",
            "issue": "Detached instance and absolute positioning",
            "fix": {
                "layoutMode": "VERTICAL",
                "primaryAxisAlignItems": "MIN",
                "counterAxisAlignItems": "MIN",
                "itemSpacing": "spacing.4",
            },
        },
        {
            "target": "Page Header",
            "issue": "Missing auto-layout",
            "fix": {
                "layoutMode": "HORIZONTAL",
                "primaryAxisAlignItems": "SPACE_BETWEEN",
                "counterAxisAlignItems": "CENTER",
                "itemSpacing": "spacing.5",
            },
        },
    ]
    with (out_dir / "auto-layout-fixes.json").open("w") as f:
        json.dump(auto_layout_fixes, f, indent=4)

    flat_sync_tokens = []
    for k, v in flatten_dict(proposed_tokens):
        node_type = (
            "color"
            if k.startswith("color")
            else "number"
            if k.startswith(("spacing", "radius", "z", "motion.duration"))
            else "string"
        )
        if k.startswith("font"):
            node_type = "typography"
        flat_sync_tokens.append({"name": k, "value": v, "type": node_type})

    figma_sync_payload = {
        "schema": "ai_token_schema_simple_v1",
        "status": "ready_for_figma_sync",
        "tokens": flat_sync_tokens,
    }
    with (out_dir / "figma-sync-tokens.json").open("w") as f:
        json.dump(figma_sync_payload, f, indent=4)

    print(f"Generated refactor outputs in: {out_dir}")


if __name__ == "__main__":
    main()
