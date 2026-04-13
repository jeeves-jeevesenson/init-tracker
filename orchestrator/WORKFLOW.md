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
1. `POST /repos/{owner}/{repo}/issues/{issue_number}/assignees`
2. body includes:
   - `assignees: [COPILOT_DISPATCH_ASSIGNEE]` (default `copilot-swe-agent`)
   - `agent_assignment` fields:
     - `target_repo`
     - `base_branch`
     - `custom_instructions` (optional)
     - `custom_agent` (optional)
     - `model` (optional)
3. normalized task packet comment is posted after accepted assignment as a secondary artifact

Dispatch state semantics are intentionally conservative:
- `dispatch_requested` = orchestrator attempted assignment
- `awaiting_worker_start` = API accepted assignment request, worker-start still unconfirmed
- `working` / `pr_opened` = worker-start evidence arrived
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
  - issue comment from configured Copilot identity
  - PR activity tied to the task

## OpenAI usage

Used in two places:
1. **Planning**: issue -> normalized task packet (stored on `TaskPacket`)
2. **Review summarization**: PR/check updates -> concise bullets + suggested next action

## Discord notifications

Sent for meaningful transitions:
- task packet created
- task planned / awaiting approval
- task approved
- task dispatched
- approved but manual dispatch required
- task rejected
- PR opened/updated for review
- checks complete and ready for review
- checks failed / task blocked
- task failed
- task completed

## Inspection routes

- `GET /runs` (existing)
- `GET /tasks`
- `GET /tasks/{id}`

Routes are plain JSON for operational inspection.

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

Optional tuning:
- `TASK_LABEL` (default `agent:task`)
- `TASK_APPROVED_LABEL` (default `agent:approved`)
- `COPILOT_DISPATCH_ASSIGNEE` (default `copilot-swe-agent`)
- `COPILOT_TARGET_BRANCH` (default `main`)
- `COPILOT_TARGET_REPO` (default task repository)
- `COPILOT_CUSTOM_INSTRUCTIONS` (optional extra instructions sent in `agent_assignment`)
- `COPILOT_CUSTOM_AGENT` (optional GitHub custom agent identifier)
- `COPILOT_MODEL` (optional model override in `agent_assignment`)
- `OPENAI_PLANNING_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_REVIEW_MODEL` (default `gpt-4.1-mini`)
- `GITHUB_API_URL` (default `https://api.github.com`)

## Manual steps that still exist

- If GitHub dispatch is blocked by auth/plan/API limitations, a human must manually dispatch in GitHub.
- Human review/approval and merge decisions remain manual.
