from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import ANY, AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.requests import ClientDisconnect

from orchestrator.app.config import Settings
from orchestrator.app.copilot_identity import DOCUMENTED_COPILOT_ASSIGNEE_LOGIN
from orchestrator.app.github_dispatch import (
    DispatchResult,
    PullRequestInspection,
    dispatch_task_to_github_copilot,
    list_pull_request_file_details,
    lookup_pr_linked_issue_numbers,
)
from orchestrator.app.models import AgentRun, TaskPacket
from orchestrator.app import openai_planning
from orchestrator.app import openai_review
from orchestrator.app import openai_control_plane
from orchestrator.app.tasks import (
    CUSTOM_AGENT_INITIATIVE_SMITH,
    CUSTOM_AGENT_TRACKER_ENGINEER,
    _build_run_linkage_tag,
    _discover_post_dispatch_pr_candidate,
    parse_orch_linkage_tag,
)


def _reload_orchestrator_modules():
    config = importlib.import_module("orchestrator.app.config")
    db = importlib.import_module("orchestrator.app.db")
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    importlib.reload(config)
    importlib.reload(db)
    github = importlib.import_module("orchestrator.app.github_webhooks")
    openai = importlib.import_module("orchestrator.app.openai_webhooks")
    tasks = importlib.import_module("orchestrator.app.tasks")
    routes = importlib.import_module("orchestrator.app.task_routes")
    main = importlib.import_module("orchestrator.app.main")
    importlib.reload(tasks)
    importlib.reload(routes)
    importlib.reload(github)
    importlib.reload(openai)
    importlib.reload(main)
    return main, db


