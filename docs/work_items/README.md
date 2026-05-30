# Work Items Management

This directory contains the authoritative state of active, completed, and blocked work for the `init-tracker` project.

## Directory Structure

- `current_work.md`: The active ledger for the Orchestrator. Read this first.
- `active/`: Individual work item documents for tasks currently in progress.
- `completed/`: Historical records of finished work items.
- `superseded/`: Plans or work items that were replaced by a different approach.
- `blocked/`: Work items that cannot proceed due to external or internal blockers.
- `templates/`: Templates for creating new work items.

## Lifecycle

1. **Inception**: A bug report or planning document identifies a need for change.
2. **Promotion**: The developer or an agent promotes the report/plan into a formal **Work Item** using the `work_item_template.md`.
3. **Activation**: The item is moved to `active/` and added to `current_work.md`.
4. **Execution**: The agent performs the work, adhering strictly to the scope and allowed files defined in the work item.
5. **Validation**: Every completed item MUST have validation/smoke evidence recorded in the document (or a clear reason why only unit tests were used).
6. **Completion**: Once verified, the item is moved to `completed/` and updated in `current_work.md`.

## Rules of Engagement

- **No Zombie Plans**: Do not revive old plans from `majorTODO.md` or historical `docs/runtime_reports/` unless they are explicitly promoted to a new active Work Item.
- **Evidence Required**: Completion is only accepted when accompanied by evidence (logs, test results, smoke check notes).
- **Scope Discipline**: Agents MUST NOT edit files outside the `allowed files` list in an active work item. If a fix requires a scope expansion, stop and request a scope update.
- **Historical vs. Active**: Old runtime reports are historical evidence of past behavior; they are not active work instructions.
