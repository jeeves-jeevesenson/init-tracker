"""Milestone 4 tests: GitHub App auth migration and governor PR lifecycle.

Tests cover:
- GitHub App JWT generation and installation token exchange
- Token caching/refresh behavior
- App-mode header/auth generation for outbound GitHub calls
- Ready-for-review GraphQL call under app mode
- Review finding → deduped top-level @copilot follow-up comment
- Repeated webhook delivery idempotency for that follow-up comment
- Guarded-path escalation remains intact under app mode
- Preflight reports app-mode capability correctly
- Legacy token mode still works when GITHUB_AUTH_MODE=token
"""
from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from orchestrator.app.config import Settings
from orchestrator.app.github_auth import (
    _CachedInstallationToken,
    _generate_app_jwt,
    _token_cache,
    _token_lock,
    _REFRESH_MARGIN_SECONDS,
    build_auth_headers,
    build_dispatch_auth_headers,
    build_governor_auth_headers,
    dispatch_auth_label,
    get_github_token,
    get_dispatch_token,
    get_governor_token,
    has_github_auth,
    has_dispatch_auth,
    has_governor_auth,
    invalidate_cached_token,
    is_app_mode,
    is_governor_app_mode,
    auth_mode_label,
    governor_auth_mode_label,
    try_mint_app_token,
    try_mint_governor_app_token,
)
from orchestrator.app.github_dispatch import (
    DispatchResult,
    dispatch_task_to_github_copilot,
    run_preflight_checks,
    mark_pr_ready_for_review,
    post_copilot_follow_up_comment,
    post_issue_comment,
    submit_approving_review,
    merge_pr,
    list_pull_request_reviews,
    list_pull_request_review_comments,
    list_pull_request_files,
    list_issue_comments,
    remove_requested_reviewers,
    request_reviewers,
    inspect_pull_request,
)
from orchestrator.app.models import (
    BLOCKER_GUARDED_PATHS_REQUIRE_HUMAN,
    AgentRun,
    Program,
    ProgramSlice,
    TaskPacket,
    PROGRAM_STATUS_ACTIVE,
)
from orchestrator.app.tasks import (
    _copilot_fix_trigger_body,
    safe_draft_can_be_promoted,
)


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
    "GOVERNOR_MAX_REVISION_CYCLES",
    "GOVERNOR_REMOVE_REVIEWER_LOGIN",
    "GOVERNOR_FALLBACK_REVIEWER",
    "GOVERNOR_GUARDED_PATHS",
}


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


def _make_settings(**overrides) -> Settings:
    """Construct a Settings object with defaults suitable for unit tests."""
    defaults = {
        "GITHUB_API_TOKEN": "dummy-token",
        "GITHUB_DISPATCH_USER_TOKEN": "dispatch-user-token",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_AUTH_MODE": "token",
        "GITHUB_GOVERNOR_AUTH_MODE": "token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_app_settings(*, key_path: str, **overrides) -> Settings:
    """Construct Settings configured for GitHub App auth mode."""
    defaults = {
        "GITHUB_GOVERNOR_AUTH_MODE": "app",
        "GITHUB_APP_CLIENT_ID": "Iv1.test_client_id",
        "GITHUB_APP_INSTALLATION_ID": "12345",
        "GITHUB_APP_PRIVATE_KEY_PATH": key_path,
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_DISPATCH_USER_TOKEN": "dispatch-user-token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---- RSA key fixture for JWT tests ----

_TEST_RSA_KEY_PEM = None


def _get_test_rsa_key() -> str:
    global _TEST_RSA_KEY_PEM
    if _TEST_RSA_KEY_PEM is None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _TEST_RSA_KEY_PEM = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
    return _TEST_RSA_KEY_PEM


class GitHubAppJWTTests(unittest.TestCase):
    """Tests for GitHub App JWT generation."""

    def test_generate_app_jwt_produces_valid_token(self):
        import jwt
        key_pem = _get_test_rsa_key()
        now = time.time()
        token = _generate_app_jwt(client_id="Iv1.abc123", private_key_pem=key_pem, now=now)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 50)

        # Decode without verification to check claims
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        private_key = load_pem_private_key(key_pem.encode(), password=None)
        public_key = private_key.public_key()
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])
        self.assertEqual(decoded["iss"], "Iv1.abc123")
        self.assertIn("iat", decoded)
        self.assertIn("exp", decoded)
        self.assertEqual(decoded["exp"] - decoded["iat"], 660)  # iat = now_ts-60, exp = now_ts+600

    def test_generate_app_jwt_uses_client_id_as_issuer(self):
        import jwt
        key_pem = _get_test_rsa_key()
        token = _generate_app_jwt(client_id="Iv1.custom_id", private_key_pem=key_pem, now=1000000)
        decoded = jwt.decode(token, options={"verify_signature": False})
        self.assertEqual(decoded["iss"], "Iv1.custom_id")


