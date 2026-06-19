Task ID:
<task-id>

Repo path:
~/src/init-tracker

Mode:
<Plan|Execution|Research|Workflow/Admin>

Goal / gate / work item:
<exact goal and active gate/work item>

Source document:
<path/to/source/doc, usually docs/work_items/current_work.md plus active work item>

Files to inspect first:
- <file1>
- <file2>

Allowed files:
- <file-to-edit>

Forbidden scope:
- No broad repo scan.
- No recursive tree scan.
- No whole-repo grep unless explicitly listed below.
- No opportunistic fixes.
- No old plans, old bugs, completed work, runtime reports, or majorTODO.md unless named above.
- No production deployment, SSH, service restart, DNS/FQDN/topology changes, or push.
- No YAML reformatting unless explicitly scoped.
- No browser smoke unless explicitly authorized by the developer.

Validation commands:
- <Validation must be explicitly provided by the Orchestrator/task author and bounded to the task scope. If none are listed, stop and report that validation is missing instead of inventing commands.>
- Examples, not defaults:
  - Doc/workflow tasks: `git status --short && timeout 10s git diff --check`
  - App/code tasks, only if explicitly authorized/listed: `python3 -m py_compile <edited-files> && timeout 30s python3 -m unittest <relevant-tests>`
- Do not run full test suites, broad validation, browser smoke, deploys, restarts, or production commands unless explicitly authorized.
- If required validation passes, stop and report.

AGY token budget:
- Read named files first.
- Maximum initial reads: <N, usually 5 or fewer>.
- Prefer `grep`, `head`, `tail`, and `sed` summaries over full logs/files.
- Do not use broad discovery to compensate for missing context.
- Stop if required context is missing.
- Stop immediately after validation/report.

Ephemeral context rule:
- ChatGPT chats, pasted summaries, and uploaded files are volatile.
- Repo files are the durable source of truth.
- Any decision or context needed later must be written to the repo or reported as needing persistence.

Stop / logging conditions:
- Need files outside allowed list.
- Need app/runtime scope not authorized.
- Same validation fails twice.
- Context limit warning.
- Required validation is missing.
- Task cannot be completed without developer decision.
- Keep command output summarized. Do not paste full logs unless asked.

Final report requirements:
- Task ID.
- Files inspected.
- Files changed.
- Summary of changes.
- Validation commands and results.
- Any skipped validation and why.
- Remaining risks or follow-up.
- Exact `git status --short` output.
