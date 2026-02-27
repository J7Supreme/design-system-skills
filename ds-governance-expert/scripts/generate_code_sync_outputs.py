import argparse
import json
from datetime import datetime
from pathlib import Path


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def find_latest_refactor_dir(base_dir: Path) -> Path:
    candidates = list((base_dir / "3_refactor-output").glob("refactor_*"))
    if not candidates:
        raise FileNotFoundError("No refactor_* directory found under 3_refactor-output/")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def flatten_dark_mode_color(node, prefix="color"):
    flat = []
    if not isinstance(node, dict):
        return flat
    for k, v in node.items():
        new_prefix = f"{prefix}.{k}"
        if isinstance(v, dict) and "value" in v:
            flat.append({"name": new_prefix, "value": v["value"], "type": "color"})
        elif isinstance(v, dict):
            flat.extend(flatten_dark_mode_color(v, new_prefix))
    return flat


def hex_to_figma_rgba(hex_str: str):
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c + c for c in hex_str)

    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    a = 1.0
    if len(hex_str) == 8:
        a = int(hex_str[6:8], 16) / 255.0

    return {"r": r, "g": g, "b": b, "a": a}


def main():
    parser = argparse.ArgumentParser(description="Generate code-sync artifacts from refactor outputs.")
    parser.add_argument("--input", type=str, default=None, help="Path to figma-sync-tokens.json")
    parser.add_argument("--dark", type=str, default=None, help="Path to dark-mode-tokens.json")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for code-sync artifacts")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    latest_refactor_dir = find_latest_refactor_dir(base_dir)

    input_path = Path(args.input) if args.input else latest_refactor_dir / "figma-sync-tokens.json"
    dark_mode_path = Path(args.dark) if args.dark else latest_refactor_dir / "dark-mode-tokens.json"

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = base_dir / "4_code-sync-output" / f"sync_{timestamp}"

    out_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r") as f:
        master_data = json.load(f)
    with dark_mode_path.open("r") as f:
        dark_data = json.load(f)

    tokens_list = master_data.get("tokens", [])
    dark_list = dark_data.get("tokens", [])
    if not dark_list and "color" in dark_data:
        dark_list = flatten_dark_mode_color(dark_data.get("color", {}), prefix="color")

    # 2. W3C DTCG Format Converter (tokens.w3c.json)
    w3c_dict = {}
    type_mapping = {
        "color": "color",
        "spacing": "dimension",
        "radius": "dimension",
        "size": "dimension",
        "fontFamily": "fontFamily",
        "fontWeight": "fontWeight",
        "lineHeight": "number",
        "letterSpacing": "dimension",
        "shadow": "shadow",
        "duration": "duration",
        "easing": "cubicBezier",
        "z": "number",
    }

    for t in tokens_list:
        name_parts = t["name"].split(".")
        val = t["value"]

        raw_type = t.get("type") or name_parts[0]
        w3c_type = type_mapping.get(raw_type, raw_type)

        if raw_type == "font":
            if "size" in name_parts:
                w3c_type = "dimension"
            if "family" in name_parts:
                w3c_type = "fontFamily"
            if "weight" in name_parts:
                w3c_type = "fontWeight"

        nested_set(w3c_dict, name_parts, {"$value": val, "$type": w3c_type})

    w3c_output = {
        "$schema": "https://design-tokens.github.io/community-group/format/",
        "tokens": w3c_dict,
    }
    with (out_dir / "tokens.w3c.json").open("w") as f:
        json.dump(w3c_output, f, indent=4)
    print("Generated W3C Tokens: tokens.w3c.json")

    # 3. CSS Variables Converter (variables.css)
    css_lines = [":root {"]
    for t in tokens_list:
        var_name = "--" + t["name"].replace(".", "-")
        css_lines.append(f"  {var_name}: {t['value']};")
    css_lines.append("}\n")

    if dark_list:
        css_lines.append("@media (prefers-color-scheme: dark) {")
        css_lines.append("  :root {")
        for dt in dark_list:
            var_name = "--" + dt["name"].replace(".", "-")
            if "value" in dt:
                css_lines.append(f"    {var_name}: {dt['value']};")
        css_lines.append("  }")
        css_lines.append("}\n")

        css_lines.append(".dark {")
        for dt in dark_list:
            var_name = "--" + dt["name"].replace(".", "-")
            if "value" in dt:
                css_lines.append(f"  {var_name}: {dt['value']};")
        css_lines.append("}\n")

    with (out_dir / "variables.css").open("w") as f:
        f.write("\n".join(css_lines))
    print("Generated CSS Variables: variables.css")

    # 4. Tailwind Config Extender (tailwind.theme.js)
    tw_colors = {}
    tw_spacing = {}
    tw_radius = {}
    tw_fonts = {}
    tw_shadows = {}

    for t in tokens_list:
        name_parts = t["name"].split(".")
        var_ref = f"var(--{t['name'].replace('.', '-')})"

        if name_parts[0] == "color":
            nested_set(tw_colors, name_parts[1:], var_ref)
        elif name_parts[0] == "spacing":
            nested_set(tw_spacing, name_parts[1:], var_ref)
        elif name_parts[0] == "radius":
            nested_set(tw_radius, name_parts[1:], var_ref)
        elif name_parts[0] == "shadow":
            nested_set(tw_shadows, name_parts[1:], var_ref)
        elif name_parts[0] == "font":
            if name_parts[1] == "family":
                nested_set(tw_fonts, ["family"] + name_parts[2:], var_ref)
            elif name_parts[1] == "size":
                nested_set(tw_fonts, ["size"] + name_parts[2:], var_ref)

    tw_output = f"""/** @type {{import('tailwindcss').Config}} */
module.exports = {{
  theme: {{
    extend: {{
      colors: {json.dumps(tw_colors, indent=6)},
      spacing: {json.dumps(tw_spacing, indent=6)},
      borderRadius: {json.dumps(tw_radius, indent=6)},
      boxShadow: {json.dumps(tw_shadows, indent=6)},
      fontFamily: {json.dumps(tw_fonts.get('family', dict()), indent=6)},
      fontSize: {json.dumps(tw_fonts.get('size', dict()), indent=6)}
    }}
  }}
}}
"""

    with (out_dir / "tailwind.theme.js").open("w") as f:
        f.write(tw_output)
    print("Generated Tailwind Config: tailwind.theme.js")

    # 5. Figma Variables Sync Payload (figma-api-payload.json)
    figma_collections = {
        "colors": {
            "modes": {"Light": "light_mode_id", "Dark": "dark_mode_id"},
            "variables": [],
        },
        "numbers": {
            "modes": {"Value": "default_mode"},
            "variables": [],
        },
        "strings": {
            "modes": {"Value": "default_mode"},
            "variables": [],
        },
    }

    dark_mode_map = {dt["name"]: dt for dt in dark_list}

    for t in tokens_list:
        cat = t["name"].split(".")[0]
        val = t["value"]

        if cat in ["color", "background", "border", "text", "icon"]:
            try:
                light_val = hex_to_figma_rgba(val)
                dark_val = hex_to_figma_rgba(dark_mode_map.get(t["name"], {}).get("value", val))
                figma_collections["colors"]["variables"].append(
                    {
                        "name": t["name"].replace(".", "/"),
                        "type": "COLOR",
                        "valuesByMode": {
                            "light_mode_id": light_val,
                            "dark_mode_id": dark_val,
                        },
                    }
                )
            except Exception:
                pass
        elif cat in ["spacing", "radius", "z"]:
            try:
                num = float(str(val).replace("px", ""))
                figma_collections["numbers"]["variables"].append(
                    {
                        "name": t["name"].replace(".", "/"),
                        "type": "FLOAT",
                        "valuesByMode": {"default_mode": num},
                    }
                )
            except Exception:
                pass
        else:
            figma_collections["strings"]["variables"].append(
                {
                    "name": t["name"].replace(".", "/"),
                    "type": "STRING",
                    "valuesByMode": {"default_mode": str(val)},
                }
            )

    with (out_dir / "figma-api-payload.json").open("w") as f:
        json.dump({"collections": figma_collections}, f, indent=4)
    print("Generated Figma Variables API Payload: figma-api-payload.json")
    print(f"Generated code-sync outputs in: {out_dir}")


if __name__ == "__main__":
    main()
