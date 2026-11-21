"""Parser behavior tests for Phase 1 event coverage."""

from __future__ import annotations

from valheim_log_webhook.config import RuntimeConfig
from valheim_log_webhook.events import EventType, NormalizedEvent, ParseMiss
from valheim_log_webhook.parser import parse_line


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


def test_parse_online_event() -> None:
    result = parse_line("Game server connected to playfab", _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.SERVER_ONLINE


def test_parse_offline_event() -> None:
    result = parse_line("Valheim server Shutting down now", _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.SERVER_OFFLINE


def test_parse_join_event_extracts_name_and_steam_id() -> None:
    line = "Got character ZDOID from Astrid : 12345 owner 76561198000000001"
    result = parse_line(line, _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.PLAYER_JOIN
    assert result.player_name == "Astrid"
    assert result.steam_id == "76561198000000001"


def test_parse_leave_requires_steam_id() -> None:
    result = parse_line("Closing socket for unknown peer", _config())

    assert isinstance(result, ParseMiss)
    assert result.reason == "leave_missing_steam_id"


def test_parse_raid_event_extracts_name() -> None:
    result = parse_line("Random event set: wolves", _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.RAID_START
    assert result.raid_name == "wolves"


def test_parse_death_event_extracts_name() -> None:
    line = "Got character ZDOID from Bjorn : owner 76561198000000001 got status effect Dead"
    result = parse_line(line, _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.PLAYER_DEATH
    assert result.player_name == "Bjorn"


def test_parse_death_event_with_only_steam_id_still_emits_event() -> None:
    line = "76561198000000001 got status effect Dead"
    result = parse_line(line, _config())

    assert isinstance(result, NormalizedEvent)
    assert result.event_type == EventType.PLAYER_DEATH
    assert result.player_name is None
    assert result.steam_id == "76561198000000001"


def test_parse_non_matching_line_emits_parse_miss() -> None:
    result = parse_line("Unrelated world tick log line", _config())

    assert isinstance(result, ParseMiss)
    assert result.reason == "no_pattern_match"
