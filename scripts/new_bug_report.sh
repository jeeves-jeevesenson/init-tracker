#!/bin/bash
# scripts/new_bug_report.sh - Creates a new bug report from the template.

TEMPLATE="docs/bug_reports/templates/bug_report_template.md"
INBOX_DIR="docs/bug_reports/inbox"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <slug>"
    echo "Example: $0 spell-engine-timeout"
    exit 1
fi

SLUG=$1
DATE=$(date +%Y%m%d)
FILENAME="${DATE}-${SLUG}.md"
TARGET_PATH="${INBOX_DIR}/${FILENAME}"

# Create inbox if missing
mkdir -p "$INBOX_DIR"

if [ ! -f "$TEMPLATE" ]; then
    echo "Error: Template not found at $TEMPLATE"
    exit 1
fi

if [ -f "$TARGET_PATH" ]; then
    echo "Error: Bug report already exists at $TARGET_PATH"
    exit 1
fi

cp "$TEMPLATE" "$TARGET_PATH"

# Basic substitution for title and date
sed -i "s/\[ID\]/ITR-${DATE}/g" "$TARGET_PATH"
sed -i "s/\[Title\]/${SLUG}/g" "$TARGET_PATH"
sed -i "s/YYYY-MM-DD/$(date +%Y-%m-%d)/g" "$TARGET_PATH"

echo "Created new bug report: $TARGET_PATH"
echo "Please edit this file to provide details."