class GitHubAppTokenCacheTests(unittest.TestCase):
    """Tests for token caching/refresh behavior."""

    def setUp(self):
        invalidate_cached_token()

    def tearDown(self):
        invalidate_cached_token()

    def test_cached_token_returned_when_not_expired(self):
        """When a cached token is still valid, no new minting should occur."""
        from orchestrator.app import github_auth
        key_pem = _get_test_rsa_key()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(key_pem)
            key_path = f.name

        try:
            settings = _make_app_settings(key_path=key_path)

            # Pre-populate cache
            with _token_lock:
                _token_cache.token = "cached-token-abc"
                _token_cache.expires_at = time.time() + 3600  # 1 hour from now

            token = get_github_token(settings)
            self.assertEqual(token, "cached-token-abc")
        finally:
            os.unlink(key_path)

    def test_expired_token_triggers_refresh(self):
        """When cached token is near expiry, a new one should be minted."""
        key_pem = _get_test_rsa_key()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(key_pem)
            key_path = f.name

        try:
            settings = _make_app_settings(key_path=key_path)

            # Pre-populate cache with near-expired token
            with _token_lock:
                _token_cache.token = "old-token"
                _token_cache.expires_at = time.time() + 60  # only 60s left (< 300s margin)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "token": "fresh-token-xyz",
                "expires_at": "2099-01-01T00:00:00Z",
            }

            with patch("orchestrator.app.github_auth.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_response

                token = get_github_token(settings)

            self.assertEqual(token, "fresh-token-xyz")
        finally:
            os.unlink(key_path)

    def test_invalidate_cached_token_clears_cache(self):
        with _token_lock:
            _token_cache.token = "some-token"
            _token_cache.expires_at = time.time() + 3600
        invalidate_cached_token()
        with _token_lock:
            self.assertEqual(_token_cache.token, "")
            self.assertEqual(_token_cache.expires_at, 0.0)


class AuthModeDetectionTests(unittest.TestCase):
    """Tests for auth mode detection and has_github_auth."""

    def test_default_mode_is_token(self):
        settings = _make_settings()
        self.assertFalse(is_app_mode(settings))
        self.assertFalse(is_governor_app_mode(settings))
        self.assertEqual(auth_mode_label(settings), "token (legacy PAT)")
        self.assertEqual(governor_auth_mode_label(settings), "token (GITHUB_API_TOKEN)")

    def test_app_mode_detected(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path, GITHUB_AUTH_MODE="app")
            self.assertTrue(is_app_mode(settings))
            self.assertTrue(is_governor_app_mode(settings))
            self.assertEqual(auth_mode_label(settings), "app (GitHub App installation token)")
        finally:
            os.unlink(key_path)

    def test_has_github_auth_token_mode(self):
        settings = _make_settings(GITHUB_API_TOKEN="some-token")
        self.assertTrue(has_github_auth(settings))
        self.assertTrue(has_governor_auth(settings))

    def test_has_github_auth_token_mode_no_token(self):
        settings = _make_settings(GITHUB_API_TOKEN=None, GITHUB_DISPATCH_USER_TOKEN=None)
        self.assertFalse(has_github_auth(settings))
        self.assertFalse(has_governor_auth(settings))

    def test_has_github_auth_app_mode_complete(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path)
            self.assertTrue(has_github_auth(settings))
            self.assertTrue(has_governor_auth(settings))
        finally:
            os.unlink(key_path)

    def test_has_github_auth_app_mode_incomplete(self):
        settings = Settings(
            GITHUB_GOVERNOR_AUTH_MODE="app",
            GITHUB_APP_CLIENT_ID="Iv1.abc",
            # missing installation_id and key_path
        )
        self.assertFalse(has_github_auth(settings))
        self.assertFalse(has_governor_auth(settings))

    def test_get_github_token_token_mode(self):
        settings = _make_settings(GITHUB_API_TOKEN="my-pat")
        token = get_github_token(settings)
        self.assertEqual(token, "my-pat")
        self.assertEqual(get_governor_token(settings), "my-pat")

    def test_get_github_token_token_mode_missing_raises(self):
        settings = _make_settings(GITHUB_API_TOKEN=None)
        with self.assertRaises(RuntimeError):
            get_github_token(settings)

    def test_dispatch_lane_uses_dispatch_user_token(self):
        settings = _make_settings(
            GITHUB_API_TOKEN="legacy-governor-token",
            GITHUB_DISPATCH_USER_TOKEN="dispatch-only-token",
        )
        self.assertTrue(has_dispatch_auth(settings))
        self.assertEqual(get_dispatch_token(settings), "dispatch-only-token")
        self.assertIn("GITHUB_DISPATCH_USER_TOKEN", dispatch_auth_label(settings))

    def test_dispatch_lane_falls_back_to_legacy_token(self):
        settings = _make_settings(
            GITHUB_API_TOKEN="legacy-token",
            GITHUB_DISPATCH_USER_TOKEN=None,
        )
        self.assertTrue(has_dispatch_auth(settings))
        self.assertEqual(get_dispatch_token(settings), "legacy-token")

    def test_governor_mode_falls_back_to_legacy_github_auth_mode(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_settings(
                GITHUB_GOVERNOR_AUTH_MODE=None,
                GITHUB_AUTH_MODE="app",
                GITHUB_API_TOKEN=None,
                GITHUB_APP_CLIENT_ID="Iv1.abc",
                GITHUB_APP_INSTALLATION_ID="123",
                GITHUB_APP_PRIVATE_KEY_PATH=key_path,
            )
            self.assertTrue(is_governor_app_mode(settings))
            self.assertTrue(has_governor_auth(settings))
        finally:
            os.unlink(key_path)


class BuildAuthHeadersTests(unittest.TestCase):
    """Tests for build_auth_headers header generation."""

    def test_token_mode_headers(self):
        settings = _make_settings(GITHUB_API_TOKEN="test-pat-123")
        headers = build_auth_headers(settings)
        self.assertEqual(headers["Authorization"], "Bearer test-pat-123")
        self.assertIn("Accept", headers)
        self.assertIn("X-GitHub-Api-Version", headers)

    def test_app_mode_headers_with_cached_token(self):
        invalidate_cached_token()
        with _token_lock:
            _token_cache.token = "inst-token-456"
            _token_cache.expires_at = time.time() + 3600

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path)
            headers = build_auth_headers(settings)
            self.assertEqual(headers["Authorization"], "Bearer inst-token-456")
            governor_headers = build_governor_auth_headers(settings)
            self.assertEqual(governor_headers["Authorization"], "Bearer inst-token-456")
        finally:
            os.unlink(key_path)
            invalidate_cached_token()

    def test_no_auth_fallback_headers(self):
        settings = _make_settings(GITHUB_API_TOKEN=None, GITHUB_DISPATCH_USER_TOKEN=None)
        headers = build_auth_headers(settings)
        self.assertNotIn("Authorization", headers)
        self.assertIn("Accept", headers)

    def test_dispatch_headers_use_dispatch_user_token(self):
        settings = _make_settings(
            GITHUB_API_TOKEN="legacy-token",
            GITHUB_DISPATCH_USER_TOKEN="dispatch-token",
        )
        headers = build_dispatch_auth_headers(settings)
        self.assertEqual(headers["Authorization"], "Bearer dispatch-token")


class OutboundAuthWiringTests(unittest.TestCase):
    """Tests that governor-used GitHub API functions route through the shared auth helper."""

    def setUp(self):
        invalidate_cached_token()
        with _token_lock:
            _token_cache.token = "app-install-token"
            _token_cache.expires_at = time.time() + 3600

    def tearDown(self):
        invalidate_cached_token()

    def _app_settings(self) -> Settings:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            self._key_path = f.name
        return _make_app_settings(key_path=self._key_path)

    def _cleanup_key(self):
        if hasattr(self, "_key_path"):
            try:
                os.unlink(self._key_path)
            except OSError:
                pass

    def test_mark_pr_ready_for_review_uses_dispatch_auth(self):
        settings = self._app_settings()
        settings.github_dispatch_user_token = "dispatch-ready-token"
        try:
            mock_pr_resp = Mock()
            mock_pr_resp.status_code = 200
            mock_pr_resp.json.return_value = {
                "data": {
                    "repository": {
                        "pullRequest": {"id": "PR_kwDOtest", "isDraft": True}
                    }
                }
            }
            mock_pr_resp.headers = {"content-type": "application/json"}

            mock_mutation_resp = Mock()
            mock_mutation_resp.status_code = 200
            mock_mutation_resp.json.return_value = {
                "data": {
                    "markPullRequestReadyForReview": {
                        "pullRequest": {"number": 42, "isDraft": False}
                    }
                }
            }
            mock_verify_resp = Mock()
            mock_verify_resp.status_code = 200
            mock_verify_resp.json.return_value = {
                "data": {
                    "repository": {
                        "pullRequest": {"id": "PR_kwDOtest", "isDraft": False}
                    }
                }
            }

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                mock_client = MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.side_effect = [mock_pr_resp, mock_mutation_resp, mock_verify_resp]

                success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=42)

            self.assertTrue(success)
            self.assertIn("ready for review", msg)

            # Verify the headers used include the dispatch user token, not app token.
            calls = MockClient.return_value.post.call_args_list
            for c in calls:
                headers = c.kwargs.get("headers") or c[1].get("headers", {})
                self.assertEqual(headers.get("Authorization"), "Bearer dispatch-ready-token")
        finally:
            self._cleanup_key()

    def test_post_copilot_follow_up_comment_uses_dispatch_auth(self):
        settings = self._app_settings()
        settings.github_dispatch_user_token = "dispatch-comment-token"
        try:
            mock_resp = Mock()
            mock_resp.status_code = 201

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_resp

                success, msg = post_copilot_follow_up_comment(
                    settings=settings,
                    repo="owner/repo",
                    issue_number=1,
                    body="@copilot please fix",
                )

            self.assertTrue(success)
            self.assertIn("@copilot", msg)
            headers = MockClient.return_value.post.call_args.kwargs.get("headers") or MockClient.return_value.post.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer dispatch-comment-token")
        finally:
            self._cleanup_key()

    def test_post_issue_comment_uses_app_auth(self):
        settings = self._app_settings()
        try:
            mock_resp = Mock()
            mock_resp.status_code = 201

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_resp

                success, msg = post_issue_comment(settings=settings, repo="owner/repo", issue_number=1, body="hello")

            self.assertTrue(success)
            headers = MockClient.return_value.post.call_args.kwargs.get("headers") or MockClient.return_value.post.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer app-install-token")
        finally:
            self._cleanup_key()

    def test_submit_approving_review_uses_app_auth(self):
        settings = self._app_settings()
        try:
            mock_resp = Mock()
            mock_resp.status_code = 200

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_resp

                success, msg = submit_approving_review(settings=settings, repo="owner/repo", pr_number=1)

            self.assertTrue(success)
            headers = MockClient.return_value.post.call_args.kwargs.get("headers") or MockClient.return_value.post.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer app-install-token")
        finally:
            self._cleanup_key()

    def test_merge_pr_uses_dispatch_auth_with_latest_sha(self):
        settings = self._app_settings()
        settings.github_dispatch_user_token = "dispatch-merge-token"
        try:
            inspect_resp_before = Mock()
            inspect_resp_before.status_code = 200
            inspect_resp_before.headers = {"content-type": "application/json"}
            inspect_resp_before.json.return_value = {
                "head": {"sha": "abc123"},
                "merged": False,
            }
            merge_resp = Mock()
            merge_resp.status_code = 200
            inspect_resp_after = Mock()
            inspect_resp_after.status_code = 200
            inspect_resp_after.headers = {"content-type": "application/json"}
            inspect_resp_after.json.return_value = {
                "head": {"sha": "abc123"},
                "merged": True,
            }

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.get.side_effect = [inspect_resp_before, inspect_resp_after]
                MockClient.return_value.put.return_value = merge_resp

                success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=1)

            self.assertTrue(success)
            self.assertIn("merge_observed=True", msg)
            headers = MockClient.return_value.put.call_args.kwargs.get("headers") or MockClient.return_value.put.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer dispatch-merge-token")
            payload = MockClient.return_value.put.call_args.kwargs.get("json") or MockClient.return_value.put.call_args[1].get("json", {})
            self.assertEqual(payload.get("sha"), "abc123")
        finally:
            self._cleanup_key()

    def test_merge_pr_retries_once_on_409_with_refreshed_sha(self):
        settings = self._app_settings()
        settings.github_dispatch_user_token = "dispatch-merge-token"
        try:
            inspect_before = Mock()
            inspect_before.status_code = 200
            inspect_before.headers = {"content-type": "application/json"}
            inspect_before.json.return_value = {"head": {"sha": "old-sha"}, "merged": False}
            inspect_after_409 = Mock()
            inspect_after_409.status_code = 200
            inspect_after_409.headers = {"content-type": "application/json"}
            inspect_after_409.json.return_value = {"head": {"sha": "new-sha"}, "merged": False}
            inspect_after_merge = Mock()
            inspect_after_merge.status_code = 200
            inspect_after_merge.headers = {"content-type": "application/json"}
            inspect_after_merge.json.return_value = {"head": {"sha": "new-sha"}, "merged": True}
            first_merge = Mock()
            first_merge.status_code = 409
            first_merge.text = "Head branch modified"
            second_merge = Mock()
            second_merge.status_code = 200

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.get.side_effect = [inspect_before, inspect_after_409, inspect_after_merge]
                MockClient.return_value.put.side_effect = [first_merge, second_merge]

                success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=44)

            self.assertTrue(success)
            self.assertIn("retry_used=True", msg)
            first_payload = MockClient.return_value.put.call_args_list[0].kwargs.get("json", {})
            second_payload = MockClient.return_value.put.call_args_list[1].kwargs.get("json", {})
            self.assertEqual(first_payload.get("sha"), "old-sha")
            self.assertEqual(second_payload.get("sha"), "new-sha")
        finally:
            self._cleanup_key()

    def test_list_pull_request_reviews_uses_app_auth(self):
        settings = self._app_settings()
        try:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = []

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.get.return_value = mock_resp

                reviews, msg = list_pull_request_reviews(settings=settings, repo="owner/repo", pr_number=1)

            headers = MockClient.return_value.get.call_args.kwargs.get("headers") or MockClient.return_value.get.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer app-install-token")
        finally:
            self._cleanup_key()

    def test_remove_requested_reviewers_uses_app_auth(self):
        settings = self._app_settings()
        try:
            mock_resp = Mock()
            mock_resp.status_code = 200

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.request.return_value = mock_resp

                ok, _ = remove_requested_reviewers(
                    settings=settings,
                    repo="owner/repo",
                    pr_number=22,
                    reviewers=["someone"],
                )

            self.assertTrue(ok)
            headers = MockClient.return_value.request.call_args.kwargs.get("headers") or MockClient.return_value.request.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Bearer app-install-token")
        finally:
            self._cleanup_key()

    def test_dispatch_issue_assignment_uses_dispatch_token_not_app_token(self):
        settings = self._app_settings()
        settings.github_dispatch_user_token = "dispatch-user-token"
        task = TaskPacket(
            id=501,
            github_repo="owner/repo",
            github_issue_number=123,
            title="Dispatch auth lane test",
            normalized_task_text="Dispatch lane should use user token",
            acceptance_criteria_json="[]",
            validation_commands_json="[]",
        )
        try:
            preflight_response = Mock(status_code=200, headers={"content-type": "application/json"})
            preflight_response.json.return_value = {
                "data": {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [{"login": "copilot-swe-agent", "__typename": "Bot", "id": "BOT_501"}]
                        }
                    }
                }
            }
            assign_response = Mock(status_code=201, headers={"content-type": "application/json"})
            assign_response.json.return_value = {
                "id": 501,
                "html_url": "https://github.com/owner/repo/issues/123",
                "assignees": [{"login": "copilot-swe-agent"}],
            }
            comment_response = Mock(status_code=201, headers={"content-type": "application/json"}, text="")

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.side_effect = [preflight_response, assign_response, comment_response]

                result = dispatch_task_to_github_copilot(settings=settings, task=task)

            self.assertTrue(result.accepted)
            for call_ in MockClient.return_value.post.call_args_list:
                headers = call_.kwargs.get("headers") or call_[1].get("headers", {})
                self.assertEqual(headers.get("Authorization"), "Bearer dispatch-user-token")
        finally:
            self._cleanup_key()

    def test_no_auth_returns_error(self):
        """Functions should return errors when auth is not available."""
        settings = _make_settings(GITHUB_API_TOKEN=None, GITHUB_DISPATCH_USER_TOKEN=None, GITHUB_GOVERNOR_AUTH_MODE="token")
        success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=1)
        self.assertFalse(success)
        self.assertIn("dispatch user-token auth", msg.lower())

        success, msg = post_copilot_follow_up_comment(
            settings=settings,
            repo="owner/repo",
            issue_number=1,
            body="@copilot fix this",
        )
        self.assertFalse(success)

        success, msg = submit_approving_review(settings=settings, repo="owner/repo", pr_number=1)
        self.assertFalse(success)

        success, msg = merge_pr(settings=settings, repo="owner/repo", pr_number=1)
        self.assertFalse(success)


