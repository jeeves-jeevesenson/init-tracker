# AGY Migration Context

This repo is in migration mode. The active strategic lane is:

**ASGI server first, runtime as a service.**

AGY tasks must stay bounded to the task packet and its scope JSON:

- Unrelated bug inbox dirt and `logs/context/` are not default work.
- `docs/work_items/current_work.md` must not be closed or edited unless the scope JSON sets `allow_work_close=true`.
- Every migration task must define explicit `allowed_edit_paths` and `forbidden_paths`.
- Known pre-existing dirt must be listed in `baseline_allowed_dirty_paths`; do not clean it opportunistically.
- Do not commit, push, deploy, restart services, or touch production topology unless explicitly scoped.
- Final reports must include `scripts/agent_scope_validate.py <scope.json>` output.

Use the repo-local scope guard before reporting success:

```sh
python3 scripts/agent_scope_validate.py path/to/scope.json
```
