# init-tracker Bug Reporting Workflow

This directory manages the lifecycle of bug reports for the `init-tracker` project.

## Directory Structure

- `inbox/`: New bug reports awaiting triage.
- `triaged/`: Verified bugs that have been prioritized and are ready for implementation.
- `resolved/`: Bugs that have been fixed and verified.
- `templates/`: Official bug report templates.

## Lifecycle

1. **Intake**: Raw smoke notes, frustrations, or logs are processed by the **init-tracker Bug Reporting Tool** (Custom GPT).
2. **Reporting**: The tool generates a markdown report using the `templates/bug_report_template.md`.
3. **Storage**: The report is saved to `docs/bug_reports/inbox/YYYYMMDD-slug.md`.
4. **Triage**: The developer or Orchestrator reviews the bug, assigns severity/priority, and moves it to `triaged/`.
5. **Promotion**: Bug reports are NOT active work by default. To activate a bug, the Orchestrator or developer MUST run the promotion script:
   ```bash
   python3 scripts/promote_bug_report.py docs/bug_reports/inbox/BUG-YYYYMMDD-slug.md
   ```
   This creates a formal Work Item in `docs/work_items/active/` and updates the `current_work.md` ledger.
6. **Fixing**: The **init-tracker Orchestrator** consumes active Work Items (promoted from bug reports or planning docs) and performs the fix.
7. **Resolution**: Once verified, the Work Item is moved to `completed/` and the bug report is moved to `resolved/`.

## Promotion Rules

- **No Ephemeral Bugs**: Do not start fixing a bug based only on chat memory or raw logs. It must be an official bug report first.
- **Evidence Required**: Orchestrator should only promote a bug if it has a confirmed reproduction path or sufficient diagnostic evidence.
- **Developer Priority**: If a bug is outside the current recovery gate, it should only be promoted if the developer explicitly prioritizes it.

## Guidelines

- **One Bug Per Report**: Keep reports focused on a single issue to avoid confusion.
- **Severity (S0-S3)**:
  - **S0**: Blocker (System unusable, data loss).
  - **S1**: Critical (Major feature broken, no workaround).
  - **S2**: Major (Feature broken but has workaround, or minor feature broken).
  - **S3**: Minor (UI polish, typo, cosmetic issues).
- **Priority (P0-P3)**:
  - **P0**: Urgent (Fix immediately).
  - **P1**: High (Fix in current gate).
  - **P2**: Medium (Fix in next gate).
  - **P3**: Low (Fix when time permits).
- **No Hypotheses as Root Cause**: Always distinguish between what is observed and what is suspected.
- **No Secrets**: Never store credentials, API keys, or sensitive PII in bug reports.
- **Orchestrator Handoff**: Each report must include a handoff section to guide the agent who will eventually fix the bug.
