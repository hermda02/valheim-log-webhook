"""Webhook delivery retry behavior tests."""

from __future__ import annotations

from urllib.error import URLError

from valheim_log_webhook.events import EventType
from valheim_log_webhook.routing import DiscordChannel, OutboundWebhook
from valheim_log_webhook.webhook import send_with_retry


def _outbound() -> OutboundWebhook:
    return OutboundWebhook(
        event_type=EventType.SERVER_ONLINE,
        channel=DiscordChannel.LOG,
        url="https://discord.com/api/webhooks/1/log",
        payload={"username": "Hugin", "content": "[ONLINE] Valheim server is online."},
    )


def test_retry_once_on_network_error_then_success() -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def post_fn(_url: str, _payload: dict[str, str], _timeout: float) -> int:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError("network")
        return 204

    result = send_with_retry(
        _outbound(),
        timeout_seconds=2,
        retry_delay_seconds=0.5,
        post_fn=post_fn,
        sleep_fn=sleeps.append,
    )

    assert result.success is True
    assert result.attempts == 2
    assert sleeps == [0.5]


def test_retry_once_on_http_5xx_then_fail() -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def post_fn(_url: str, _payload: dict[str, str], _timeout: float) -> int:
        attempts["count"] += 1
        return 503

    result = send_with_retry(
        _outbound(),
        timeout_seconds=2,
        retry_delay_seconds=0.5,
        post_fn=post_fn,
        sleep_fn=sleeps.append,
    )

    assert result.success is False
    assert result.attempts == 2
    assert result.status_code == 503
    assert sleeps == [0.5]


def test_no_retry_on_http_4xx() -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def post_fn(_url: str, _payload: dict[str, str], _timeout: float) -> int:
        attempts["count"] += 1
        return 400

    result = send_with_retry(
        _outbound(),
        timeout_seconds=2,
        retry_delay_seconds=0.5,
        post_fn=post_fn,
        sleep_fn=sleeps.append,
    )

    assert result.success is False
    assert result.attempts == 1
    assert result.status_code == 400
    assert sleeps == []
