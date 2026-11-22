"""Integration tests for event-to-webhook processing flow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from valheim_log_webhook import app
from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.events import ParseMiss
from valheim_log_webhook.maintenance import BackupCoordinator
from valheim_log_webhook.routing import OutboundWebhook
from valheim_log_webhook.webhook import SendResult


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        container_name="valheim-server",
        reconnect_delay_seconds=0.01,
        filter_online="Game server connected",
        filter_offline="Shutting down",
        filter_join="Got character ZDOID from",
        filter_leave="Closing socket",
        filter_raid="Random event set:",
        filter_death="got status effect Dead",
        discord_webhook_debug="https://discord.com/api/webhooks/1/debug",
        discord_webhook_log="https://discord.com/api/webhooks/1/log",
        discord_webhook_players="https://discord.com/api/webhooks/1/players",
        webhook_timeout_seconds=5,
        webhook_retry_delay_seconds=1,
    )


def test_process_lines_sends_webhooks_for_matching_events(monkeypatch: object) -> None:
    sent: list[OutboundWebhook] = []
    misses: list[ParseMiss] = []

    def fake_send(outbound: OutboundWebhook, **_kwargs: object) -> SendResult:
        sent.append(outbound)
        return SendResult(success=True, attempts=1, status_code=204)

    monkeypatch.setattr(app, "send_with_retry", fake_send)

    lines = [
        "not a match",
        "Game server connected",
        "Got character ZDOID from Astrid : owner 76561198000000001",
    ]

    app.process_lines(lines, _config(), on_parse_miss=misses.append)

    assert len(sent) == 2
    assert sent[0].payload["content"].startswith("[ONLINE]")
    assert sent[1].payload["content"].startswith("[JOIN]")
    assert [miss.reason for miss in misses] == ["no_pattern_match"]


def test_process_lines_suppresses_offline_during_backup_window(
    monkeypatch: object,
) -> None:
    sent: list[OutboundWebhook] = []

    def fake_send(outbound: OutboundWebhook, **_kwargs: object) -> SendResult:
        sent.append(outbound)
        return SendResult(success=True, attempts=1, status_code=204)

    monkeypatch.setattr(app, "send_with_retry", fake_send)

    config = RuntimeConfig(
        **{
            **_config().__dict__,
            "backups_enabled": True,
            "backups_cron": "5 4 * * *",
            "backup_grace_minutes": 25,
            "backup_suppress_before_minutes": 5,
            "backup_suppress_after_minutes": 25,
            "timezone_name": "Europe/Oslo",
        }
    )
    coordinator = BackupCoordinator(
        config,
        now_fn=lambda: datetime(2026, 1, 1, 3, 10, tzinfo=UTC),
    )

    lines = ["Shutting down"]
    app.process_lines(
        lines,
        config,
        on_parse_miss=lambda _miss: None,
        backup_coordinator=coordinator,
    )

    assert sent == []


def test_process_lines_suppresses_duplicate_join_and_sends_death_event(
    monkeypatch: object,
) -> None:
    sent: list[OutboundWebhook] = []

    def fake_send(outbound: OutboundWebhook, **_kwargs: object) -> SendResult:
        sent.append(outbound)
        return SendResult(success=True, attempts=1, status_code=204)

    monkeypatch.setattr(app, "send_with_retry", fake_send)

    lines = [
        "Got character ZDOID from Astrid : owner 76561198000000001",
        "Got character ZDOID from Astrid : owner 76561198000000001",
        "76561198000000001 got status effect Dead",
    ]

    app.process_lines(lines, _config(), on_parse_miss=lambda _miss: None)

    assert [outbound.payload["content"] for outbound in sent] == [
        "[JOIN] Astrid joined the realm.",
        "[DEATH] Astrid has died.",
    ]


def test_process_lines_resolves_leave_player_name_from_prior_join(
    monkeypatch: object,
) -> None:
    sent: list[OutboundWebhook] = []

    def fake_send(outbound: OutboundWebhook, **_kwargs: object) -> SendResult:
        sent.append(outbound)
        return SendResult(success=True, attempts=1, status_code=204)

    monkeypatch.setattr(app, "send_with_retry", fake_send)

    lines = [
        "Got character ZDOID from Leif : owner 76561198000000002",
        "Closing socket 76561198000000002",
    ]

    app.process_lines(lines, _config(), on_parse_miss=lambda _miss: None)

    assert [outbound.payload["content"] for outbound in sent] == [
        "[JOIN] Leif joined the realm.",
        "[LEAVE] Leif left the realm.",
    ]


def test_process_lines_resolves_leave_name_from_persisted_player_map(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    sent: list[OutboundWebhook] = []

    def fake_send(outbound: OutboundWebhook, **_kwargs: object) -> SendResult:
        sent.append(outbound)
        return SendResult(success=True, attempts=1, status_code=204)

    monkeypatch.setattr(app, "send_with_retry", fake_send)

    map_path = tmp_path / "player-map.json"
    config = RuntimeConfig(
        **{
            **_config().__dict__,
            "player_map_file_path": str(map_path),
        }
    )

    app.process_lines(
        ["Got character ZDOID from Leif : owner 76561198000000002"],
        config,
        on_parse_miss=lambda _miss: None,
    )
    sent.clear()

    app.process_lines(
        ["Closing socket 76561198000000002"],
        config,
        on_parse_miss=lambda _miss: None,
    )

    assert [outbound.payload["content"] for outbound in sent] == [
        "[LEAVE] Leif left the realm.",
    ]
