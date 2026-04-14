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


def _reload_orchestrator_modules():
    config = importlib.import_module("orchestrator.app.config")
    db = importlib.import_module("orchestrator.app.db")
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    importlib.reload(config)
    importlib.reload(db)
    github = importlib.import_module("orchestrator.app.github_webhooks")
    openai = importlib.import_module("orchestrator.app.openai_webhooks")
    main = importlib.import_module("orchestrator.app.main")
    importlib.reload(github)
    importlib.reload(openai)
    importlib.reload(main)
    return main


class OrchestratorMilestone1Tests(unittest.TestCase):
    ENV_KEYS = {
        "ORCHESTRATOR_ENV_FILE",
        "DATABASE_URL",
        "GH_WEBHOOK_SECRET",
        "OPENAI_WEBHOOK_SECRET",
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_URL",
        "ORCHESTRATOR_SECRET_KEY",
        "GITHUB_API_TOKEN",
        "GITHUB_DISPATCH_USER_TOKEN",
        "GITHUB_AUTH_MODE",
        "GITHUB_GOVERNOR_AUTH_MODE",
        "GITHUB_APP_CLIENT_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_PRIVATE_KEY_PATH",
        "GITHUB_API_URL",
        "DEFAULT_REPO_OWNER",
        "DEFAULT_REPO_NAME",
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

    def test_config_loads_from_env_file(self):
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "orchestrator.env"
            env_file.write_text(
                "\n".join(
                    [
                        "GH_WEBHOOK_SECRET=from-file-gh",
                        "OPENAI_WEBHOOK_SECRET=from-file-openai",
                        f"DATABASE_URL=sqlite:///{Path(td) / 'envfile.db'}",
                    ]
                ),
                encoding="utf-8",
            )
            old_env_file = os.environ.get("ORCHESTRATOR_ENV_FILE")
            os.environ["ORCHESTRATOR_ENV_FILE"] = str(env_file)
            try:
                config = importlib.import_module("orchestrator.app.config")
                config.get_settings.cache_clear()
                importlib.reload(config)
                settings = config.get_settings()
                self.assertEqual(settings.gh_webhook_secret, "from-file-gh")
                self.assertEqual(settings.openai_webhook_secret, "from-file-openai")
                self.assertTrue(settings.database_url.endswith("envfile.db"))
            finally:
                if old_env_file is None:
                    os.environ.pop("ORCHESTRATOR_ENV_FILE", None)
                else:
                    os.environ["ORCHESTRATOR_ENV_FILE"] = old_env_file

    def test_github_webhook_rejects_invalid_signature(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main = _reload_orchestrator_modules()
            with TestClient(main.app) as client:
                response = client.post(
                    "/github/webhook",
                    headers={"X-GitHub-Event": "ping", "X-GitHub-Delivery": "abc"},
                    json={"zen": "hello"},
                )
                self.assertEqual(response.status_code, 403)

    def test_github_ping_with_valid_signature_succeeds_and_records(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main = _reload_orchestrator_modules()
            body = json.dumps({"zen": "ping"}).encode("utf-8")
            signature = self._github_signature("test-gh-secret", body)
            with TestClient(main.app) as client:
                response = client.post(
                    "/github/webhook",
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": signature,
                        "X-GitHub-Event": "ping",
                        "X-GitHub-Delivery": "delivery-1",
                    },
                    content=body,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["message"], "pong")
                self.assertFalse(response.json()["duplicate"])

                runs_response = client.get("/runs")
                self.assertEqual(runs_response.status_code, 200)
                data = runs_response.json()
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["runs"][0]["source"], "github")
                self.assertEqual(data["runs"][0]["status"], "pong")

    def test_github_duplicate_delivery_is_accepted_without_duplicate_row_or_notification(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            main = _reload_orchestrator_modules()
            body = json.dumps({"action": "opened"}).encode("utf-8")
            signature = self._github_signature("test-gh-secret", body)
            with patch("orchestrator.app.github_webhooks.notify_discord") as mocked_notify:
                with TestClient(main.app) as client:
                    headers = {
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": signature,
                        "X-GitHub-Event": "pull_request",
                        "X-GitHub-Delivery": "delivery-dedupe-1",
                    }
                    first = client.post("/github/webhook", headers=headers, content=body)
                    second = client.post("/github/webhook", headers=headers, content=body)

                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
                    self.assertFalse(first.json()["duplicate"])
                    self.assertTrue(second.json()["duplicate"])
                    self.assertEqual(mocked_notify.call_count, 0)

                    runs_response = client.get("/runs")
                    self.assertEqual(runs_response.status_code, 200)
                    self.assertEqual(runs_response.json()["count"], 1)

    def test_openai_webhook_verification_path_is_wired(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["OPENAI_WEBHOOK_SECRET"] = "test-openai-secret"
            main = _reload_orchestrator_modules()
            with patch(
                "orchestrator.app.openai_webhooks._verify_openai_webhook",
                return_value={"id": "evt_123", "type": "response.completed", "status": "completed"},
            ) as mocked_verify:
                with TestClient(main.app) as client:
                    response = client.post(
                        "/openai/webhook",
                        headers={"Content-Type": "application/json"},
                        content=json.dumps({"id": "evt_123", "type": "response.completed"}),
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.json()["duplicate"])
                    mocked_verify.assert_called_once()

    def test_openai_duplicate_delivery_is_accepted_without_duplicate_row_or_notification(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["OPENAI_WEBHOOK_SECRET"] = "test-openai-secret"
            main = _reload_orchestrator_modules()
            with patch(
                "orchestrator.app.openai_webhooks._verify_openai_webhook",
                return_value={"id": "evt_dup_1", "type": "response.completed", "status": "completed"},
            ) as mocked_verify:
                with patch("orchestrator.app.openai_webhooks.notify_discord") as mocked_notify:
                    with TestClient(main.app) as client:
                        payload = json.dumps({"id": "evt_dup_1", "type": "response.completed"})
                        first = client.post(
                            "/openai/webhook",
                            headers={"Content-Type": "application/json"},
                            content=payload,
                        )
                        second = client.post(
                            "/openai/webhook",
                            headers={"Content-Type": "application/json"},
                            content=payload,
                        )
                        self.assertEqual(first.status_code, 200)
                        self.assertEqual(second.status_code, 200)
                        self.assertFalse(first.json()["duplicate"])
                        self.assertTrue(second.json()["duplicate"])
                        self.assertEqual(mocked_notify.call_count, 1)
                        self.assertEqual(mocked_verify.call_count, 2)

                        runs_response = client.get("/runs")
                        self.assertEqual(runs_response.status_code, 200)
                        self.assertEqual(runs_response.json()["count"], 1)

    def test_runs_route_is_sane_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            main = _reload_orchestrator_modules()
            with TestClient(main.app) as client:
                response = client.get("/runs")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 0)

    def test_unknown_route_returns_404(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            main = _reload_orchestrator_modules()
            with TestClient(main.app) as client:
                response = client.get("/phpinfo")
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
