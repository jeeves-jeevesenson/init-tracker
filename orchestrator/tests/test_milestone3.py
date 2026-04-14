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
    BLOCKER_WAITING_FOR_PERMISSIONS,
    BLOCKER_WAITING_FOR_REPO_SETTING,
    BLOCKER_AUTO_MERGE_DISABLED,
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
    "GOVERNOR_MAX_REVISION_CYCLES",
    "GOVERNOR_REMOVE_REVIEWER_LOGIN",
    "GOVERNOR_FALLBACK_REVIEWER",
    "GOVERNOR_GUARDED_PATHS",
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
                            continuation_decision="complete",
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

    def test_merged_pr_without_continuation_evidence_does_not_advance_program(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 406
            pr_number = 14
            merge_payload = self._build_pr_merged_payload(pr_number, issue_number, repo)

            with patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Missing continuation evidence",
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
                            title="Program",
                            normalized_goal="goal",
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
                            title="Slice",
                            objective="obj",
                            acceptance_criteria_json="[]",
                            status=SLICE_STATUS_WAITING_FOR_MERGE,
                            task_packet_id=task.id,
                            last_decision="continue",
                            last_decision_event_key="t",
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
                        task_id = task.id
                        prog_id = program.id

                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-single-slice-406",
                        event="pull_request",
                        payload=merge_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

                    task_payload = client.get(f"/tasks/{task_id}").json()["task"]
                    self.assertEqual(task_payload["status"], "blocked")
                    self.assertIn("reconciliation incomplete", (task_payload["latest_summary"] or "").lower())

                with Session(db.get_engine()) as session:
                    updated_program = session.get(Program, prog_id)
                    self.assertEqual(updated_program.status, PROGRAM_STATUS_ACTIVE)


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
                # A 403 error is classified as a permissions failure, not a generic PR-ready stall.
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_PERMISSIONS)

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