def _post_github_local(client: TestClient, *, secret: str, delivery: str, event: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
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


class OrchestratorMilestone2Tests(unittest.TestCase):
    ENV_KEYS = {
        "ORCHESTRATOR_ENV_FILE",
        "DATABASE_URL",
        "GH_WEBHOOK_SECRET",
        "OPENAI_WEBHOOK_SECRET",
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_URL",
        "ORCHESTRATOR_SECRET_KEY",
        "ORCHESTRATOR_DEBUG_WORKFLOW",
        "GITHUB_API_TOKEN",
        "GITHUB_DISPATCH_USER_TOKEN",
        "GITHUB_AUTH_MODE",
        "GITHUB_GOVERNOR_AUTH_MODE",
        "GITHUB_APP_CLIENT_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_PRIVATE_KEY_PATH",
        "TASK_LABEL",
        "TASK_APPROVED_LABEL",
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
        "OPENAI_FLAGSHIP_MODEL",
        "OPENAI_HELPER_MODEL",
        "OPENAI_ENABLE_PROMPT_CACHING",
        "OPENAI_PROMPT_CACHE_RETENTION",
        "OPENAI_ENABLE_RESPONSE_CHAINING",
        "PROGRAM_AUTO_PLAN",
        "PROGRAM_AUTO_APPROVE",
        "PROGRAM_AUTO_DISPATCH",
        "PROGRAM_AUTO_CONTINUE",
        "PROGRAM_AUTO_MERGE",
        "PROGRAM_MAX_REVISION_ATTEMPTS",
    }

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @staticmethod
    def _github_signature(secret: str, body: bytes) -> str:
        return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    def _post_github(self, client: TestClient, *, secret: str, delivery: str, event: str, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        signature = self._github_signature(secret, body)
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

    def test_issue_with_task_label_creates_planned_task_packet(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 123,
                    "node_id": "I_123",
                    "title": "Implement dispatch",
                    "body": "Please implement milestone 2.",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Implement milestone 2 dispatcher",
                    "scope": ["Add task packet", "Add dispatch"],
                    "non_goals": ["No auto-merge"],
                    "acceptance_criteria": ["Task persisted", "Approval required"],
                    "validation_guidance": ["python -m compileall orchestrator"],
                    "implementation_brief": "Build a durable orchestrator flow.",
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.json()["duplicate"])

                    tasks_response = client.get("/tasks")
                    self.assertEqual(tasks_response.status_code, 200)
                    self.assertEqual(tasks_response.json()["count"], 1)
                    task = tasks_response.json()["tasks"][0]
                    self.assertEqual(task["github_issue_number"], 123)
                    self.assertEqual(task["status"], "awaiting_approval")
                    self.assertEqual(task["approval_state"], "pending")
                    self.assertIn("Objective:", task["normalized_task_text"])
                    self.assertIn("Task planned and awaiting approval", task["latest_summary"])
                    self.assertEqual(task["worker_selection_mode"], "automatic")
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_TRACKER_ENGINEER)

    def test_auto_routing_selects_initiative_smith_for_broad_task(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 201,
                    "node_id": "I_201",
                    "title": "Architecture migration and stabilization pass",
                    "body": "Need broad end-to-end migration.",
                    "labels": [{"name": "agent:task"}],
                },
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Stabilize architecture",
                    "scope": ["Cross-system migration"],
                    "non_goals": [],
                    "acceptance_criteria": ["Complete migration"],
                    "validation_guidance": ["python -m unittest orchestrator.tests.test_milestone2"],
                    "implementation_brief": "Broad pass",
                    "recommended_worker": "initiative-smith",
                    "recommended_scope_class": "broad",
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-broad-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_INITIATIVE_SMITH)
                    self.assertEqual(task["recommended_worker"], "initiative-smith")
                    self.assertEqual(task["recommended_scope_class"], "broad")
                    self.assertEqual(task["worker_selection_mode"], "automatic")

    def test_auto_routing_prefers_deterministic_narrow_over_planner_hint(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 211,
                    "node_id": "I_211",
                    "title": "Bugfix follow-up polish",
                    "body": "Contained fix for a narrow regression",
                    "labels": [{"name": "agent:task"}],
                },
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Fix bug",
                    "scope": ["narrow bugfix"],
                    "non_goals": [],
                    "acceptance_criteria": ["bug fixed"],
                    "validation_guidance": ["python -m unittest orchestrator.tests.test_milestone2"],
                    "implementation_brief": "narrow pass",
                    "recommended_worker": "initiative-smith",
                    "recommended_scope_class": "broad",
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-narrow-deterministic-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_TRACKER_ENGINEER)
                    self.assertEqual(task["recommended_worker"], "tracker-engineer")
                    self.assertEqual(task["recommended_scope_class"], "narrow")
                    self.assertIn("deterministic", (task["worker_selection_reason"] or "").lower())

    def test_auto_routing_prefers_deterministic_broad_over_planner_hint(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 212,
                    "node_id": "I_212",
                    "title": "Architecture migration stabilization workstream",
                    "body": "Broad refactor and foundation migration",
                    "labels": [{"name": "agent:task"}],
                },
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Broad migration",
                    "scope": ["migration"],
                    "non_goals": [],
                    "acceptance_criteria": ["migration complete"],
                    "validation_guidance": ["python -m unittest orchestrator.tests.test_milestone2"],
                    "implementation_brief": "broad pass",
                    "recommended_worker": "tracker-engineer",
                    "recommended_scope_class": "narrow",
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-broad-deterministic-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_INITIATIVE_SMITH)
                    self.assertEqual(task["recommended_worker"], "initiative-smith")
                    self.assertEqual(task["recommended_scope_class"], "broad")
                    self.assertIn("deterministic", (task["worker_selection_reason"] or "").lower())

    def test_manual_override_label_wins_over_auto_routing(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 202,
                    "node_id": "I_202",
                    "title": "Fix targeted bug",
                    "body": "Narrow bug fix task",
                    "labels": [{"name": "agent:task"}],
                },
            }
            issue_override_payload = {
                "action": "labeled",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 202,
                    "node_id": "I_202",
                    "title": "Fix targeted bug",
                    "body": "Narrow bug fix task",
                    "labels": [{"name": "agent:task"}, {"name": "agent:initiative-smith"}],
                },
                "label": {"name": "agent:initiative-smith"},
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 202},
                "comment": {"body": "/approve"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Fix bug",
                    "scope": ["single bugfix"],
                    "non_goals": [],
                    "acceptance_criteria": ["Bug fixed"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "Narrow fix",
                    "recommended_worker": "tracker-engineer",
                    "recommended_scope_class": "narrow",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatched successfully",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-override-1",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-override-1",
                        event="issues",
                        payload=issue_override_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-approve-override-1",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_INITIATIVE_SMITH)
                    self.assertEqual(task["worker_selection_mode"], "override")
                    self.assertEqual(task["worker_override_label"], "agent:initiative-smith")

    def test_unknown_override_label_blocks_approval_clearly(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 203,
                    "node_id": "I_203",
                    "title": "Unknown override",
                    "body": "Task with unsupported override",
                    "labels": [{"name": "agent:task"}, {"name": "agent:unknown-worker"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 203},
                "comment": {"body": "/approve"},
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Override",
                    "scope": ["routing"],
                    "non_goals": [],
                    "acceptance_criteria": ["fail clearly"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "Override handling",
                },
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-unknown-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-approve-unknown-1",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "blocked")
                    self.assertEqual(task["worker_selection_mode"], "override_invalid")
                    self.assertIn("Unsupported agent override label", task["worker_selection_reason"])

    def test_approval_comment_dispatches_once(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 124,
                    "node_id": "I_124",
                    "title": "Dispatch me",
                    "body": "Need approval before dispatch",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 124},
                "comment": {"body": "/approve"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["dispatch once"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatched successfully",
                    dispatch_id="c_1",
                    dispatch_url="https://github.com/example/comment/1",
                ),
            ) as mocked_dispatch, patch("orchestrator.app.tasks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    opened = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-2",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(opened.status_code, 200)

                    first_approve = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-1",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    second_approve = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-2",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self.assertEqual(first_approve.status_code, 200)
                    self.assertEqual(second_approve.status_code, 200)

                    task_response = client.get("/tasks")
                    task = task_response.json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertEqual(task["approval_state"], "approved")
                    self.assertEqual(task["latest_run"]["status"], "awaiting_worker_start")
                    self.assertEqual(task["selected_custom_agent"], CUSTOM_AGENT_TRACKER_ENGINEER)
                    self.assertIsInstance(task["dispatch_payload_summary"], dict)
                    self.assertNotIn("custom_agent", task["dispatch_payload_summary"]["agent_assignment"])
                    self.assertIn(
                        "dispatch_mode=plain_copilot_fallback",
                        task["dispatch_payload_summary"]["dispatch_mode_summary"],
                    )

                self.assertEqual(mocked_dispatch.call_count, 1)
                task_dispatch_messages = [
                    str(call.args[0])
                    for call in mocked_notify.call_args_list
                    if call.args and str(call.args[0]).startswith("Task dispatched:")
                ]
                self.assertEqual(len(task_dispatch_messages), 1)
                self.assertIn("dispatch_mode=plain_copilot_fallback", task_dispatch_messages[0])

                with Session(db.get_engine()) as session:
                    run_count = len(list(session.exec(select(AgentRun)).all()))
                    self.assertEqual(run_count, 1)

    def test_override_after_active_run_does_not_duplicate_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 204,
                    "node_id": "I_204",
                    "title": "Bug fix",
                    "body": "contained patch",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 204},
                "comment": {"body": "/approve"},
            }
            assigned_payload = {
                "action": "assigned",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 204,
                    "node_id": "I_204",
                    "title": "Bug fix",
                    "body": "contained patch",
                    "labels": [{"name": "agent:task"}, {"name": "agent:approved"}],
                },
                "assignee": {"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN},
            }
            override_payload = {
                "action": "labeled",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 204,
                    "node_id": "I_204",
                    "title": "Bug fix",
                    "body": "contained patch",
                    "labels": [
                        {"name": "agent:task"},
                        {"name": "agent:approved"},
                        {"name": "agent:initiative-smith"},
                    ],
                },
                "label": {"name": "agent:initiative-smith"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "fix bug",
                    "scope": ["bugfix"],
                    "non_goals": [],
                    "acceptance_criteria": ["fix once"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "patch",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatched successfully",
                    dispatch_id="dispatch-204",
                ),
            ) as mocked_dispatch:
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-204",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-204",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-assigned-204",
                        event="issues",
                        payload=assigned_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-override-204",
                        event="issues",
                        payload=override_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")

                self.assertEqual(mocked_dispatch.call_count, 1)
                with Session(db.get_engine()) as session:
                    run_count = len(list(session.exec(select(AgentRun)).all()))
                    self.assertEqual(run_count, 1)

    def test_dispatch_request_payload_uses_agent_assignment_fields(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": "copilot-swe-agent",
                "COPILOT_TARGET_BRANCH": "main",
                "COPILOT_TARGET_REPO": "jeeves-jeevesenson/init-tracker",
                "COPILOT_CUSTOM_INSTRUCTIONS": "Follow repo workflow.",
                "COPILOT_CUSTOM_AGENT": "Initiative Smith",
                "COPILOT_MODEL": "gpt-4.1-mini",
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=42,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=126,
            title="Dispatch payload validation",
            normalized_task_text="Normalized text",
            acceptance_criteria_json='["A"]',
            validation_commands_json='["python -m compileall orchestrator"]',
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(
                status_code=200,
                headers={"content-type": "application/json"},
            )
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"login": "copilot-swe-agent", "__typename": "Bot", "id": "BOT_1"},
                            ]
                        }
                    }
                }
            }
            assign_response = Mock(
                status_code=201,
                headers={"content-type": "application/json"},
            )
            assign_response.json.return_value = {
                "id": 9001,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/126",
                "assignees": [{"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")
            mocked_client.post.side_effect = [preflight_response, assign_response, comment_response]

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertTrue(result.accepted)
            self.assertFalse(result.manual_required)
            self.assertIn("suggestedActors=['copilot-swe-agent']", result.summary)

            first_call = mocked_client.post.call_args_list[0]
            self.assertEqual(
                first_call.args[0],
                "https://api.github.com/graphql",
            )
            second_call = mocked_client.post.call_args_list[1]
            self.assertEqual(
                second_call.args[0],
                "https://api.github.com/repos/jeeves-jeevesenson/init-tracker/issues/126/assignees",
            )
            payload = second_call.kwargs["json"]
            self.assertEqual(payload["assignees"], [DOCUMENTED_COPILOT_ASSIGNEE_LOGIN])
            self.assertEqual(payload["agent_assignment"]["target_repo"], "jeeves-jeevesenson/init-tracker")
            self.assertEqual(payload["agent_assignment"]["base_branch"], "main")
            self.assertEqual(payload["agent_assignment"]["custom_instructions"], "Follow repo workflow.")
            self.assertNotIn("custom_agent", payload["agent_assignment"])
            self.assertEqual(payload["agent_assignment"]["model"], "gpt-4.1-mini")
            self.assertIn("dispatch_mode=plain_copilot_fallback", result.summary)

    def test_lookup_pr_linked_issue_numbers_parses_live_graphql_connected_event_shape(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
            },
            clear=False,
        ):
            settings = Settings()
        graphql_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "closingIssuesReferences": {
                            "nodes": [
                                {
                                    "number": 103,
                                    "repository": {"nameWithOwner": "jeeves-jeevesenson/init-tracker"},
                                }
                            ]
                        },
                        "timelineItems": {
                            "nodes": [
                                {
                                    "__typename": "ConnectedEvent",
                                    "subject": {
                                        "__typename": "Issue",
                                        "number": 103,
                                        "repository": {"nameWithOwner": "jeeves-jeevesenson/init-tracker"},
                                    },
                                }
                            ]
                        },
                    }
                }
            }
        }
        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            graphql_response = Mock(
                status_code=200,
                headers={"content-type": "application/json"},
                text=json.dumps(graphql_payload),
            )
            graphql_response.json.return_value = graphql_payload
            mocked_client.post.return_value = graphql_response

            linked_numbers, summary = lookup_pr_linked_issue_numbers(
                settings=settings,
                repo="jeeves-jeevesenson/init-tracker",
                pr_number=104,
            )

            self.assertEqual(linked_numbers, {103})
            self.assertIn("resolved 1 linked issue(s)", summary)

    def test_dispatch_payload_prefers_task_selected_custom_agent(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": "copilot-swe-agent",
                "COPILOT_TARGET_BRANCH": "main",
                "COPILOT_TARGET_REPO": "jeeves-jeevesenson/init-tracker",
                "COPILOT_CUSTOM_AGENT": "Initiative Smith",
                "ENABLE_GITHUB_CUSTOM_AGENT_DISPATCH": "true",
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=46,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=133,
            title="Dispatch payload selected worker validation",
            normalized_task_text="Normalized text",
            selected_custom_agent=CUSTOM_AGENT_TRACKER_ENGINEER,
            acceptance_criteria_json='["A"]',
            validation_commands_json='["python -m compileall orchestrator"]',
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(status_code=200, headers={"content-type": "application/json"})
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [{"login": "copilot-swe-agent", "__typename": "Bot", "id": "BOT_46"}]
                        }
                    }
                }
            }
            assign_response = Mock(status_code=201, headers={"content-type": "application/json"})
            assign_response.json.return_value = {
                "id": 9010,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/133",
                "assignees": [{"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")
            mocked_client.post.side_effect = [preflight_response, assign_response, comment_response]
            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertTrue(result.accepted)
            payload = mocked_client.post.call_args_list[1].kwargs["json"]
            self.assertEqual(payload["agent_assignment"]["custom_agent"], CUSTOM_AGENT_TRACKER_ENGINEER)
            self.assertIn("dispatch_mode=custom_agent_launch", result.summary)

    def test_default_dispatch_assignee_uses_documented_copilot_bot_login(self):
        with patch.dict(os.environ, {"COPILOT_DISPATCH_ASSIGNEE": ""}, clear=False):
            os.environ.pop("COPILOT_DISPATCH_ASSIGNEE", None)
            settings = Settings()
        self.assertEqual(settings.copilot_dispatch_assignee, DOCUMENTED_COPILOT_ASSIGNEE_LOGIN)

    def test_dispatch_accepts_legacy_copilot_assignee_config_via_normalization(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": "copilot-swe-agent",
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=43,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=130,
            title="Dispatch normalization validation",
            normalized_task_text="Normalized text",
            acceptance_criteria_json='["A"]',
            validation_commands_json='["python -m compileall orchestrator"]',
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(
                status_code=200,
                headers={"content-type": "application/json"},
            )
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"login": "copilot-swe-agent", "__typename": "Bot", "id": "BOT_2"},
                            ]
                        }
                    }
                }
            }
            assign_response = Mock(
                status_code=201,
                headers={"content-type": "application/json"},
            )
            assign_response.json.return_value = {
                "id": 9002,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/130",
                "assignees": [{"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")
            mocked_client.post.side_effect = [preflight_response, assign_response, comment_response]

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertTrue(result.accepted)
            self.assertFalse(result.manual_required)
            second_call = mocked_client.post.call_args_list[1]
            self.assertEqual(second_call.kwargs["json"]["assignees"], [DOCUMENTED_COPILOT_ASSIGNEE_LOGIN])

    def test_dispatch_manual_required_when_response_omits_copilot_assignee(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=44,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=131,
            title="Dispatch response assignee verification",
            normalized_task_text="Normalized text",
            acceptance_criteria_json='["A"]',
            validation_commands_json='["python -m compileall orchestrator"]',
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(
                status_code=200,
                headers={"content-type": "application/json"},
            )
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"login": "copilot-swe-agent", "__typename": "Bot", "id": "BOT_3"},
                            ]
                        }
                    }
                }
            }
            assign_response = Mock(
                status_code=201,
                headers={"content-type": "application/json"},
            )
            assign_response.json.return_value = {
                "id": 9003,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/131",
                "assignees": [{"login": "someone-else"}],
            }
            mocked_client.post.side_effect = [preflight_response, assign_response]

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertFalse(result.accepted)
            self.assertTrue(result.manual_required)
            self.assertIn(f"expected={DOCUMENTED_COPILOT_ASSIGNEE_LOGIN}", result.summary)
            self.assertIn("actual=['someone-else']", result.summary)

    def test_dispatch_preflight_blocks_when_suggested_actors_lack_copilot(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=45,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=132,
            title="Dispatch preflight failure",
            normalized_task_text="Normalized text",
            acceptance_criteria_json='["A"]',
            validation_commands_json='["python -m compileall orchestrator"]',
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(
                status_code=200,
                headers={"content-type": "application/json"},
            )
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"login": "some-other-bot[bot]", "__typename": "Bot", "id": "BOT_4"},
                            ]
                        }
                    }
                }
            }
            mocked_client.post.side_effect = [preflight_response]

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertFalse(result.accepted)
            self.assertTrue(result.manual_required)
            self.assertEqual(result.state, "blocked")
            self.assertIn("Copilot cloud agent not enabled or not assignable in this repository", result.summary)
            self.assertIn("suggestedActors=['some-other-bot[bot]']", result.summary)
            self.assertEqual(len(mocked_client.post.call_args_list), 1)

    def test_dispatch_rejection_sets_manual_dispatch_needed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 126,
                    "node_id": "I_126",
                    "title": "Dispatch rejection",
                    "body": "Should require manual intervention",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 126},
                "comment": {"body": "/approve"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["manual state on rejection"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary="GitHub API rejected assignment (403)",
                ),
            ):
                with TestClient(main.app) as client:
                    opened = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-3",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(opened.status_code, 200)

                    approved = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-3",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self.assertEqual(approved.status_code, 200)

                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "manual_dispatch_needed")
                    self.assertEqual(task["latest_run"]["status"], "manual_dispatch_needed")
                    self.assertIn("rejected", task["latest_summary"].lower())

    def test_worker_start_assignee_evidence_upgrades_manual_dispatch_needed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 141,
                    "node_id": "I_141",
                    "title": "Manual dispatch reconciliation",
                    "body": "Should upgrade out of manual state when worker evidence appears",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 141},
                "comment": {"body": "/approve"},
            }
            assigned_payload = {
                "action": "assigned",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 141,
                    "node_id": "I_141",
                    "title": "Manual dispatch reconciliation",
                    "body": "Should upgrade out of manual state when worker evidence appears",
                    "labels": [{"name": "agent:task"}, {"name": "agent:approved"}],
                },
                "assignee": {"name": "Copilot Coding Agent"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["manual state can be corrected from worker evidence"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                    "recommended_worker": "tracker-engineer",
                    "recommended_scope_class": "narrow",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary="Initial assignment verification failed",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-141",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-141",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task_before = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_before["status"], "manual_dispatch_needed")

                    assigned = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-assigned-141",
                        event="issues",
                        payload=assigned_payload,
                    )
                    self.assertEqual(assigned.status_code, 200)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "awaiting_worker_start")
                    self.assertEqual(task_after["latest_run"]["status"], "awaiting_worker_start")
                    self.assertEqual(task_after["selected_custom_agent"], CUSTOM_AGENT_TRACKER_ENGINEER)
                    self.assertEqual(
                        task_after["latest_run"]["selected_custom_agent"],
                        CUSTOM_AGENT_TRACKER_ENGINEER,
                    )

    def test_worker_comment_evidence_upgrades_manual_dispatch_needed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 144,
                    "node_id": "I_144",
                    "title": "Manual dispatch reconciliation by comment",
                    "body": "Comment signal should upgrade stale manual state",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 144},
                "comment": {"body": "/approve"},
            }
            worker_comment_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 144},
                "comment": {
                    "body": "Picking this up now.",
                    "user": {"name": "Copilot"},
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["comment evidence upgrades stale manual state"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary="Initial assignment verification failed",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-144",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-144",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task_before = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_before["status"], "manual_dispatch_needed")

                    comment = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-worker-comment-144",
                        event="issue_comment",
                        payload=worker_comment_payload,
                    )
                    self.assertEqual(comment.status_code, 200)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "awaiting_worker_start")
                    self.assertEqual(task_after["latest_run"]["status"], "awaiting_worker_start")

    def test_pr_evidence_upgrades_manual_dispatch_needed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 145,
                    "node_id": "I_145",
                    "title": "Manual dispatch reconciliation by PR evidence",
                    "body": "PR evidence should upgrade stale manual state",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 145},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 345,
                    "title": "Fixes #145",
                    "body": "Implements the requested fix",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/345",
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["PR evidence upgrades stale manual state"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary="Initial assignment verification failed",
                ),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={"summary_bullets": ["PR linked"], "next_action": "review"},
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-145",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-145",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task_before = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_before["status"], "manual_dispatch_needed")

                    pr_event = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-145",
                        event="pull_request",
                        payload=pr_payload,
                    )
                    self.assertEqual(pr_event.status_code, 200)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "pr_opened")
                    self.assertEqual(task_after["latest_run"]["status"], "pr_opened")

    def test_label_approval_dispatches(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 127,
                    "node_id": "I_127",
                    "title": "Label approval",
                    "body": "Label should approve",
                    "labels": [{"name": "agent:task"}],
                },
            }
            issue_labeled_payload = {
                "action": "labeled",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 127,
                    "node_id": "I_127",
                    "title": "Label approval",
                    "body": "Label should approve",
                    "labels": [{"name": "agent:task"}, {"name": "agent:approved"}],
                },
                "label": {"name": "agent:approved"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["label approval dispatches"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-4",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    labeled = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-labeled-4",
                        event="issues",
                        payload=issue_labeled_payload,
                    )
                    self.assertEqual(labeled.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["approval_state"], "approved")
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertEqual(task["latest_run"]["status"], "awaiting_worker_start")

    def test_worker_start_signal_from_issue_assignment_transitions_to_working(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 128,
                    "node_id": "I_128",
                    "title": "Worker start signal",
                    "body": "Await worker start",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 128},
                "comment": {"body": "/approve"},
            }
            assigned_payload = {
                "action": "assigned",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 128,
                    "node_id": "I_128",
                    "title": "Worker start signal",
                    "body": "Await worker start",
                    "labels": [{"name": "agent:task"}, {"name": "agent:approved"}],
                },
                "assignee": {"login": "copilot-swe-agent"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["worker start signal promotes status"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-5",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-5",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    assigned = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-assigned-5",
                        event="issues",
                        payload=assigned_payload,
                    )
                    self.assertEqual(assigned.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertEqual(task["latest_run"]["status"], "awaiting_worker_start")

    def test_worker_failure_comment_sets_worker_failed_state(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 142,
                    "node_id": "I_142",
                    "title": "Worker startup failure mapping",
                    "body": "Map startup failure to worker_failed",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 142},
                "comment": {"body": "/approve"},
            }
            failure_comment_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 142},
                "comment": {
                    "body": "The agent encountered an error and was unable to start working on this task.",
                    "user": {"name": "Copilot / Copilot SWE Agent"},
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["worker startup failure is classified"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-142",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-142",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    failed = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-failed-comment-142",
                        event="issue_comment",
                        payload=failure_comment_payload,
                    )
                    self.assertEqual(failed.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "worker_failed")
                    self.assertEqual(task["latest_run"]["status"], "worker_failed")
                    self.assertIn("startup failure", task["latest_summary"].lower())

    def test_worker_failure_comment_reconciles_stale_manual_dispatch_needed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 146,
                    "node_id": "I_146",
                    "title": "Worker startup failure from stale manual state",
                    "body": "Map startup failure to worker_failed from manual dispatch state",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 146},
                "comment": {"body": "/approve"},
            }
            failure_comment_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 146},
                "comment": {
                    "body": "The agent encountered an error and was unable to start working on this task.",
                    "user": {"login": "copilot-swe-agent"},
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["startup failure from stale manual state is classified"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary="Initial assignment verification failed",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-146",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-146",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task_before = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_before["status"], "manual_dispatch_needed")

                    failed = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-failed-comment-146",
                        event="issue_comment",
                        payload=failure_comment_payload,
                    )
                    self.assertEqual(failed.status_code, 200)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "worker_failed")
                    self.assertEqual(task_after["latest_run"]["status"], "worker_failed")
                    self.assertIn("startup failure", (task_after["latest_summary"] or "").lower())

    def test_worker_start_signal_from_issue_assignment_recognizes_documented_bot_login(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 132,
                    "node_id": "I_132",
                    "title": "Worker start signal documented login",
                    "body": "Await worker start",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 132},
                "comment": {"body": "/approve"},
            }
            assigned_payload = {
                "action": "assigned",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 132,
                    "node_id": "I_132",
                    "title": "Worker start signal documented login",
                    "body": "Await worker start",
                    "labels": [{"name": "agent:task"}, {"name": "agent:approved"}],
                },
                "assignee": {"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["worker start signal promotes status"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-7",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-7",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    assigned = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-assigned-7",
                        event="issues",
                        payload=assigned_payload,
                    )
                    self.assertEqual(assigned.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertEqual(task["latest_run"]["status"], "awaiting_worker_start")

    def test_issue_comment_multiline_approve_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 129,
                    "node_id": "I_129",
                    "title": "Multiline approve command",
                    "body": "Command may appear on later line",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 129},
                "comment": {"body": "Looks good.\n\n/approve please continue"},
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["multiline approval command works"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-6",
                        event="issues",
                        payload=issue_payload,
                    )
                    approved = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-6",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self.assertEqual(approved.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["approval_state"], "approved")

    def test_tasks_detail_route_and_duplicate_issue_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 125,
                    "node_id": "I_125",
                    "title": "Inspect routes",
                    "body": "Testing task detail route",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Inspect tasks route",
                    "scope": ["/tasks", "/tasks/{id}"],
                    "non_goals": [],
                    "acceptance_criteria": ["route returns data"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "route validation",
                },
            ):
                with TestClient(main.app) as client:
                    first = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-dup-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    second = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-dup-1",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
                    self.assertFalse(first.json()["duplicate"])
                    self.assertTrue(second.json()["duplicate"])

                    tasks_response = client.get("/tasks")
                    self.assertEqual(tasks_response.status_code, 200)
                    self.assertEqual(tasks_response.json()["count"], 1)

                    task_id = tasks_response.json()["tasks"][0]["id"]
                    detail = client.get(f"/tasks/{task_id}")
                    self.assertEqual(detail.status_code, 200)
                    self.assertEqual(detail.json()["task"]["id"], task_id)

                    missing = client.get("/tasks/9999")
                    self.assertEqual(missing.status_code, 404)

    def test_planning_retry_failure_after_success_keeps_non_failed_state_and_avoids_failure_notification(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 143,
                    "node_id": "I_143",
                    "title": "Planning retry stability",
                    "body": "Duplicate retries should not regress final state",
                    "labels": [{"name": "agent:task"}],
                },
            }
            issue_edited_payload = {
                "action": "edited",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 143,
                    "node_id": "I_143",
                    "title": "Planning retry stability",
                    "body": "Duplicate retries should not regress final state",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                side_effect=[
                    {
                        "objective": "Plan succeeds first",
                        "scope": ["planning"],
                        "non_goals": [],
                        "acceptance_criteria": ["planned"],
                        "validation_guidance": ["unit tests"],
                        "implementation_brief": "first pass success",
                    },
                    RuntimeError("openai transient scope error"),
                ],
            ), patch("orchestrator.app.tasks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    first = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-143",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    second = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-edited-143",
                        event="issues",
                        payload=issue_edited_payload,
                    )
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_approval")
                    self.assertEqual(task["approval_state"], "pending")
                    self.assertIn("keeping current state", task["latest_summary"])
                    failure_messages = [
                        str(call.args[0])
                        for call in mocked_notify.call_args_list
                        if call.args and "Task failed during planning" in str(call.args[0])
                    ]
                    self.assertEqual(failure_messages, [])

    def test_planning_retry_success_after_success_avoids_duplicate_planned_notification(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 144,
                    "node_id": "I_144",
                    "title": "plain copilot fallback proof",
                    "body": "Fix duplicate planned messages in orchestrator notifications.",
                    "labels": [{"name": "agent:task"}],
                },
            }
            issue_edited_payload = {
                "action": "edited",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 144,
                    "node_id": "I_144",
                    "title": "plain copilot fallback proof",
                    "body": "Fix duplicate planned messages in orchestrator notifications (edited).",
                    "labels": [{"name": "agent:task"}],
                },
            }

            plan_result = {
                "objective": "Fix duplicate notifications",
                "scope": ["orchestrator"],
                "non_goals": [],
                "acceptance_criteria": ["no duplicate planned messages"],
                "validation_guidance": ["unit tests"],
                "implementation_brief": "add guard on re-plan",
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                side_effect=[plan_result, plan_result],
            ), patch("orchestrator.app.tasks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    first = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-144",
                        event="issues",
                        payload=issue_opened_payload,
                    )
                    second = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-edited-144",
                        event="issues",
                        payload=issue_edited_payload,
                    )
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_approval")
                    planned_messages = [
                        str(call.args[0])
                        for call in mocked_notify.call_args_list
                        if call.args and "Task planned / awaiting approval" in str(call.args[0])
                    ]
                    self.assertEqual(len(planned_messages), 1)

    def test_structured_internal_plan_and_worker_brief_persist_separately(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 301,
                    "node_id": "I_301",
                    "title": "Structured planning persistence",
                    "body": "Persist internal plan and worker brief separately",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "internal_plan": {
                        "objective": "Upgrade planner",
                        "scope": ["Persist plan artifacts"],
                        "non_goals": ["No worker migration"],
                        "acceptance_criteria": ["Artifacts persisted"],
                        "validation_guidance": ["python -m compileall orchestrator"],
                        "implementation_brief": "Store internal and worker artifacts distinctly.",
                        "task_type": "feature",
                        "difficulty": "medium",
                        "repo_areas": ["orchestrator/app/tasks.py"],
                        "execution_risks": ["state drift"],
                        "reviewer_focus": ["payload separation"],
                        "recommended_scope_class": "broad",
                        "recommended_worker": "initiative-smith",
                    },
                    "worker_brief": {
                        "objective": "Implement structured planning storage",
                        "concise_scope": ["Persist internal plan JSON", "Persist worker brief JSON"],
                        "implementation_brief": "Keep worker-facing dispatch brief concise.",
                        "acceptance_criteria": ["Data available via /tasks routes"],
                        "validation_commands": ["python -m compileall orchestrator"],
                        "non_goals": ["No architecture redesign"],
                        "target_branch": "main",
                        "repo_grounded_hints": ["orchestrator/app/models.py"],
                    },
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-301",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertIsInstance(task["internal_plan"], dict)
                    self.assertIsInstance(task["worker_brief"], dict)
                    self.assertEqual(task["internal_plan"]["task_type"], "feature")
                    self.assertEqual(task["worker_brief"]["target_branch"], "main")
                    self.assertNotIn("recommended_worker", task["worker_brief"])

    def test_plain_fallback_dispatch_comment_omits_internal_worker_labels(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_API_TOKEN": "token",
                "GITHUB_API_URL": "https://api.github.com",
                "COPILOT_DISPATCH_ASSIGNEE": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
                "ENABLE_GITHUB_CUSTOM_AGENT_DISPATCH": "false",
            },
            clear=False,
        ):
            settings = Settings()
        task = TaskPacket(
            id=302,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=302,
            title="Dispatch packet should be worker-only",
            selected_custom_agent=CUSTOM_AGENT_INITIATIVE_SMITH,
            recommended_worker="initiative-smith",
            recommended_scope_class="broad",
            worker_brief_json=json.dumps(
                {
                    "objective": "Apply worker brief",
                    "concise_scope": ["Update planner stage"],
                    "implementation_brief": "Use worker brief only for dispatch packet.",
                    "acceptance_criteria": ["No internal labels in comment"],
                    "validation_commands": ["python -m compileall orchestrator"],
                    "non_goals": ["Do not expose internal routing"],
                    "target_branch": "main",
                    "repo_grounded_hints": ["orchestrator/app/github_dispatch.py"],
                }
            ),
        )

        with patch("orchestrator.app.github_dispatch.httpx.Client") as mocked_client_cls:
            mocked_client = mocked_client_cls.return_value.__enter__.return_value
            preflight_response = Mock(status_code=200, headers={"content-type": "application/json"})
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {
                                    "login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
                                    "__typename": "Bot",
                                    "id": "BOT_302",
                                }
                            ]
                        }
                    }
                }
            }
            assign_response = Mock(status_code=201, headers={"content-type": "application/json"})
            assign_response.json.return_value = {
                "id": 9302,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/302",
                "assignees": [{"login": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")
            mocked_client.post.side_effect = [preflight_response, assign_response, comment_response]

            linkage_tag = "ORCH-LINK: task=302 issue=302 run=77"
            result = dispatch_task_to_github_copilot(settings=settings, task=task, linkage_tag=linkage_tag)
            self.assertTrue(result.accepted)
            comment_payload = mocked_client.post.call_args_list[2].kwargs["json"]
            body = comment_payload["body"]
            self.assertNotIn("recommended_worker", body)
            self.assertNotIn("selected_custom_agent", body)
            self.assertNotIn("Initiative Smith", body)
            self.assertIn('"execution_mode": "plain_copilot_fallback"', body)
            self.assertIn(linkage_tag, body)
            self.assertIn("include this exact line in the PR body", body)

    def test_build_run_linkage_tag_format_is_deterministic(self):
        task = TaskPacket(
            id=47,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=115,
        )
        run = AgentRun(
            id=426,
            task_packet_id=47,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=115,
        )
        self.assertEqual(
            _build_run_linkage_tag(task=task, run=run),
            "ORCH-LINK: task=47 issue=115 run=426",
        )

    def test_parse_orch_linkage_tag_extracts_expected_fields_and_rejects_malformed(self):
        body = """
        ## Summary
        Some normal PR text.

        ORCH-LINK: task=49 issue=121 run=47
        """
        parsed = parse_orch_linkage_tag(body)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["task_id"], 49)
        self.assertEqual(parsed["issue_number"], 121)
        self.assertEqual(parsed["run_id"], 47)
        self.assertIsNone(parse_orch_linkage_tag("ORCH-LINK: task=49 issue=abc run=47"))

    def test_post_dispatch_discovery_prefers_exact_linkage_tag_over_heuristic_candidate(self):
        settings = Settings()
        task = TaskPacket(
            id=47,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=115,
        )
        run = AgentRun(
            id=99,
            task_packet_id=47,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=115,
            linkage_tag="ORCH-LINK: task=47 issue=115 run=99",
        )
        candidates = [
            {
                "number": 8801,
                "title": "Fixes #115",
                "body": "heuristic candidate",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user": {"login": "copilot-swe-agent"},
                "head": {"ref": "copilot/fix-115"},
            },
            {
                "number": 8802,
                "title": "Background cleanup",
                "body": "Contains ORCH-LINK: task=47 issue=115 run=99",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user": {"login": "octocat"},
                "head": {"ref": "cleanup/no-issue-token"},
            },
        ]
        with patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")):
            selected, reason, _ = _discover_post_dispatch_pr_candidate(
                settings=settings,
                task=task,
                run=run,
                dispatch_observed_at=datetime.now(timezone.utc),
            )
        self.assertIsNotNone(selected)
        self.assertEqual(reason, "linked_exact_linkage_tag")
        self.assertEqual(selected["pr"]["number"], 8802)
        self.assertIn("exact_linkage_tag_match", selected["reasons"])

    def test_post_dispatch_discovery_falls_back_to_heuristics_when_linkage_tag_missing(self):
        settings = Settings()
        task = TaskPacket(
            id=48,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=116,
        )
        run = AgentRun(
            id=100,
            task_packet_id=48,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=116,
            linkage_tag="ORCH-LINK: task=48 issue=116 run=100",
        )
        candidates = [
            {
                "number": 8810,
                "title": "Fixes #116",
                "body": "missing linkage tag but still relevant",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user": {"login": "copilot-swe-agent"},
                "head": {"ref": "copilot/fix-116"},
            }
        ]
        with patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")):
            selected, reason, _ = _discover_post_dispatch_pr_candidate(
                settings=settings,
                task=task,
                run=run,
                dispatch_observed_at=datetime.now(timezone.utc),
            )
        self.assertIsNotNone(selected)
        self.assertEqual(reason, "linked_heuristic")
        self.assertEqual(selected["pr"]["number"], 8810)

    def test_post_dispatch_discovery_does_not_false_link_when_tag_missing_and_no_heuristics(self):
        settings = Settings()
        task = TaskPacket(
            id=49,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=117,
        )
        run = AgentRun(
            id=101,
            task_packet_id=49,
            github_repo="jeeves-jeevesenson/init-tracker",
            github_issue_number=117,
            linkage_tag="ORCH-LINK: task=49 issue=117 run=101",
        )
        candidates = [
            {
                "number": 8820,
                "title": "Refactor lint config",
                "body": "No issue token and no linkage tag",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user": {"login": "copilot-swe-agent"},
                "head": {"ref": "copilot/refactor-lint"},
            }
        ]
        with patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")):
            selected, reason, _ = _discover_post_dispatch_pr_candidate(
                settings=settings,
                task=task,
                run=run,
                dispatch_observed_at=datetime.now(timezone.utc),
            )
        self.assertIsNone(selected)
        self.assertEqual(reason, "linkage_tag_missing_in_candidate_prs")

    def test_dispatch_persists_linkage_tag_and_dispatch_payload_summary(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 920,
                    "node_id": "I_920",
                    "title": "Persist linkage tag",
                    "body": "Ensure linkage persistence",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 920},
                "comment": {"body": "/approve"},
            }
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=([], "none")), \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-920", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-approve-920", event="issue_comment", payload=approve_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    run = task["latest_run"]
                    self.assertTrue(str(run["linkage_tag"]).startswith("ORCH-LINK: task="))
                    self.assertIn("issue=920", str(run["linkage_tag"]))
                    self.assertEqual(
                        run["dispatch_payload_summary"]["linkage_tag"],
                        run["linkage_tag"],
                    )

    def test_review_artifact_generation_and_storage(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 303,
                    "node_id": "I_303",
                    "title": "Review artifact persistence",
                    "body": "Need review artifact storage",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 303},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 88,
                    "title": "Implements #303",
                    "body": "Closes #303",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/88",
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Plan for review artifact",
                    "scope": ["dispatch and review"],
                    "non_goals": [],
                    "acceptance_criteria": ["review saved"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "produce run review artifact",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {
                        "decision": "continue",
                        "status": "met",
                        "confidence": 0.9,
                        "scope_alignment": ["Planner and reviewer paths updated"],
                        "acceptance_assessment": ["scope met"],
                        "risk_findings": ["none identified"],
                        "merge_recommendation": "merge_ready",
                        "revision_instructions": [],
                        "audit_recommendation": "",
                        "next_slice_hint": "",
                        "summary": ["Scope met and ready for review."],
                    },
                    "summary_bullets": ["Scope met and ready for review."],
                    "next_action": "continue",
                },
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-303",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-303",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-303",
                        event="pull_request",
                        payload=pr_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    review_artifact = task["latest_run"]["review_artifact"]
                    self.assertIsInstance(review_artifact, dict)
                    self.assertEqual(review_artifact["status"], "met")
                    self.assertEqual(review_artifact["merge_recommendation"], "merge_ready")

    def test_task_lifecycle_response_chaining_persists_and_flows_review_to_governor(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 330,
                    "node_id": "I_330",
                    "title": "Lifecycle chaining persistence",
                    "body": "Need chaining between review and governor calls",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 330},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 130,
                    "id": 9130,
                    "title": "Implements #330",
                    "body": "Closes #330",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/130",
                    "draft": False,
                    "changed_files": 2,
                    "commits": 1,
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            }
            review_artifact = {
                "decision": "continue",
                "status": "met",
                "confidence": 0.9,
                "scope_alignment": ["review phase complete"],
                "acceptance_assessment": ["good"],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["Ready to continue."],
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Plan task",
                    "scope": ["scope"],
                    "non_goals": [],
                    "acceptance_criteria": ["done"],
                    "validation_guidance": ["tests"],
                    "implementation_brief": "brief",
                    "planning_meta": {"openai_last_response_id": "resp_plan_330"},
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": review_artifact,
                    "summary_bullets": ["Ready to continue."],
                    "next_action": "continue",
                    "openai_meta": {"response_id": "resp_review_330"},
                },
            ) as mocked_review, patch(
                "orchestrator.app.tasks.summarize_governor_update",
                return_value={
                    "governor_artifact": {
                        "decision": "wait",
                        "summary": ["Waiting for checks/merge policy."],
                        "revision_requests": [],
                        "escalation_reason": "",
                    },
                    "summary_bullets": ["Waiting for checks/merge policy."],
                    "next_action": "wait",
                    "openai_meta": {"response_id": "resp_governor_330"},
                },
            ) as mocked_governor, patch(
                "orchestrator.app.tasks.list_pull_request_files",
                return_value=(["orchestrator/app/tasks.py"], ""),
            ), patch(
                "orchestrator.app.tasks.list_pull_request_reviews",
                return_value=([], ""),
            ), patch(
                "orchestrator.app.tasks.list_pull_request_review_comments",
                return_value=([], ""),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-330",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-330",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-330",
                        event="pull_request",
                        payload=pr_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["openai_last_response_id"], "resp_plan_330")
                    self.assertEqual(task["latest_run"]["openai_last_response_id"], "resp_governor_330")
                    self.assertIsNone(mocked_review.call_args.kwargs.get("previous_response_id"))
                    self.assertEqual(
                        mocked_governor.call_args.kwargs.get("previous_response_id"),
                        "resp_review_330",
                    )

    def test_fallback_mode_keeps_routing_metadata_separate_from_worker_brief(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 304,
                    "node_id": "I_304",
                    "title": "Migration architecture pass",
                    "body": "broad architecture migration",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 304},
                "comment": {"body": "/approve"},
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "internal_plan": {
                        "objective": "Broad migration",
                        "scope": ["cross-system"],
                        "non_goals": [],
                        "acceptance_criteria": ["migration complete"],
                        "validation_guidance": ["python -m unittest orchestrator.tests.test_milestone2"],
                        "implementation_brief": "broad pass",
                        "task_type": "migration",
                        "difficulty": "large",
                        "repo_areas": ["orchestrator/app/tasks.py"],
                        "execution_risks": ["coordination"],
                        "reviewer_focus": ["scope"],
                        "recommended_scope_class": "broad",
                        "recommended_worker": "initiative-smith",
                    },
                    "worker_brief": {
                        "objective": "Implement broad migration slice",
                        "concise_scope": ["planning pipeline"],
                        "implementation_brief": "worker-facing brief",
                        "acceptance_criteria": ["dispatch is clear"],
                        "validation_commands": ["python -m compileall orchestrator"],
                        "non_goals": ["no persona labels"],
                        "target_branch": "main",
                        "repo_grounded_hints": ["orchestrator/app/openai_planning.py"],
                    },
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-304",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-304",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["routing"]["selected_custom_agent"], CUSTOM_AGENT_INITIATIVE_SMITH)
                    self.assertEqual(task["github_execution_mode"], "plain_copilot_fallback")
                    self.assertNotIn("selected_custom_agent", json.dumps(task["worker_brief"]))

    def test_malformed_planning_output_is_handled_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 305,
                    "node_id": "I_305",
                    "title": "Malformed planning output",
                    "body": "Planner returns malformed content",
                    "labels": [{"name": "agent:task"}],
                },
            }
            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                side_effect=RuntimeError("planning validation failed: missing objective"),
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-305",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "failed")
                    self.assertIn("Planning failed", task["latest_summary"])
                    self.assertIn("missing objective", task["latest_summary"])

    def test_deterministic_routing_and_worker_brief_remain_separate(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 306,
                    "node_id": "I_306",
                    "title": "Bugfix follow-up separation",
                    "body": "narrow bug fix should force deterministic narrow route",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "internal_plan": {
                        "objective": "Fix bug",
                        "scope": ["narrow fix"],
                        "non_goals": [],
                        "acceptance_criteria": ["bug fixed"],
                        "validation_guidance": ["unit tests"],
                        "implementation_brief": "narrow patch",
                        "task_type": "bugfix",
                        "difficulty": "small",
                        "repo_areas": ["orchestrator/app/tasks.py"],
                        "execution_risks": ["regression"],
                        "reviewer_focus": ["deterministic route"],
                        "recommended_scope_class": "broad",
                        "recommended_worker": "initiative-smith",
                    },
                    "worker_brief": {
                        "objective": "Fix the narrow bug",
                        "concise_scope": ["patch bug path"],
                        "implementation_brief": "apply a contained fix",
                        "acceptance_criteria": ["bug fixed"],
                        "validation_commands": ["python -m unittest orchestrator.tests.test_milestone2"],
                        "non_goals": ["no broad migration"],
                        "target_branch": "main",
                        "repo_grounded_hints": ["orchestrator/app/tasks.py"],
                    },
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-306",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["routing"]["recommended_worker"], "tracker-engineer")
                    self.assertEqual(task["worker_brief"]["objective"], "Fix the narrow bug")
                    self.assertNotIn("recommended_worker", task["worker_brief"])

    def test_program_routes_show_program_and_slice_linkage(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 550,
                    "node_id": "I_550",
                    "title": "Program route coverage",
                    "body": "Large approved objective",
                    "labels": [{"name": "agent:task"}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "internal_plan": {
                        "objective": "Deliver broad objective",
                        "scope": ["program model", "review loop"],
                        "non_goals": [],
                        "acceptance_criteria": ["program visible"],
                        "validation_guidance": ["python -m pytest orchestrator/tests -q"],
                        "implementation_brief": "land additive program runner",
                        "task_type": "feature",
                        "difficulty": "large",
                        "repo_areas": ["orchestrator/app"],
                        "execution_risks": ["event duplication"],
                        "reviewer_focus": ["program linkage"],
                        "recommended_scope_class": "broad",
                        "recommended_worker": "initiative-smith",
                        "internal_routing_metadata": {},
                    },
                    "worker_brief": {
                        "objective": "Deliver slice 1",
                        "concise_scope": ["program model"],
                        "implementation_brief": "implement first slice",
                        "acceptance_criteria": ["slice 1 complete"],
                        "validation_commands": ["python -m pytest orchestrator/tests -q"],
                        "non_goals": [],
                        "target_branch": "main",
                        "repo_grounded_hints": ["orchestrator/app/tasks.py"],
                    },
                    "program_plan": {
                        "normalized_program_objective": "Deliver broad objective",
                        "definition_of_done": ["all slices complete"],
                        "non_goals": [],
                        "milestones": [{"key": "M1", "title": "M1", "goal": "slice done"}],
                        "slices": [
                            {
                                "slice_number": 1,
                                "milestone_key": "M1",
                                "title": "Slice 1",
                                "objective": "Deliver slice 1",
                                "acceptance_criteria": ["slice 1 complete"],
                                "non_goals": [],
                                "expected_file_zones": ["orchestrator/app/tasks.py"],
                                "continuation_hint": "continue",
                                "slice_type": "implementation",
                            }
                        ],
                        "current_slice_brief": "Deliver slice 1",
                        "acceptance_criteria": ["slice 1 complete"],
                        "risk_profile": ["event duplication"],
                        "recommended_worker": "initiative-smith",
                        "recommended_scope_class": "broad",
                        "continuation_hints": ["continue"],
                    },
                },
            ):
                with TestClient(main.app) as client:
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-program-550",
                        event="issues",
                        payload=issue_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertIsNotNone(task["program_id"])
                    self.assertIsNotNone(task["program_slice_id"])

                    programs_response = client.get("/programs")
                    self.assertEqual(programs_response.status_code, 200)
                    programs = programs_response.json()["programs"]
                    self.assertEqual(len(programs), 1)
                    self.assertEqual(programs[0]["current_slice"]["task_packet_id"], task["id"])

    def test_reviewer_revise_decision_redispatches_same_slice(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 551,
                    "node_id": "I_551",
                    "title": "Revision loop objective",
                    "body": "Need iterative revisions",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 551},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "id": 55101,
                    "number": 5511,
                    "title": "Implements #551",
                    "body": "Closes #551",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/5511",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            }
            workflow_payload = {
                "action": "completed",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "workflow_run": {
                    "id": 9988,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/9988",
                    "pull_requests": [{"number": 5511}],
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Iterative revision objective",
                    "scope": ["review loop"],
                    "non_goals": [],
                    "acceptance_criteria": ["revision handled"],
                    "validation_guidance": ["python -m pytest orchestrator/tests -q"],
                    "implementation_brief": "enable reviewer-driven revisions",
                    "task_type": "feature",
                    "difficulty": "medium",
                    "repo_areas": ["orchestrator/app/tasks.py"],
                    "execution_risks": ["looping revisions"],
                    "reviewer_focus": ["revision path"],
                    "recommended_scope_class": "narrow",
                    "recommended_worker": "tracker-engineer",
                    "internal_routing_metadata": {},
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ) as mocked_dispatch, patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {
                        "decision": "revise",
                        "status": "partial",
                        "confidence": 0.7,
                        "scope_alignment": ["scope partially met"],
                        "acceptance_assessment": ["needs another pass"],
                        "risk_findings": ["minor gaps"],
                        "merge_recommendation": "review_required",
                        "revision_instructions": ["address failing edge case"],
                        "audit_recommendation": "",
                        "next_slice_hint": "",
                        "summary": ["Revision requested"],
                    },
                    "summary_bullets": ["Revision requested"],
                    "next_action": "revise",
                },
            ):
                with TestClient(main.app) as client:
                    self.assertEqual(
                        self._post_github(
                            client,
                            secret="test-gh-secret",
                            delivery="delivery-program-551-open",
                            event="issues",
                            payload=issue_payload,
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        self._post_github(
                            client,
                            secret="test-gh-secret",
                            delivery="delivery-program-551-approve",
                            event="issue_comment",
                            payload=approve_payload,
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        self._post_github(
                            client,
                            secret="test-gh-secret",
                            delivery="delivery-program-551-pr",
                            event="pull_request",
                            payload=pr_payload,
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        self._post_github(
                            client,
                            secret="test-gh-secret",
                            delivery="delivery-program-551-wf",
                            event="workflow_run",
                            payload=workflow_payload,
                        ).status_code,
                        200,
                    )

            self.assertGreaterEqual(mocked_dispatch.call_count, 1)
            with Session(db.get_engine()) as session:
                query = (
                    select(AgentRun)
                    .where(AgentRun.github_repo == "jeeves-jeevesenson/init-tracker")
                    .where(AgentRun.github_issue_number == 551)
                    .order_by(AgentRun.created_at.desc())
                )
                runs = list(session.exec(query).all())
                self.assertGreaterEqual(len(runs), 1)
                decisions = {run.continuation_decision for run in runs}
                self.assertIn("revise", decisions)

    def test_github_webhook_body_disconnect_returns_retryable_failure(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, _ = _reload_orchestrator_modules()
            with patch("orchestrator.app.github_webhooks.Request.body", new=AsyncMock(side_effect=ClientDisconnect())):
                with TestClient(main.app) as client:
                    response = client.post(
                        "/github/webhook",
                        headers={"X-GitHub-Event": "issues", "X-GitHub-Delivery": "disconnect-1"},
                        content=b"",
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertIn("retry", response.json()["detail"].lower())
                    runs = client.get("/runs").json()
                    self.assertEqual(runs["count"], 0)

    def test_stale_assignment_only_run_reconciles_to_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["WORKER_WEAK_EVIDENCE_STALE_MINUTES"] = "1"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                with Session(db.get_engine()) as session:
                    task = TaskPacket(
                        github_repo="jeeves-jeevesenson/init-tracker",
                        github_issue_number=616,
                        title="Stale weak evidence",
                        raw_body="body",
                        status="working",
                        approval_state="approved",
                        latest_summary="Worker start signal: issue assigned to Copilot",
                    )
                    session.add(task)
                    session.commit()
                    session.refresh(task)
                    stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)
                    run = AgentRun(
                        task_packet_id=task.id,
                        provider="github_copilot",
                        github_repo=task.github_repo,
                        github_issue_number=task.github_issue_number,
                        status="working",
                        last_summary="Worker start signal: issue assigned to copilot-swe-agent",
                        updated_at=stale_time,
                        created_at=stale_time,
                    )
                    session.add(run)
                    session.commit()

                tasks = client.get("/tasks").json()["tasks"]
                self.assertEqual(tasks[0]["status"], "blocked")
                self.assertEqual(tasks[0]["latest_run"]["status"], "blocked")
                self.assertIn("missing=github_pr_number", tasks[0]["latest_summary"])

    def test_unlinked_external_pr_activity_does_not_count_as_progress(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 617,
                    "node_id": "I_617",
                    "title": "Unlinked PR reconciliation",
                    "body": "Track PR linkage",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 617},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 9991,
                    "title": "Unrelated PR",
                    "body": "No issue reference here.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9991",
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["linkage stays truthful"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_issue_timeline_events",
                return_value=([], "none"),
            ):
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-617",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-617",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-617",
                        event="pull_request",
                        payload=pr_payload,
                    )
                    self.assertEqual(response.status_code, 202)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertIsNone(task["latest_run"]["github_pr_number"])
                    self.assertIn("pr association pending (retryable)", task["latest_summary"].lower())

    def test_pull_request_webhook_explicit_issue_ref_links_task(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 620,
                    "node_id": "I_620",
                    "title": "Explicit PR reference linkage",
                    "body": "Ensure explicit refs still link",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 620},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6201,
                    "title": "Fixes #620",
                    "body": "Implements requested change.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6201",
                    "changed_files": 1,
                    "commits": 1,
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["explicit refs map directly"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {"decision": "wait", "summary": ["PR opened"], "revision_instructions": []},
                    "summary_bullets": ["PR opened"],
                    "next_action": "wait",
                },
            ):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-620", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-620", event="issue_comment", payload=approve_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-620", event="pull_request", payload=pr_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["github_pr_number"], 6201)

    def test_pull_request_webhook_authoritative_connected_event_links_without_text_refs(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 103,
                    "node_id": "I_103",
                    "title": "Authoritative webhook association",
                    "body": "Link PRs through issue graph evidence",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 103},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 104,
                    "title": "Add blank file test",
                    "body": "Implements coverage improvements.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/104",
                    "draft": True,
                    "changed_files": 1,
                    "commits": 1,
                    "head": {"ref": "copilot/add-blank-file-test", "sha": "abc123def456"},
                    "node_id": "PR_kw_104",
                },
            }
            graphql_payload = {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "nodes": [
                                    {
                                        "number": 103,
                                        "repository": {"nameWithOwner": "jeeves-jeevesenson/init-tracker"},
                                    }
                                ]
                            },
                            "timelineItems": {
                                "nodes": [
                                    {
                                        "__typename": "ConnectedEvent",
                                        "subject": {
                                            "__typename": "Issue",
                                            "number": 103,
                                            "repository": {"nameWithOwner": "jeeves-jeevesenson/init-tracker"},
                                        },
                                    }
                                ]
                            },
                        }
                    }
                }
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["authoritative linkage works"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {"decision": "wait", "summary": ["PR opened"], "revision_instructions": []},
                    "summary_bullets": ["PR opened"],
                    "next_action": "wait",
                },
            ), patch(
                "orchestrator.app.github_dispatch.httpx.Client",
            ) as mocked_client_cls:
                mocked_client = mocked_client_cls.return_value.__enter__.return_value
                graphql_response = Mock(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    text=json.dumps(graphql_payload),
                )
                graphql_response.json.return_value = graphql_payload
                mocked_client.post.return_value = graphql_response
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-103", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-103", event="issue_comment", payload=approve_payload)
                    task_after_approve = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after_approve["status"], "awaiting_worker_start")
                    self.assertEqual(task_after_approve["latest_run"]["status"], "awaiting_worker_start")
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-104", event="pull_request", payload=pr_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["github_pr_number"], 104)
                    self.assertEqual(task["latest_run"]["github_pr_url"], "https://github.com/jeeves-jeevesenson/init-tracker/pull/104")
                    self.assertEqual(task["latest_run"]["github_pr_node_id"], "PR_kw_104")
                    self.assertNotIn("reconciliation incomplete", task["latest_summary"].lower())

    def test_pull_request_webhook_ready_for_review_advances_existing_linked_draft_pr(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 624,
                    "node_id": "I_624",
                    "title": "Draft to ready PR transition",
                    "body": "Ensure linked draft transitions cleanly",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 624},
                "comment": {"body": "/approve"},
            }
            opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6241,
                    "title": "Copilot change without issue ref",
                    "body": "No textual issue refs in this draft",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6241",
                    "draft": True,
                    "changed_files": 2,
                    "commits": 1,
                    "head": {"ref": "copilot/fix-624", "sha": "beadfeed624"},
                },
            }
            ready_payload = {
                "action": "ready_for_review",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6241,
                    "title": "Copilot change without issue ref",
                    "body": "No textual issue refs in this draft",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6241",
                    "draft": False,
                    "changed_files": 2,
                    "commits": 2,
                    "head": {"ref": "copilot/fix-624", "sha": "beadfeed624"},
                    "updated_at": "2026-04-15T00:00:00Z",
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["authoritative linkage works"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.list_issue_timeline_events",
                return_value=([{"event": "referenced", "commit_id": "beadfeed624"}], "ok"),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {"decision": "wait", "summary": ["PR event observed"], "revision_instructions": []},
                    "summary_bullets": ["PR event observed"],
                    "next_action": "wait",
                },
            ):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-624", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-624", event="issue_comment", payload=approve_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-624", event="pull_request", payload=opened_payload)
                    task_after_open = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after_open["latest_run"]["github_pr_number"], 6241)
                    self.assertEqual(task_after_open["status"], "pr_opened")
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-ready-624", event="pull_request", payload=ready_payload)
                    task_after_ready = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after_ready["status"], "pr_opened")
                    self.assertEqual(task_after_ready["latest_run"]["status"], "pr_opened")
                    self.assertEqual(task_after_ready["latest_run"]["github_pr_number"], 6241)
                    self.assertNotIn("reconciliation incomplete", task_after_ready["latest_summary"].lower())

    def test_pull_request_webhook_unmatched_copilot_draft_without_authoritative_evidence_does_not_link(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 625,
                    "node_id": "I_625",
                    "title": "No false copilot draft linking",
                    "body": "Draft PR should not link without authoritative evidence",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 625},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6251,
                    "title": "Copilot draft branch",
                    "body": "No explicit issue refs.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6251",
                    "draft": True,
                    "head": {"ref": "copilot/some-random-change", "sha": "cafebabe625"},
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["linkage stays truthful"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.lookup_pr_linked_issue_numbers",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.list_issue_timeline_events",
                return_value=([], "none"),
            ):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-625", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-625", event="issue_comment", payload=approve_payload)
                    response = self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-625", event="pull_request", payload=pr_payload)
                    self.assertEqual(response.status_code, 202)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertIsNone(task["latest_run"]["github_pr_number"])
                    self.assertIn("pr association pending (retryable)", task["latest_summary"].lower())

    def test_pull_request_webhook_missing_dispatch_auth_reports_explicit_reconciliation_reason(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ.pop("GITHUB_API_TOKEN", None)
            os.environ.pop("GITHUB_DISPATCH_USER_TOKEN", None)
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 626,
                    "node_id": "I_626",
                    "title": "Auth missing diagnostics",
                    "body": "Ensure authoritative failure is explicit",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 626},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6261,
                    "title": "No textual refs",
                    "body": "No direct issue mention.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6261",
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["dispatch accepted"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-626", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-626", event="issue_comment", payload=approve_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-626", event="pull_request", payload=pr_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertIn("reason=dispatch_auth_missing", task["latest_summary"])

    def test_pull_request_webhook_authoritative_association_ambiguous_does_not_link(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload_1 = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 622, "node_id": "I_622", "title": "First candidate", "body": "Task one", "labels": [{"name": "agent:task"}]},
            }
            issue_payload_2 = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 623, "node_id": "I_623", "title": "Second candidate", "body": "Task two", "labels": [{"name": "agent:task"}]},
            }
            approve_payload_1 = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 622},
                "comment": {"body": "/approve"},
            }
            approve_payload_2 = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 623},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6231,
                    "title": "No textual refs",
                    "body": "No issue refs in this PR.",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6231",
                    "head": {"ref": "copilot/add-test", "sha": "feedface01"},
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["dispatch accepted"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.lookup_pr_linked_issue_numbers",
                return_value=({622, 623}, "ok"),
            ):
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-622", event="issues", payload=issue_payload_1)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-623", event="issues", payload=issue_payload_2)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-622", event="issue_comment", payload=approve_payload_1)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-623", event="issue_comment", payload=approve_payload_2)
                    response = self._post_github(client, secret="test-gh-secret", delivery="delivery-pr-opened-6231", event="pull_request", payload=pr_payload)
                    self.assertEqual(response.status_code, 202)
                    tasks = client.get("/tasks").json()["tasks"]
                    self.assertFalse(any(task["latest_run"]["github_pr_number"] == 6231 for task in tasks))
                    self.assertFalse(any(task["status"] == "pr_opened" for task in tasks))
                    self.assertTrue(any("reason=candidate_match_ambiguous" in (task["latest_summary"] or "") for task in tasks))

    def test_pull_request_webhook_assigned_retryable_miss_recovers_on_later_opened(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 106,
                    "node_id": "I_106",
                    "title": "Recover from early PR association miss",
                    "body": "Assigned event can arrive before authoritative link exists",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 106},
                "comment": {"body": "/approve"},
            }
            assigned_payload = {
                "action": "assigned",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 107,
                    "title": "Early assignment event",
                    "body": "No textual refs yet",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/107",
                    "draft": True,
                    "head": {"ref": "copilot/fix-106", "sha": "cafe0107"},
                },
            }
            opened_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 107,
                    "title": "Early assignment event",
                    "body": "No textual refs yet",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/107",
                    "draft": False,
                    "changed_files": 2,
                    "commits": 2,
                    "head": {"ref": "copilot/fix-106", "sha": "cafe0107"},
                    "updated_at": "2026-04-15T00:00:00Z",
                },
            }
            graphql_payload = {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "nodes": [
                                    {
                                        "number": 106,
                                        "repository": {"nameWithOwner": "jeeves-jeevesenson/init-tracker"},
                                    }
                                ]
                            },
                            "timelineItems": {"nodes": []},
                        }
                    }
                }
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["retryable miss can recover"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch(
                "orchestrator.app.tasks.list_recent_pull_requests",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.lookup_pr_linked_issue_numbers",
                side_effect=[([], "none"), ({106}, "ok")],
            ), patch(
                "orchestrator.app.tasks.list_issue_timeline_events",
                return_value=([], "none"),
            ), patch(
                "orchestrator.app.tasks.summarize_work_update",
                return_value={
                    "review_artifact": {"decision": "wait", "summary": ["PR opened"], "revision_instructions": []},
                    "summary_bullets": ["PR opened"],
                    "next_action": "wait",
                },
            ), patch(
                "orchestrator.app.github_dispatch.httpx.Client",
            ) as mocked_client_cls:
                mocked_client = mocked_client_cls.return_value.__enter__.return_value
                graphql_response = Mock(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    text=json.dumps(graphql_payload),
                )
                graphql_response.json.return_value = graphql_payload
                mocked_client.post.return_value = graphql_response
                with TestClient(main.app) as client:
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-task-opened-106", event="issues", payload=issue_payload)
                    self._post_github(client, secret="test-gh-secret", delivery="delivery-approve-106", event="issue_comment", payload=approve_payload)
                    response_assigned = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-assigned-107",
                        event="pull_request",
                        payload=assigned_payload,
                    )
                    self.assertEqual(response_assigned.status_code, 202)
                    task_after_assigned = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after_assigned["status"], "awaiting_worker_start")
                    self.assertIn("pr association pending (retryable)", (task_after_assigned["latest_summary"] or "").lower())
                    self.assertIsNone(task_after_assigned["latest_run"]["github_pr_number"])

                    response_opened = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-107",
                        event="pull_request",
                        payload=opened_payload,
                    )
                    self.assertEqual(response_opened.status_code, 200)
                    task_after_opened = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after_opened["status"], "pr_opened")
                    self.assertEqual(task_after_opened["latest_run"]["status"], "pr_opened")
                    self.assertEqual(task_after_opened["latest_run"]["github_pr_number"], 107)

    def test_empty_pr_is_rejected_as_progress(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {
                    "number": 618,
                    "node_id": "I_618",
                    "title": "Empty PR rejection",
                    "body": "Reject empty PRs",
                    "labels": [{"name": "agent:task"}],
                },
            }
            approve_payload = {
                "action": "created",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 618},
                "comment": {"body": "/approve"},
            }
            pr_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "pull_request": {
                    "number": 6181,
                    "title": "Fixes #618",
                    "body": "Implements nothing",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/6181",
                    "changed_files": 0,
                    "commits": 1,
                },
            }

            with patch(
                "orchestrator.app.tasks.plan_task_packet",
                return_value={
                    "objective": "Dispatch task",
                    "scope": ["dispatch"],
                    "non_goals": [],
                    "acceptance_criteria": ["empty PR blocked"],
                    "validation_guidance": ["unit tests"],
                    "implementation_brief": "dispatch this",
                },
            ), patch(
                "orchestrator.app.tasks.dispatch_task_to_github_copilot",
                return_value=DispatchResult(
                    attempted=True,
                    accepted=True,
                    manual_required=False,
                    state="accepted",
                    summary="Dispatch accepted",
                ),
            ), patch("orchestrator.app.tasks.summarize_work_update") as mocked_summarize:
                with TestClient(main.app) as client:
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-task-opened-618",
                        event="issues",
                        payload=issue_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-approve-618",
                        event="issue_comment",
                        payload=approve_payload,
                    )
                    self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-pr-opened-618",
                        event="pull_request",
                        payload=pr_payload,
                    )
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "blocked")
                    self.assertIn("empty pr", task["latest_summary"].lower())
                    mocked_summarize.assert_not_called()

    def test_workflow_run_recovers_unlinked_run_from_orch_link_tag(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            workflow_payload = {
                "action": "in_progress",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "workflow_run": {
                    "id": 77001,
                    "name": "CI",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/77001",
                    "pull_requests": [{"number": 122}],
                },
            }
            with patch(
                "orchestrator.app.tasks.inspect_pull_request",
                return_value=PullRequestInspection(
                    ok=True,
                    changed_files=3,
                    commits=1,
                    draft=False,
                    state="open",
                    merged=False,
                    summary="ok",
                    number=122,
                    node_id="PR_kw_122",
                    html_url="https://github.com/jeeves-jeevesenson/init-tracker/pull/122",
                    body="context\nORCH-LINK: task=49 issue=121 run=47\n",
                ),
            ):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            id=49,
                            github_repo="jeeves-jeevesenson/init-tracker",
                            github_issue_number=121,
                            title="Recover workflow linkage from ORCH-LINK",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            latest_summary="worker running",
                        )
                        session.add(task)
                        session.commit()
                        run = AgentRun(
                            id=47,
                            task_packet_id=task.id,
                            provider="github_copilot",
                            github_repo=task.github_repo,
                            github_issue_number=task.github_issue_number,
                            status="working",
                            last_summary="worker running",
                        )
                        session.add(run)
                        session.commit()
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-recover-122",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(response.status_code, 200)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "working")
                    self.assertEqual(task_after["latest_run"]["github_pr_number"], 122)
                    self.assertNotIn("reconciliation incomplete", (task_after["latest_summary"] or "").lower())

    def test_workflow_run_invalid_orch_link_does_not_false_link_and_is_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            workflow_payload = {
                "action": "in_progress",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "workflow_run": {
                    "id": 77101,
                    "name": "CI",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/77101",
                    "pull_requests": [{"number": 122}],
                },
            }
            with patch(
                "orchestrator.app.tasks.inspect_pull_request",
                return_value=PullRequestInspection(
                    ok=True,
                    changed_files=1,
                    commits=1,
                    draft=False,
                    state="open",
                    merged=False,
                    summary="ok",
                    number=122,
                    node_id="PR_kw_122",
                    html_url="https://github.com/jeeves-jeevesenson/init-tracker/pull/122",
                    body="ORCH-LINK: task=149 issue=999 run=147",
                ),
            ):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            id=149,
                            github_repo="jeeves-jeevesenson/init-tracker",
                            github_issue_number=221,
                            title="Invalid ORCH-LINK should not recover",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            latest_summary="worker running",
                        )
                        session.add(task)
                        session.commit()
                        run = AgentRun(
                            id=147,
                            task_packet_id=task.id,
                            provider="github_copilot",
                            github_repo=task.github_repo,
                            github_issue_number=task.github_issue_number,
                            status="working",
                            last_summary="worker running",
                        )
                        session.add(run)
                        session.commit()
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-invalid-link-122",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(response.status_code, 202)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "working")
                    self.assertIsNone(task_after["latest_run"]["github_pr_number"])
                    self.assertIn("pr association pending (retryable)", (task_after["latest_summary"] or "").lower())

    def test_workflow_run_first_miss_without_orch_link_is_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            workflow_payload = {
                "action": "queued",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "workflow_run": {
                    "id": 77201,
                    "name": "CI",
                    "status": "queued",
                    "conclusion": None,
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/77201",
                    "pull_requests": [{"number": 7000}],
                },
            }
            with patch(
                "orchestrator.app.tasks.inspect_pull_request",
                return_value=PullRequestInspection(
                    ok=True,
                    changed_files=1,
                    commits=1,
                    draft=False,
                    state="open",
                    merged=False,
                    summary="ok",
                    number=7000,
                    node_id="PR_kw_7000",
                    html_url="https://github.com/jeeves-jeevesenson/init-tracker/pull/7000",
                    body="No linkage in this PR body",
                ),
            ):
                with TestClient(main.app) as client:
                    with Session(db.get_engine()) as session:
                        task = TaskPacket(
                            github_repo="jeeves-jeevesenson/init-tracker",
                            github_issue_number=321,
                            title="Workflow first miss retryable",
                            raw_body="body",
                            status="working",
                            approval_state="approved",
                            latest_summary="worker running",
                        )
                        session.add(task)
                        session.commit()
                        session.refresh(task)
                        run = AgentRun(
                            task_packet_id=task.id,
                            provider="github_copilot",
                            github_repo=task.github_repo,
                            github_issue_number=task.github_issue_number,
                            status="working",
                            last_summary="worker running",
                        )
                        session.add(run)
                        session.commit()
                    response = self._post_github(
                        client,
                        secret="test-gh-secret",
                        delivery="delivery-workflow-no-link-7000",
                        event="workflow_run",
                        payload=workflow_payload,
                    )
                    self.assertEqual(response.status_code, 202)
                    task_after = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task_after["status"], "working")
                    self.assertIn("pr association pending (retryable)", (task_after["latest_summary"] or "").lower())
                    self.assertNotIn("reconciliation incomplete", (task_after["latest_summary"] or "").lower())

    def test_workflow_run_existing_pr_link_still_processes_normally(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            workflow_payload = {
                "action": "in_progress",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "workflow_run": {
                    "id": 77301,
                    "name": "Copilot run",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/77301",
                    "pull_requests": [{"number": 6191}],
                },
            }
            with TestClient(main.app) as client:
                with Session(db.get_engine()) as session:
                    task = TaskPacket(
                        github_repo="jeeves-jeevesenson/init-tracker",
                        github_issue_number=619,
                        title="Existing linked run path",
                        raw_body="body",
                        status="working",
                        approval_state="approved",
                    )
                    session.add(task)
                    session.commit()
                    session.refresh(task)
                    run = AgentRun(
                        task_packet_id=task.id,
                        provider="github_copilot",
                        github_repo=task.github_repo,
                        github_issue_number=task.github_issue_number,
                        github_pr_number=6191,
                        status="working",
                        last_summary="worker running",
                    )
                    session.add(run)
                    session.commit()
                response = self._post_github(
                    client,
                    secret="test-gh-secret",
                    delivery="delivery-workflow-linked-619",
                    event="workflow_run",
                    payload=workflow_payload,
                )
                self.assertEqual(response.status_code, 200)
                task_data = client.get("/tasks").json()["tasks"][0]
                self.assertEqual(task_data["status"], "working")
                self.assertEqual(task_data["latest_run"]["github_pr_number"], 6191)

    def test_canceled_worker_session_is_not_successful_progress(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                with Session(db.get_engine()) as session:
                    task = TaskPacket(
                        github_repo="jeeves-jeevesenson/init-tracker",
                        github_issue_number=619,
                        title="Canceled worker session",
                        raw_body="body",
                        status="working",
                        approval_state="approved",
                    )
                    session.add(task)
                    session.commit()
                    session.refresh(task)
                    run = AgentRun(
                        task_packet_id=task.id,
                        provider="github_copilot",
                        github_repo=task.github_repo,
                        github_issue_number=task.github_issue_number,
                        github_pr_number=6191,
                        status="working",
                        last_summary="worker running",
                    )
                    session.add(run)
                    session.commit()

                workflow_payload = {
                    "action": "completed",
                    "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                    "workflow_run": {
                        "id": 61901,
                        "name": "Copilot run",
                        "status": "completed",
                        "conclusion": "cancelled",
                        "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/61901",
                        "pull_requests": [{"number": 6191}],
                    },
                }
                response = self._post_github(
                    client,
                    secret="test-gh-secret",
                    delivery="delivery-workflow-cancelled-619",
                    event="workflow_run",
                    payload=workflow_payload,
                )
                self.assertEqual(response.status_code, 200)
                task_data = client.get("/tasks").json()["tasks"][0]
                self.assertEqual(task_data["status"], "blocked")
                self.assertEqual(task_data["latest_run"]["status"], "blocked")


class OpenAIPlanningSchemaTests(unittest.TestCase):
    def test_internal_task_plan_schema_required_matches_properties(self):
        schema = openai_planning.INTERNAL_TASK_PLAN_SCHEMA
        self.assertEqual(set(schema["properties"].keys()), set(schema["required"]))
        openai_planning._validate_schema_required_keys(schema_name="internal_task_plan", schema=schema)

    def test_recommended_worker_is_nullable_required(self):
        schema = openai_planning.INTERNAL_TASK_PLAN_SCHEMA
        field_schema = schema["properties"]["recommended_worker"]
        self.assertIn("recommended_worker", schema["required"])
        self.assertEqual(field_schema["type"], ["string", "null"])
        self.assertIn(None, field_schema["enum"])

    def test_recommended_scope_class_is_nullable_required(self):
        schema = openai_planning.INTERNAL_TASK_PLAN_SCHEMA
        field_schema = schema["properties"]["recommended_scope_class"]
        self.assertIn("recommended_scope_class", schema["required"])
        self.assertEqual(field_schema["type"], ["string", "null"])
        self.assertIn(None, field_schema["enum"])

    def test_schema_validation_fails_clearly_when_property_missing_from_required(self):
        schema = json.loads(json.dumps(openai_planning.INTERNAL_TASK_PLAN_SCHEMA))
        schema["required"].remove("recommended_worker")
        with self.assertRaises(RuntimeError) as ctx:
            openai_planning._validate_schema_required_keys(schema_name="internal_task_plan", schema=schema)
        message = str(ctx.exception)
        self.assertIn("internal_task_plan", message)
        self.assertIn("missing from required", message)
        self.assertIn("recommended_worker", message)

    def test_plan_task_packet_accepts_nullable_required_internal_plan_fields(self):
        planning_response = Mock(
            output_parsed={
                "objective": "Harden planner schema",
                "scope": ["planner"],
                "non_goals": [],
                "acceptance_criteria": ["schema accepted"],
                "validation_guidance": ["python -m compileall orchestrator"],
                "implementation_brief": "fix structured output contract",
                "task_type": "bugfix",
                "difficulty": "small",
                "repo_areas": ["orchestrator/app/openai_planning.py"],
                "execution_risks": ["none"],
                "reviewer_focus": ["schema contract"],
                "recommended_scope_class": None,
                "recommended_worker": None,
                "internal_routing_metadata": None,
            }
        )
        worker_brief_response = Mock(
            output_parsed={
                "objective": "Implement planner schema hardening",
                "concise_scope": ["fix planner schema parity"],
                "implementation_brief": "keep worker brief stable",
                "acceptance_criteria": ["planner path succeeds"],
                "validation_commands": ["python -m unittest orchestrator.tests.test_milestone2"],
                "non_goals": ["no dispatcher redesign"],
                "target_branch": "main",
                "repo_grounded_hints": ["orchestrator/app/openai_planning.py"],
            }
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            settings = Settings()
        with patch("orchestrator.app.openai_planning.OpenAI") as mocked_openai:
            mocked_client = mocked_openai.return_value
            mocked_client.responses.create.side_effect = [planning_response, worker_brief_response]
            packet = openai_planning.plan_task_packet(
                settings=settings,
                repo="jeeves-jeevesenson/init-tracker",
                issue_number=999,
                issue_title="Planner schema fix",
                issue_body="Fix structured planner schema mismatch",
            )

        self.assertEqual(packet["internal_plan"]["recommended_worker"], None)
        self.assertEqual(packet["internal_plan"]["recommended_scope_class"], None)
        self.assertGreaterEqual(mocked_client.responses.create.call_count, 2)
        self.assertIn("program_plan", packet)

    def test_prompt_cache_key_generation_is_stable(self):
        first = openai_control_plane.build_prompt_cache_key(stage="planner", repo="Jeeves-Jeevesenson/init-tracker")
        second = openai_control_plane.build_prompt_cache_key(stage="planner", repo="jeeves-jeevesenson/init-tracker")
        third = openai_control_plane.build_prompt_cache_key(stage="worker_brief", repo="jeeves-jeevesenson/init-tracker")
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertTrue(first.startswith("orchestrator:planner:"))

    def test_model_selection_uses_flagship_and_helper_tiers(self):
        settings = Settings(
            OPENAI_FLAGSHIP_MODEL="gpt-flagship-test",
            OPENAI_HELPER_MODEL="gpt-helper-test",
        )
        planner_model, planner_tier = openai_control_plane.select_model_for_stage(
            settings=settings,
            stage="planner",
            fallback_model="fallback-model",
        )
        brief_model, brief_tier = openai_control_plane.select_model_for_stage(
            settings=settings,
            stage="worker_brief",
            fallback_model="fallback-model",
        )
        self.assertEqual(planner_model, "gpt-flagship-test")
        self.assertEqual(planner_tier, "flagship")
        self.assertEqual(brief_model, "gpt-helper-test")
        self.assertEqual(brief_tier, "helper")

    def test_plan_task_packet_wires_prompt_cache_and_response_chain(self):
        planning_response = Mock(
            id="resp_plan_1",
            output_parsed={
                "objective": "Harden planner controls",
                "scope": ["planner"],
                "non_goals": [],
                "acceptance_criteria": ["schema accepted"],
                "validation_guidance": ["python -m compileall orchestrator"],
                "implementation_brief": "structured output",
                "task_type": "feature",
                "difficulty": "small",
                "repo_areas": ["orchestrator/app/openai_planning.py"],
                "execution_risks": ["none"],
                "reviewer_focus": ["contract"],
                "recommended_scope_class": "narrow",
                "recommended_worker": "tracker-engineer",
                "internal_routing_metadata": None,
            },
        )
        worker_brief_response = Mock(
            id="resp_brief_1",
            output_parsed={
                "objective": "Implement planner controls",
                "concise_scope": ["cache + chaining"],
                "implementation_brief": "keep behavior",
                "acceptance_criteria": ["controls wired"],
                "validation_commands": ["python -m pytest orchestrator/tests/test_milestone2.py -q"],
                "non_goals": ["no workflow redesign"],
                "target_branch": "main",
                "repo_grounded_hints": ["orchestrator/app/openai_planning.py"],
            },
        )
        program_response = Mock(
            id="resp_program_1",
            output_parsed={
                "normalized_program_objective": "Improve OpenAI efficiency",
                "definition_of_done": ["controls enabled"],
                "non_goals": ["no auth refactor"],
                "milestones": [{"key": "M1", "title": "Controls", "goal": "Wire controls"}],
                "slices": [
                    {
                        "slice_number": 1,
                        "milestone_key": "M1",
                        "title": "Wire OpenAI controls",
                        "objective": "Add cache + chaining",
                        "acceptance_criteria": ["wired"],
                        "non_goals": ["none"],
                        "expected_file_zones": ["orchestrator/app"],
                        "continuation_hint": "",
                        "slice_type": "implementation",
                    }
                ],
                "current_slice_brief": "Add controls now",
                "acceptance_criteria": ["wired"],
                "risk_profile": ["low"],
                "recommended_worker": "tracker-engineer",
                "recommended_scope_class": "narrow",
                "continuation_hints": [],
            },
        )

        settings = Settings(
            OPENAI_API_KEY="test-key",
            OPENAI_ENABLE_PROMPT_CACHING="true",
            OPENAI_ENABLE_RESPONSE_CHAINING="true",
            OPENAI_FLAGSHIP_MODEL="gpt-flagship-test",
            OPENAI_HELPER_MODEL="gpt-helper-test",
        )
        with patch("orchestrator.app.openai_planning.OpenAI") as mocked_openai:
            mocked_client = mocked_openai.return_value
            mocked_client.responses.create.side_effect = [planning_response, worker_brief_response, program_response]
            packet = openai_planning.plan_task_packet(
                settings=settings,
                repo="jeeves-jeevesenson/init-tracker",
                issue_number=999,
                issue_title="OpenAI controls",
                issue_body="Add cache/chaining",
                previous_response_id="resp_prev_123",
            )

        first_call = mocked_client.responses.create.call_args_list[0].kwargs
        second_call = mocked_client.responses.create.call_args_list[1].kwargs
        self.assertEqual(first_call.get("previous_response_id"), "resp_prev_123")
        self.assertIn("prompt_cache_key", first_call)
        self.assertIn("planner", first_call.get("prompt_cache_key", ""))
        self.assertEqual(second_call.get("previous_response_id"), "resp_plan_1")
        self.assertIn("worker_brief", second_call.get("prompt_cache_key", ""))
        self.assertEqual(packet["planning_meta"]["openai_last_response_id"], "resp_program_1")

    def test_review_structured_output_validation_rejects_invalid_decision(self):
        bad_response = Mock(
            id="resp_bad_review",
            output_parsed={
                "decision": "ship_it_now",
                "status": "met",
                "confidence": 0.9,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "merge_ready",
                "revision_instructions": [],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": ["ok"],
            },
        )
        settings = Settings(OPENAI_API_KEY="test-key")
        with patch("orchestrator.app.openai_review.OpenAI") as mocked_openai:
            mocked_client = mocked_openai.return_value
            mocked_client.responses.create.return_value = bad_response
            with self.assertRaises(RuntimeError):
                openai_review.summarize_work_update(
                    settings=settings,
                    update_context=json.dumps({"repo": "jeeves-jeevesenson/init-tracker", "event": "pull_request"}),
                    previous_response_id="resp_prev",
                )

    def test_post_dispatch_pr_discovery_links_and_upgrades_worker_state(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()
            def _post_local(client: TestClient, delivery: str, event: str, payload: dict):
                body = json.dumps(payload).encode("utf-8")
                signature = "sha256=" + hmac.new(b"test-gh-secret", body, hashlib.sha256).hexdigest()
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
            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 501, "node_id": "I_501", "title": "Deadlock fix", "body": "Fix deadlock", "labels": [{"name": "agent:task"}]},
            }
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 501}, "comment": {"body": "/approve"}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=([{"number": 701, "title": "Fixes #501", "body": "done", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/701", "node_id": "PR_kw_test", "draft": True, "state": "open", "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": "copilot-swe-agent"}, "head": {"ref": "copilot/fix-501"}}], "ok")), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review", return_value=(True, "ok")) as mocked_ready, \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=Mock(ok=True, draft=False)), \
                 patch("orchestrator.app.tasks.notify_discord"), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "wait", "summary": ["ok"], "revision_requests": [], "escalation_reason": ""}}):
                with TestClient(main.app) as client:
                    _post_local(client, "task-501-open", "issues", issue_payload)
                    _post_local(client, "task-501-approve", "issue_comment", approve_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["github_pr_number"], 701)
                    self.assertEqual(task["latest_run"]["github_pr_url"], "https://github.com/jeeves-jeevesenson/init-tracker/pull/701")
                    self.assertEqual(task["latest_run"]["github_pr_node_id"], "PR_kw_test")
                    mocked_ready.assert_called_once_with(
                        settings=ANY,
                        repo="jeeves-jeevesenson/init-tracker",
                        pr_number=701,
                    )

    def test_post_dispatch_pr_discovery_ambiguous_candidates_keeps_awaiting_with_reason(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()
            def _post_local(client: TestClient, delivery: str, event: str, payload: dict):
                body = json.dumps(payload).encode("utf-8")
                signature = "sha256=" + hmac.new(b"test-gh-secret", body, hashlib.sha256).hexdigest()
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
            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 502, "node_id": "I_502", "title": "Deadlock fix", "body": "Fix deadlock", "labels": [{"name": "agent:task"}]},
            }
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 502}, "comment": {"body": "/approve"}}
            candidates = [
                {"number": 702, "title": "Fixes #502", "body": "a", "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": "copilot-swe-agent"}, "head": {"ref": "copilot/fix-502"}},
                {"number": 703, "title": "Fixes #502", "body": "b", "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": "copilot-swe-agent"}, "head": {"ref": "copilot/fix-502-b"}},
            ]
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")), \
                 patch("orchestrator.app.tasks._log_workflow_checkpoint") as mocked_log, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    _post_local(client, "task-502-open", "issues", issue_payload)
                    _post_local(client, "task-502-approve", "issue_comment", approve_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertIsNone(task["latest_run"]["github_pr_number"])
                self.assertTrue(
                    any(
                        call.kwargs.get("event") == "pr_discovery_linkage_skipped"
                        and call.kwargs.get("skip_reason") == "candidate_prs_ambiguous"
                        for call in mocked_log.call_args_list
                    )
                )

    def test_post_dispatch_pr_discovery_no_candidates_logs_explicit_reason(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()
            def _post_local(client: TestClient, delivery: str, event: str, payload: dict):
                body = json.dumps(payload).encode("utf-8")
                signature = "sha256=" + hmac.new(b"test-gh-secret", body, hashlib.sha256).hexdigest()
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
            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 503, "node_id": "I_503", "title": "Deadlock fix", "body": "Fix deadlock", "labels": [{"name": "agent:task"}]},
            }
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 503}, "comment": {"body": "/approve"}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=([], "none")), \
                 patch("orchestrator.app.tasks._log_workflow_checkpoint") as mocked_log, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    _post_local(client, "task-503-open", "issues", issue_payload)
                    _post_local(client, "task-503-approve", "issue_comment", approve_payload)
                self.assertTrue(
                    any(
                        call.kwargs.get("event") == "pr_discovery_linkage_skipped"
                        and call.kwargs.get("skip_reason") == "no_recent_pr_candidates"
                        for call in mocked_log.call_args_list
                    )
                )

    def test_post_dispatch_pr_discovery_skips_copilot_branch_without_issue_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            def _post_local(client: TestClient, delivery: str, event: str, payload: dict):
                body = json.dumps(payload).encode("utf-8")
                signature = "sha256=" + hmac.new(b"test-gh-secret", body, hashlib.sha256).hexdigest()
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

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 503, "node_id": "I_503", "title": "Deadlock fix", "body": "Fix deadlock", "labels": [{"name": "agent:task"}]},
            }
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 503}, "comment": {"body": "/approve"}}
            candidates = [
                {
                    "number": 705,
                    "title": "Cleanup CI workflow",
                    "body": "does not reference task",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "user": {"login": "copilot-swe-agent"},
                    "head": {"ref": "copilot/fix-deadlock"},
                }
            ]
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")), \
                 patch("orchestrator.app.tasks._log_workflow_checkpoint") as mocked_log, \
                 patch("orchestrator.app.tasks.notify_discord"):
                with TestClient(main.app) as client:
                    _post_local(client, "task-503b-open", "issues", issue_payload)
                    _post_local(client, "task-503b-approve", "issue_comment", approve_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "awaiting_worker_start")
                    self.assertIsNone(task["latest_run"]["github_pr_number"])
                self.assertTrue(
                    any(
                        call.kwargs.get("event") == "pr_discovery_linkage_skipped"
                        and call.kwargs.get("skip_reason") == "linkage_tag_missing_in_candidate_prs"
                        for call in mocked_log.call_args_list
                    )
                )

    def test_post_dispatch_pr_discovery_links_from_branch_issue_token(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, _ = _reload_orchestrator_modules()

            def _post_local(client: TestClient, delivery: str, event: str, payload: dict):
                body = json.dumps(payload).encode("utf-8")
                signature = "sha256=" + hmac.new(b"test-gh-secret", body, hashlib.sha256).hexdigest()
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

            issue_payload = {
                "action": "opened",
                "repository": {"full_name": "jeeves-jeevesenson/init-tracker"},
                "issue": {"number": 504, "node_id": "I_504", "title": "Deadlock fix", "body": "Fix deadlock", "labels": [{"name": "agent:task"}]},
            }
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 504}, "comment": {"body": "/approve"}}
            candidates = [
                {
                    "number": 706,
                    "title": "Threading cleanup",
                    "body": "done",
                    "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/706",
                    "node_id": "PR_kw_test_706",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "user": {"login": "copilot-swe-agent"},
                    "head": {"ref": "copilot/fix-504"},
                }
            ]
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "x", "scope": [], "non_goals": [], "acceptance_criteria": [], "validation_guidance": [], "implementation_brief": "x"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.list_recent_pull_requests", return_value=(candidates, "ok")), \
                 patch("orchestrator.app.tasks.mark_pr_ready_for_review", return_value=(True, "ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=Mock(ok=True, draft=False)), \
                 patch("orchestrator.app.tasks.notify_discord"), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "wait", "summary": ["ok"], "revision_requests": [], "escalation_reason": ""}}):
                with TestClient(main.app) as client:
                    _post_local(client, "task-504-open", "issues", issue_payload)
                    _post_local(client, "task-504-approve", "issue_comment", approve_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["status"], "pr_opened")
                    self.assertEqual(task["latest_run"]["github_pr_number"], 706)
                    self.assertEqual(task["latest_run"]["github_pr_url"], "https://github.com/jeeves-jeevesenson/init-tracker/pull/706")
                    self.assertEqual(task["latest_run"]["github_pr_node_id"], "PR_kw_test_706")

    def test_final_merge_audit_docs_only_auto_merges_without_human_escalation(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 880, "node_id": "I_880", "title": "Docs polish", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 880}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 88001, "number": 8801, "title": "Docs for #880", "body": "Closes #880", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8801", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean"}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 88002, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/88002", "pull_requests": [{"number": 8801}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 3, "deletions": 1, "patch": "+updated docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.97, "doc_only": True, "safe_to_merge": True, "requires_followup": False, "summary": ["Docs-only and safe."], "findings": [], "merge_rationale": "Safe docs update.", "escalation_reason": "", "review_scope": ["patch"]}, "openai_meta": {"response_id": "resp_audit_880"}}), \
                 patch("orchestrator.app.tasks.submit_approving_review", return_value=(True, "approved")) as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")) as mocked_merge:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-880-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-880-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-880-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-880-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertEqual(state.get("final_audit_decision"), "approve_and_merge")
                    self.assertNotEqual(state.get("last_governor_decision"), "escalate_human")
                    mocked_approve.assert_called()
                    mocked_merge.assert_called()

    def test_final_merge_audit_request_revision_stays_recoverable(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 881, "node_id": "I_881", "title": "Code update", "body": "code", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 881}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 88101, "number": 8811, "title": "Code for #881", "body": "Closes #881", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8811", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean"}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 88102, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/88102", "pull_requests": [{"number": 8811}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Code", "scope": ["code"], "non_goals": [], "acceptance_criteria": ["code"], "validation_guidance": [], "implementation_brief": "code"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "orchestrator/app/tasks.py", "status": "modified", "additions": 4, "deletions": 1, "patch": "+code"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.post_copilot_follow_up_comment", return_value=(True, "posted")) as mocked_comment, \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "request_revision", "confidence": 0.8, "doc_only": False, "safe_to_merge": False, "requires_followup": True, "summary": ["Need one revision"], "findings": [{"severity": "medium", "path": "orchestrator/app/tasks.py", "summary": "Edge case", "suggested_fix": "Handle edge case"}], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-881-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-881-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-881-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-881-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertEqual(state.get("last_governor_decision"), "request_revision")
                    self.assertGreaterEqual(int(state.get("revision_cycle_count") or 0), 1)
                    mocked_comment.assert_called()

    def test_guarded_paths_still_escalate_even_if_merge_audit_approves(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            os.environ["GOVERNOR_GUARDED_PATHS"] = "orchestrator/app/*"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 882, "node_id": "I_882", "title": "Guarded", "body": "guarded", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 882}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 88201, "number": 8821, "title": "Guarded for #882", "body": "Closes #882", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8821", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean"}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 88202, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/88202", "pull_requests": [{"number": 8821}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Guarded", "scope": ["guarded"], "non_goals": [], "acceptance_criteria": ["guarded"], "validation_guidance": [], "implementation_brief": "guarded"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "orchestrator/app/tasks.py", "status": "modified", "additions": 3, "deletions": 0, "patch": "+guarded"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.9, "doc_only": False, "safe_to_merge": True, "requires_followup": False, "summary": ["ok"], "findings": [], "merge_rationale": "ok", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-882-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-882-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-882-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-882-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["latest_run"]["governor_state"]["last_governor_decision"], "escalate_human")

    def test_merge_audit_invalid_output_falls_back_without_blind_merge(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 883, "node_id": "I_883", "title": "Fallback", "body": "fallback", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 883}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 88301, "number": 8831, "title": "Fallback for #883", "body": "Closes #883", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8831", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean"}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 88302, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/88302", "pull_requests": [{"number": 8831}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Fallback", "scope": ["fallback"], "non_goals": [], "acceptance_criteria": ["fallback"], "validation_guidance": [], "implementation_brief": "fallback"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/readme.md", "status": "modified", "additions": 3, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.9, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["invalid"], "findings": [], "merge_rationale": "", "escalation_reason": "invalid", "review_scope": ["fallback"]}}), \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")) as mocked_merge:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-883-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-883-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-883-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-883-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["latest_run"]["governor_state"]["last_governor_decision"], "wait")
                    mocked_merge.assert_not_called()

    def test_merge_audit_approve_escalates_when_merge_auth_missing(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ.pop("GITHUB_DISPATCH_USER_TOKEN", None)
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 884, "node_id": "I_884", "title": "Auth missing", "body": "auth", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 884}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 88401, "number": 8841, "title": "Auth for #884", "body": "Closes #884", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8841", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean"}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 88402, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/88402", "pull_requests": [{"number": 8841}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Auth", "scope": ["auth"], "non_goals": [], "acceptance_criteria": ["auth"], "validation_guidance": [], "implementation_brief": "auth"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/readme.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+auth"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.9, "doc_only": True, "safe_to_merge": True, "requires_followup": False, "summary": ["ok"], "findings": [], "merge_rationale": "ok", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-884-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-884-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-884-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-884-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertEqual(state.get("last_governor_decision"), "escalate_human")

    def test_workflow_checks_success_sticks_for_later_pull_request_events(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 890, "node_id": "I_890", "title": "Docs sticky checks", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 890}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89001, "number": 8901, "title": "Docs for #890", "body": "Closes #890", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8901", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-sticky-890"}}}
            pr_edited_payload = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89001, "number": 8901, "title": "Docs for #890", "body": "Closes #890", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8901", "updated_at": "2026-01-01T00:10:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-sticky-890"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 89002, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-sticky-890", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/89002", "pull_requests": [{"number": 8901}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 2, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_governor_update", return_value={"governor_artifact": {"decision": "escalate_human", "summary": ["fallback"], "revision_requests": [], "escalation_reason": "fallback"}}) as mocked_governor, \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "wait", "confidence": 0.8, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["need another pass"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}) as mocked_merge_audit:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-890-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-890-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-890-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-890-wf", event="workflow_run", payload=workflow_payload)
                    governor_calls_after_workflow = mocked_governor.call_count
                    _post_github_local(client, secret="test-gh-secret", delivery="d-890-pr-edited", event="pull_request", payload=pr_edited_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertTrue(state.get("effective_checks_passed"))
                    self.assertEqual(state.get("last_successful_checks_head_sha"), "sha-sticky-890")
                    self.assertEqual(mocked_governor.call_count, governor_calls_after_workflow)
                    self.assertGreaterEqual(mocked_merge_audit.call_count, 2)
                    self.assertNotEqual(state.get("last_governor_decision"), "escalate_human")

    def test_stale_partial_final_audit_is_rerun_and_can_merge(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 891, "node_id": "I_891", "title": "Docs stale audit", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 891}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89101, "number": 8911, "title": "Docs for #891", "body": "Closes #891", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8911", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-stale-891"}}}
            pr_edited_payload = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89101, "number": 8911, "title": "Docs for #891", "body": "Closes #891", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8911", "updated_at": "2026-01-01T00:10:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-stale-891"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 89102, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-stale-891", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/89102", "pull_requests": [{"number": 8911}]}}
            stale_then_approve = [
                {"merge_audit_artifact": {"decision": "wait", "confidence": 0.4, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["partial evidence"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}},
                {"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.95, "doc_only": True, "safe_to_merge": True, "requires_followup": False, "summary": ["evidence complete"], "findings": [], "merge_rationale": "ready", "escalation_reason": "", "review_scope": ["patch"]}},
            ]
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 4, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", side_effect=stale_then_approve) as mocked_merge_audit, \
                 patch("orchestrator.app.tasks.submit_approving_review", return_value=(True, "approved")) as mocked_approve, \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")) as mocked_merge:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-891-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-891-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-891-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-891-wf", event="workflow_run", payload=workflow_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-891-pr-edited", event="pull_request", payload=pr_edited_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertGreaterEqual(mocked_merge_audit.call_count, 2)
                    self.assertEqual(state.get("final_audit_decision"), "approve_and_merge")
                    self.assertNotEqual(state.get("last_governor_decision"), "escalate_human")
                    mocked_approve.assert_called()
                    mocked_merge.assert_called()

    def test_docs_only_merge_audit_context_marks_truncated_or_missing_patch_safely(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 892, "node_id": "I_892", "title": "Docs truncation", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 892}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89201, "number": 8921, "title": "Docs for #892", "body": "Closes #892", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8921", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-docs-892"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 89202, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-docs-892", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/89202", "pull_requests": [{"number": 8921}]}}

            def _safe_wait_on_truncated_payload(*, settings, update_context, previous_response_id=None):
                context = json.loads(update_context)
                file_summary = context.get("file_detail_summary") or {}
                self.assertTrue(
                    int(file_summary.get("truncated_patch_count") or 0) > 0
                    or not bool(file_summary.get("all_patches_present"))
                )
                return {
                    "merge_audit_artifact": {
                        "decision": "wait",
                        "confidence": 0.3,
                        "doc_only": True,
                        "safe_to_merge": False,
                        "requires_followup": True,
                        "summary": ["Patch evidence insufficient."],
                        "findings": [],
                        "merge_rationale": "",
                        "escalation_reason": "",
                        "review_scope": ["patch"],
                    }
                }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 5000, "deletions": 0, "patch": "+" + ("long-doc-line " * 300)}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", side_effect=_safe_wait_on_truncated_payload), \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")) as mocked_merge:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-892-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-892-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-892-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-892-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    state = task["latest_run"]["governor_state"]
                    self.assertEqual(state.get("last_governor_decision"), "wait")
                    mocked_merge.assert_not_called()

    def test_guarded_paths_escalate_even_with_sticky_checks_and_audit_approval(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            os.environ["GOVERNOR_GUARDED_PATHS"] = "orchestrator/app/*"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 893, "node_id": "I_893", "title": "Guard sticky", "body": "guarded", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 893}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 89301, "number": 8931, "title": "Guarded for #893", "body": "Closes #893", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/8931", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-guard-893"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 89302, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-guard-893", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/89302", "pull_requests": [{"number": 8931}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Guarded", "scope": ["guarded"], "non_goals": [], "acceptance_criteria": ["guarded"], "validation_guidance": [], "implementation_brief": "guarded"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "orchestrator/app/tasks.py", "status": "modified", "additions": 2, "deletions": 0, "patch": "+guarded"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.95, "doc_only": False, "safe_to_merge": True, "requires_followup": False, "summary": ["approve"], "findings": [], "merge_rationale": "ok", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-893-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-893-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-893-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-893-wf", event="workflow_run", payload=workflow_payload)
                    task = client.get("/tasks").json()["tasks"][0]
                    self.assertEqual(task["latest_run"]["governor_state"]["last_governor_decision"], "escalate_human")

    def test_workflow_run_persists_pr_linked_head_sha_when_workflow_head_differs(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 930, "node_id": "I_930", "title": "workflow sha", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 930}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93001, "number": 9301, "title": "Docs", "body": "Closes #930", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9301", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "abc123"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93002, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "wrong-sha", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93002", "pull_requests": [{"number": 9301, "head": {"sha": "abc123"}}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "wait", "confidence": 0.6, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["pending"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-930-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-930-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-930-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-930-wf", event="workflow_run", payload=workflow_payload)
                    state = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertEqual(state.get("last_successful_checks_head_sha"), "abc123")

    def test_effective_checks_passed_uses_persisted_sha_and_new_head_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 931, "node_id": "I_931", "title": "sticky invalidation", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 931}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93101, "number": 9311, "title": "Docs", "body": "Closes #931", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9311", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "abc123"}}}
            pr_edited_same = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93101, "number": 9311, "title": "Docs", "body": "Closes #931", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9311", "updated_at": "2026-01-01T00:05:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "abc123"}}}
            pr_edited_new = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93101, "number": 9311, "title": "Docs", "body": "Closes #931", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9311", "updated_at": "2026-01-01T00:10:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "newsha"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93102, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93102", "pull_requests": [{"number": 9311, "head": {"sha": "abc123"}}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "wait", "confidence": 0.5, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["hold"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-wf", event="workflow_run", payload=workflow_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-pr-same", event="pull_request", payload=pr_edited_same)
                    state = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertTrue(state.get("effective_checks_passed"))
                    _post_github_local(client, secret="test-gh-secret", delivery="d-931-pr-new", event="pull_request", payload=pr_edited_new)
                    state_after_new = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertFalse(state_after_new.get("effective_checks_passed"))

    def test_merge_audit_idempotence_reuses_prior_for_identical_state(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 932, "node_id": "I_932", "title": "idempotence", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 932}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93201, "number": 9321, "title": "Docs", "body": "Closes #932", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9321", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-idem"}}}
            pr_edited_payload = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93201, "number": 9321, "title": "Docs", "body": "Closes #932", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9321", "updated_at": "2026-01-01T00:10:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-idem"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93202, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93202", "pull_requests": [{"number": 9321, "head": {"sha": "sha-idem"}}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([{"filename": "docs/guide.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+docs"}], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "wait", "confidence": 0.6, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["pending"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}) as mocked_merge_audit:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-wf", event="workflow_run", payload=workflow_payload)
                    calls_after_first_eligible = mocked_merge_audit.call_count
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-pr-edit-1", event="pull_request", payload=pr_edited_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-932-pr-edit-2", event="pull_request", payload=pr_edited_payload)
                    self.assertEqual(mocked_merge_audit.call_count, calls_after_first_eligible)

    def test_list_pull_request_file_details_paginates_and_preserves_patch(self):
        settings = Settings(github_api_token="dummy-token")
        page_one = Mock()
        page_one.status_code = 200
        page_one.headers = {
            "content-type": "application/json",
            "link": '<https://api.github.com/repos/jeeves-jeevesenson/init-tracker/pulls/77/files?per_page=100&page=2>; rel="next"',
        }
        page_one.json.return_value = [
            {"filename": "docs/guide.md", "status": "modified", "additions": 2, "deletions": 1, "patch": "@@ -1 +1 @@\n-old\n+new"}
        ]
        page_two = Mock()
        page_two.status_code = 200
        page_two.headers = {"content-type": "application/json"}
        page_two.json.return_value = []
        mock_client = Mock()
        mock_client.get.side_effect = [page_one, page_two]
        mock_httpx = Mock()
        mock_httpx.__enter__ = Mock(return_value=mock_client)
        mock_httpx.__exit__ = Mock(return_value=None)
        with patch("orchestrator.app.github_dispatch.has_governor_auth", return_value=True), patch(
            "orchestrator.app.github_dispatch.httpx.Client",
            return_value=mock_httpx,
        ):
            details, message = list_pull_request_file_details(
                settings=settings,
                repo="jeeves-jeevesenson/init-tracker",
                pr_number=77,
            )
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["filename"], "docs/guide.md")
        self.assertIn("+new", details[0]["patch"])
        self.assertIn("across 2 page(s)", message)

    def test_merge_audit_uses_patch_fallback_when_file_details_are_empty(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 933, "node_id": "I_933", "title": "Docs fallback", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 933}, "comment": {"body": "/approve"}}
            pr_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93301, "number": 9331, "title": "Docs for #933", "body": "Closes #933", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9331", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-933"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93302, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-933", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93302", "pull_requests": [{"number": 9331}]}}

            def _assert_patch_fallback(*, settings, update_context, previous_response_id=None):
                payload = json.loads(update_context)
                self.assertTrue(payload.get("file_detail_summary", {}).get("patch_fallback_used"))
                self.assertTrue(payload.get("file_details"))
                self.assertIn("docs/guide.md", [item.get("filename") for item in payload.get("file_details", [])])
                return {
                    "merge_audit_artifact": {
                        "decision": "wait",
                        "confidence": 0.6,
                        "doc_only": True,
                        "safe_to_merge": False,
                        "requires_followup": True,
                        "summary": ["patch fallback evidence used"],
                        "findings": [],
                        "merge_rationale": "",
                        "escalation_reason": "",
                        "review_scope": ["patch"],
                    }
                }

            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([], "empty details")), \
                 patch("orchestrator.app.tasks.fetch_pull_request_patch", return_value=("diff --git a/docs/guide.md b/docs/guide.md\n--- a/docs/guide.md\n+++ b/docs/guide.md\n@@ -1 +1 @@\n-old\n+new\n", "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", side_effect=_assert_patch_fallback) as mocked_merge_audit:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-933-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-933-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-933-pr", event="pull_request", payload=pr_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-933-wf", event="workflow_run", payload=workflow_payload)
                    state = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertEqual(mocked_merge_audit.call_count, 1)
                    self.assertTrue(state.get("final_audit_patch_fallback_used"))

    def test_no_evidence_audit_not_reused_once_evidence_appears(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 934, "node_id": "I_934", "title": "Docs evidence", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 934}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93401, "number": 9341, "title": "Docs", "body": "Closes #934", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9341", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-934"}}}
            pr_edit_payload = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93401, "number": 9341, "title": "Docs", "body": "Closes #934", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9341", "updated_at": "2026-01-01T00:05:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-934"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93402, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-934", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93402", "pull_requests": [{"number": 9341}]}}
            file_detail_side_effect = [
                ([], "empty"),
                ([{"filename": "docs/guide.md", "status": "modified", "additions": 1, "deletions": 0, "patch": "+docs"}], "ok"),
            ]
            merge_audit_results = [
                {"merge_audit_artifact": {"decision": "wait", "confidence": 0.2, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["missing evidence"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}},
                {"merge_audit_artifact": {"decision": "approve_and_merge", "confidence": 0.95, "doc_only": True, "safe_to_merge": True, "requires_followup": False, "summary": ["evidence available"], "findings": [], "merge_rationale": "ready", "escalation_reason": "", "review_scope": ["patch"]}},
            ]
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", side_effect=file_detail_side_effect), \
                 patch("orchestrator.app.tasks.fetch_pull_request_patch", return_value=("", "no patch")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", side_effect=merge_audit_results) as mocked_merge_audit, \
                 patch("orchestrator.app.tasks.submit_approving_review", return_value=(True, "approved")), \
                 patch("orchestrator.app.tasks.merge_pr", return_value=(True, "merged")):
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-934-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-934-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-934-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-934-wf", event="workflow_run", payload=workflow_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-934-pr-edit", event="pull_request", payload=pr_edit_payload)
                    self.assertEqual(mocked_merge_audit.call_count, 2)
                    state = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertEqual(state.get("final_audit_decision"), "approve_and_merge")
                    self.assertFalse(state.get("final_audit_evidence_missing"))

    def test_zero_progress_no_evidence_churn_does_not_repeat_merge_audit(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-token"
            main, _ = _reload_orchestrator_modules()
            issue_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 935, "node_id": "I_935", "title": "No evidence churn", "body": "docs", "labels": [{"name": "agent:task"}]}}
            approve_payload = {"action": "created", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "issue": {"number": 935}, "comment": {"body": "/approve"}}
            pr_open_payload = {"action": "opened", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93501, "number": 9351, "title": "Docs", "body": "Closes #935", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9351", "updated_at": "2026-01-01T00:00:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-935"}}}
            pr_edit_payload = {"action": "edited", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "pull_request": {"id": 93501, "number": 9351, "title": "Docs", "body": "Closes #935", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/pull/9351", "updated_at": "2026-01-01T00:10:00Z", "draft": False, "mergeable": True, "mergeable_state": "clean", "head": {"sha": "sha-935"}}}
            workflow_payload = {"action": "completed", "repository": {"full_name": "jeeves-jeevesenson/init-tracker"}, "workflow_run": {"id": 93502, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "sha-935", "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/actions/runs/93502", "pull_requests": [{"number": 9351}]}}
            with patch("orchestrator.app.tasks.plan_task_packet", return_value={"objective": "Docs", "scope": ["docs"], "non_goals": [], "acceptance_criteria": ["docs"], "validation_guidance": [], "implementation_brief": "docs"}), \
                 patch("orchestrator.app.tasks.dispatch_task_to_github_copilot", return_value=DispatchResult(attempted=True, accepted=True, manual_required=False, state="accepted", summary="ok")), \
                 patch("orchestrator.app.tasks.inspect_pull_request", return_value=PullRequestInspection(ok=True, changed_files=1, commits=1, draft=False, state="open", merged=False, mergeable=True, mergeable_state="clean", summary="ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_file_details", return_value=([], "empty")), \
                 patch("orchestrator.app.tasks.fetch_pull_request_patch", return_value=("", "no patch")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.summarize_merge_audit", return_value={"merge_audit_artifact": {"decision": "wait", "confidence": 0.2, "doc_only": True, "safe_to_merge": False, "requires_followup": True, "summary": ["missing evidence"], "findings": [], "merge_rationale": "", "escalation_reason": "", "review_scope": ["patch"]}}) as mocked_merge_audit:
                with TestClient(main.app) as client:
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-open", event="issues", payload=issue_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-approve", event="issue_comment", payload=approve_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-pr-open", event="pull_request", payload=pr_open_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-wf", event="workflow_run", payload=workflow_payload)
                    first_count = mocked_merge_audit.call_count
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-pr-edit-1", event="pull_request", payload=pr_edit_payload)
                    _post_github_local(client, secret="test-gh-secret", delivery="d-935-pr-edit-2", event="pull_request", payload=pr_edit_payload)
                    self.assertEqual(mocked_merge_audit.call_count, first_count)
                    state = client.get("/tasks").json()["tasks"][0]["latest_run"]["governor_state"]
                    self.assertTrue(state.get("final_audit_evidence_missing"))
                    self.assertEqual(state.get("last_governor_decision"), "wait")


if __name__ == "__main__":
    unittest.main()
