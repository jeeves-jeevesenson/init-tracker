#!/usr/bin/env python3
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime

# scripts/promote_bug_report.py

def parse_args():
    parser = argparse.ArgumentParser(description="Promote a bug report to an active work item.")
    parser.add_argument("bug_path", help="Path to the bug report markdown file.")
    parser.add_argument("--replace-active", action="store_true", help="Replace the currently active work item in the ledger.")
    return parser.parse_args()

def extract_metadata(bug_content):
    # Match "# Bug Report: ID - Title"
    match = re.search(r"^# Bug Report: (.+?) - (.+)$", bug_content, re.MULTILINE)
    if match:
        bug_id = match.group(1).strip()
        title = match.group(2).strip()
        return bug_id, title

    return "BUG-UNKNOWN", "Untitled Bug"

def main():
    args = parse_args()
    bug_path = Path(args.bug_path)

    if not bug_path.exists():
        print(f"ERROR: Bug report not found at {bug_path}")
        sys.exit(1)

    # Validate location
    valid_parents = ["docs/bug_reports/inbox", "docs/bug_reports/triaged"]
    parent_str = str(bug_path.parent)
    if not any(valid_parent in parent_str for valid_parent in valid_parents):
        print(f"ERROR: Bug report must be in docs/bug_reports/inbox/ or docs/bug_reports/triaged/")
        sys.exit(1)

    bug_content = bug_path.read_text()
    bug_id, title = extract_metadata(bug_content)

    # Derive Work ID
    # If bug_id is BUG-YYYYMMDD-slug, work_id is WORK-YYYYMMDD-slug
    work_id = bug_id.replace("BUG-", "WORK-")
    if "WORK-" not in work_id:
        # Fallback if ID doesn't follow BUG- prefix
        work_id = f"WORK-{datetime.now().strftime('%Y%m%d')}-{bug_path.stem}"

    work_item_path = Path(f"docs/work_items/active/{work_id}.md")
    if work_item_path.exists():
        print(f"ERROR: Work item {work_item_path} already exists.")
        sys.exit(1)

    triaged_bug_path = Path(f"docs/bug_reports/triaged/{bug_path.name}")

    # Check current_work.md
    ledger_path = Path("docs/work_items/current_work.md")
    if not ledger_path.exists():
        print(f"WARNING: {ledger_path} missing. Creating minimal ledger.")
        ledger_content = """# Current Work Ledger

## Current Status

<!-- ACTIVE_WORK_STATUS_START -->
- **Status:** No Active Work
<!-- ACTIVE_WORK_STATUS_END -->

---

## Active Work Table

| ID | Title | Status | Goal |
| --- | --- | --- | --- |
<!-- ACTIVE_WORK_TABLE_START -->
<!-- ACTIVE_WORK_TABLE_END -->
"""
        ledger_path.write_text(ledger_content)

    ledger_content = ledger_path.read_text()

    # Check if active work already exists
    status_match = re.search(r"<!-- ACTIVE_WORK_STATUS_START -->(.*?)<!-- ACTIVE_WORK_STATUS_END -->", ledger_content, re.DOTALL)
    if status_match:
        status_text = status_match.group(1)
        if "Status: Active" in status_text and not args.replace_active:
            print("ERROR: An active work item already exists in the ledger.")
            print("Use --replace-active to override.")
            sys.exit(1)

    # Load template
    template_path = Path("docs/work_items/templates/work_item_template.md")
    if template_path.exists():
        template = template_path.read_text()
    else:
        print("WARNING: Work item template missing. Using minimal template.")
        template = "# Work Item: [ID] - [Title]\n\n- **Status:** Active\n- **Source:** [Source]"

    # Populate template
    work_content = template.replace("[ID]", work_id)
    work_content = work_content.replace("[Title]", title)
    work_content = work_content.replace("[Active / Completed / Superseded / Blocked]", "Active")
    work_content = work_content.replace("[Reference to Bug Report or Planning Doc]", str(bug_path))

    # Write Work Item
    print(f"Creating work item: {work_item_path}")
    work_item_path.write_text(work_content)

    # Move bug report if needed
    if bug_path != triaged_bug_path:
        if triaged_bug_path.exists():
            print(f"WARNING: {triaged_bug_path} already exists. Leaving bug report at {bug_path}")
        else:
            print(f"Moving bug report to: {triaged_bug_path}")
            bug_path.rename(triaged_bug_path)

    # Update Ledger Status
    new_status = f"""
- **Status:** Active
- **Current Work Item:** {work_id}: {title}
- **Active Gate:** (Derived from {work_id})
- **Allowed Next Action:** Fix bug reported in {triaged_bug_path}
"""
    ledger_content = re.sub(
        r"<!-- ACTIVE_WORK_STATUS_START -->.*?<!-- ACTIVE_WORK_STATUS_END -->",
        f"<!-- ACTIVE_WORK_STATUS_START -->{new_status}<!-- ACTIVE_WORK_STATUS_END -->",
        ledger_content,
        flags=re.DOTALL
    )

    # Update Ledger Table
    new_row = f"| {work_id} | {title} | Active | Fix bug reported in {triaged_bug_path} |\n"
    ledger_content = re.sub(
        r"(<!-- ACTIVE_WORK_TABLE_START -->\s*)",
        r"\1" + new_row,
        ledger_content
    )

    ledger_path.write_text(ledger_content)
    print(f"Updated ledger: {ledger_path}")
    print(f"\nSUCCESS: Bug {bug_id} promoted to {work_id}")

if __name__ == "__main__":
    main()
