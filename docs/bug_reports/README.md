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
5. **Fixing**: The **init-tracker Orchestrator** consumes bug reports from `triaged/` and decides on the next implementation task.
6. **Resolution**: Once verified, the report is moved to `resolved/`.

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
