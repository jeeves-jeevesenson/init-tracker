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

## Dispatch behavior

Dispatch currently uses GitHub REST API:
1. assign issue to configured Copilot assignee (`COPILOT_DISPATCH_ASSIGNEE`, default `copilot`)
2. post normalized task packet as an issue comment

If dispatch API/auth is unavailable, task remains approved for manual dispatch and the `AgentRun` is marked blocked with a reason.

## Worker progress tracking

Tracked webhook event types:
- `pull_request`
- `workflow_run`
- `issue_comment` (approval commands)
- `issues` (task intake + optional label approval)

Behavior:
- PR events are correlated back to task/agent run (issue references preferred, fallback to latest dispatched task in repo)
- workflow run events are correlated via PR numbers
- run/task summary is updated with concise AI-generated review/summarization

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

Optional tuning:
- `TASK_LABEL` (default `agent:task`)
- `TASK_APPROVED_LABEL` (default `agent:approved`)
- `COPILOT_DISPATCH_ASSIGNEE` (default `copilot`)
- `COPILOT_TARGET_BRANCH` (default `main`)
- `OPENAI_PLANNING_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_REVIEW_MODEL` (default `gpt-4.1-mini`)
- `GITHUB_API_URL` (default `https://api.github.com`)

## Manual steps that still exist

- If GitHub dispatch is blocked by auth/plan/API limitations, a human must manually dispatch in GitHub.
- Human review/approval and merge decisions remain manual.
