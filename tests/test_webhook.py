"""Unit tests for app/webhook.py"""

import hashlib
import hmac
import json

import pytest

from app.webhook import _verify_signature, _should_trigger


# ── signature verification ─────────────────────────────────────────────────────

def test_verify_signature_valid():
    secret = "test_secret"
    payload = b'{"action": "opened"}'
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = secret
    try:
        assert _verify_signature(payload, sig) is True
    finally:
        wh.WEBHOOK_SECRET = original


def test_verify_signature_invalid():
    secret = "correct_secret"
    payload = b'{"action": "opened"}'
    wrong_sig = "sha256=" + hmac.new(b"wrong_secret", payload, hashlib.sha256).hexdigest()

    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = secret
    try:
        assert _verify_signature(payload, wrong_sig) is False
    finally:
        wh.WEBHOOK_SECRET = original


def test_verify_signature_missing_header():
    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = "some_secret"
    try:
        assert _verify_signature(b"payload", None) is False
        assert _verify_signature(b"payload", "not-sha256=abc") is False
    finally:
        wh.WEBHOOK_SECRET = original


def test_verify_signature_no_secret_skips():
    """If WEBHOOK_SECRET is not set, verification is skipped (returns True)."""
    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = ""
    try:
        assert _verify_signature(b"anything", None) is True
    finally:
        wh.WEBHOOK_SECRET = original


# ── trigger pattern matching ───────────────────────────────────────────────────

def test_should_trigger_yaml():
    assert _should_trigger(["config/model.yaml"]) is True


def test_should_trigger_json():
    assert _should_trigger(["app-manifest.json"]) is True


def test_should_trigger_prompt_in_path():
    assert _should_trigger(["prompts/system_prompt.txt"]) is True


def test_should_trigger_txt():
    assert _should_trigger(["instructions.txt"]) is True


def test_should_not_trigger_python():
    assert _should_trigger(["app/main.py", "app/utils.py"]) is False


def test_should_not_trigger_markdown():
    assert _should_trigger(["README.md", "CHANGELOG.md"]) is False


def test_should_not_trigger_empty():
    assert _should_trigger([]) is False


def test_should_trigger_mixed_files():
    """Returns True if any file in the list matches."""
    assert _should_trigger(["app/main.py", "config/model.yaml"]) is True


# ── webhook endpoint ───────────────────────────────────────────────────────────

def test_ping_event(api_client):
    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = ""
    try:
        r = api_client.post(
            "/github/webhook",
            headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"},
            json={"zen": "test"},
        )
        assert r.status_code == 200
        assert r.json()["message"] == "pong"
    finally:
        wh.WEBHOOK_SECRET = original


def test_non_pr_event_ignored(api_client):
    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = ""
    try:
        r = api_client.post(
            "/github/webhook",
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
            json={"commits": []},
        )
        assert r.status_code == 200
        assert "Ignoring" in r.json()["message"]
    finally:
        wh.WEBHOOK_SECRET = original


def test_invalid_signature_rejected(api_client):
    import app.webhook as wh
    original = wh.WEBHOOK_SECRET
    wh.WEBHOOK_SECRET = "real_secret"
    try:
        r = api_client.post(
            "/github/webhook",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=invalidsignature",
                "Content-Type": "application/json",
            },
            json={"action": "opened"},
        )
        assert r.status_code == 401
    finally:
        wh.WEBHOOK_SECRET = original
