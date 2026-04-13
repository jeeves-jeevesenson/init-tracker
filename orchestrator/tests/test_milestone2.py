from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from orchestrator.app.github_dispatch import DispatchResult
from orchestrator.app.models import AgentRun


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
                    success=True,
                    manual_required=False,
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
                    self.assertEqual(task["status"], "dispatched")
                    self.assertEqual(task["approval_state"], "approved")
                    self.assertEqual(task["latest_run"]["status"], "dispatched")

                self.assertEqual(mocked_dispatch.call_count, 1)

                with Session(db.get_engine()) as session:
                    run_count = len(list(session.exec(select(AgentRun)).all()))
                    self.assertEqual(run_count, 1)

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
