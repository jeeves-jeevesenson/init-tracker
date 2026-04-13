"""Milestone 3 tests: orchestrator touchpoint-elimination pass.

Tests cover:
- Trusted kickoff / auto-confirm
- Backward-compatible manual confirm flow
- Merge-and-continue (the critical chain-link)
- Workflow approval blocker detection and surfacing
- Draft PR stall detection and un-draft attempt
- Auto-dispatch after next-slice creation
- Explicit blocker-state surfacing in /programs
- Idempotency for repeated merge / continuation events
"""
from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from orchestrator.app.config import Settings
from orchestrator.app.github_dispatch import DispatchResult
from orchestrator.app.models import (
    BLOCKER_WAITING_FOR_MERGE,
    BLOCKER_WAITING_FOR_WORKFLOW_APPROVAL,
    BLOCKER_WAITING_FOR_PR_READY,
    BLOCKER_WAITING_FOR_ISSUE_CREATION,
    AgentRun,
    Program,
    ProgramSlice,
    TaskPacket,
    SLICE_STATUS_COMPLETED,
    SLICE_STATUS_WAITING_FOR_MERGE,
    PROGRAM_STATUS_COMPLETED,
    PROGRAM_STATUS_ACTIVE,
)


def _reload_orchestrator_modules():
    config = importlib.import_module("orchestrator.app.config")
    db = importlib.import_module("orchestrator.app.db")
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    importlib.reload(config)
    importlib.reload(db)
    programs = importlib.import_module("orchestrator.app.programs")
    tasks = importlib.import_module("orchestrator.app.tasks")
    routes = importlib.import_module("orchestrator.app.task_routes")
    github = importlib.import_module("orchestrator.app.github_webhooks")
    openai = importlib.import_module("orchestrator.app.openai_webhooks")
    main = importlib.import_module("orchestrator.app.main")
    importlib.reload(programs)
    importlib.reload(tasks)
    importlib.reload(routes)
    importlib.reload(github)
    importlib.reload(openai)
    importlib.reload(main)
    return main, db


def _github_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post_github(client: TestClient, *, secret: str, delivery: str, event: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    signature = _github_signature(secret, body)
    return client.post(
        "/github/webhook",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
        },
        content=body,
    )


_PLAN_RETURN_NARROW = {
    "objective": "Fix a contained bug",
    "scope": ["single bugfix"],
    "non_goals": ["no refactor"],
    "acceptance_criteria": ["bug fixed"],
    "validation_guidance": ["python -m compileall ."],
    "implementation_brief": "Patch the broken path.",
}

_PLAN_RETURN_BROAD = {
    "objective": "Large migration",
    "scope": ["cross-system migration"],
    "non_goals": ["no UI changes"],
    "acceptance_criteria": ["migration complete"],
    "validation_guidance": ["python -m pytest tests/ -q"],
    "implementation_brief": "Broad orchestrator pass.",
    "recommended_worker": "initiative-smith",
    "recommended_scope_class": "broad",
    "program_plan": {
        "normalized_program_objective": "Full migration",
        "definition_of_done": ["All slices merged"],
        "non_goals": ["no downtime"],
        "milestones": [{"key": "M1"}, {"key": "M2"}],
        "slices": [
            {
                "slice_number": 1,
                "milestone_key": "M1",
                "slice_type": "implementation",
                "title": "Slice One",
                "objective": "First slice work",
                "acceptance_criteria": ["slice 1 done"],
                "non_goals": [],
                "expected_file_zones": [],
                "continuation_hint": "",
            },
            {
                "slice_number": 2,
                "milestone_key": "M2",
                "slice_type": "implementation",
                "title": "Slice Two",
                "objective": "Second slice work",
                "acceptance_criteria": ["slice 2 done"],
                "non_goals": [],
                "expected_file_zones": [],
                "continuation_hint": "",
            },
        ],
    },
}