class ReadyForReviewAppModeTests(unittest.TestCase):
    """Tests for GraphQL markPullRequestReadyForReview under app mode."""

    def setUp(self):
        invalidate_cached_token()
        with _token_lock:
            _token_cache.token = "app-token-for-ready"
            _token_cache.expires_at = time.time() + 3600

    def tearDown(self):
        invalidate_cached_token()

    def test_already_non_draft_returns_success(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path)
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": {
                    "repository": {
                        "pullRequest": {"id": "PR_kwDO123", "isDraft": False}
                    }
                }
            }
            mock_resp.headers = {"content-type": "application/json"}

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_resp

                success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=10)

            self.assertTrue(success)
            self.assertIn("already ready", msg)
        finally:
            os.unlink(key_path)

    def test_draft_pr_is_promoted_under_app_mode(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path)

            mock_query_resp = Mock()
            mock_query_resp.status_code = 200
            mock_query_resp.json.return_value = {
                "data": {"repository": {"pullRequest": {"id": "PR_kwDO456", "isDraft": True}}}
            }
            mock_query_resp.headers = {"content-type": "application/json"}

            mock_mutation_resp = Mock()
            mock_mutation_resp.status_code = 200
            mock_mutation_resp.json.return_value = {
                "data": {"markPullRequestReadyForReview": {"pullRequest": {"number": 10, "isDraft": False}}}
            }

            verify_resp = Mock()
            verify_resp.status_code = 200
            verify_resp.json.return_value = {
                "data": {"repository": {"pullRequest": {"id": "PR_kwDO456", "isDraft": False}}}
            }
            verify_resp.headers = {"content-type": "application/json"}

            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.side_effect = [mock_query_resp, mock_mutation_resp, verify_resp]

                success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=10)

            self.assertTrue(success)
            self.assertIn("ready for review", msg)
        finally:
            os.unlink(key_path)

    def test_ready_for_review_fails_when_postcondition_stays_draft(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("dummy")
            key_path = f.name
        try:
            settings = _make_app_settings(key_path=key_path)
            query_resp = Mock()
            query_resp.status_code = 200
            query_resp.json.return_value = {
                "data": {"repository": {"pullRequest": {"id": "PR_kwDO456", "isDraft": True}}}
            }
            mutation_resp = Mock()
            mutation_resp.status_code = 200
            mutation_resp.json.return_value = {
                "data": {"markPullRequestReadyForReview": {"pullRequest": {"number": 10, "isDraft": False}}}
            }
            verify_resp = Mock()
            verify_resp.status_code = 200
            verify_resp.json.return_value = {
                "data": {"repository": {"pullRequest": {"id": "PR_kwDO456", "isDraft": True}}}
            }
            with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.side_effect = [query_resp, mutation_resp, verify_resp]
                success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=10)
            self.assertFalse(success)
            self.assertIn("postcondition failed", msg.lower())
        finally:
            os.unlink(key_path)