class MergePRTests(unittest.TestCase):
    """Tests for the merge_pr GitHub API function and auto-merge integration."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_mark_pr_ready_for_review_uses_graphql_mutation(self):
        """mark_pr_ready_for_review should use GraphQL markPullRequestReadyForReview."""
        from orchestrator.app.github_dispatch import mark_pr_ready_for_review

        settings = Settings(GITHUB_API_TOKEN="dummy-token", GITHUB_API_URL="https://api.github.com")

        query_response = MagicMock()
        query_response.status_code = 200
        query_response.json.return_value = {
            "data": {"repository": {"pullRequest": {"id": "PR_node_id_123", "isDraft": True}}}
        }
        mutation_response = MagicMock()
        mutation_response.status_code = 200
        mutation_response.json.return_value = {
            "data": {
                "markPullRequestReadyForReview": {
                    "pullRequest": {"number": 42, "isDraft": False}
                }
            }
        }

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = [query_response, mutation_response]
            mock_client_cls.return_value = mock_client

            success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=42)

        self.assertTrue(success)
        self.assertIn("marked ready for review", msg)
        self.assertEqual(mock_client.post.call_count, 2)
        second_call = mock_client.post.call_args_list[1]
        self.assertIn("/graphql", second_call.args[0])
        self.assertIn("markPullRequestReadyForReview", second_call.kwargs["json"]["query"])
        mock_client.patch.assert_not_called()

    def test_mark_pr_ready_for_review_graphql_error_returns_failure(self):
        """mark_pr_ready_for_review should return failure when mutation reports GraphQL errors."""
        from orchestrator.app.github_dispatch import mark_pr_ready_for_review

        settings = Settings(GITHUB_API_TOKEN="dummy-token", GITHUB_API_URL="https://api.github.com")

        query_response = MagicMock()
        query_response.status_code = 200
        query_response.json.return_value = {
            "data": {"repository": {"pullRequest": {"id": "PR_node_id_456", "isDraft": True}}}
        }
        mutation_response = MagicMock()
        mutation_response.status_code = 200
        mutation_response.json.return_value = {
            "errors": [{"message": "Resource not accessible by integration"}]
        }

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = [query_response, mutation_response]
            mock_client_cls.return_value = mock_client

            success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=42)

        self.assertFalse(success)
        self.assertIn("GraphQL", msg)
        self.assertEqual(mock_client.post.call_count, 2)
        second_call = mock_client.post.call_args_list[1]
        self.assertIn("markPullRequestReadyForReview", second_call.kwargs["json"]["query"])

    def test_merge_pr_success(self):
        """merge_pr should return (True, ...) on HTTP 200."""
        from orchestrator.app.github_dispatch import merge_pr
        from orchestrator.app.config import Settings
        import httpx

        settings = Settings(GITHUB_API_TOKEN="dummy-token", GITHUB_API_URL="https://api.github.com")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.put.return_value = mock_response
            mock_client_cls.return_value = mock_client

            success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=42)

        self.assertTrue(success)
        self.assertIn("42", msg)
        mock_client.put.assert_called_once()
        call_kwargs = mock_client.put.call_args
        self.assertIn("/pulls/42/merge", call_kwargs.args[0])

    def test_merge_pr_missing_token(self):
        """merge_pr should return (False, ...) when no token is configured."""
        from orchestrator.app.github_dispatch import merge_pr
        from orchestrator.app.config import Settings

        settings = Settings(GITHUB_API_TOKEN=None)
        success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=42)
        self.assertFalse(success)
        self.assertIn("token", msg.lower())

    def test_merge_pr_403_returns_failure(self):
        """merge_pr should return (False, ...) on a 403 response."""
        from orchestrator.app.github_dispatch import merge_pr
        from orchestrator.app.config import Settings

        settings = Settings(GITHUB_API_TOKEN="dummy-token")

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Resource not accessible by integration"

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.put.return_value = mock_response
            mock_client_cls.return_value = mock_client

            success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=42)

        self.assertFalse(success)
        self.assertIn("403", msg)

    def test_auto_merge_attempts_github_merge(self):
        """When auto_merge=True and checks pass and merge policy allows, the
        orchestrator should call merge_pr on GitHub."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "true"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 901
            pr_number = 51

            workflow_success_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 30001,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/30001",
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
                "next_slice_hint": "",
                "summary": ["All good"],
            }

            with patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={"review_artifact": continue_artifact, "summary_bullets": ["Good"], "next_action": "continue"},
            ), patch(
                "orchestrator.app.programs._create_github_issue_for_slice",
                return_value=902,
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True, accepted=True, manual_required=False,
                    state="accepted", summary="Dispatched",
                ),
            ), patch(
                "orchestrator.app.programs.merge_pr",
                return_value=(True, "PR #51 merged successfully"),
            ) as mocked_merge, patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Merge test",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Merge program",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_continue=True,
                            auto_dispatch=True,
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
                        delivery="delivery-merge-test-901",
                        event="workflow_run",
                        payload=workflow_success_payload,
                    )
                    self.assertEqual(resp.status_code, 200)

            # merge_pr should have been called with the correct PR number
            mocked_merge.assert_called_once_with(
                settings=unittest.mock.ANY,
                repo=repo,
                pr_number=pr_number,
            )

    def test_auto_merge_403_sets_permissions_blocker(self):
        """When merge_pr returns 403, the program should show a waiting_for_permissions blocker."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "true"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 903
            pr_number = 52

            workflow_success_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 30003,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/30003",
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
                "next_slice_hint": "",
                "summary": ["All good"],
            }

            with patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={"review_artifact": continue_artifact, "summary_bullets": ["Good"], "next_action": "continue"},
            ), patch(
                "orchestrator.app.programs._create_github_issue_for_slice",
                return_value=904,
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True, accepted=True, manual_required=False,
                    state="accepted", summary="Dispatched",
                ),
            ), patch(
                "orchestrator.app.programs.merge_pr",
                return_value=(False, "GitHub returned 403 when merging PR #52: Resource not accessible"),
            ), patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Merge perm test",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Perm test program",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
                            auto_continue=True,
                            auto_dispatch=True,
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
                        prog_id = program.id

                    _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-merge-perm-903",
                        event="workflow_run",
                        payload=workflow_success_payload,
                    )

            with Session(db.get_engine()) as session:
                updated_program = session.get(Program, prog_id)
                blocker = json.loads(updated_program.blocker_state_json or "{}")
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_PERMISSIONS)

    def test_non_permission_undraft_failure_sets_pr_ready_blocker(self):
        """A non-403 un-draft failure should set the generic waiting_for_pr_ready blocker."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 905
            pr_number = 55

            draft_pr_payload = {
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
                    "changed_files": 1,
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
                return_value=(False, "GitHub returned 500 when un-drafting PR #55: server error"),
            ), patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo=repo,
                            github_issue_number=issue_number,
                            title="Non-perm undraft test",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            acceptance_criteria_json='["done"]',
                            task_kind="program_slice",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)

                        program = Program(
                            github_repo=repo,
                            root_issue_number=issue_number,
                            title="Non-perm test",
                            normalized_goal="complete",
                            status=PROGRAM_STATUS_ACTIVE,
                            current_slice_number=1,
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
                        delivery="delivery-non-perm-905",
                        event="pull_request",
                        payload=draft_pr_payload,
                    )

            with Session(db.get_engine()) as session:
                updated_program = session.get(Program, prog_id)
                blocker = json.loads(updated_program.blocker_state_json or "{}")
                # A non-403 error uses the generic waiting_for_pr_ready reason
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_PR_READY)


