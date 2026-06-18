Task ID:
<task-id>

Repo path:
~/src/init-tracker

Mode:
<Plan|Execution|Research>

Source document:
<path/to/source/doc> (e.g., docs/work_items/current_work.md)

Files to inspect:
- <file1>
- <file2>

Allowed files:
- <file-to-edit>

Forbidden scope:
- No broad repo scan
- No production deployment/SSH
- No YAML reformatting

Validation commands:
- <Validation must be explicitly provided by the Orchestrator/task author and bounded to the task scope. If none are listed, stop and report that validation is missing instead of inventing commands.>
- Examples (NOT defaults):
  - Doc/workflow tasks: git status --short && timeout 10s git diff --check
  - App/code tasks (only if explicitly authorized/listed): python3 -m py_compile <edited-files> && timeout 30s python3 -m unittest <relevant-tests>
- Do not run full test suites, broad validation, browser smoke, deploys, restarts, or production commands unless explicitly authorized.

AGY Token Budget:
- No broad searches, recursive tree scans, or whole-repo greps unless explicitly listed by the task
- Max 5 file reads before first edit
- Stop immediately after validation/report

Stop/Logging conditions:
- Same test fails twice
- Need files outside allowed list
- Context limit warning

Final report requirements:
- Files inspected/changed
- Test results
- git status --short
- Next recommended pass
