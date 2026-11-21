"""Routing and payload formatting tests for Discord delivery."""

from __future__ import annotations

from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.events import EventType, NormalizedEvent
from valheim_log_webhook.routing import DiscordChannel, route_event_to_webhook


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


def test_route_server_online_to_log_channel() -> None:
    outbound = route_event_to_webhook(
        NormalizedEvent(event_type=EventType.SERVER_ONLINE, raw_line="x"),
        _config(),
    )

    assert outbound is not None
    assert outbound.channel == DiscordChannel.LOG
    assert outbound.url.endswith("/log")
    assert outbound.payload["content"].startswith("[ONLINE]")


def test_route_player_join_to_players_channel() -> None:
    outbound = route_event_to_webhook(
        NormalizedEvent(
            event_type=EventType.PLAYER_JOIN,
            raw_line="x",
            player_name="Astrid",
            steam_id="76561198000000001",
        ),
        _config(),
    )

    assert outbound is not None
    assert outbound.channel == DiscordChannel.PLAYERS
    assert outbound.url.endswith("/players")
    assert "Astrid" in outbound.payload["content"]


def test_route_skips_unset_webhook_url() -> None:
    config = _config()
    config = RuntimeConfig(
        **{**config.__dict__, "discord_webhook_players": None},
    )

    outbound = route_event_to_webhook(
        NormalizedEvent(
            event_type=EventType.PLAYER_DEATH, raw_line="x", player_name="Leif"
        ),
        config,
    )

    assert outbound is None


def test_route_skips_invalid_webhook_url() -> None:
    config = _config()
    config = RuntimeConfig(
        **{**config.__dict__, "discord_webhook_log": "http://example.com/not-discord"},
    )

    outbound = route_event_to_webhook(
        NormalizedEvent(event_type=EventType.SERVER_OFFLINE, raw_line="x"),
        config,
    )

    assert outbound is None
