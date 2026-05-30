# Living Document Protocol

A **Living Document** is a repo-resident file that tracks the evolving state of a specific subsystem, migration, or recovery gate.

## Protocol Mandates

1. **Status Declaration**: Every living document MUST declare its current status at the top (e.g., `Active`, `Completed`, `Superseded`, `Blocked`).
2. **Current-Work Ledger Integration**: Only living documents marked as `Active` in `docs/work_items/current_work.md` are valid sources for execution.
3. **Evidence Over Aspiration**: Update living documents based on **empirical evidence** from tests, logs, and smoke checks. Do not update based on assumed success.
4. **Promotion Rules**:
    - **Bug Reports**: If a bug report (from the Bug Reporting Tool) is confirmed and prioritized, it must be promoted to a Work Item in `docs/work_items/active/`.
    - **Planning Docs**: Once a research/planning pass is complete and a decision is reached, the resulting plan must spawn one or more Work Items.
5. **Nonvolatile Evidence**: Smoke test results, trace logs, and validation outputs must be recorded directly in the relevant Work Item or a linked `runtime_report`. Do not leave them only in the session chat.

## Orchestrator Selection Rules

The Orchestrator MUST follow this hierarchy when choosing work:
1. **Current Work Ledger**: Consult `docs/work_items/current_work.md` first.
2. **Active Work Items**: Follow the instructions in the `active/` work item specified by the ledger.
3. **Refusal**: If the ledger is empty or the task is finished, the Orchestrator MUST refuse to invent new work and instead ask the developer for direction.

## Completion Definitions

- **Completed**: The work is done, verified by evidence, and the documentation (including `majorTODO.md`) is updated to reflect reality.
- **Superseded**: The approach was abandoned or replaced by a better plan. The document must explain *why* and point to the new plan.
- **Blocked**: Work cannot continue. The document must explicitly state the blocker (e.g., missing API, environment failure, hardware constraint).
