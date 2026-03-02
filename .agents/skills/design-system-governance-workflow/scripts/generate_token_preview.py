import json
import os
import argparse
from datetime import datetime

def generate_preview(input_json_path: str, output_html_path: str):
    with open(input_json_path, "r") as f:
        proposed_data = json.load(f)

    tokens = proposed_data.get("tokens", {}).get("color", {})
    brand_primary = tokens.get("brand", {}).get("primary", {}).get("500", {}).get("value", "#000000")
    bg_primary = proposed_data.get("tokens", {}).get("background", {}).get("primary", {}).get("value", "#ffffff")
    text_primary = proposed_data.get("tokens", {}).get("text", {}).get("primary", {}).get("value", "#000000")

    # Extract scales for display
    primary_scale = tokens.get("brand", {}).get("primary", {})
    neutral_scale = tokens.get("neutral", {})
    status_success = tokens.get("status", {}).get("success", {})
    status_warning = tokens.get("status", {}).get("warning", {})
    status_danger = tokens.get("status", {}).get("danger", {})
    status_info = tokens.get("status", {}).get("info", {})

    def generate_color_swatches(scale_dict):
        swatches_html = ""
        # Sort numeric keys if possible
        keys = sorted(scale_dict.keys(), key=lambda x: int(x) if x.isdigit() else 9999)
        for k in keys:
            val = scale_dict[k].get("value", "#000")
            swatches_html += f"""
            <div class="flex flex-col gap-2">
                <div class="h-16 w-full rounded-md border" style="background-color: {val};"></div>
                <div class="flex justify-between text-xs">
                    <span class="font-medium text-slate-700">{k}</span>
                    <span class="text-slate-500 uppercase">{val}</span>
                </div>
            </div>
            """
        return swatches_html

    def generate_status_swatches(status_dict):
        swatches_html = ""
        for k, v in status_dict.items():
            val = v.get("value", "#000")
            swatches_html += f"""
            <div class="flex flex-col gap-2">
                <div class="h-16 w-full rounded-md border" style="background-color: {val};"></div>
                <div class="flex justify-between text-xs">
                    <span class="font-medium text-slate-700">{k}</span>
                    <span class="text-slate-500 uppercase">{val}</span>
                </div>
            </div>
            """
        return swatches_html

    # Extract spacing, radius, typography
    spacing_tokens = proposed_data.get("tokens", {}).get("spacing", {})
    radius_tokens = proposed_data.get("tokens", {}).get("radius", {})

    def generate_spacing_table(spacing_dict):
        keys = sorted(spacing_dict.keys(), key=lambda x: int(x) if x.isdigit() else 9999)
        html = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">'
        for k in keys:
            val = spacing_dict[k].get("value")
            # Try to extract px value for visual box if it exists
            px_val = val.replace("px", "") if isinstance(val, str) and "px" in val else "0"
            html += f"""
            <div class="flex items-center gap-4 border-b pb-4">
                <div class="w-12 text-sm font-medium text-slate-700">space-{k}</div>
                <div class="w-16 text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded text-center">{val}</div>
                <div class="flex-1 flex items-center">
                    <div class="bg-[var(--primary)] opacity-20" style="width: {px_val}px; height: 16px;"></div>
                </div>
            </div>
            """
        html += "</div>"
        return html

    def generate_radius_table(radius_dict):
        keys = ["none", "sm", "md", "lg", "xl", "2xl", "full"] # common order
        # filter keys that exist
        keys = [k for k in keys if k in radius_dict]
        html = '<div class="grid grid-cols-2 md:grid-cols-4 gap-6">'
        for k in keys:
            val = radius_dict[k].get("value")
            html += f"""
            <div class="flex flex-col gap-3">
                <div class="h-24 w-full bg-slate-100 border border-slate-200" style="border-radius: {val};"></div>
                <div class="flex justify-between items-center text-sm">
                    <span class="font-medium text-slate-700">radius-{k}</span>
                    <span class="text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded">{val}</span>
                </div>
            </div>
            """
        html += "</div>"
        return html

    typography_tokens = proposed_data.get("tokens", {}).get("font", {})

    def generate_typography_table(font_dict):
        family = font_dict.get("family", {})
        size = font_dict.get("size", {})
        # weight = font_dict.get("weight", {}) # Not used in the provided snippet
        # lineheight = font_dict.get("lineheight", {}) # Not used in the provided snippet
        
        html = '<div class="space-y-8">'
        
        # Font Families
        html += '<div class="grid grid-cols-1 md:grid-cols-3 gap-6">'
        for k, v in family.items():
            val = v.get("value", "")
            html += f"""
            <div class="p-4 border rounded-lg bg-white">
                <div class="text-xs text-slate-500 uppercase tracking-wider mb-2">font-{k}</div>
                <div class="font-medium text-slate-900 text-xl" style="font-family: {val}">{val}</div>
            </div>
            """
        html += '</div>'

        # Font Sizes
        html += '<div><h4 class="text-sm font-semibold text-slate-500 mb-3 uppercase tracking-wider">Sizes</h4>'
        html += '<div class="space-y-4">'
        # Use standard ordering for typical tailwind sizes, fallback to alphabetical
        size_order = {"xs":1, "sm":2, "base":3, "lg":4, "xl":5, "2xl":6, "3xl":7, "4xl":8, "5xl":9}
        keys = sorted(size.keys(), key=lambda k: size_order.get(k, 100))
        for k in keys:
            v = size[k]
            val = v.get("value", "16px")
            html += f"""
            <div class="flex items-end gap-6 border-b pb-4">
                <div class="w-16 text-sm font-medium text-slate-700">text-{k}</div>
                <div class="w-16 text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded text-center mb-1">{val}</div>
                <div class="flex-1 text-slate-900 truncate" style="font-size: {val}; line-height: 1;">The quick brown fox jumps over the lazy dog</div>
            </div>
            """
        html += '</div></div>'
        
        html += '</div>'
        return html

    shadow_tokens = proposed_data.get("tokens", {}).get("shadow", {})

    def generate_shadow_table(shadow_dict):
        keys = ["none", "xs", "sm", "md", "lg", "xl", "2xl"]
        keys = [k for k in keys if k in shadow_dict]
        html = '<div class="grid grid-cols-2 lg:grid-cols-4 gap-8">'
        for k in keys:
            val = shadow_dict[k].get("value")
            html += f"""
            <div class="flex flex-col gap-4">
                <div class="h-24 w-full bg-white rounded-lg border border-slate-100 flex items-center justify-center p-4 text-center text-xs text-slate-400" style="box-shadow: {val};">
                    Shadow {k.upper()}
                </div>
                <div class="flex flex-col gap-1">
                    <span class="font-medium text-slate-700 text-sm">shadow-{k}</span>
                    <span class="text-xs text-slate-500 font-mono break-all">{val}</span>
                </div>
            </div>
            """
        html += "</div>"
        return html

    zindex_tokens = proposed_data.get("tokens", {}).get("z", {})

    def generate_zindex_table(z_dict):
        keys = ["below", "base", "raised", "dropdown", "sticky", "overlay", "modal", "toast", "tooltip"]
        keys = [k for k in keys if k in z_dict]
        
        html = '<div class="space-y-2">'
        for i, k in enumerate(keys):
            val = z_dict[k].get("value")
            # Visual stacking representation
            bg_opacity = 100 - (i * 10)
            html += f"""
            <div class="flex items-center justify-between p-3 border rounded-md bg-white relative overflow-hidden">
                <div class="absolute inset-0 bg-slate-900" style="opacity: {bg_opacity}%; z-index: {val};"></div>
                <div class="relative z-10 flex w-full justify-between items-center text-white mix-blend-difference">
                    <span class="font-medium">z-{k}</span>
                    <span class="font-mono bg-white/20 px-2 py-0.5 rounded text-sm">{val}</span>
                </div>
            </div>
            """
        html += "</div>"
        return html

    motion_tokens = proposed_data.get("tokens", {}).get("motion", {})

    def generate_motion_table(motion_dict):
        duration = motion_dict.get("duration", {})
        easing = motion_dict.get("easing", {})

        html = '<div class="grid grid-cols-1 md:grid-cols-2 gap-8">'
        
        # Durations
        html += '<div><h4 class="font-medium text-slate-700 mb-4">Duration</h4><div class="space-y-4">'
        # Order by size roughly
        d_keys = sorted(duration.keys(), key=lambda x: int(duration[x].get("value", "0ms").replace("ms",""))) if duration else []
        for k in d_keys:
            val = duration[k].get("value")
            html += f"""
            <div class="flex items-center gap-4">
                <div class="w-16 text-sm font-medium text-slate-700">duration-{k}</div>
                <div class="w-16 text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded text-center">{val}</div>
                <div class="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div class="h-full bg-[var(--primary)] rounded-full transition-all" style="width: 100%; transition-duration: {val};"></div>
                </div>
            </div>
            """
        html += '</div></div>'

        # Easing
        html += '<div><h4 class="font-medium text-slate-700 mb-4">Easing</h4><div class="space-y-4">'
        for k, v in easing.items():
            val = v.get("value")
            html += f"""
            <div class="flex items-center gap-4">
                <div class="w-20 text-sm font-medium text-slate-700">ease-{k}</div>
                <div class="flex-1 text-xs text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded truncate">{val}</div>
            </div>
            """
        html += '</div></div>'

        html += '</div>'
        return html

    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "optimizer-report-template.html")
    with open(template_path, "r", encoding="utf-8") as tf:
        html_template = tf.read()

    html_content = html_template.replace("__BRAND_PRIMARY__", str(brand_primary)) \
        .replace("__COLOR_PRIMARY_SCALE__", generate_color_swatches(primary_scale)) \
        .replace("__COLOR_NEUTRAL_SCALE__", generate_color_swatches(neutral_scale)) \
        .replace("__STATUS_SUCCESS_SWATCHES__", generate_status_swatches(status_success)) \
        .replace("__STATUS_WARNING_SWATCHES__", generate_status_swatches(status_warning)) \
        .replace("__STATUS_DANGER_SWATCHES__", generate_status_swatches(status_danger)) \
        .replace("__STATUS_INFO_SWATCHES__", generate_status_swatches(status_info)) \
        .replace("__SPACING_TABLE__", generate_spacing_table(spacing_tokens)) \
        .replace("__RADIUS_TABLE__", generate_radius_table(radius_tokens)) \
        .replace("__TYPOGRAPHY_TABLE__", generate_typography_table(typography_tokens)) \
        .replace("__SHADOW_TABLE__", generate_shadow_table(shadow_tokens)) \
        .replace("__ZINDEX_TABLE__", generate_zindex_table(zindex_tokens)) \
        .replace("__MOTION_TABLE__", generate_motion_table(motion_tokens)) \
        .replace("__DANGER_DEFAULT__", status_danger.get('default', {}).get('value', '#ef4444')) \
        .replace("__INFO_SUBTLE__", status_info.get('subtle', {}).get('value', '#eff6ff')) \
        .replace("__INFO_BORDER__", status_info.get('border', {}).get('value', '#bfdbfe')) \
        .replace("__INFO_TEXT__", status_info.get('text', {}).get('value', '#1e3a8a')) \
        .replace("__SUCCESS_SUBTLE__", status_success.get('subtle', {}).get('value', '#f0fdf4')) \
        .replace("__SUCCESS_BORDER__", status_success.get('border', {}).get('value', '#bbf7d0')) \
        .replace("__SUCCESS_TEXT__", status_success.get('text', {}).get('value', '#14532d')) \
        .replace("__WARNING_SUBTLE__", status_warning.get('subtle', {}).get('value', '#fffbeb')) \
        .replace("__WARNING_BORDER__", status_warning.get('border', {}).get('value', '#fde68a')) \
        .replace("__WARNING_TEXT__", status_warning.get('text', {}).get('value', '#78350f')) \
        .replace("__DANGER_SUBTLE__", status_danger.get('subtle', {}).get('value', '#fef2f2')) \
        .replace("__DANGER_BORDER__", status_danger.get('border', {}).get('value', '#fecaca')) \
        .replace("__DANGER_TEXT__", status_danger.get('text', {}).get('value', '#7f1d1d'))

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Token optimization preview generated at: {output_html_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate Token Preview HTML")
    parser.add_argument("--json", required=True, help="Path to proposed-tokens.json")
    parser.add_argument("--out", required=True, help="Output HTML path")
    args = parser.parse_args()
    
    generate_preview(args.json, args.out)