class GitHubDispatchHelperTests(unittest.TestCase):
    def test_remove_requested_reviewers_helper_calls_delete_endpoint(self):
        from orchestrator.app.github_dispatch import remove_requested_reviewers
        settings = Settings(GITHUB_API_TOKEN="dummy-token", GITHUB_API_URL="https://api.github.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value = mock_client
            ok, _ = remove_requested_reviewers(
                settings=settings,
                repo="owner/repo",
                pr_number=12,
                reviewers=["jeeves-jeevesenson"],
            )
        self.assertTrue(ok)
        self.assertTrue(mock_client.request.called)

    def test_submit_approving_review_helper_calls_reviews_endpoint(self):
        from orchestrator.app.github_dispatch import submit_approving_review
        settings = Settings(GITHUB_API_TOKEN="dummy-token", GITHUB_API_URL="https://api.github.com")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client
            ok, _ = submit_approving_review(settings=settings, repo="owner/repo", pr_number=44)
        self.assertTrue(ok)
        call_kwargs = mock_client.post.call_args
        self.assertIn("/pulls/44/reviews", call_kwargs.args[0])


class GovernorLoopTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _create_linked_task_run(
        self,
        db,
        *,
        repo: str,
        issue_number: int,
        pr_number: int,
        with_program: bool = True,
    ) -> tuple[int, int | None]:
        with Session(db.get_engine()) as session:
            task = TaskPacket(
                github_repo=repo,
                github_issue_number=issue_number,
                title="Governor test task",
                raw_body="body",
                status="working",
                approval_state="approved",
                acceptance_criteria_json='["done"]',
                task_kind="program_slice" if with_program else "single_task",
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            program_id = None
            if with_program:
                program = Program(
                    github_repo=repo,
                    root_issue_number=issue_number,
                    title="Governor test program",
                    normalized_goal="goal",
                    status=PROGRAM_STATUS_ACTIVE,
                    current_slice_number=1,
                    auto_merge=True,
                    auto_dispatch=True,
                    auto_continue=True,
                )
                session.add(program)
                session.commit()
                session.refresh(program)
                program_id = program.id

                slice1 = ProgramSlice(
                    program_id=program.id,
                    slice_number=1,
                    milestone_key="M1",
                    title="Slice",
                    objective="Objective",
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

            run = AgentRun(
                task_packet_id=task.id,
                program_id=task.program_id,
                program_slice_id=task.program_slice_id,
                provider="github_copilot",
                github_repo=repo,
                github_issue_number=issue_number,
                github_pr_number=pr_number,
                status="working",
                last_summary="working",
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return task.id, program_id

    def test_reviewer_cleanup_removes_jeeves_from_requested_reviewers(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 1001
            pr_number = 71

            payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 7100,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": True,
                    "state": "open",
                    "requested_reviewers": [{"login": "jeeves-jeevesenson"}],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
            default_review = {
                "decision": "continue",
                "status": "met",
                "confidence": 0.8,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "review_required",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["ok"],
            }
            with patch("orchestrator.app.tasks.summarize_work_update", return_value={"review_artifact": default_review, "summary_bullets": ["ok"], "next_action": "continue"}), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "wait", "summary": ["wait"], "revision_requests": [], "escalation_reason": ""}}), \
                 patch("orchestrator.app.tasks.remove_requested_reviewers", return_value=(True, "ok")) as mocked_remove, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["helper_script.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=False,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-governor-cleanup-1",
                        event="pull_request",
                        payload=payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            mocked_remove.assert_called_once()

    def test_revision_batching_comment_is_deduped_across_repeated_deliveries(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 1002
            pr_number = 72
            payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 7200,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 2,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
            default_review = {
                "decision": "revise",
                "status": "partial",
                "confidence": 0.6,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "review_required",
                "revision_instructions": ["fix failing test"],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["needs changes"],
            }
            governor_artifact = {
                "decision": "request_revision",
                "summary": ["Copilot findings need fixes"],
                "revision_requests": ["Fix null handling in governor loop"],
                "escalation_reason": "",
            }
            with patch("orchestrator.app.tasks.summarize_work_update", return_value={"review_artifact": default_review, "summary_bullets": ["revise"], "next_action": "revise"}), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": governor_artifact}), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.post_issue_comment", return_value=(True, "ok")) as mocked_comment, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=False,
                    )
                    first = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-governor-revision-1",
                        event="pull_request",
                        payload=payload,
                    )
                    second = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-governor-revision-2",
                        event="pull_request",
                        payload=payload,
                    )
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
            self.assertEqual(mocked_comment.call_count, 1)

    def test_guarded_path_escalation_blocks_unattended_approve_and_merge(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()
            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 1003
            pr_number = 73
            program_id = None

            payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 7300,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
            default_review = {
                "decision": "continue",
                "status": "met",
                "confidence": 0.8,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["ok"],
            }
            with patch("orchestrator.app.tasks.summarize_work_update", return_value={"review_artifact": default_review, "summary_bullets": ["ok"], "next_action": "continue"}), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "approve_and_merge", "summary": ["merge"], "revision_requests": [], "escalation_reason": ""}}), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=([".github/workflows/ci.yml"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.submit_approving_review", return_value=(True, "ok")) as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "ok")) as mocked_merge, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    _, program_id = self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-governor-guarded-1",
                        event="pull_request",
                        payload=payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            mocked_approve.assert_not_called()
            mocked_merge.assert_not_called()
            with Session(db.get_engine()) as session:
                program = session.get(Program, program_id)
                blocker = json.loads(program.blocker_state_json or "{}")
                self.assertEqual(blocker.get("reason"), "guarded_paths_require_human_review")

    def test_approve_and_merge_is_gated_on_green_checks(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()
            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 1004
            pr_number = 74
            payload = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 7400,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
            default_review = {
                "decision": "continue",
                "status": "met",
                "confidence": 0.8,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["ok"],
            }
            with patch("orchestrator.app.tasks.summarize_work_update", return_value={"review_artifact": default_review, "summary_bullets": ["ok"], "next_action": "continue"}), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "approve_and_merge", "summary": ["merge"], "revision_requests": [], "escalation_reason": ""}}), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.submit_approving_review", return_value=(True, "ok")) as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "ok")) as mocked_merge, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=False,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-governor-check-gate-1",
                        event="pull_request",
                        payload=payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            mocked_approve.assert_not_called()
            mocked_merge.assert_not_called()


