#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

def main():
    parser = argparse.ArgumentParser(description="DM Webdev Debug Capture Tool")
    parser.add_argument("--url", default="http://127.0.0.1:8787/dm", help="URL of the DM console")
    parser.add_argument("--line", type=int, help="Line number to show context for in served HTML")
    parser.add_argument("--output-dir", default="logs/webdev-debug/latest", help="Output directory for debug bundle")
    args = parser.parse_args()

    # Normalize base URL (e.g. remove trailing /dm or /dm/map)
    base_url = args.url
    if "/dm" in base_url:
        base_url = base_url.split("/dm")[0]
    base_url = base_url.rstrip("/")

    debug_dir = Path(args.output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting DM webdev debug capture for {args.url}")
    print(f"[*] Writing bundle to {debug_dir}")

    # 1. Capture /dm HTML
    dm_html = capture_url(args.url, debug_dir / "dm.html")
    
    # 2. Capture API endpoints
    capture_url(f"{base_url}/api/dm/combat", debug_dir / "dm_combat.json")
    capture_url(f"{base_url}/api/dm/monster-pilot", debug_dir / "dm_monster_pilot.json")

    # 3. Analyze and Summarize
    summary = analyze_bundle(debug_dir, dm_html, args.line)
    
    # 4. Write Summary
    (debug_dir / "summary.md").write_text(summary, encoding="utf-8")
    
    print("\n--- DEBUG SUMMARY ---")
    print(summary)
    print("----------------------")
    print(f"\n[*] Report saved to {debug_dir}/summary.md")

def capture_url(url: str, output_path: Path) -> str:
    print(f"[+] Fetching {url}...")
    try:
        # Use a short timeout to avoid hanging
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read()
            output_path.write_bytes(content)
            return content.decode('utf-8', errors='replace')
    except urllib.error.URLError as e:
        err_msg = f"ERROR: Failed to fetch {url}: {e}"
        print(f"    {err_msg}")
        output_path.write_text(err_msg, encoding="utf-8")
        return ""
    except Exception as e:
        err_msg = f"ERROR: Unexpected error fetching {url}: {e}"
        print(f"    {err_msg}")
        output_path.write_text(err_msg, encoding="utf-8")
        return ""

def summarize_json_file(path: Path) -> str:
    if not path.exists():
        return "File missing"
    content = path.read_text(encoding="utf-8")
    if content.startswith("ERROR:"):
        return content
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return f"Array with {len(data)} items"
        if isinstance(data, dict):
            if "ok" in data and not data["ok"]:
                return f"Error response: {data.get('detail') or data.get('error')}"
            keys = list(data.keys())
            key_str = ", ".join(keys[:8])
            if len(keys) > 8:
                key_str += "..."
            return f"Object with keys: {key_str}"
        return "JSON (other type)"
    except Exception:
        return "Invalid JSON"

def analyze_bundle(debug_dir: Path, html: str, target_line: Optional[int]) -> str:
    summary = []
    summary.append("# DM Webdev Debug Summary")
    
    # API Summary
    summary.append("\n## API Status")
    summary.append(f"- **/api/dm/combat:** {summarize_json_file(debug_dir / 'dm_combat.json')}")
    summary.append(f"- **/api/dm/monster-pilot:** {summarize_json_file(debug_dir / 'dm_monster_pilot.json')}")

    # HTML Analysis
    summary.append("\n## HTML Analysis")
    if not html:
        summary.append("- **ERROR:** No HTML captured.")
    else:
        auth_required = "Not found"
        if 'data-dm-auth-required="True"' in html:
            auth_required = "True (Auth screen should show)"
        elif 'data-dm-auth-required="False"' in html:
            auth_required = "False (Passwordless mode active)"

        overlay_class = "Not found"
        overlay_match = re.search(r'id="authOverlay"\s+class="([^"]+)"', html)
        if overlay_match:
            overlay_class = overlay_match.group(1)

        summary.append(f"- **data-dm-auth-required:** {auth_required}")
        summary.append(f"- **authOverlay class:** {overlay_class}")
        
        # Function detection
        funcs = [
            "bootstrapPasswordlessDmConsole",
            "fetchSnapshot",
            "applySnapshot",
            "renderMonsterPilot",
            "monsterPilotMoveAction"
        ]
        found_funcs = []
        for f in funcs:
            if re.search(r'\b' + re.escape(f) + r'\b', html):
                found_funcs.append(f)
        
        missing_funcs = [f for f in funcs if f not in found_funcs]
        
        summary.append(f"- **Found functions:** {', '.join(found_funcs) if found_funcs else 'None'}")
        if missing_funcs:
            summary.append(f"- **MISSING functions:** {', '.join(missing_funcs)}")

    # Common Noise
    summary.append("\n## Common Noise (Safe to Ignore)")
    summary.append("- `favicon.ico 404`: Expected if no favicon provided.")
    summary.append("- `chrome-extension://...`: Noise from browser extensions.")

    # Line Context
    if target_line and html:
        lines = html.splitlines()
        summary.append(f"\n## Line Context (around line {target_line})")
        # 1-based indexing for humans, 0-based for list
        start_idx = max(0, target_line - 11)
        end_idx = min(len(lines), target_line + 10)
        
        summary.append("```javascript")
        for i in range(start_idx, end_idx):
            line_num = i + 1
            marker = " ->" if line_num == target_line else "   "
            summary.append(f"{line_num:5}{marker} {lines[i]}")
        summary.append("```")

    return "\n".join(summary)

if __name__ == "__main__":
    main()