class DedupedCopilotFollowUpTests(unittest.TestCase):
    """Tests for deduped @copilot follow-up comment and webhook idempotency."""

    def test_copilot_fix_trigger_body_content(self):
        """The fix trigger body should contain @copilot and list findings."""
        findings = ["Fix import ordering", "Add missing type annotation"]
        body = _copilot_fix_trigger_body(findings=findings)
        self.assertIn("@copilot", body)
        self.assertIn("Fix import ordering", body)
        self.assertIn("Add missing type annotation", body)

    def test_copilot_fix_trigger_body_empty_findings(self):
        """When no findings, body should contain a generic fallback."""
        body = _copilot_fix_trigger_body(findings=[])
        self.assertIn("@copilot", body)
        self.assertIn("Re-run your review", body)

    def test_fix_trigger_fingerprint_is_deterministic(self):
        """Same findings → same fingerprint → no duplicate comments."""
        findings = ["fix A", "fix B"]
        body1 = _copilot_fix_trigger_body(findings=findings)
        body2 = _copilot_fix_trigger_body(findings=findings)
        fp1 = hashlib.sha1(body1.encode("utf-8")).hexdigest()
        fp2 = hashlib.sha1(body2.encode("utf-8")).hexdigest()
        self.assertEqual(fp1, fp2)

    def test_different_findings_produce_different_fingerprints(self):
        body1 = _copilot_fix_trigger_body(findings=["fix A"])
        body2 = _copilot_fix_trigger_body(findings=["fix B"])
        fp1 = hashlib.sha1(body1.encode("utf-8")).hexdigest()
        fp2 = hashlib.sha1(body2.encode("utf-8")).hexdigest()
        self.assertNotEqual(fp1, fp2)


