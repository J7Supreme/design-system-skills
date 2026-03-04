import json
import os
import argparse
from datetime import datetime
from html import escape

def generate_preview(input_json_path: str, output_html_path: str):
    with open(input_json_path, "r") as f:
        proposed_data = json.load(f)

    metadata = proposed_data.get("metadata", {})
    tokens = proposed_data.get("tokens", {}).get("color", {})
    brand_primary = tokens.get("brand", {}).get("primary", {}).get("500", {}).get("value", "transparent")

    # Extract scales for display
    primary_scale = tokens.get("brand", {}).get("primary", {})
    neutral_scale = tokens.get("neutral", {})
    status_success = tokens.get("status", {}).get("success", {})
    status_warning = tokens.get("status", {}).get("warning", {})
    status_danger = tokens.get("status", {}).get("danger", {})
    status_info = tokens.get("status", {}).get("info", {})

    def empty_state(message):
        return f"""
        <div class="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
            {escape(message)}
        </div>
        """

    def render_provenance_banner():
        data_sources = metadata.get("data_sources", [])
        source_cards = []
        for source in data_sources:
            status = source.get("status", "unknown").replace("_", " ")
            source_cards.append(
                f"""
                <div class="rounded-lg border border-slate-200 bg-white p-4">
                    <div class="flex items-center justify-between gap-3">
                        <div class="font-semibold text-slate-900">{escape(source.get("label", source.get("kind", "Unknown source")))}</div>
                        <div class="text-xs uppercase tracking-wider text-slate-500">{escape(status)}</div>
                    </div>
                    <div class="mt-2 text-xs text-slate-500">Reference: {escape(source.get("reference") or "None")}</div>
                    <div class="mt-1 text-xs text-slate-500">Reason: {escape(source.get("reason") or "None")}</div>
                </div>
                """
            )

        notices = []
        if metadata.get("user_notice"):
            notices.append(metadata["user_notice"])
        if metadata.get("prerequisite_notice"):
            notices.append(metadata["prerequisite_notice"])

        notices_html = "".join(
            f'<div class="rounded-md border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-900">{escape(note)}</div>'
            for note in notices
        )
        source_cards_html = "".join(source_cards) if source_cards else empty_state("No source ledger was recorded for this run.")
        proposal_note = metadata.get(
            "proposal_note",
            "This preview renders generated proposal tokens only.",
        )
        return f"""
        <div class="mt-6 space-y-4">
            <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div class="text-sm font-semibold uppercase tracking-wider text-slate-500">Data Provenance</div>
                <div class="mt-2 text-sm text-slate-600">
                    Primary source: {escape(metadata.get("source_label") or "Unknown")} ({escape(metadata.get("source_kind") or "unknown")})<br>
                    MCP used: {escape("Yes" if metadata.get("mcp_used") else "No")}<br>
                    Source reference: {escape(metadata.get("source_reference") or "None")}<br>
                    Proposal note: {escape(proposal_note)}
                </div>
                <div class="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {source_cards_html}
                </div>
            </div>
            {notices_html}
        </div>
        """

    def generate_color_swatches(scale_dict):
        if not scale_dict:
            return empty_state("No proposed tokens for this category in this run.")
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
        if not status_dict:
            return empty_state("No proposed semantic tokens in this state.")
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
        if not spacing_dict:
            return empty_state("No proposed spacing tokens in this run.")
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
        if not radius_dict:
            return empty_state("No proposed radius tokens in this run.")
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
        if not family and not size:
            return empty_state("No proposed typography tokens in this run.")
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
        if not shadow_dict:
            return empty_state("No proposed shadow tokens in this run.")
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
        if not z_dict:
            return empty_state("No proposed z-index tokens in this run.")
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
        if not duration and not easing:
            return empty_state("No proposed motion tokens in this run.")

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

    def generate_destructive_button():
        destructive = status_danger.get("default", {}).get("value")
        if not destructive:
            return empty_state("No proposed destructive token was generated for this run.")
        return f"""
        <button class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 text-white shadow hover:opacity-90 h-9 px-4 py-2" style="background-color: {destructive}">
            Destructive
        </button>
        """

    def generate_alert_previews():
        alert_specs = [
            ("info", "System Update", "A new software version is available for download.", "info", status_info),
            ("success", "Payment Successful", "Your transaction has been processed correctly.", "check-circle-2", status_success),
            ("warning", "Usage Warning", "You are approaching your monthly API limit.", "alert-triangle", status_warning),
            ("danger", "Connection Error", "Failed to connect to the database. Please try again.", "alert-octagon", status_danger),
        ]
        cards = []
        for _, title, body, icon, values in alert_specs:
            subtle = values.get("subtle", {}).get("value")
            border = values.get("border", {}).get("value")
            text = values.get("text", {}).get("value")
            if not (subtle and border and text):
                continue
            cards.append(
                f"""
                <div class="relative w-full rounded-lg border p-4 text-sm flex items-start gap-3" style="background-color: {subtle}; border-color: {border}; color: {text}">
                    <i data-lucide="{icon}" class="w-5 h-5 mt-0.5"></i>
                    <div>
                        <h5 class="mb-1 font-medium leading-none tracking-tight">{escape(title)}</h5>
                        <div class="text-sm opacity-90">{escape(body)}</div>
                    </div>
                </div>
                """
            )
        if not cards:
            return empty_state("Semantic alert previews are unavailable because no complete semantic status token sets were proposed in this run.")
        return f'<div class="space-y-4 max-w-2xl">{"".join(cards)}</div>'

    has_any_status = any([status_success, status_warning, status_danger, status_info])
    status_empty_note = "" if has_any_status else empty_state(
        "No semantic status tokens were proposed in this run. The preview omits any fallback colors."
    )

    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "optimizer-report-template.html")
    with open(template_path, "r", encoding="utf-8") as tf:
        html_template = tf.read()

    html_content = html_template.replace("__BRAND_PRIMARY__", str(brand_primary)) \
        .replace("__PROVENANCE_BANNER__", render_provenance_banner()) \
        .replace("__COLOR_PRIMARY_SCALE__", generate_color_swatches(primary_scale)) \
        .replace("__COLOR_NEUTRAL_SCALE__", generate_color_swatches(neutral_scale)) \
        .replace("__STATUS_EMPTY_NOTE__", status_empty_note) \
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
        .replace("__DESTRUCTIVE_BUTTON__", generate_destructive_button()) \
        .replace("__ALERT_PREVIEWS__", generate_alert_previews())

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Token optimization preview generated at: {output_html_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate Token Preview HTML")
    parser.add_argument("--json", required=True, help="Path to proposed-tokens.json")
    parser.add_argument("--out", required=True, help="Output HTML path")
    args = parser.parse_args()
    
    generate_preview(args.json, args.out)