ENV_KEYS = {
    "ORCHESTRATOR_ENV_FILE",
    "DATABASE_URL",
    "GH_WEBHOOK_SECRET",
    "OPENAI_WEBHOOK_SECRET",
    "OPENAI_API_KEY",
    "DISCORD_WEBHOOK_URL",
    "ORCHESTRATOR_SECRET_KEY",
    "GITHUB_API_TOKEN",
    "TASK_LABEL",
    "TASK_APPROVED_LABEL",
    "TRUSTED_KICKOFF_LABEL",
    "PROGRAM_TRUSTED_AUTO_CONFIRM",
    "COPILOT_DISPATCH_ASSIGNEE",
    "COPILOT_TARGET_BRANCH",
    "COPILOT_TARGET_REPO",
    "COPILOT_CUSTOM_INSTRUCTIONS",
    "COPILOT_CUSTOM_AGENT",
    "ENABLE_GITHUB_CUSTOM_AGENT_DISPATCH",
    "COPILOT_MODEL",
    "OPENAI_PLANNING_MODEL",
    "OPENAI_REVIEW_MODEL",
    "OPENAI_PLANNING_REASONING_EFFORT",
    "OPENAI_REVIEW_REASONING_EFFORT",
    "OPENAI_ESCALATE_REASONING_FOR_BROAD_TASKS",
    "OPENAI_PLANNING_BROAD_REASONING_EFFORT",
    "OPENAI_CONTROL_PLANE_MODE",
    "OPENAI_ENABLE_BACKGROUND_REQUESTS",
    "PROGRAM_AUTO_PLAN",
    "PROGRAM_AUTO_APPROVE",
    "PROGRAM_AUTO_DISPATCH",
    "PROGRAM_AUTO_CONTINUE",
    "PROGRAM_AUTO_MERGE",
    "PROGRAM_MAX_REVISION_ATTEMPTS",
}


class TrustedKickoffTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_trusted_kickoff_label_auto_confirms_after_planning(self):
        """Issue with agent:task + program:kickoff should be auto-approved without a
        second manual confirmation step."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 301,
                    "node_id": "I_301",
                    "title": "Broad migration pass",
                    "body": "Run the full migration.",
                    "labels": [{"name": "agent:task"}, {"name": "program:kickoff"}],
                },
            }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value=_PLAN_RETURN_NARROW), \
                 patch(
                     "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                     return_value=DispatchResult(
                         attempted=True,
                         accepted=True,
                         manual_required=False,
                         state="accepted",
                         summary="Dispatched",
                         dispatch_id="d_301",
                         dispatch_url="https://github.com/example/dispatch/301",
                     ),
                 ) as mocked_dispatch:
                with TestClient(main.app) as client:
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-kickoff-301",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

                    task = client.get("/tasks").json()["tasks"][0]
                    # Should be dispatched (not sitting at awaiting_approval)
                    self.assertEqual(task["approval_state"], "approved")
                    self.assertIn(task["status"], {"awaiting_worker_start", "dispatched", "approved"})
                    mocked_dispatch.assert_called_once()

    def test_trusted_kickoff_disabled_does_not_auto_confirm(self):
        """When PROGRAM_TRUSTED_AUTO_CONFIRM=false the kickoff label is inert and
        the task stays at awaiting_approval."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_TRUSTED_AUTO_CONFIRM"] = "false"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 302,
                    "node_id": "I_302",
                    "title": "Broad migration pass",
                    "body": "Run the full migration.",
                    "labels": [{"name": "agent:task"}, {"name": "program:kickoff"}],
                },
            }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value=_PLAN_RETURN_NARROW), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot") as mocked_dispatch:
                with TestClient(main.app) as client:
                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-kickoff-302",
                        event="issues",
                        payload=issue_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["approval_state"], "pending")
                    self.assertEqual(task["status"], "awaiting_approval")
                    mocked_dispatch.assert_not_called()

    def test_regular_issue_still_requires_explicit_approval(self):
        """Issues without the trusted kickoff label must still wait for explicit approval —
        backward compatibility preserved."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 303,
                    "node_id": "I_303",
                    "title": "Regular task",
                    "body": "Standard narrow task.",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value=_PLAN_RETURN_NARROW), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot") as mocked_dispatch:
                with TestClient(main.app) as client:
                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-regular-303",
                        event="issues",
                        payload=issue_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["approval_state"], "pending")
                    self.assertEqual(task["status"], "awaiting_approval")
                    mocked_dispatch.assert_not_called()

    def test_trusted_kickoff_custom_label_name(self):
        """TRUSTED_KICKOFF_LABEL env var allows a non-default label name."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["TRUSTED_KICKOFF_LABEL"] = "ci:auto-approve"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 304,
                    "node_id": "I_304",
                    "title": "Custom label task",
                    "body": "Uses custom auto-approve label.",
                    "labels": [{"name": "agent:task"}, {"name": "ci:auto-approve"}],
                },
            }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value=_PLAN_RETURN_NARROW), \
                 patch(
                     "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                     return_value=DispatchResult(
                         attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok"
                     ),
                 ) as mocked_dispatch:
                with TestClient(main.app) as client:
                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-custom-label-304",
                        event="issues",
                        payload=issue_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["approval_state"], "approved")
                    mocked_dispatch.assert_called_once()


class MergeAndContinueTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _build_pr_merged_payload(self, pr_number: int, issue_number: int, repo: str) -> dict:
        return {
            "action": "closed",
            "repository": {"full_name": repo},
            "pull_request": {
                "number": pr_number,
                "id": pr_number * 100,
                "title": f"Fix issue #{issue_number}",
                "body": f"Closes #{issue_number}",
                "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                "merged": True,
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "changed_files": 3,
                "commits": 2,
                "updated_at": "2024-01-01T00:00:00Z",
            },
        }

    def _setup_task_with_pr_and_review(
        self,
        db,
        *,
        repo: str,
        issue_number: int,
        pr_number: int,
        decision: str = "continue",
        slice_status: str = SLICE_STATUS_WAITING_FOR_MERGE,
    ) -> tuple[int, int, int, int]:
        """Insert a task+run+program+slice in a realistic post-review state.

        Returns (task_id, run_id, program_id, slice1_id).
        Must be called inside a TestClient context so that tables already exist.
        """
        from orchestrator.app.models import (
            TaskPacket,
            AgentRun,
            Program,
            ProgramSlice,
            APPROVAL_APPROVED,
            PROGRAM_STATUS_ACTIVE,
            TASK_STATUS_PR_OPENED,
            RUN_STATUS_PR_OPENED,
        )

        with Session(db.get_engine()) as session:
            task = TaskPacket(
                github_repo=repo,
                github_issue_number=issue_number,
                title="Test slice task",
                raw_body="body",
                status=TASK_STATUS_PR_OPENED,
                approval_state=APPROVAL_APPROVED,
                acceptance_criteria_json="[]",
                selected_custom_agent="Initiative Tracker Engineer",
                worker_selection_mode="automatic",
                task_kind="program_slice",
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            program = Program(
                github_repo=repo,
                root_issue_number=issue_number,
                title="Test program",
                normalized_goal="Complete migration",
                status=PROGRAM_STATUS_ACTIVE,
                current_slice_number=1,
                auto_plan=True,
                auto_approve=True,
                auto_dispatch=True,
                auto_continue=True,
                auto_merge=False,
            )
            session.add(program)
            session.commit()
            session.refresh(program)

            slice1 = ProgramSlice(
                program_id=program.id,
                slice_number=1,
                milestone_key="M1",
                title="Slice One",
                objective="First slice",
                acceptance_criteria_json='["slice 1 done"]',
                status=slice_status,
                task_packet_id=task.id,
            )
            session.add(slice1)

            slice2 = ProgramSlice(
                program_id=program.id,
                slice_number=2,
                milestone_key="M2",
                title="Slice Two",
                objective="Second slice",
                acceptance_criteria_json='["slice 2 done"]',
                status="planned",
            )
            session.add(slice2)
            session.commit()
            session.refresh(slice1)
            session.refresh(slice2)

            task.program_id = program.id
            task.program_slice_id = slice1.id
            session.add(task)
            session.commit()
            session.refresh(task)

            artifact = {
                "decision": decision,
                "status": "complete",
                "confidence": 0.9,
                "scope_alignment": [],
                "acceptance_assessment": ["slice 1 done"],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "Continue to slice 2",
                "summary": ["Slice 1 looks good"],
            }

            run = AgentRun(
                task_packet_id=task.id,
                program_id=program.id,
                program_slice_id=slice1.id,
                provider="github_copilot",
                github_repo=repo,
                github_issue_number=issue_number,
                github_pr_number=pr_number,
                status=RUN_STATUS_PR_OPENED,
                last_summary="PR opened",
                continuation_decision=decision,
                review_artifact_json=json.dumps(artifact),
            )
            session.add(run)
            session.commit()
            session.refresh(run)

            slice1.latest_run_id = run.id
            slice1.linked_pr_number = pr_number
            slice1.last_decision = decision
            slice1.last_decision_event_key = f"pull_request:pr_{pr_number}:opened:t"
            session.add(slice1)
            session.commit()
            session.refresh(slice1)

            return task.id, run.id, program.id, slice1.id

    def test_merge_advances_program_from_waiting_for_merge(self):
        """After a PR is merged, a slice that was WAITING_FOR_MERGE must be advanced
        and the program must move to the next slice."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 401
            pr_number = 11

            merge_payload = self._build_pr_merged_payload(pr_number, issue_number, repo)

            with patch("orchestrator.app.tasks.notify_discord"), \
                 patch("orchestrator.app.programs._create_github_issue_for_slice", return_value=402), \
                 patch(
                     "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                     return_value=DispatchResult(
                         attempted=True, accepted=True, manual_required=False,
                         state="accepted", summary="Dispatched next slice",
                     ),
                 ) as mocked_dispatch:
                with TestClient(main.app) as client:
                    # Set up data inside the client context so tables exist
                    _, _, prog_id, slice1_id = self._setup_task_with_pr_and_review(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        slice_status=SLICE_STATUS_WAITING_FOR_MERGE,
                    )

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-merged-401",
                        event="pull_request",
                        payload=merge_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

                with Session(db.get_engine()) as session:
                    updated_slice1 = session.get(ProgramSlice, slice1_id)
                    updated_program = session.get(Program, prog_id)
                    self.assertEqual(updated_slice1.status, SLICE_STATUS_COMPLETED, "slice1 should be completed")
                    self.assertEqual(updated_program.current_slice_number, 2, "program should advance to slice 2")
                    self.assertEqual(updated_program.status, PROGRAM_STATUS_ACTIVE)

                # auto_dispatch=True so the next slice task should have been dispatched
                mocked_dispatch.assert_called_once()

    def test_repeated_merge_events_are_idempotent(self):
        """Sending the same PR merged webhook twice must not double-advance the program."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 403
            pr_number = 12

            merge_payload = self._build_pr_merged_payload(pr_number, issue_number, repo)

            with patch("orchestrator.app.tasks.notify_discord"), \
                 patch("orchestrator.app.programs._create_github_issue_for_slice", return_value=404), \
                 patch(
                     "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                     return_value=DispatchResult(
                         attempted=True, accepted=True, manual_required=False,
                         state="accepted", summary="ok",
                     ),
                 ) as mocked_dispatch:
                with TestClient(main.app) as client:
                    _, _, prog_id, _ = self._setup_task_with_pr_and_review(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        slice_status=SLICE_STATUS_WAITING_FOR_MERGE,
                    )

                    # First event
                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-merged-403-a",
                        event="pull_request",
                        payload=merge_payload,
                    )
                    # Second event — duplicate payload, different delivery ID
                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-merged-403-b",
                        event="pull_request",
                        payload=merge_payload,
                    )

                with Session(db.get_engine()) as session:
                    updated_program = session.get(Program, prog_id)
                    self.assertEqual(updated_program.current_slice_number, 2, "should have advanced exactly once")

                # Dispatch should have been called at most once per slice
                self.assertLessEqual(mocked_dispatch.call_count, 2)

    def test_merge_of_single_slice_program_marks_program_complete(self):
        """When there is no next slice after a merge, the program should be marked complete."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 405
            pr_number = 13

            merge_payload = self._build_pr_merged_payload(pr_number, issue_number, repo)

            with patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    # Create a single-slice program inside the client context
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Single slice",
                            raw_body="body",
                            status="pr_opened",
                            approval_state="approved",
                            acceptance_criteria_json="[]",
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Single slice program",
                            normalized_goal="Complete single slice",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_continue=True,
                            auto_dispatch=True,
                            auto_merge=False,
                        )
                        session.add(program)
                        session.commit()
                        session.refresh(program)

                        slice1 = ProgramSlice(
                            program_id=program.id,
                            slice_number=1,
                            milestone_key="M1",
                            title="Only Slice",
                            objective="Do everything",
                            acceptance_criteria_json="[]",
                            status=SLICE_STATUS_WAITING_FOR_MERGE,
                            task_packet_id=task.id,
                            last_decision="continue",
                            last_decision_event_key="test_key",
                        )
                        session.add(slice1)
                        session.commit()
                        session.refresh(slice1)

                        task.program_id = program.id
                        task.program_slice_id = slice1.id
                        session.add(task)

                        run = AgentRun(
                            task_packet_id=task.id,
                            program_id=program.id,
                            program_slice_id=slice1.id,
                            provider="github_copilot",
                            github_repo=repo,
                            github_issue_number=issue_number,
                            github_pr_number=pr_number,
                            status="pr_opened",
                            last_summary="pr opened",
                            review_artifact_json=json.dumps({"decision": "complete"}),
                        )
                        session.add(run)
                        session.commit()
                        session.refresh(run)
                        prog_id = program.id

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-single-slice-405",
                        event="pull_request",
                        payload=merge_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

            with Session(db.get_engine()) as session:
                updated_program = session.get(Program, prog_id)
                self.assertEqual(updated_program.status, PROGRAM_STATUS_COMPLETED)


class WorkflowApprovalBlockerTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_workflow_waiting_status_surfaces_explicit_blocker(self):
        """A workflow_run event with status=waiting must set the task and program
        to an explicit waiting_for_workflow_approval blocker, not appear as working."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 501
            pr_number = 21

            workflow_waiting_payload = {
                "action": "requested",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 9999,
                    "name": "CI / lint-and-test",
                    "status": "waiting",
                    "conclusion": None,
                    "html_url": f"https://github.com/{repo}/actions/runs/9999",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    # Set up task/run inside the client context
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Test workflow approval",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json="[]",
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Test program",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                        )
                        session.add(program)
                        session.commit()
                        session.refresh(program)

                        slice1 = ProgramSlice(
                            program_id=program.id,
                            slice_number=1,
                            milestone_key="M1",
                            title="Slice One",
                            objective="First slice",
                            acceptance_criteria_json="[]",
                            status="in_progress",
                            task_packet_id=task.id,
                        )
                        session.add(slice1)
                        session.commit()
                        session.refresh(slice1)

                        task.program_id = program.id
                        task.program_slice_id = slice1.id
                        session.add(task)

                        run = AgentRun(
                            task_packet_id=task.id,
                            program_id=program.id,
                            program_slice_id=slice1.id,
                            provider="github_copilot",
                            github_repo=repo,
                            github_issue_number=issue_number,
                            github_pr_number=pr_number,
                            status="working",
                            last_summary="working",
                        )
                        session.add(run)
                        session.commit()
                        prog_id = program.id

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-waiting-501",
                        event="workflow_run",
                        payload=workflow_waiting_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

                    tasks_data = client.get("/tasks").json()
                    task_data = tasks_data["tasks"][0]
                    self.assertEqual(task_data["status"], "blocked")

            with Session(db.get_engine()) as session:
                updated_program = session.get(Program, prog_id)
                blocker = json.loads(updated_program.blocker_state_json or "{}")
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_WORKFLOW_APPROVAL)
                self.assertIn("approval", updated_program.latest_summary.lower())

            # Discord notification should mention workflow approval
            notify_calls = [str(c.args[0]) for c in mocked_notify.call_args_list if c.args]
            self.assertTrue(any("approval" in msg.lower() for msg in notify_calls))

    def test_workflow_action_waiting_also_detected(self):
        """A workflow_run event with action=waiting (not just status=waiting) is also blocked."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 502
            pr_number = 22

            workflow_waiting_payload = {
                "action": "waiting",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 10000,
                    "name": "Copilot checks",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": f"https://github.com/{repo}/actions/runs/10000",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Workflow action waiting",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json="[]",
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        run = AgentRun(
                            task_packet_id=task.id,
                            provider="github_copilot",
                            github_repo=repo,
                            github_issue_number=issue_number,
                            github_pr_number=pr_number,
                            status="working",
                            last_summary="working",
                        )
                        session.add(run)
                        session.commit()

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-action-waiting-502",
                        event="workflow_run",
                        payload=workflow_waiting_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

                    tasks_data = client.get("/tasks").json()
                    updated_task = tasks_data["tasks"][0]
                    self.assertEqual(updated_task["status"], "blocked")
                    self.assertIn("waiting", updated_task["latest_summary"].lower())


class DraftPRHandlingTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_draft_pr_with_continue_decision_attempts_undraft(self):
        """When a PR is opened as draft and review says 'continue', the orchestrator
        should attempt to mark it ready for review via the GitHub API."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 601
            pr_number = 31

            draft_pr_opened_payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": pr_number * 100,
                    "title": f"Draft: fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": True,
                    "mergeable": None,
                    "mergeable_state": "unknown",
                    "changed_files": 2,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }

            continue_artifact = {
                "decision": "continue",
                "status": "complete",
                "confidence": 0.9,
                "scope_alignment": [],
                "acceptance_assessment": ["done"],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["Looks good"],
            }

            with patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={"review_artifact": continue_artifact, "summary_bullets": ["Good"], "next_action": "continue"},
            ), patch(
                "orchestrator.app.tasks.mark_pr_ready_for_review",
                return_value=(True, "PR #31 marked ready for review"),
            ) as mocked_undraft, patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Draft PR task",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Draft test",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_continue=True,
                            auto_dispatch=True,
                            auto_merge=False,
                        )
                        session.add(program)
                        session.commit()
                        session.refresh(program)

                        slice1 = ProgramSlice(
                            program_id=program.id,
                            slice_number=1,
                            milestone_key="M1",
                            title="Slice",
                            objective="do it",
                            acceptance_criteria_json='["done"]',
                            status="in_progress",
                            task_packet_id=task.id,
                        )
                        session.add(slice1)
                        session.commit()
                        session.refresh(slice1)

                        task.program_id = program.id
                        task.program_slice_id = slice1.id
                        session.add(task)
                        session.commit()

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-draft-pr-601",
                        event="pull_request",
                        payload=draft_pr_opened_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

            mocked_undraft.assert_called_once_with(
                settings=unittest.mock.ANY,
                repo=repo,
                pr_number=pr_number,
            )

    def test_draft_pr_undraft_failure_surfaces_blocker(self):
        """When un-drafting fails, the program should show waiting_for_pr_ready blocker."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 602
            pr_number = 32

            draft_pr_opened_payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": pr_number * 100,
                    "title": f"Draft: issue #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": True,
                    "mergeable": None,
                    "mergeable_state": "unknown",
                    "changed_files": 2,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }

            continue_artifact = {
                "decision": "continue",
                "status": "complete",
                "confidence": 0.9,
                "scope_alignment": [],
                "acceptance_assessment": ["done"],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["Looks good"],
            }

            with patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={"review_artifact": continue_artifact, "summary_bullets": ["Good"], "next_action": "continue"},
            ), patch(
                "orchestrator.app.tasks.mark_pr_ready_for_review",
                return_value=(False, "GitHub returned 403 when un-drafting PR #32"),
            ), patch("orchestrator.app.tasks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Draft PR fail task",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Draft fail test",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_continue=True,
                            auto_dispatch=True,
                            auto_merge=False,
                        )
                        session.add(program)
                        session.commit()
                        session.refresh(program)

                        slice1 = ProgramSlice(
                            program_id=program.id,
                            slice_number=1,
                            milestone_key="M1",
                            title="Slice",
                            objective="do it",
                            acceptance_criteria_json='["done"]',
                            status="in_progress",
                            task_packet_id=task.id,
                        )
                        session.add(slice1)
                        session.commit()
                        session.refresh(slice1)

                        task.program_id = program.id
                        task.program_slice_id = slice1.id
                        session.add(task)
                        session.commit()
                        prog_id = program.id

                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-draft-pr-fail-602",
                        event="pull_request",
                        payload=draft_pr_opened_payload,
                    )

            with Session(db.get_engine()) as session:
                updated_program = session.get(Program, prog_id)
                blocker = json.loads(updated_program.blocker_state_json or "{}")
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_PR_READY)

            notify_calls = [str(c.args[0]) for c in mocked_notify.call_args_list if c.args]
            self.assertTrue(any("stall" in msg.lower() or "draft" in msg.lower() for msg in notify_calls))


class ProgramInspectionTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_programs_api_exposes_wait_reason(self):
        """GET /programs should include wait_reason when a program is blocked."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                with Session(db.get_engine()) as session:
                    program = Program(
                        github_repo="jeeves-jeevesenson/init-tracker",
                        root_issue_number=701,
                        title="Test",
                        normalized_goal="goal",
                        status="blocked",
                        current_slice_number=1,
                        blocker_state_json=json.dumps({"reason": BLOCKER_WAITING_FOR_MERGE, "slice_id": 1}),
                    )
                    session.add(program)
                    session.commit()

                resp = client.get("/programs")
                self.assertEqual(resp.status_code, 200)
                programs = resp.json()["programs"]
                self.assertEqual(len(programs), 1)
                prog = programs[0]
                self.assertIn("wait_reason", prog)
                self.assertEqual(prog["wait_reason"], BLOCKER_WAITING_FOR_MERGE)
                self.assertIn("blocker_state", prog)
                self.assertEqual(prog["blocker_state"]["reason"], BLOCKER_WAITING_FOR_MERGE)

    def test_programs_api_wait_reason_none_when_not_blocked(self):
        """GET /programs wait_reason should be None for a healthy active program."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                with Session(db.get_engine()) as session:
                    program = Program(
                        github_repo="jeeves-jeevesenson/init-tracker",
                        root_issue_number=702,
                        title="Active",
                        normalized_goal="goal",
                        status=PROGRAM_STATUS_ACTIVE,
                        current_slice_number=1,
                    )
                    session.add(program)
                    session.commit()

                resp = client.get("/programs")
                self.assertEqual(resp.status_code, 200)
                prog = resp.json()["programs"][0]
                self.assertIsNone(prog["wait_reason"])


class AutoDispatchAfterSliceCreationTests(unittest.TestCase):
    """When apply_reviewer_decision creates a follow-up task it should also dispatch it
    automatically when auto_dispatch=True."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_auto_dispatch_fires_for_next_slice_after_workflow_success(self):
        """After a workflow_run completes with success and the reviewer says continue,
        the next slice should be dispatched automatically."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "true"  # enable auto-merge so continuation fires on workflow success
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 801
            pr_number = 41

            workflow_success_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 20001,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/20001",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            continue_artifact = {
                "decision": "continue",
                "status": "complete",
                "confidence": 0.95,
                "scope_alignment": [],
                "acceptance_assessment": ["done"],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "slice 2",
                "summary": ["All checks pass"],
            }

            with patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": continue_artifact,
                    "summary_bullets": ["All checks pass"],
                    "next_action": "continue",
                },
            ), patch(
                "orchestrator.app.programs._create_github_issue_for_slice",
                return_value=802,
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True, accepted=True, manual_required=False,
                    state="accepted", summary="Next slice dispatched",
                ),
            ) as mocked_dispatch, patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="First slice",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            selected_custom_agent="Initiative Tracker Engineer",
                            worker_selection_mode="automatic",
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Auto-dispatch test",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_plan=True,
                            auto_approve=True,
                            auto_dispatch=True,
                            auto_continue=True,
                            auto_merge=True,
                        )
                        session.add(program)
                        session.commit()
                        session.refresh(program)

                        slice1 = ProgramSlice(
                            program_id=program.id,
                            slice_number=1,
                            milestone_key="M1",
                            title="Slice One",
                            objective="First slice",
                            acceptance_criteria_json='["done"]',
                            status="in_progress",
                            task_packet_id=task.id,
                        )
                        session.add(slice1)

                        slice2 = ProgramSlice(
                            program_id=program.id,
                            slice_number=2,
                            milestone_key="M2",
                            title="Slice Two",
                            objective="Second slice",
                            acceptance_criteria_json='["slice 2 done"]',
                            status="planned",
                        )
                        session.add(slice2)
                        session.commit()
                        session.refresh(slice1)
                        session.refresh(slice2)

                        task.program_id = program.id
                        task.program_slice_id = slice1.id
                        session.add(task)

                        run = AgentRun(
                            task_packet_id=task.id,
                            program_id=program.id,
                            program_slice_id=slice1.id,
                            provider="github_copilot",
                            github_repo=repo,
                            github_issue_number=issue_number,
                            github_pr_number=pr_number,
                            status="pr_opened",
                            last_summary="pr opened",
                        )
                        session.add(run)
                        session.commit()

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-success-801",
                        event="workflow_run",
                        payload=workflow_success_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

            # The next slice task should have been dispatched automatically
            mocked_dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