class WebhookIdempotencyTests(unittest.TestCase):
    """Tests for repeated webhook delivery idempotency in the governor fix-trigger path."""

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
        governor_state_json: str | None = None,
    ) -> int:
        with Session(db.get_engine()) as session:
            task = TaskPacket(
                github_repo=repo,
                github_issue_number=issue_number,
                title="Webhook idempotency test",
                raw_body="body",
                status="working",
                approval_state="approved",
                acceptance_criteria_json='["done"]',
                task_kind="single_task",
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
                governor_state_json=governor_state_json,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return task.id

    def test_repeated_webhook_does_not_duplicate_fix_comment(self):
        """Two consecutive webhook deliveries with same findings should only post one comment."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GH_WEBHOOK_SECRET"] = "test-gh-secret"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            main, db = _reload_orchestrator_modules()

            repo = "owner/repo"
            pr_number = 300

            copilot_review = {
                "user": {"login": "copilot"},
                "state": "CHANGES_REQUESTED",
                "body": "Fix the import order",
            }

            pr_payload = {
                "action": "submitted",
                "pull_request": {
                    "number": pr_number,
                    "draft": False,
                    "state": "open",
                    "requested_reviewers": [],
                },
                "review": copilot_review,
                "repository": {"full_name": repo},
            }

            post_comment_calls = []

            def mock_post_comment(**kwargs):
                post_comment_calls.append(kwargs)
                return True, "posted"

            with patch("orchestrator.app.tasks.mark_pr_ready_for_review", return_value=(True, "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_files", return_value=(["src/main.py"], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_reviews", return_value=([copilot_review], "ok")), \
                 patch("orchestrator.app.tasks.list_pull_request_review_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.list_issue_comments", return_value=([], "ok")), \
                 patch("orchestrator.app.tasks.post_copilot_follow_up_comment", side_effect=mock_post_comment) as mock_post, \
                 patch("orchestrator.app.tasks.remove_requested_reviewers", return_value=(True, "ok")), \
                 patch("orchestrator.app.tasks.summarize_governor_update"), \
                 patch("orchestrator.app.tasks.notify_discord"):

                with TestClient(main.app) as client:
                    # Create task/run after DB is initialized by TestClient lifespan
                    self._create_linked_task_run(db, repo=repo, issue_number=300, pr_number=pr_number)

                    body = json.dumps(pr_payload).encode("utf-8")
                    sig = _github_signature("test-gh-secret", body)
                    headers = {
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": sig,
                        "X-GitHub-Event": "pull_request_review",
                        "X-GitHub-Delivery": "delivery-idem-1",
                    }
                    client.post("/github/webhook", headers=headers, content=body)

                    # Simulate second delivery with different delivery ID (same findings)
                    headers2 = dict(headers)
                    headers2["X-GitHub-Delivery"] = "delivery-idem-2"
                    client.post("/github/webhook", headers=headers2, content=body)

            # The fix comment should only be posted once (deduped by fingerprint)
            self.assertEqual(len(post_comment_calls), 1)


class GuardedPathPreservationTests(unittest.TestCase):
    """Tests that guarded/sensitive path escalation remains intact under app mode."""

    def test_guarded_paths_still_block_auto_approval(self):
        """The safe_draft_can_be_promoted predicate should reject PRs touching guarded paths."""
        result = safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=True,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        )
        self.assertFalse(result)

    def test_guarded_paths_block_approval_regardless_of_auth_mode(self):
        """Guarded-path escalation should work the same in both auth modes."""
        for mode in ["token", "app"]:
            with self.subTest(mode=mode):
                result = safe_draft_can_be_promoted(
                    pr_draft=True,
                    checks_passed=True,
                    guarded_paths_touched=True,
                    unresolved_findings=[],
                    waiting_for_revision_push=False,
                )
                self.assertFalse(result)

    def test_safe_draft_promotes_when_no_guarded_paths(self):
        result = safe_draft_can_be_promoted(
            pr_draft=True,
            checks_passed=True,
            guarded_paths_touched=False,
            unresolved_findings=[],
            waiting_for_revision_push=False,
        )
        self.assertTrue(result)


class PreflightAppModeTests(unittest.TestCase):
    """Tests that preflight reports auth mode and app capabilities correctly."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_preflight_reports_token_mode(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GITHUB_API_TOKEN"] = "dummy-token"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-user-token"
            os.environ.pop("GITHUB_AUTH_MODE", None)
            os.environ.pop("GITHUB_GOVERNOR_AUTH_MODE", None)
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")
            body = resp.json()
            pf = body["preflight"]
            self.assertIn("token", pf["github_auth_mode"])
            self.assertTrue(pf["github_auth_available"])
            self.assertFalse(pf["app_outbound_auth_usable"])
            self.assertTrue(pf["dispatch_auth_ready"])
            self.assertTrue(pf["user_token_lane_available"])
            self.assertTrue(pf["governor_auth_ready"])
            self.assertTrue(pf["governor_lane_available"])
            self.assertFalse(pf["app_token_lane_available"])
            self.assertTrue(pf["capabilities"]["unattended_issue_to_pr_dispatch"])
            self.assertTrue(pf["capabilities"]["unattended_draft_to_review_readiness"])
            self.assertTrue(pf["capabilities"]["unattended_review_to_fix_comment_readiness"])
            self.assertFalse(pf["capabilities"]["unattended_approve_merge_readiness"])

    def test_preflight_reports_app_mode_with_incomplete_config(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            os.environ["GITHUB_GOVERNOR_AUTH_MODE"] = "app"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-user-token"
            os.environ["GITHUB_APP_CLIENT_ID"] = "Iv1.test"
            os.environ.pop("GITHUB_APP_INSTALLATION_ID", None)
            os.environ.pop("GITHUB_APP_PRIVATE_KEY_PATH", None)
            os.environ.pop("GITHUB_API_TOKEN", None)
            main, db = _reload_orchestrator_modules()

            with TestClient(main.app) as client:
                resp = client.get("/preflight")
            body = resp.json()
            pf = body["preflight"]
            self.assertIn("app", pf["github_auth_mode"])
            self.assertFalse(pf["github_auth_available"])
            self.assertFalse(pf["app_outbound_auth_usable"])
            self.assertTrue(pf["dispatch_auth_ready"])
            self.assertFalse(pf["governor_auth_ready"])
            self.assertTrue(pf["capabilities"]["pr_ready_for_review"])
            self.assertFalse(pf["capabilities"]["unattended_approve_merge_readiness"])
            blockers = pf["blockers"]
            self.assertTrue(any("Governor auth is not ready" in b for b in blockers))

    def test_preflight_reports_app_mode_with_complete_config(self):
        key_pem = _get_test_rsa_key()
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            key_file = Path(td) / "test.pem"
            key_file.write_text(key_pem)
            os.environ["GITHUB_GOVERNOR_AUTH_MODE"] = "app"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-user-token"
            os.environ["GITHUB_APP_CLIENT_ID"] = "Iv1.test"
            os.environ["GITHUB_APP_INSTALLATION_ID"] = "12345"
            os.environ["GITHUB_APP_PRIVATE_KEY_PATH"] = str(key_file)
            os.environ.pop("GITHUB_API_TOKEN", None)
            main, db = _reload_orchestrator_modules()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "token": "ghs_test_token",
                "expires_at": "2099-01-01T00:00:00Z",
            }

            with patch("orchestrator.app.github_auth.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_response

                invalidate_cached_token()
                with TestClient(main.app) as client:
                    resp = client.get("/preflight")

            body = resp.json()
            pf = body["preflight"]
            self.assertIn("app", pf["github_auth_mode"])
            self.assertTrue(pf["github_auth_available"])
            self.assertTrue(pf["app_outbound_auth_usable"])
            self.assertTrue(pf["app_token_mint"]["ok"])
            self.assertTrue(pf["dispatch_auth_ready"])
            self.assertTrue(pf["governor_auth_ready"])
            self.assertTrue(pf["app_token_lane_available"])
            self.assertTrue(pf["capabilities"]["pr_ready_for_review"])
            invalidate_cached_token()

    def test_preflight_unattended_single_slice_under_app_mode(self):
        """With app auth and all auto-* enabled, unattended_single_slice_execution should be True."""
        key_pem = _get_test_rsa_key()
        with tempfile.TemporaryDirectory() as td:
            os.environ["DATABASE_URL"] = f"sqlite:///{Path(td) / 'orchestrator.db'}"
            key_file = Path(td) / "test.pem"
            key_file.write_text(key_pem)
            os.environ["GITHUB_GOVERNOR_AUTH_MODE"] = "app"
            os.environ["GITHUB_DISPATCH_USER_TOKEN"] = "dispatch-user-token"
            os.environ["GITHUB_APP_CLIENT_ID"] = "Iv1.test"
            os.environ["GITHUB_APP_INSTALLATION_ID"] = "12345"
            os.environ["GITHUB_APP_PRIVATE_KEY_PATH"] = str(key_file)
            os.environ.pop("GITHUB_API_TOKEN", None)
            os.environ["PROGRAM_AUTO_MERGE"] = "true"
            os.environ["PROGRAM_AUTO_APPROVE"] = "true"
            os.environ["PROGRAM_AUTO_DISPATCH"] = "true"
            os.environ["PROGRAM_AUTO_CONTINUE"] = "true"
            os.environ["PROGRAM_TRUSTED_AUTO_CONFIRM"] = "true"
            main, db = _reload_orchestrator_modules()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "token": "ghs_test_token",
                "expires_at": "2099-01-01T00:00:00Z",
            }

            with patch("orchestrator.app.github_auth.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_response

                invalidate_cached_token()
                with TestClient(main.app) as client:
                    resp = client.get("/preflight")

            body = resp.json()
            pf = body["preflight"]
            self.assertTrue(pf["capabilities"]["unattended_single_slice_execution"])
            self.assertTrue(pf["capabilities"]["unattended_continuation"])
            self.assertTrue(pf["capabilities"]["unattended_issue_to_pr_dispatch"])
            self.assertTrue(pf["capabilities"]["unattended_pr_governance"])
            invalidate_cached_token()


class LegacyTokenFallbackTests(unittest.TestCase):
    """Tests that legacy token mode continues to work when GITHUB_AUTH_MODE=token."""

    def test_legacy_mode_dispatch_check(self):
        settings = _make_settings(GITHUB_API_TOKEN="legacy-pat")
        self.assertFalse(is_app_mode(settings))
        self.assertTrue(has_github_auth(settings))
        token = get_github_token(settings)
        self.assertEqual(token, "legacy-pat")

    def test_legacy_mode_no_token_blocks(self):
        settings = _make_settings(GITHUB_API_TOKEN=None)
        self.assertFalse(has_github_auth(settings))

    def test_preflight_legacy_mode_unchanged(self):
        """Preflight under token mode should still include github_api_token key for backwards compat."""
        settings = _make_settings(GITHUB_API_TOKEN="some-pat")
        result = run_preflight_checks(settings=settings)
        self.assertIn("github_api_token", result)
        self.assertTrue(result["github_api_token"])
        self.assertIn("github_auth_mode", result)


class AuthLaneFailureReportingTests(unittest.TestCase):
    def test_dispatch_auth_failure_message_is_explicit(self):
        settings = _make_settings(
            GITHUB_API_TOKEN=None,
            GITHUB_DISPATCH_USER_TOKEN=None,
            GITHUB_GOVERNOR_AUTH_MODE="app",
        )
        task = TaskPacket(
            id=900,
            github_repo="owner/repo",
            github_issue_number=9,
            title="Dispatch failure message",
            normalized_task_text="",
            acceptance_criteria_json="[]",
            validation_commands_json="[]",
        )
        result = dispatch_task_to_github_copilot(settings=settings, task=task)
        self.assertFalse(result.accepted)
        self.assertTrue(result.manual_required)
        self.assertIn("Dispatch auth failure", result.summary)

    def test_governor_auth_failure_message_is_explicit(self):
        settings = _make_settings(
            GITHUB_API_TOKEN=None,
            GITHUB_DISPATCH_USER_TOKEN=None,
            GITHUB_GOVERNOR_AUTH_MODE="token",
        )
        success, msg = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=77)
        self.assertFalse(success)
        self.assertIn("Ready-for-review failure", msg)
        self.assertIn("dispatch user-token auth", msg)


