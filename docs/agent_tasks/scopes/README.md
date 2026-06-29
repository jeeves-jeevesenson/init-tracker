# AGY Scope JSON Guard

A scope JSON is a repo-local, machine-checkable task boundary for AGY migration-mode work. It describes which files a task may edit, which files or directories are forbidden, whether staging/commit behavior is allowed, and which diff patterns must not appear.

Use it as the objective gate before reporting a migration task as successful:

```sh
python3 scripts/agent_scope_validate.py docs/agent_tasks/scopes/<scope>.json
```

## Required Keys

Every scope JSON must include:

- `task_id`: stable task identifier string.
- `allowed_edit_paths`: files or directories the task may change.
- `forbidden_paths`: files or directories that must not change.
- `forbidden_diff_patterns`: literal strings that must not appear in `git diff` or staged diff content.
- `allow_work_close`: set `true` only when the task may edit or close `docs/work_items/current_work.md`.
- `allow_commit`: set `true` only when staging/commit work is explicitly allowed.
- `required_clean_staging`: set `true` for normal AGY tasks so staged changes fail validation.

Recommended optional keys:

- `baseline_allowed_dirty_paths`: known unrelated dirty files or directories that existed before the task. These are reported as `[WARN]` instead of forcing the run to fail.
- `allow_untracked_outside_allowed`: defaults to `false`. Use only for rare workflow tasks where unrelated untracked files are expected and harmless.

Path entries are repo-relative. File entries match that file and anything below it if it is a directory. Directory entries should use a trailing slash, such as `logs/context/`.

## Migration Task Packet Usage

Future migration AGY task packets should reference a concrete scope JSON near the validation section:

```text
Scope JSON:
- docs/agent_tasks/scopes/<task-id>.json

Validation commands:
- git status --short
- timeout 10s python3 scripts/agent_scope_validate.py docs/agent_tasks/scopes/<task-id>.json
```

The task packet and scope JSON should agree. If they disagree, stop and ask for developer clarification instead of choosing the broader interpretation.

## Failure Policy

Treat any `[FAIL]` line as a blocking scope failure. Do not repair unrelated dirty files to make the validator pass. Either revert only the task's own out-of-scope edits, narrow the task, or ask the developer to update the scope JSON.

`[WARN]` lines are informational. They usually identify known baseline dirt that was intentionally excluded from the task.

## Example Workflow

1. Create or read the task scope JSON before editing.
2. Implement only files listed in `allowed_edit_paths`.
3. Run `timeout 10s python3 scripts/agent_scope_validate.py <scope.json>`.
4. Stop and report the validator output.

The validator is not a substitute for focused tests. It only checks objective scope boundaries against the current git state.