class PreflightEndpointTests(unittest.TestCase):
    """Tests for GET /preflight diagnostic endpoint."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_preflight_returns_ok(self):
        """GET /preflight should return a structured report."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "false"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")

            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["ok"])
            pf = body["preflight"]
            self.assertIn("github_api_token", pf)
            self.assertIn("auto_merge_enabled", pf)
            self.assertIn("capabilities", pf)
            self.assertIn("blockers", pf)
            self.assertIn("admin_prerequisites", pf)
            self.assertIn("unattended_continuation", pf["capabilities"])
            self.assertIn("unattended_single_slice_execution", pf["capabilities"])
            self.assertIn("governor", pf)

    def test_preflight_unattended_false_when_auto_merge_disabled(self):
        """When PROGRAM_AUTO_MERGE=false, unattended_continuation should be False."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "false"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")

            body = resp.json()
            self.assertFalse(body["preflight"]["capabilities"]["unattended_continuation"])
            # Should mention auto_merge in blockers
            blockers = body["preflight"]["blockers"]
            self.assertTrue(any("auto_merge" in b.lower() or "auto-merge" in b.lower() for b in blockers))

    def test_preflight_unattended_true_when_all_enabled(self):
        """When all auto-* settings and the token are present, unattended_continuation is True."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["PROGRAM_AUTO_MERGE"] = "true"
            os.environ["PROGRAM_AUTO_CONTINUE"] = "true"
            os.environ["PROGRAM_AUTO_DISPATCH"] = "true"
            os.environ["PROGRAM_AUTO_APPROVE"] = "true"
            os.environ["PROGRAM_TRUSTED_AUTO_CONFIRM"] = "true"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")

            body = resp.json()
            self.assertTrue(body["preflight"]["capabilities"]["unattended_continuation"])
            self.assertTrue(body["preflight"]["github_api_token"])
            self.assertTrue(body["preflight"]["auto_merge_enabled"])

    def test_preflight_no_token_surfaces_blocker(self):
        """When GITHUB_API_TOKEN is absent, preflight should surface a blocker."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ.pop("GITHUB_API_TOKEN", None)
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")

            body = resp.json()
            self.assertFalse(body["preflight"]["github_api_token"])
            self.assertFalse(body["preflight"]["capabilities"]["unattended_continuation"])
            blockers = body["preflight"]["blockers"]
            self.assertTrue(any("token" in b.lower() or "github_api_token" in b for b in blockers))


class GovernorHardeningTests(unittest.TestCase):
    """Tests for governor hardening: deterministic safe-draft promotion,
    revision-in-flight blocking, mark-ready failure truthfulness,
    webhook ClientDisconnect, and reviewer cleanup idempotency."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _create_linked_task_run(
        self,
        db,
        *,
        repo: str,
        issue_number: int,
        pr_number: int,
        with_program: bool = True,
        governor_state_json: str | None = None,
    ) -> tuple[int, int | None]:
        with Session(db.get_engine()) as session:
            task = TaskPacket(
                github_repo=repo,
                github_issue_number=issue_number,
                title="Governor hardening test task",
                raw_body="body",
                status="working",
                approval_state="approved",
                acceptance_criteria_json='["done"]',
                task_kind="program_slice" if with_program else "single_task",
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            program_id = None
            if with_program:
                program = Program(
                    github_repo=repo,
                    root_issue_number=issue_number,
                    title="Governor hardening test program",
                    normalized_goal="goal",
                    status=PROGRAM_STATUS_ACTIVE,
                    current_slice_number=1,
                    auto_merge=True,
                    auto_dispatch=True,
                    auto_continue=True,
                )
                session.add(program)
                session.commit()
                session.refresh(program)
                program_id = program.id

                slice1 = ProgramSlice(
                    program_id=program.id,
                    slice_number=1,
                    milestone_key="M1",
                    title="Slice",
                    objective="Objective",
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

            run = AgentRun(
                task_packet_id=task.id,
                program_id=task.program_id,
                program_slice_id=task.program_slice_id,
                provider="github_copilot",
                github_repo=repo,
                github_issue_number=issue_number,
                github_pr_number=pr_number,
                status="working",
                last_summary="working",
                governor_state_json=governor_state_json,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return task.id, program_id

    def test_safe_draft_green_checks_no_guarded_paths_auto_promotes(self):
        """A draft PR with green checks, no guarded paths, no unresolved findings,
        and no revision-in-flight should be deterministically promoted to ready
        for review without requiring OpenAI."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 2001
            pr_number = 201

            # Simulate: workflow_run completed with success → checks_passed=True
            # PR is draft, no guarded paths
            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90001,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90001",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review", return_value=(True, "PR #201 marked ready for review")) as mocked_undraft, \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_openai_governor, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    # Pre-create a task/run with pr_draft=True in governor state
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=json.dumps({"pr_draft": True}),
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-safe-draft-promote-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # The deterministic promotion should have called mark_pr_ready_for_review
            mocked_undraft.assert_called_once()
            # The OpenAI governor should NOT have been called — deterministic path short-circuits
            mocked_openai_governor.assert_not_called()

    def test_guarded_paths_touched_blocks_auto_promotion(self):
        """A draft PR touching guarded paths should NOT be auto-promoted,
        even if checks are green and there are no findings."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GOVERNOR_GUARDED_PATHS"] = ".github/workflows/*"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 2002
            pr_number = 202

            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90002,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90002",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review") as mocked_undraft, \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "escalate_human", "summary": ["guarded"], "revision_requests": [], "escalation_reason": "guarded paths"},
                 }), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=([".github/workflows/ci.yml"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=json.dumps({"pr_draft": True}),
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-guarded-no-promote-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Must NOT auto-promote because guarded paths are touched
            mocked_undraft.assert_not_called()

    def test_revision_in_flight_blocks_auto_promotion(self):
        """A draft PR with waiting_for_revision_push=True should NOT be
        auto-promoted even if checks are green and findings are resolved."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 2003
            pr_number = 203

            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90003,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90003",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            # Governor state: revision was posted and we're still waiting for push
            # BUT there are still unresolved findings (so waiting_for_revision_push stays True)
            governor_state = json.dumps({
                "pr_draft": True,
                "waiting_for_revision_push": True,
                "last_revision_comment_fingerprint": "abc123",
                "revision_cycle_count": 1,
            })

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "revise", "status": "partial", "confidence": 0.6,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": ["fix test"],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["needs changes"],
                },
                "summary_bullets": ["needs changes"],
                "next_action": "revise",
            }), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review") as mocked_undraft, \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "wait", "summary": ["waiting"], "revision_requests": [], "escalation_reason": ""},
                 }), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Fix null check"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=governor_state,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-revision-in-flight-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Must NOT auto-promote because revision is in flight with unresolved findings
            mocked_undraft.assert_not_called()

    def test_mark_ready_failure_surfaces_blocker(self):
        """When the safe-draft promotion API call fails, the governor must persist
        a truthful blocker state and not report successful promotion."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 2004
            pr_number = 204

            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90004,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90004",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review", return_value=(False, "GitHub returned 403: insufficient permissions")) as mocked_undraft, \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_openai_governor, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    _, program_id = self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=json.dumps({"pr_draft": True}),
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-mark-ready-fail-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # mark_pr_ready_for_review was called but failed
            mocked_undraft.assert_called_once()
            # OpenAI governor should still not be called — the deterministic path handled it
            mocked_openai_governor.assert_not_called()
            # Program should be blocked with BLOCKER_WAITING_FOR_PR_READY
            with Session(db.get_engine()) as session:
                program = session.get(Program, program_id)
                blocker = json.loads(program.blocker_state_json or "{}")
                self.assertEqual(blocker.get("reason"), BLOCKER_WAITING_FOR_PR_READY)
                self.assertIn("403", blocker.get("detail", ""))

    def test_webhook_client_disconnect_handled_cleanly(self):
        """ClientDisconnect during webhook body read returns 503 JSONResponse
        without raising an unhandled ASGI exception, and logs contextual info."""
        from unittest.mock import AsyncMock
        from starlette.requests import ClientDisconnect as CD
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()
            with patch("orchestrator.app.github_webhooks.Request.body", new=AsyncMock(side_effect=CD())):
                with TestClient(main.app, raise_server_exceptions=False) as client:
                    response = client.post(
                        "/github/webhook",
                        headers={
                            "X-GitHub-Event": "pull_request",
                            "X-GitHub-Delivery": "disconnect-test-99",
                        },
                        content=b"",
                    )
                    self.assertEqual(response.status_code, 503)
                    body = response.json()
                    self.assertFalse(body.get("ok"))
                    self.assertIn("disconnected", body.get("detail", "").lower())

    def test_reviewer_cleanup_is_idempotent_on_repeated_runs(self):
        """Reviewer cleanup should work correctly on repeated governor invocations
        and track the cleanup result in governor state."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 2006
            pr_number = 206

            payload_1 = {
                "action": "opened",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 20600,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [{"login": "jeeves-jeevesenson"}],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
            # Second delivery: reviewer already removed
            payload_2 = {
                "action": "synchronize",
                "repository": {"full_name": repo},
                "pull_request": {
                    "number": pr_number,
                    "id": 20600,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 2,
                    "updated_at": "2024-01-01T01:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "wait", "summary": ["wait"], "revision_requests": [], "escalation_reason": ""},
                 }), \
                 patch("orchestrator.app.tasks.remove_requested_reviewers", return_value=(True, "ok")) as mocked_remove, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["orchestrator/app/tasks.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=False,
                    )
                    # First delivery: reviewer present → should remove
                    resp1 = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-cleanup-idem-1",
                        event="pull_request",
                        payload=payload_1,
                    )
                    self.assertEqual(resp1.status_code, 200)
                    # Second delivery: reviewer already gone → should not re-call remove
                    resp2 = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-cleanup-idem-2",
                        event="pull_request",
                        payload=payload_2,
                    )
                    self.assertEqual(resp2.status_code, 200)
            # remove was called only once (first delivery had the reviewer)
            self.assertEqual(mocked_remove.call_count, 1)

    def test_safe_draft_predicate_unit(self):
        """Unit test for the safe_draft_can_be_promoted predicate."""
        from orchestrator.app.tasks import safe_draft_can_be_promoted

        # Happy path: all conditions met
        self.assertTrue(safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=False,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        ))
        # Not a draft → no promotion needed
        self.assertFalse(safe_draft_can_be_promoted(
            pr_draft=False,
            checks_passed=True,
            guarded_paths_touched=False,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        ))
        # Checks not passed
        self.assertFalse(safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=False,
            guarded_paths_touched=False,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        ))
        # Guarded paths
        self.assertFalse(safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=True,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        ))
        # Unresolved findings
        self.assertFalse(safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=False,
            unresolved_findings=["Fix null check"],
            waiting_for_revision_push=False,
        ))
        # Waiting for revision push
        self.assertFalse(safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=False,
            unresolved_findings=[],
            waiting_for_revision_push=True,
        ))


class CopilotFixTriggerTests(unittest.TestCase):
    """Tests for the deterministic @copilot fix-trigger comment after Copilot
    review findings, deduplication, waiting-for-push blocking, re-review
    progression, and approval/merge gating."""

    _saved_env: dict[str, str | None]

    def setUp(self):
        self._saved_env = {}
        for key in (
            "DATABASE_URL", "GH_WEBHOOK_SECRET", "GITHUB_API_TOKEN",
            "GOVERNOR_GUARDED_PATHS", "GOVERNOR_REMOVE_REVIEWER_LOGIN",
        ):
            self._saved_env[key] = os.environ.get(key)

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _create_linked_task_run(
        self,
        db,
        *,
        repo: str,
        issue_number: int,
        pr_number: int,
        with_program: bool = True,
        governor_state_json: str | None = None,
    ) -> tuple[int, int | None]:
        with Session(db.get_engine()) as session:
            task = TaskPacket(
                github_repo=repo,
                github_issue_number=issue_number,
                title="Fix trigger test task",
                raw_body="body",
                status="working",
                approval_state="approved",
                acceptance_criteria_json='["done"]',
                task_kind="program_slice" if with_program else "single_task",
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            program_id = None
            if with_program:
                program = Program(
                    github_repo=repo,
                    root_issue_number=issue_number,
                    title="Fix trigger test program",
                    normalized_goal="goal",
                    status=PROGRAM_STATUS_ACTIVE,
                    current_slice_number=1,
                    auto_merge=True,
                    auto_dispatch=True,
                    auto_continue=True,
                )
                session.add(program)
                session.commit()
                session.refresh(program)
                program_id = program.id

                slice1 = ProgramSlice(
                    program_id=program.id,
                    slice_number=1,
                    milestone_key="M1",
                    title="Slice",
                    objective="Objective",
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

            run = AgentRun(
                task_packet_id=task.id,
                program_id=task.program_id,
                program_slice_id=task.program_slice_id,
                provider="github_copilot",
                github_repo=repo,
                github_issue_number=issue_number,
                github_pr_number=pr_number,
                status="working",
                last_summary="working",
                governor_state_json=governor_state_json,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return task.id, program_id

    # ---- Unit tests for _copilot_fix_trigger_body ----

    def test_fix_trigger_body_format(self):
        """The fix-trigger body starts with the required sentence, includes
        Focus on: with bullet findings, and ends with the guidance line."""
        from orchestrator.app.tasks import _copilot_fix_trigger_body

        body = _copilot_fix_trigger_body(findings=["Fix null check", "Add input validation"])
        self.assertTrue(body.startswith(
            "@copilot apply the unresolved review feedback on this pull request "
            "and push fixes directly to this branch."
        ))
        self.assertIn("Focus on:", body)
        self.assertIn("- Fix null check", body)
        self.assertIn("- Add input validation", body)
        self.assertIn(
            "If a finding is not valid, explain briefly in the PR conversation "
            "instead of changing code.",
            body,
        )

    def test_fix_trigger_body_empty_findings_fallback(self):
        """When no findings, the body includes a generic re-run bullet."""
        from orchestrator.app.tasks import _copilot_fix_trigger_body

        body = _copilot_fix_trigger_body(findings=[])
        self.assertIn("Focus on:", body)
        self.assertIn("Re-run your review", body)

    def test_fix_trigger_body_truncates_at_12(self):
        """Only the first 12 findings appear in the body."""
        from orchestrator.app.tasks import _copilot_fix_trigger_body

        findings = [f"Finding {i}" for i in range(20)]
        body = _copilot_fix_trigger_body(findings=findings)
        self.assertIn("- Finding 11", body)
        self.assertNotIn("- Finding 12", body)

    # ---- Integration tests: deterministic fix-trigger posting ----

    def test_ready_pr_with_copilot_findings_posts_fix_trigger(self):
        """A ready (non-draft) PR that receives Copilot review with unresolved
        findings should deterministically post the @copilot fix-trigger comment
        without requiring OpenAI."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3001
            pr_number = 301

            review_payload = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50001,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Fix null check in line 42",
                    "submitted_at": "2024-06-01T00:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30100,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_governor, \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Fix null check in line 42"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-fix-trigger-1",
                        event="pull_request_review",
                        payload=review_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Fix-trigger comment must have been posted
            mocked_post.assert_called_once()
            posted_body = mocked_post.call_args[1].get("body") or mocked_post.call_args[0][-1]
            self.assertTrue(posted_body.startswith(
                "@copilot apply the unresolved review feedback on this pull request"
            ))
            self.assertIn("Fix null check in line 42", posted_body)
            # OpenAI governor should NOT have been called — deterministic path short-circuits
            mocked_governor.assert_not_called()

    def test_fix_trigger_deduplication_on_repeated_webhook(self):
        """Reprocessing the same review webhook does not create a duplicate
        fix-trigger comment because of fingerprint deduplication."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3002
            pr_number = 302

            review_payload_1 = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50002,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Add error handling",
                    "submitted_at": "2024-06-01T00:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30200,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:00:00Z",
                },
            }
            # Second delivery: different event key but same findings
            review_payload_2 = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50002,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Add error handling",
                    "submitted_at": "2024-06-01T00:01:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30200,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:01:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_governor, \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Add error handling"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                    )
                    # First delivery
                    resp1 = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-fix-trigger-dedup-1",
                        event="pull_request_review",
                        payload=review_payload_1,
                    )
                    self.assertEqual(resp1.status_code, 200)
                    # Second delivery (redelivery with different timestamp)
                    resp2 = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-fix-trigger-dedup-2",
                        event="pull_request_review",
                        payload=review_payload_2,
                    )
                    self.assertEqual(resp2.status_code, 200)
            # Comment should only have been posted ONCE
            self.assertEqual(mocked_post.call_count, 1)
            # OpenAI governor should NOT have been called
            mocked_governor.assert_not_called()

    def test_fix_trigger_blocks_immediate_approve_and_merge(self):
        """After the fix-trigger comment is posted, the workflow must NOT
        approve or merge — it remains in waiting_for_revision_push state."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3003
            pr_number = 303

            review_payload = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50003,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Validate input parameter",
                    "submitted_at": "2024-06-01T00:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30300,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_governor, \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.submit_approving_review") as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr") as mocked_merge, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Validate input parameter"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-fix-blocks-merge-1",
                        event="pull_request_review",
                        payload=review_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Fix-trigger was posted
            mocked_post.assert_called_once()
            # But approve and merge were NOT called
            mocked_approve.assert_not_called()
            mocked_merge.assert_not_called()
            # Governor state should have waiting_for_revision_push=True
            with Session(db.get_engine()) as session:
                run = session.exec(
                    select(AgentRun)
                    .where(AgentRun.github_repo == repo)
                    .where(AgentRun.github_pr_number == pr_number)
                ).first()
                state = json.loads(run.governor_state_json or "{}")
                self.assertTrue(state.get("waiting_for_revision_push"))
                self.assertEqual(state.get("last_governor_decision"), "fix_trigger_posted")

    def test_push_after_fix_trigger_reenters_review_pipeline(self):
        """A push to the PR branch after the fix-trigger clears
        waiting_for_revision_push when findings are resolved, allowing
        the workflow to proceed to approval and merge."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3004
            pr_number = 304

            # Governor state: fix-trigger already posted, waiting for push
            governor_state = json.dumps({
                "pr_draft": False,
                "waiting_for_revision_push": True,
                "fix_trigger_fingerprint": "abc123",
                "revision_cycle_count": 1,
            })

            # Simulate: workflow_run completed with success (after Copilot push)
            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90010,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90010",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "merge_ready", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "approve_and_merge", "summary": ["ready"], "revision_requests": [], "escalation_reason": ""},
                 }), \
                 patch("orchestrator.app.tasks.submit_approving_review") as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")) as mocked_merge, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=governor_state,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-push-after-trigger-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Findings resolved → approval + merge should proceed
            mocked_approve.assert_called_once()
            mocked_merge.assert_called_once()

    def test_unresolved_findings_after_rereview_blocks_merge(self):
        """If unresolved Copilot findings remain after re-review, the PR
        is not approved or merged."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3005
            pr_number = 305

            # Governor state: fix-trigger posted, waiting for push
            governor_state = json.dumps({
                "pr_draft": False,
                "waiting_for_revision_push": True,
                "fix_trigger_fingerprint": "old-fp",
                "revision_cycle_count": 1,
            })

            # Copilot re-review arrives with NEW findings
            review_payload = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50005,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "New finding: missing error handler",
                    "submitted_at": "2024-06-01T01:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30500,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 2,
                    "updated_at": "2024-06-01T01:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update") as mocked_governor, \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.submit_approving_review") as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr") as mocked_merge, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "New finding: missing error handler"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=governor_state,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-rereview-findings-1",
                        event="pull_request_review",
                        payload=review_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # New fix trigger should be posted for the NEW findings
            mocked_post.assert_called_once()
            posted_body = mocked_post.call_args[1].get("body") or mocked_post.call_args[0][-1]
            self.assertIn("missing error handler", posted_body)
            # Must NOT approve or merge
            mocked_approve.assert_not_called()
            mocked_merge.assert_not_called()

    def test_guarded_paths_escalate_instead_of_fix_trigger(self):
        """When guarded paths are touched, the governor escalates to human
        rather than posting the fix-trigger comment."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GOVERNOR_GUARDED_PATHS"] = ".github/workflows/*"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3006
            pr_number = 306

            review_payload = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50006,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Fix workflow config",
                    "submitted_at": "2024-06-01T00:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30600,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "escalate_human", "summary": ["guarded"], "revision_requests": [], "escalation_reason": "guarded paths"},
                 }), \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=([".github/workflows/ci.yml"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Fix workflow config"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-guarded-escalate-1",
                        event="pull_request_review",
                        payload=review_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # The fix-trigger comment should NOT be posted (guarded path → escalation)
            mocked_post.assert_not_called()

    def test_draft_pr_with_findings_does_not_trigger_fix(self):
        """A draft PR with Copilot findings should NOT fire the deterministic
        fix-trigger; it should proceed to the normal OpenAI-directed path."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3007
            pr_number = 307

            review_payload = {
                "action": "submitted",
                "repository": {"full_name": repo},
                "review": {
                    "id": 50007,
                    "user": {"login": "copilot"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Fix null check",
                    "submitted_at": "2024-06-01T00:00:00Z",
                },
                "pull_request": {
                    "number": pr_number,
                    "id": 30700,
                    "title": f"Fix #{issue_number}",
                    "body": f"Closes #{issue_number}",
                    "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                    "merged": False,
                    "draft": True,
                    "state": "open",
                    "requested_reviewers": [],
                    "changed_files": 1,
                    "commits": 1,
                    "updated_at": "2024-06-01T00:00:00Z",
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "review_required", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "request_revision", "summary": ["needs fix"], "revision_requests": ["Fix null check"], "escalation_reason": ""},
                 }) as mocked_governor, \
                 patch("orchestrator.app.tasks.post_issue_comment") as mocked_post, \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Fix null check"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=json.dumps({"pr_draft": True}),
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-draft-no-trigger-1",
                        event="pull_request_review",
                        payload=review_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Draft PR should go through OpenAI path, not deterministic fix trigger
            mocked_governor.assert_called_once()
            # The posted comment should use the old batched_revision format, not the fix-trigger format
            if mocked_post.called:
                posted_body = mocked_post.call_args[1].get("body") or mocked_post.call_args[0][-1]
                self.assertNotIn(
                    "apply the unresolved review feedback",
                    posted_body,
                )

    def test_approve_and_merge_blocked_by_waiting_for_revision_push(self):
        """Even if OpenAI says approve_and_merge, a PR in waiting_for_revision_push
        state should not be approved or merged."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "jeeves-jeevesenson/init-tracker"
            issue_number = 3008
            pr_number = 308

            # Governor state: waiting for revision push, but findings just cleared
            # In this edge case, waiting_for_revision_push should block merge
            governor_state = json.dumps({
                "pr_draft": False,
                "waiting_for_revision_push": True,
                "fix_trigger_fingerprint": "some-fp",
                "revision_cycle_count": 1,
            })

            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": repo},
                "workflow_run": {
                    "id": 90020,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": f"https://github.com/{repo}/actions/runs/90020",
                    "pull_requests": [{"number": pr_number}],
                },
            }

            with patch("orchestrator.app.tasks.summarize_work_update", return_value={
                "review_artifact": {
                    "decision": "continue", "status": "met", "confidence": 0.8,
                    "scope_alignment": [], "acceptance_assessment": [], "risk_findings": [],
                    "merge_recommendation": "merge_ready", "revision_instructions": [],
                    "audit_recommendation": "", "next_slice_hint": "", "summary": ["ok"],
                },
                "summary_bullets": ["ok"],
                "next_action": "continue",
            }), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={
                     "governor_artifact": {"decision": "approve_and_merge", "summary": ["ready"], "revision_requests": [], "escalation_reason": ""},
                 }), \
                 patch("orchestrator.app.tasks.submit_approving_review") as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr") as mocked_merge, \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([
                     {"user": {"login": "copilot"}, "state": "CHANGES_REQUESTED", "body": "Stale finding"},
                 ], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._create_linked_task_run(
                        db,
                        repo=repo,
                        issue_number=issue_number,
                        pr_number=pr_number,
                        with_program=True,
                        governor_state_json=governor_state,
                    )
                    resp = _post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-waiting-blocks-merge-1",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(resp.status_code, 200)
            # Must NOT approve or merge while findings are unresolved
            mocked_approve.assert_not_called()
            mocked_merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
