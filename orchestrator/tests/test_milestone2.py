from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from orchestrator.app.config import Settings
from orchestrator.app.github_dispatch import DispatchResult, dispatch_task_to_github_copilot
from orchestrator.app.models import AgentRun, TaskPacket


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
        "COPILOT_MODEL",
        "OPENAI_PLANNING_MODEL",
        "OPENAI_REVIEW_MODEL",
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
            ) as mocked_dispatch:
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

                self.assertEqual(mocked_dispatch.call_count, 1)

                with Session(db.get_engine()) as session:
                    run_count = len(list(session.exec(select(AgentRun)).all()))
                    self.assertEqual(run_count, 1)

    def test_dispatch_request_payload_uses_agent_assignment_fields(self):
        settings = Settings(
            github_api_token="token",
            github_api_url="https://api.github.com",
            copilot_dispatch_assignee="copilot-swe-agent",
            copilot_target_branch="main",
            copilot_target_repo="jeeves-jeevesenson/init-tracker",
            copilot_custom_instructions="Follow repo workflow.",
            copilot_custom_agent="Initiative Smith",
            copilot_model="gpt-4.1-mini",
        )
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
            assign_response = Mock(
                status_code=201,
                headers={"content-type": "application/json"},
            )
            assign_response.json.return_value = {
                "id": 9001,
                "html_url": "https://github.com/jeeves-jeevesenson/init-tracker/issues/126",
                "assignees": [{"login": "copilot-swe-agent"}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")
            mocked_client.post.side_effect = [assign_response, comment_response]

            result = dispatch_task_to_github_copilot(settings=settings, task=task)
            self.assertTrue(result.accepted)
            self.assertFalse(result.manual_required)

            first_call = mocked_client.post.call_args_list[0]
            self.assertEqual(
                first_call.args[0],
                "https://api.github.com/repos/jeeves-jeevesenson/init-tracker/issues/126/assignees",
            )
            payload = first_call.kwargs["json"]
            self.assertEqual(payload["assignees"], ["copilot-swe-agent"])
            self.assertEqual(payload["agent_assignment"]["target_repo"], "jeeves-jeevesenson/init-tracker")
            self.assertEqual(payload["agent_assignment"]["base_branch"], "main")
            self.assertEqual(payload["agent_assignment"]["custom_instructions"], "Follow repo workflow.")
            self.assertEqual(payload["agent_assignment"]["custom_agent"], "Initiative Smith")
            self.assertEqual(payload["agent_assignment"]["model"], "gpt-4.1-mini")

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
                    self.assertEqual(task["status"], "working")
                    self.assertEqual(task["latest_run"]["status"], "working")

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


if __name__ == "__main__":
    unittest.main()
