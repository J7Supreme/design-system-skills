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

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Gap Agent — Preview</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Include Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {{
            --primary: {brand_primary};
        }}
    </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex">

    <!-- Sidebar -->
    <aside class="w-64 border-r bg-white flex flex-col hidden md:flex sticky top-0 h-screen">
        <div class="p-6 border-b">
            <div class="flex items-center gap-2 font-bold text-lg tracking-tight">
                <div class="w-6 h-6 rounded bg-[var(--primary)]"></div>
                Token Gap Preview
            </div>
        </div>
        <nav class="flex-1 p-4 space-y-1">
            <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 mt-4 px-2">Foundation</div>
            <a href="#colors" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="palette" class="w-4 h-4"></i> Colors
            </a>
            <a href="#spacing-radius" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="ruler" class="w-4 h-4"></i> Spacing & Radius
            </a>
            <a href="#typography" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="type" class="w-4 h-4"></i> Typography
            </a>
            <a href="#shadow-zindex" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="layers" class="w-4 h-4"></i> Shadow & Z-Index
            </a>
            <a href="#motion" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="play-circle" class="w-4 h-4"></i> Motion
            </a>
            <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 mt-8 px-2">Components</div>
            <a href="#buttons" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="square" class="w-4 h-4"></i> Buttons
            </a>
            <a href="#inputs" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="text-cursor-input" class="w-4 h-4"></i> Inputs
            </a>
            <a href="#cards" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="panel-top" class="w-4 h-4"></i> Cards
            </a>
            <a href="#alerts" class="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-md">
                <i data-lucide="alert-circle" class="w-4 h-4"></i> Alerts
            </a>
        </nav>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 max-w-5xl mx-auto p-8 lg:p-12">
        <header class="mb-12">
            <h1 class="text-4xl font-extrabold tracking-tight mb-2">Design System Proposed Tokens</h1>
            <p class="text-lg text-slate-500">A live preview of the generated token gap proposals, rendered using standard UI patterns.</p>
        </header>

        <!-- Color Scales -->
        <section id="colors" class="mb-16">
            <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Color foundation</h2>
            
            <div class="mb-8">
                <h3 class="text-lg font-medium mb-4">Brand Primary Scale</h3>
                <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {generate_color_swatches(primary_scale)}
                </div>
            </div>

            <div class="mb-8">
                <h3 class="text-lg font-medium mb-4">Neutral Scale</h3>
                <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {generate_color_swatches(neutral_scale)}
                </div>
            </div>

            <div class="mb-8">
                <h3 class="text-lg font-medium mb-4">Semantic Status</h3>
                
                <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
                    <div>
                        <h4 class="text-sm font-semibold text-slate-500 mb-3 uppercase tracking-wider">Success</h4>
                        <div class="grid grid-cols-1 gap-4">
                            {generate_status_swatches(status_success)}
                        </div>
                    </div>
                    <div>
                        <h4 class="text-sm font-semibold text-slate-500 mb-3 uppercase tracking-wider">Warning</h4>
                        <div class="grid grid-cols-1 gap-4">
                            {generate_status_swatches(status_warning)}
                        </div>
                    </div>
                    <div>
                        <h4 class="text-sm font-semibold text-slate-500 mb-3 uppercase tracking-wider">Danger</h4>
                        <div class="grid grid-cols-1 gap-4">
                            {generate_status_swatches(status_danger)}
                        </div>
                    </div>
                    <div>
                        <h4 class="text-sm font-semibold text-slate-500 mb-3 uppercase tracking-wider">Info</h4>
                        <div class="grid grid-cols-1 gap-4">
                            {generate_status_swatches(status_info)}
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="spacing-radius" class="mb-16">
            <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Spacing & Radius</h2>
            
            <div class="mb-12">
                <h3 class="text-lg font-medium mb-4">Spacing Scale</h3>
                {generate_spacing_table(spacing_tokens)}
            </div>

            <div class="mb-8">
                <h3 class="text-lg font-medium mb-4">Corner Radius</h3>
                {generate_radius_table(radius_tokens)}
            </div>
        </section>

        <section id="typography" class="mb-16">
            <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Typography</h2>
            {generate_typography_table(typography_tokens)}
        </section>

        <section id="shadow-zindex" class="mb-16">
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-16">
                <div>
                    <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Shadow & Elevation</h2>
                    {generate_shadow_table(shadow_tokens)}
                </div>
                <div>
                    <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Z-Index Stacking</h2>
                    {generate_zindex_table(zindex_tokens)}
                </div>
            </div>
        </section>

        <section id="motion" class="mb-16">
            <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-6">Motion & Animation</h2>
            {generate_motion_table(motion_tokens)}
        </section>

        <!-- Components Preview using Shadcn UI Tailwind equivalents -->
        <section id="components">
            <h2 class="text-2xl font-semibold tracking-tight border-b pb-2 mb-8">Component Previews</h2>
            
            <div id="buttons" class="mb-12">
                <h3 class="text-xl font-medium mb-4">Buttons</h3>
                <div class="p-6 border rounded-lg bg-white shadow-sm flex flex-wrap gap-4 items-center">
                    <button class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 text-white shadow hover:opacity-90 h-9 px-4 py-2" style="background-color: var(--primary)">
                        Primary Button
                    </button>
                    
                    <button class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border shadow-sm hover:bg-slate-100 hover:text-slate-900 h-9 px-4 py-2 bg-white text-slate-900">
                        Secondary Outline
                    </button>
                    
                    <button class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 hover:bg-slate-100 hover:text-slate-900 h-9 px-4 py-2 text-slate-900">
                        Ghost
                    </button>
                    
                    <button class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 text-white shadow hover:opacity-90 h-9 px-4 py-2" style="background-color: {status_danger.get('default', dict()).get('value', '#red')}">
                        Destructive
                    </button>
                </div>
            </div>

            <div id="inputs" class="mb-12">
                <h3 class="text-xl font-medium mb-4">Inputs & Forms</h3>
                <div class="p-6 border rounded-lg bg-white shadow-sm max-w-md space-y-4">
                    <div class="space-y-2">
                        <label class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Email address</label>
                        <input type="email" class="flex h-9 w-full rounded-md border border-slate-200 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-1 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:ring-[var(--primary)]" placeholder="name@example.com">
                        <p class="text-[0.8rem] text-slate-500">Enter your core communication email.</p>
                    </div>
                </div>
            </div>

            <div id="cards" class="mb-12">
                <h3 class="text-xl font-medium mb-4">Cards</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="rounded-xl border bg-white text-slate-950 shadow">
                        <div class="flex flex-col space-y-1.5 p-6">
                            <h3 class="font-semibold leading-none tracking-tight">Create project</h3>
                            <p class="text-sm text-slate-500">Deploy your new project in one-click.</p>
                        </div>
                        <div class="p-6 pt-0">
                            <form>
                                <div class="grid w-full items-center gap-4">
                                    <div class="flex flex-col space-y-1.5">
                                        <label class="text-sm font-medium">Name</label>
                                        <input class="flex h-9 w-full rounded-md border border-slate-200 bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--primary)]" placeholder="Name of your project">
                                    </div>
                                </div>
                            </form>
                        </div>
                        <div class="flex items-center p-6 pt-0 gap-2">
                            <button class="inline-flex items-center justify-center rounded-md text-sm font-medium border shadow-sm hover:bg-slate-100 h-9 px-4 text-slate-900 bg-white">Cancel</button>
                            <button class="inline-flex items-center justify-center rounded-md text-sm font-medium shadow text-white h-9 px-4" style="background-color: var(--primary)">Deploy</button>
                        </div>
                    </div>
                </div>
            </div>

            <div id="alerts" class="mb-12">
                <h3 class="text-xl font-medium mb-4">Alerts (Semantic Colors)</h3>
                <div class="space-y-4 max-w-2xl">
                    <div class="relative w-full rounded-lg border p-4 text-sm flex items-start gap-3" style="background-color: {status_info.get('subtle', dict()).get('value')}; border-color: {status_info.get('border', dict()).get('value')}; color: {status_info.get('text', dict()).get('value')}">
                        <i data-lucide="info" class="w-5 h-5 mt-0.5"></i>
                        <div>
                            <h5 class="mb-1 font-medium leading-none tracking-tight">System Update</h5>
                            <div class="text-sm opacity-90">A new software version is available for download.</div>
                        </div>
                    </div>

                    <div class="relative w-full rounded-lg border p-4 text-sm flex items-start gap-3" style="background-color: {status_success.get('subtle', dict()).get('value')}; border-color: {status_success.get('border', dict()).get('value')}; color: {status_success.get('text', dict()).get('value')}">
                        <i data-lucide="check-circle-2" class="w-5 h-5 mt-0.5"></i>
                        <div>
                            <h5 class="mb-1 font-medium leading-none tracking-tight">Payment Successful</h5>
                            <div class="text-sm opacity-90">Your transaction has been processed correctly.</div>
                        </div>
                    </div>

                    <div class="relative w-full rounded-lg border p-4 text-sm flex items-start gap-3" style="background-color: {status_warning.get('subtle', dict()).get('value')}; border-color: {status_warning.get('border', dict()).get('value')}; color: {status_warning.get('text', dict()).get('value')}">
                        <i data-lucide="alert-triangle" class="w-5 h-5 mt-0.5"></i>
                        <div>
                            <h5 class="mb-1 font-medium leading-none tracking-tight">Usage Warning</h5>
                            <div class="text-sm opacity-90">You are approaching your monthly API limit.</div>
                        </div>
                    </div>

                    <div class="relative w-full rounded-lg border p-4 text-sm flex items-start gap-3" style="background-color: {status_danger.get('subtle', dict()).get('value')}; border-color: {status_danger.get('border', dict()).get('value')}; color: {status_danger.get('text', dict()).get('value')}">
                        <i data-lucide="alert-octagon" class="w-5 h-5 mt-0.5"></i>
                        <div>
                            <h5 class="mb-1 font-medium leading-none tracking-tight">Connection Error</h5>
                            <div class="text-sm opacity-90">Failed to connect to the database. Please try again.</div>
                        </div>
                    </div>
                </div>
            </div>

        </section>
    </main>

    <script>
        lucide.createIcons();
    </script>
</body>
</html>
"""

    with open(output_html_path, "w") as f:
        f.write(html_content)

    print(f"Token gap preview generated at: {output_html_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate Token Preview HTML")
    parser.add_argument("--json", required=True, help="Path to proposed-tokens.json")
    parser.add_argument("--out", required=True, help="Output HTML path")
    args = parser.parse_args()
    
    generate_preview(args.json, args.out)
