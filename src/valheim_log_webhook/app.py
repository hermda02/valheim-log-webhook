"""Application-level event processing loop."""

from __future__ import annotations

import logging
from dataclasses import replace
from collections.abc import Callable, Iterable

from .config import RuntimeConfig
from .events import EventType, NormalizedEvent, ParseMiss
from .maintenance import BackupCoordinator
from .pipeline import parse_stream
from .routing import route_event_to_webhook
from .webhook import send_with_retry

LOGGER = logging.getLogger(__name__)

type ParseMissFn = Callable[[ParseMiss], None]


def process_lines(
    lines: Iterable[str],
    config: RuntimeConfig,
    on_parse_miss: ParseMissFn,
    *,
    backup_coordinator: BackupCoordinator | None = None,
) -> None:
    """Process raw log lines into routed webhook deliveries.

    Parameters
    ----------
    lines : Iterable[str]
        Raw incoming log stream.
    config : RuntimeConfig
        Runtime configuration.
    on_parse_miss : ParseMissFn
        Callback invoked for non-emitting parse outcomes.
    """
    known_player_names: dict[str, str] = {}
    connected_players: set[str] = set()

    for event in parse_stream(lines, config, on_parse_miss=on_parse_miss):
        event = _enrich_player_name(event, known_player_names)

        if _is_duplicate_join(event, connected_players):
            LOGGER.debug(
                "suppressed_join_event reason=already_connected steam_id=%s player_name=%s",
                event.steam_id,
                event.player_name,
            )
            continue

        _track_player_presence(event, known_player_names, connected_players)

        if _should_suppress_offline(event, backup_coordinator):
            LOGGER.info("suppressed_offline_event reason=backup_window")
            continue

        _deliver_event(event, config)


def send_scheduled_offline_alert(config: RuntimeConfig) -> None:
    """Emit an offline alert from post-backup health-check failure.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime configuration.
    """
    _deliver_event(
        NormalizedEvent(
            event_type=EventType.SERVER_OFFLINE,
            raw_line="post_backup_healthcheck_failure",
        ),
        config,
    )


def _should_suppress_offline(
    event: NormalizedEvent,
    backup_coordinator: BackupCoordinator | None,
) -> bool:
    """Return whether an offline event should be suppressed."""
    if backup_coordinator is None:
        return False
    if event.event_type != EventType.SERVER_OFFLINE:
        return False
    return backup_coordinator.suppression_active()


def _deliver_event(event: NormalizedEvent, config: RuntimeConfig) -> None:
    """Route and deliver one normalized event."""
    outbound = route_event_to_webhook(event, config)
    if outbound is None:
        return

    result = send_with_retry(
        outbound,
        timeout_seconds=config.webhook_timeout_seconds,
        retry_delay_seconds=config.webhook_retry_delay_seconds,
    )
    if result.success:
        LOGGER.info(
            "webhook_sent event_type=%s channel=%s status=%s attempts=%s",
            outbound.event_type,
            outbound.channel,
            result.status_code,
            result.attempts,
        )


def _enrich_player_name(
    event: NormalizedEvent,
    known_player_names: dict[str, str],
) -> NormalizedEvent:
    """Backfill player names from known Steam ID mappings."""
    if event.player_name is not None:
        return event
    if event.steam_id is None:
        return event

    known_name = known_player_names.get(event.steam_id)
    if known_name is None:
        return event

    return replace(event, player_name=known_name)


def _is_duplicate_join(event: NormalizedEvent, connected_players: set[str]) -> bool:
    """Return whether a player-join event is a duplicate for a connected player."""
    if event.event_type != EventType.PLAYER_JOIN:
        return False

    player_key = _player_key(event)
    if player_key is None:
        return False

    return player_key in connected_players


def _track_player_presence(
    event: NormalizedEvent,
    known_player_names: dict[str, str],
    connected_players: set[str],
) -> None:
    """Track connected players and Steam ID to player-name mappings."""
    if event.steam_id is not None and event.player_name is not None:
        known_player_names[event.steam_id] = event.player_name

    player_key = _player_key(event)
    if player_key is None:
        return

    if event.event_type == EventType.PLAYER_JOIN:
        connected_players.add(player_key)
        return
    if event.event_type == EventType.PLAYER_LEAVE:
        connected_players.discard(player_key)


def _player_key(event: NormalizedEvent) -> str | None:
    """Build a stable player identity key for presence tracking."""
    if event.steam_id is not None:
        return f"steam:{event.steam_id}"
    if event.player_name is not None:
        return f"name:{event.player_name}"
    return None
