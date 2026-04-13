# Orchestrator Milestone 2 Workflow

## How an issue becomes a task

1. GitHub sends an `issues` webhook.
2. Orchestrator only creates/updates a task packet when the issue has label `agent:task` (configurable with `TASK_LABEL`).
3. The issue title/body is persisted in `TaskPacket`.
4. Orchestrator runs OpenAI planning (`Responses API`) to normalize the issue into:
   - objective
   - scope
   - non-goals
   - acceptance criteria
   - validation guidance
   - implementation brief
5. Task status moves to `awaiting_approval`.

## Worker routing (custom agents)

Each task is routed to a GitHub custom agent and that selection is persisted on task/run state.

Auto-routing defaults:
- **Initiative Smith** (`Initiative Smith`) for broad work (migration, architecture, broad refactors, stabilization, end-to-end slices)
- **Tracker Engineer** (`Initiative Tracker Engineer`) for focused work (bug fixes, follow-ups, polish, contained subsystem work, hardening patches)

Routing is deterministic and inspectable:
- orchestrator applies deterministic keyword-first routing rules
- OpenAI planning `recommended_worker` / `recommended_scope_class` are only secondary tiebreaker hints
- final fields persisted include `selected_custom_agent`, `worker_selection_mode`, and `worker_selection_reason`

Manual override labels:
- `agent:initiative-smith`
- `agent:tracker-engineer`

Override labels win over auto-routing. Unknown `agent:*` override values fail clearly and block approval until corrected.

## Approval flow

Supported approval/rejection signals:
- Issue comment: `/approve` or `/reject`
- Issue label `agent:approved` (configurable with `TASK_APPROVED_LABEL`)

On approval:
- task `approval_state` -> `approved`
- task `status` -> `approved`
- dispatcher attempts GitHub Copilot dispatch

On rejection:
- task `approval_state` -> `rejected`
- task `status` -> `blocked`

Duplicate approval signals are safe: once dispatched/completed, additional approvals do not create duplicate dispatch runs.
Approval comments are parsed case-insensitively and can appear on later lines in a comment body.

## Dispatch behavior

Dispatch uses GitHub REST API for existing issue assignment:
1. preflight `POST /graphql` checks:
   - `repository(owner:, name:) { suggestedActors(capabilities:[CAN_BE_ASSIGNED], first:100) { nodes { login __typename ... on Bot { id } } } }`
   - Copilot cloud agent must appear in `suggestedActors` or dispatch is blocked with manual dispatch required
2. `POST /repos/{owner}/{repo}/issues/{issue_number}/assignees`
3. body includes:
   - `assignees: [COPILOT_DISPATCH_ASSIGNEE]` (canonical/default `copilot-swe-agent[bot]`; legacy aliases are normalized)
   - `agent_assignment` fields:
      - `target_repo`
      - `base_branch`
      - `custom_instructions` (optional)
      - `custom_agent` (selected routed worker; optional only when no selection exists)
      - `model` (optional)
4. normalized task packet comment is posted after accepted assignment as a secondary artifact

Dispatch state semantics are intentionally conservative:
- `dispatch_requested` = orchestrator attempted assignment
- `awaiting_worker_start` = API accepted assignment request, worker-start still unconfirmed
- `working` / `pr_opened` = worker-start evidence arrived (assignment/comment/PR evidence can upgrade prior dispatch classifications)
- `worker_failed` = Copilot worker started but then reported startup failure (for example “encountered an error and was unable to start working”)
- `manual_dispatch_needed` = API/token/permission path did not accept assignment in the expected form

The orchestrator does not treat "packet comment posted" as dispatch success.

## Worker progress tracking

Tracked webhook event types:
- `pull_request`
- `workflow_run`
- `issue_comment` (approval commands)
- `issues` (task intake + optional label approval)

Behavior:
- PR events are correlated back to task/agent run (issue references preferred, fallback to latest active dispatched task in repo)
- workflow run events are correlated via PR numbers
- run/task summary is updated with concise AI-generated review/summarization
- worker-start confirmation signals include:
  - issue assigned to configured Copilot assignee
  - issue/comment activity from Copilot identities in login/display-name forms (`Copilot`, `copilot-swe-agent`, `copilot-swe-agent[bot]`)
  - PR activity tied to the task
- later webhook evidence always reconciles stale `manual_dispatch_needed` states to `working` / `pr_opened` / `worker_failed` when worker activity is visible
- worker startup failure signals include:
  - Copilot comment indicating the worker encountered an error and was unable to start working

## OpenAI usage

Used in two places:
1. **Planning**: issue -> normalized task packet (stored on `TaskPacket`)
   - planner can also provide compact routing hints: `recommended_worker`, `recommended_scope_class`
2. **Review summarization**: PR/check updates -> concise bullets + suggested next action

## Discord notifications

Sent for meaningful transitions:
- task packet created
- task planned / awaiting approval
- task approved
- task dispatched
- worker started / worker failed after start
- approved but manual dispatch required
- task rejected
- PR opened/updated for review
- checks complete and ready for review
- checks failed / task blocked
- task failed
- task completed

Task planned/approved/dispatched/manual-dispatch and PR/check notifications include the selected worker.

## Inspection routes

- `GET /runs` (existing)
- `GET /tasks`
- `GET /tasks/{id}`

Routes are plain JSON for operational inspection and include selected worker, selection source/reason, dispatch payload summary, worker state, and PR linkage.

## Required environment variables

- `GH_WEBHOOK_SECRET` - GitHub webhook signature verification
- `OPENAI_WEBHOOK_SECRET` - OpenAI webhook signature verification
- `OPENAI_API_KEY` - required for planning/review
- `GITHUB_API_TOKEN` - required for API-based dispatch
- `DISCORD_WEBHOOK_URL` - optional notifications
- `DATABASE_URL` - SQLite URL by default

GitHub webhook subscriptions must include at minimum:
- `issues`
- `issue_comment`
- `pull_request`
- `workflow_run`

Minimum GitHub token requirement for Copilot issue assignment:
- must satisfy GitHub's Copilot issue-assignment API requirements (not issues-only access)
- include repository issue write capability plus the Copilot-assignment capability required by GitHub for cloud agent assignment
- repository must have Copilot cloud agent enabled and assignable (verified via `suggestedActors`)

Optional tuning:
- `TASK_LABEL` (default `agent:task`)
- `TASK_APPROVED_LABEL` (default `agent:approved`)
- `COPILOT_DISPATCH_ASSIGNEE` (default `copilot-swe-agent[bot]`; legacy aliases are normalized)
- `COPILOT_TARGET_BRANCH` (default `main`)
- `COPILOT_TARGET_REPO` (default task repository)
- `COPILOT_CUSTOM_INSTRUCTIONS` (optional extra instructions sent in `agent_assignment`)
- `COPILOT_CUSTOM_AGENT` (optional fallback custom agent if task routing did not set one)
- `COPILOT_MODEL` (optional model override in `agent_assignment`)
- `OPENAI_PLANNING_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_REVIEW_MODEL` (default `gpt-4.1-mini`)
- `GITHUB_API_URL` (default `https://api.github.com`)

## Manual steps that still exist

- If GitHub dispatch is blocked by auth/plan/API limitations, a human must manually dispatch in GitHub.
- Human review/approval and merge decisions remain manual.
