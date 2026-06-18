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
- python3 -m py_compile <edited-files>
- timeout 30s python3 -m unittest <relevant-tests>
- git status --short

AGY Token Budget:
- Max 3 broad searches
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