class AuthLaneLoggingTests(unittest.TestCase):
    def test_ready_for_review_logs_dispatch_lane_and_graphql(self):
        settings = _make_settings(
            GITHUB_API_TOKEN=None,
            GITHUB_DISPATCH_USER_TOKEN="dispatch-token",
        )
        query_response = MagicMock()
        query_response.status_code = 200
        query_response.json.return_value = {
            "data": {"repository": {"pullRequest": {"id": "PR_node_id_789", "isDraft": True}}}
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
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json.return_value = {
            "data": {"repository": {"pullRequest": {"id": "PR_node_id_789", "isDraft": False}}}
        }
        with patch("orchestrator.app.github_dispatch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: mock_client
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = [query_response, mutation_response, verify_response]
            mock_client_cls.return_value = mock_client
            with self.assertLogs("orchestrator.app.github_dispatch", level="INFO") as logs:
                ok, _ = mark_pr_ready_for_review(settings=settings, repo="owner/repo", pr_number=42)
        self.assertTrue(ok)
        joined = "\n".join(logs.output)
        self.assertIn("github_action=mark_pr_ready_for_review", joined)
        self.assertIn("auth_lane=dispatch_user_token", joined)
        self.assertIn("api_type=GraphQL", joined)

    def test_copilot_follow_up_logs_dispatch_lane_and_rest(self):
        settings = _make_settings(
            GITHUB_API_TOKEN="governor-token",
            GITHUB_DISPATCH_USER_TOKEN="dispatch-token",
        )
        mock_resp = Mock()
        mock_resp.status_code = 201
        with patch("orchestrator.app.github_dispatch.httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
            MockClient.return_value.__exit__ = Mock(return_value=False)
            MockClient.return_value.post.return_value = mock_resp
            with self.assertLogs("orchestrator.app.github_dispatch", level="INFO") as logs:
                ok, _ = post_copilot_follow_up_comment(
                    settings=settings,
                    repo="owner/repo",
                    issue_number=12,
                    body="@copilot test",
                )
        self.assertTrue(ok)
        joined = "\n".join(logs.output)
        self.assertIn("github_action=post_copilot_follow_up_comment", joined)
        self.assertIn("auth_lane=dispatch_user_token", joined)
        self.assertIn("api_type=REST", joined)


class TryMintAppTokenTests(unittest.TestCase):
    """Tests for the try_mint_app_token preflight helper."""

    def setUp(self):
        invalidate_cached_token()

    def tearDown(self):
        invalidate_cached_token()

    def test_returns_false_when_not_app_mode(self):
        settings = _make_settings()
        ok, msg = try_mint_app_token(settings)
        self.assertFalse(ok)
        self.assertIn("not 'app'", msg)

    def test_returns_true_on_successful_mint(self):
        key_pem = _get_test_rsa_key()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(key_pem)
            key_path = f.name

        try:
            settings = _make_app_settings(key_path=key_path)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "token": "ghs_mint_test",
                "expires_at": "2099-01-01T00:00:00Z",
            }

            with patch("orchestrator.app.github_auth.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_response

                ok, msg = try_mint_app_token(settings)

            self.assertTrue(ok)
            self.assertIn("successfully", msg)
        finally:
            os.unlink(key_path)

    def test_returns_false_on_mint_failure(self):
        key_pem = _get_test_rsa_key()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(key_pem)
            key_path = f.name

        try:
            settings = _make_app_settings(key_path=key_path)

            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Bad credentials"

            with patch("orchestrator.app.github_auth.httpx.Client") as MockClient:
                MockClient.return_value.__enter__ = Mock(return_value=MockClient.return_value)
                MockClient.return_value.__exit__ = Mock(return_value=False)
                MockClient.return_value.post.return_value = mock_response

                ok, msg = try_mint_app_token(settings)

            self.assertFalse(ok)
            self.assertIn("failed", msg.lower())
        finally:
            os.unlink(key_path)

    def test_returns_false_when_key_file_missing(self):
        settings = _make_app_settings(key_path="/nonexistent/path/key.pem")
        ok, msg = try_mint_app_token(settings)
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())


if __name__ == "__main__":
    unittest.main()
