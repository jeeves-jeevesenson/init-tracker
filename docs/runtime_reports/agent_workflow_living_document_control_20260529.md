# Agent Workflow: Living Document and Work Ledger Control

**Date**: 2026-05-29
**Status**: ACTIVE

## Problem: The Stale-Plan Failure Mode

Agents and Custom GPT sessions often suffer from "zombie plans." When a fresh session starts, the agent may find an old planning document or an unclosed bug report and attempt to revive it, even if the work is already complete or the approach has changed. This results in redundant work, regressions, and session confusion.

## Solution: Authoritative State via Living Documents

We have introduced a durable, repo-owned workflow control system consisting of three key components:

1. **The Current Work Ledger** (`docs/work_items/current_work.md`): This is the *only* source of truth for what an agent should be doing. If it's not in the ledger, it's not current work.
2. **Work Items** (`docs/work_items/active/`): Formalized, bounded tasks with explicit scope, allowed files, and validation requirements.
3. **Living Document Protocol**: A strict set of rules for how documentation (including bug reports and plans) is promoted to active work and how completion evidence is recorded.

## Integration of Tools

This system ties together our specialized agents:

- **Bug Reporting Tool**: Captures issues and generates reports. These reports are historical until promoted to a Work Item.
- **Planning Tool**: Performs deep research and architecture mapping. It generates Research Passes and Living Plans, which are strategic until promoted to a Work Item.
- **Orchestrator (Gemini/Codex)**: Executes Work Items. It MUST NOT start work that is not in the `current_work.md` ledger.

## Impact on Future Sessions

Every new ChatGPT session MUST now run `scripts/chatgpt_context_refresher.sh`. This script will now include a summary of the `current_work.md` ledger.

If an agent finds themselves without an active work item in the ledger, they are instructed to **refuse to proceed** and ask the developer for direction. This prevents the revival of stale state and ensures that all agent work is intentional and prioritized.
