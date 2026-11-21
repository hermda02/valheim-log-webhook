"""Pipeline parsing tests."""

from __future__ import annotations

from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.events import EventType, ParseMiss
from valheim_log_webhook.pipeline import parse_stream


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
    )


def test_parse_stream_emits_events_and_reports_parse_misses() -> None:
    lines = [
        "noise line",
        "Game server connected",
        "Got character ZDOID from Leif : owner 76561198000000001",
    ]
    misses: list[ParseMiss] = []

    events = list(parse_stream(lines, _config(), on_parse_miss=misses.append))

    assert [event.event_type for event in events] == [
        EventType.SERVER_ONLINE,
        EventType.PLAYER_JOIN,
    ]
    assert [miss.reason for miss in misses] == ["no_pattern_match"]
