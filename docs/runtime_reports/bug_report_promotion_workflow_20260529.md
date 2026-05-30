# Bug Report Promotion Workflow: Implementation and Validation

**Date**: 2026-05-29
**Status**: ACTIVE

## Problem: Ephemeral Bug Fixes

Before this workflow, bug reports were created but their transition to active work was informal. Agents might start fixing bugs based on chat memory or raw logs without a durable record in the `current_work.md` ledger. This made it difficult to track what was actually being worked on and increased the risk of reviving stale issues.

## Solution: Deterministic Promotion

We have implemented a script-driven promotion path:

1. **Bug Reporting Tool** creates a report in `docs/bug_reports/inbox/`.
2. **Orchestrator** (or developer) reviews the bug.
3. **Promotion Script** (`scripts/promote_bug_report.py`) is executed.
   - It validates the bug report exists.
   - It derives a unique `WORK-YYYYMMDD-slug` ID.
   - It creates a formal Work Item in `docs/work_items/active/`.
   - It moves the bug report to `docs/bug_reports/triaged/`.
   - It updates the `docs/work_items/current_work.md` ledger using machine-readable markers.

## Benefits

- **Durable State**: Bug fixes are now tracked in the repository's authoritative work ledger.
- **Verification**: Work items require explicit validation evidence before they can be marked as complete.
- **Session Safety**: Fresh sessions can immediately identify active bug-fixing tasks by reading the ledger, preventing redundant or stale work.

## Validation Performed

1. **Syntax Check**: `python3 -m py_compile scripts/promote_bug_report.py` passed.
2. **Promotion Test**:
   - Created a fake bug report: `docs/bug_reports/inbox/BUG-20260529-test-promotion.md`.
   - Ran `python3 scripts/promote_bug_report.py docs/bug_reports/inbox/BUG-20260529-test-promotion.md --replace-active`.
   - Verified that `docs/work_items/active/WORK-20260529-test-promotion.md` was created with correct content.
   - Verified that `docs/work_items/current_work.md` was updated with the new active task.
   - Verified that the bug report was moved to `docs/bug_reports/triaged/`.
3. **Guardrails Check**:
   - Attempted to promote without `--replace-active` when a task was already active; the script correctly refused.
   - Attempted to promote a non-existent file; the script correctly errored out.

## Remaining Risks

- **Manual Edits**: If a developer manually edits the ledger and breaks the markers, the script may fail. Markers are clearly labeled with `<!-- ... -->` to minimize this risk.
- **Slug Mismatches**: If the bug report title or ID format changes significantly, the extraction regex may need adjustment.
