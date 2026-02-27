import argparse
import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


def extract_figma_parts(figma_url: str):
    file_match = re.search(r"/design/([^/]+)/", figma_url)
    file_id = file_match.group(1) if file_match else "unknown-file"
    query = parse_qs(urlparse(figma_url).query)
    node_id = query.get("node-id", [""])[0]
    return file_id, node_id


def is_hex_color(value: str) -> bool:
    return isinstance(value, str) and re.match(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", value) is not None


def rgba_dict_to_hex(rgba: dict) -> str:
    r = int(round(float(rgba.get("r", 0)) * 255))
    g = int(round(float(rgba.get("g", 0)) * 255))
    b = int(round(float(rgba.get("b", 0)) * 255))
    a = float(rgba.get("a", 1.0))
    if a < 1:
        alpha = int(round(a * 255))
        return f"#{r:02x}{g:02x}{b:02x}{alpha:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_variable_defs_text(raw_text: str) -> dict:
    """
    Supports simplified outputs like:
    {'icon/default/secondary': #949494, 'text/primary': #111d4a}
    """
    colors = {}
    for name, hex_value in re.findall(r"'([^']+)'\s*:\s*(#[0-9a-fA-F]{6,8})", raw_text):
        colors[name] = hex_value.lower()
    return {"colors": colors, "typography": {}, "effects": {}}


def parse_payload(payload: dict) -> dict:
    if "colors" in payload and isinstance(payload["colors"], dict):
        return {
            "colors": payload.get("colors", {}),
            "typography": payload.get("typography", {}),
            "effects": payload.get("effects", {}),
        }

    colors = {}

    variables_map = payload.get("variables", {})
    if isinstance(variables_map, dict):
        for name, value in variables_map.items():
            if is_hex_color(value):
                colors[name.replace(".", "/")] = value.lower()

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
                    colors[name.replace(".", "/")] = rgba_dict_to_hex(first_mode_value)

    return {"colors": colors, "typography": {}, "effects": {}}


def load_input_data(input_json: Optional[Path], input_text: Optional[Path]) -> dict:
    if input_json:
        return json.loads(input_json.read_text())
    if input_text:
        raw = input_text.read_text()
        return {"_from_text": raw}
    raise ValueError("Provide --input-json or --input-text")


def main():
    parser = argparse.ArgumentParser(
        description="Normalize Figma MCP variable outputs into design-tokens-like snapshot for run_pipeline."
    )
    parser.add_argument("--figma-url", required=True, help="Figma URL containing file id and node id")
    parser.add_argument("--input-json", default=None, help="Path to MCP output JSON payload")
    parser.add_argument("--input-text", default=None, help="Path to raw text output from MCP get_variable_defs")
    parser.add_argument("--out-dir", default="2_figma-mcp-snapshot", help="Snapshot output directory")
    args = parser.parse_args()

    file_id, node_id = extract_figma_parts(args.figma_url)
    if not file_id or not node_id:
        raise ValueError("Unable to parse file id or node id from --figma-url")

    payload = load_input_data(
        Path(args.input_json) if args.input_json else None,
        Path(args.input_text) if args.input_text else None,
    )

    if "_from_text" in payload:
        normalized = parse_variable_defs_text(payload["_from_text"])
        source_type = "mcp_text"
    else:
        normalized = parse_payload(payload)
        source_type = "mcp_json"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    node_dash = node_id.replace(":", "-")
    target = out_dir / f"{file_id}__{node_dash}.json"
    latest = out_dir / "latest.json"

    wrapped = {
        "meta": {
            "source_type": source_type,
            "figma_url": args.figma_url,
            "file_id": file_id,
            "node_id": node_id,
        },
        **normalized,
    }

    target.write_text(json.dumps(wrapped, indent=2))
    latest.write_text(json.dumps(wrapped, indent=2))

    print(f"Exported snapshot: {target}")
    print(f"Updated latest: {latest}")
    print(f"Color variables: {len(normalized.get('colors', {}))}")


if __name__ == "__main__":
    main()
