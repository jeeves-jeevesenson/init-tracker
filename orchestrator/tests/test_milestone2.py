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
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.requests import ClientDisconnect

from orchestrator.app.config import Settings
from orchestrator.app.copilot_identity import DOCUMENTED_COPILOT_ASSIGNEE_LOGIN
from orchestrator.app.github_dispatch import DispatchResult, dispatch_task_to_github_copilot
from orchestrator.app.models import AgentRun, TaskPacket
from orchestrator.app import openai_planning
from orchestrator.app.tasks import CUSTOM_AGENT_INITIATIVE_SMITH, CUSTOM_AGENT_TRACKER_ENGINEER


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


class OrchestratorMilestone2Tests(unittest.TestCase):
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

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertTrue(result.accepted)
            comment_payload = mocked_client.post.call_args_list[2].kwargs["json"]
            body = comment_payload["body"]
            self.assertNotIn("recommended_worker", body)
            self.assertNotIn("selected_custom_agent", body)
            self.assertNotIn("Initiative Smith", body)
            self.assertIn('"execution_mode": "plain_copilot_fallback"', body)

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
                    self.assertEqual(task["status"], "blocked")
                    self.assertIsNone(task["latest_run"]["github_pr_number"])
                    self.assertIn("reconciliation incomplete", task["latest_summary"].lower())

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


if __name__ == "__main__":
    unittest.main()
